import streamlit as st
import pandas as pd
import re, unicodedata, io, subprocess, tempfile, os, shutil

st.set_page_config(page_title='لوحة متابعة المبيعات', page_icon='📊', layout='wide')
st.title('لوحة متابعة المبيعات والعملاء')
st.caption('تحليل الفواتير، ترتيب العملاء، ومراجعة الخصومات — مع فصل العملات وعدم اعتبار الآجل تحصيلًا نقديًا.')
TRANS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
def norm_text(x):
    x = unicodedata.normalize('NFKC', str(x)).translate(TRANS)
    return re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069]', '', x)
def clean_name(x):
    x = re.sub(r'\(?\s*\d{7,}\s*\)?', ' ', str(x))
    x = re.sub(r'\(?\s*ح\s*/\s*ع\s*\)?', ' ', x)
    x = re.sub(r'[()（）]', ' ', x)
    return re.sub(r'\s+', ' ', x).strip(' :-/') or 'غير محدد'
def parse_text(text):
    pages = text.split('\f')
    rows=[]
    for i, page in enumerate(pages):
        p=norm_text(page)
        if 'رقم الفاتورة' not in p and 'ةروتافلا مقر' not in p: continue
        # This pattern is for text extracted by pdftotext, preserving the PDF's Arabic reading order.
        inv=re.search(r'رقم الفاتورة\s*(\d+)',p)
        cur=re.search(r'العملة\s*(YR|SR)',p)
        typ=re.search(r'نوع الفاتورة\s*:\s*(\S+)',p)
        cust=re.search(r'يقيد على\s*:\s*(.+)',p)
        total=re.search(r'([\d,]+\.\d{2})\s+الإجمالي\s*:',p)
        disc=re.search(r'([\d,]+\.\d{2})\s+الخصم\s*:',p)
        if not (inv and cur and total and disc): continue
        gross=float(total.group(1).replace(',','')); discount=float(disc.group(1).replace(',',''))
        raw=cust.group(1).strip() if cust else 'غير محدد'
        rows.append({'صفحة التقرير':i+1,'رقم الفاتورة':inv.group(1),'العملة':'ريال يمني' if cur.group(1)=='YR' else 'ريال سعودي','رمز العملة':cur.group(1),'نوع الفاتورة':typ.group(1) if typ else 'غير واضح','العميل كما في التقرير':raw,'اسم العميل':clean_name(raw),'الإجمالي قبل الخصم':gross,'الخصم':discount,'الصافي بعد الخصم':gross-discount})
    if not rows: raise ValueError('تعذر استخراج الحقول من PDF مباشرة. ارفع ملف CSV أو Excel المستخرج من التقرير، أو ثبّت pdftotext (Poppler) ليعمل استخراج PDF.')
    return pd.DataFrame(rows)
def load_upload(upload):
    name=upload.name.lower()
    if name.endswith('.csv'):
        df=pd.read_csv(upload)
    elif name.endswith('.xlsx') or name.endswith('.xls'):
        df=pd.read_excel(upload)
    elif name.endswith('.pdf'):
        if not shutil.which('pdftotext'):
            raise ValueError('استخراج PDF المباشر يحتاج pdftotext/Poppler. استخدم ملف CSV المرفق مع التحليل أو صدّر تقرير أونيكس إلى Excel/CSV.')
        with tempfile.NamedTemporaryFile(suffix='.pdf',delete=False) as tmp:
            tmp.write(upload.getvalue()); path=tmp.name
        try:
            text=subprocess.run(['pdftotext','-layout','-enc','UTF-8',path,'-'],capture_output=True,text=True,check=True).stdout
        finally: os.unlink(path)
        return parse_text(text)
    else:
        raise ValueError('نوع الملف غير مدعوم. ارفع PDF أو CSV أو Excel.')
    # Map the provided analysis CSV/Excel or similar export to the expected columns.
    aliases={
        'رقم الفاتورة':['رقم الفاتورة','invoice','invoice_number'],
        'العملة':['العملة','currency'],
        'نوع الفاتورة':['نوع الفاتورة','type'],
        'اسم العميل':['اسم العميل (بعد تنظيف أولي)','اسم العميل','customer','customer_name'],
        'الإجمالي قبل الخصم':['الإجمالي قبل الخصم','total','gross'],
        'الخصم':['الخصم','discount'],
        'الصافي بعد الخصم':['الصافي بعد الخصم','net'],
        'صفحة التقرير':['صفحة التقرير','page']}
    rename={}
    for target, options in aliases.items():
        for col in df.columns:
            if str(col).strip() in options:
                rename[col]=target; break
    df=df.rename(columns=rename)
    required=['رقم الفاتورة','العملة','اسم العميل','الإجمالي قبل الخصم','الخصم']
    missing=[x for x in required if x not in df.columns]
    if missing: raise ValueError('الأعمدة التالية غير موجودة في الملف: '+', '.join(missing))
    df['الصافي بعد الخصم']=pd.to_numeric(df['الصافي بعد الخصم'],errors='coerce') if 'الصافي بعد الخصم' in df else pd.to_numeric(df['الإجمالي قبل الخصم'],errors='coerce')-pd.to_numeric(df['الخصم'],errors='coerce')
    for col in ['الإجمالي قبل الخصم','الخصم','الصافي بعد الخصم']:
        df[col]=pd.to_numeric(df[col],errors='coerce').fillna(0)
    df['رقم الفاتورة']=df['رقم الفاتورة'].astype(str)
    df['اسم العميل']=df['اسم العميل'].map(clean_name)
    if 'رمز العملة' not in df:
        df['رمز العملة']=df['العملة'].map({'ريال يمني':'YR','ريال سعودي':'SR'}).fillna(df['العملة'].astype(str))
    if 'نوع الفاتورة' not in df: df['نوع الفاتورة']='غير محدد'
    if 'صفحة التقرير' not in df: df['صفحة التقرير']=''
    return df

upload=st.file_uploader('ارفع تقرير PDF أو ملف CSV/Excel', type=['pdf','csv','xlsx','xls'])
if upload:
    try: df=load_upload(upload)
    except Exception as e: st.error(str(e)); st.stop()
    st.success(f'تم تحميل {len(df):,} فاتورة/سجل')
    currencies=['الكل']+sorted(df['العملة'].dropna().astype(str).unique().tolist())
    selected=st.selectbox('العملة',currencies)
    view=df if selected=='الكل' else df[df['العملة']==selected]
    a,b,c,d=st.columns(4)
    a.metric('عدد الفواتير',f'{len(view):,}')
    b.metric('إجمالي قبل الخصم',f"{view['الإجمالي قبل الخصم'].sum():,.2f}")
    c.metric('إجمالي الخصومات',f"{view['الخصم'].sum():,.2f}")
    d.metric('الصافي بعد الخصم',f"{view['الصافي بعد الخصم'].sum():,.2f}")
    st.subheader('1) ترتيب العملاء حسب صافي المبيعات')
    customers=view.groupby('اسم العميل',as_index=False).agg(**{'عدد الفواتير':('رقم الفاتورة','count'),'إجمالي الخصومات':('الخصم','sum'),'صافي المبيعات':('الصافي بعد الخصم','sum')}).sort_values('صافي المبيعات',ascending=False)
    st.dataframe(customers,use_container_width=True,hide_index=True)
    st.subheader('2) مراجعة الخصومات والفواتير ذات الصافي الصفري')
    audit=view[(view['الخصم']>0) | (view['الصافي بعد الخصم']==0)].copy()
    audit['ملاحظة مراجعة']=audit.apply(lambda r:'صافي صفر — راجع سبب الخصم بالكامل' if abs(r['الصافي بعد الخصم'])<0.0001 else 'تحقق من مستند الخصم والموافقة',axis=1)
    st.dataframe(audit,use_container_width=True,hide_index=True)
    dups=view[view['رقم الفاتورة'].duplicated(keep=False)]
    st.caption(f'عدد سجلات أرقام الفواتير المكررة داخل النتائج: {len(dups)}. التكرار يحتاج مراجعة ولا يعني وحده وجود خطأ.')
    st.subheader('3) كل الفواتير')
    st.dataframe(view,use_container_width=True,hide_index=True)
    st.download_button('تنزيل النتائج CSV',view.to_csv(index=False).encode('utf-8-sig'),'الفواتير_المحللة.csv','text/csv')
    st.download_button('تنزيل تحليل العملاء CSV',customers.to_csv(index=False).encode('utf-8-sig'),'تحليل_العملاء.csv','text/csv')
    st.info('المبيعات الآجلة لا تثبت التحصيل. لتحليل المتبقي على العملاء، أضف كشف حساب العملاء وسندات القبض.')
else:
    st.write('ابدأ برفع ملف الفواتير. يمكنك تجربة الملف CSV المرفق مع التحليل لعرض بيانات التقرير الحالي مباشرة.')

# ---- Persistent collection-identifier registry (SQLite) ----
import sqlite3
from datetime import datetime
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'collection_registry.sqlite3')

def db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS identifiers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT NOT NULL,
        identifier TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        customer_phone TEXT DEFAULT '',
        note TEXT DEFAULT '',
        verified INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(channel, identifier)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT NOT NULL,
        transaction_ref TEXT NOT NULL,
        sender_identifier TEXT DEFAULT '',
        sender_text TEXT DEFAULT '',
        amount REAL NOT NULL,
        currency TEXT NOT NULL,
        message_text TEXT NOT NULL,
        customer_name TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'مجهول',
        created_at TEXT NOT NULL,
        UNIQUE(channel, transaction_ref)
    )''')
    conn.commit()
    return conn

def parse_payment_message(message, channel):
    msg = norm_text(message).strip()
    # Amount pattern used by local SMS formats, e.g. 90000ر.ي, 1800ر س, 27,700 ر.ي
    amount_match = re.search(r'(?<!\d)([\d,]+(?:\.\d+)?)\s*ر\s*\.?\s*(ي|س|يمني|سعودي)', msg, re.I)
    if not amount_match:
        amount_match = re.search(r'(?:إيداع|ايداع|اضيف|أضيف|تم إيداع)\s*([\d,]+(?:\.\d+)?)', msg)
    amount = float(amount_match.group(1).replace(',', '')) if amount_match else None
    currency = 'ريال يمني' if re.search(r'ر\s*\.?\s*ي|يمني', msg, re.I) else ('ريال سعودي' if re.search(r'ر\s*\.?\s*س|سعودي', msg, re.I) else '')
    ref = ''
    ref_match = re.search(r'\bم\s*:\s*([\d]{6,})', msg)
    if ref_match:
        ref = ref_match.group(1)
    elif channel == 'الإكسبرس':
        refs = re.findall(r'(?<!\d)(\d{10,})(?!\d)', msg)
        if refs: ref = refs[-1]
    sender = ''
    if channel == 'جيب':
        sender_match = re.search(r'\bمن\s+([\d]{4,})', msg)
        if sender_match: sender = sender_match.group(1)
    elif channel == 'الإكسبرس':
        sender_match = re.search(r'حوالة\s+من\s*:?\s*(.*?)(?:\s*//|\s+\d{10,}|$)', msg)
        if sender_match: sender = sender_match.group(1).strip()
    else:
        sender_match = re.search(r'\bمن\s*:?\s*(.*?)(?:\s+م\s*:|$)', msg)
        if sender_match: sender = sender_match.group(1).strip()
    return {'amount': amount, 'currency': currency, 'ref': ref, 'sender': sender, 'message': msg}

def export_vcard(rows):
    cards=[]
    for r in rows:
        # VCF entries are optional exports; importing them into Android Contacts is a user action.
        display = f"{r['channel']} رقم {r['identifier']} - {r['customer_name']}"
        phone = re.sub(r'[^+0-9]', '', r['customer_phone'] or '')
        cards += ['BEGIN:VCARD', 'VERSION:3.0', f'FN:{display}', f'ORG:{r["channel"]}', f'NOTE:معرّف التحصيل: {r["identifier"]}; تم التأكد: {"نعم" if r["verified"] else "لا"}']
        if phone: cards.append(f'TEL;TYPE=CELL:{phone}')
        cards.append('END:VCARD')
    return '\r\n'.join(cards) + ('\r\n' if cards else '')

st.divider()
st.header('سجل معرفات التحصيل')
st.caption('قاعدة بيانات محلية محفوظة في collection_registry.sqlite3 بجانب التطبيق. لا تُسند عملية لعميل إلا بعد التحقق؛ وتصدير جهات الاتصال اختياري.')
tab_import, tab_registry, tab_history = st.tabs(['استيراد إشعار', 'قاعدة المعرفات', 'سجل العمليات'])
with tab_import:
    channel = st.selectbox('مصدر الإشعار', ['جيب', 'جوالي', 'الإكسبرس', 'شركة حوالات أخرى', 'إيداع إلكتروني آخر'], key='pay_channel')
    sms_text = st.text_area('الصق نص رسالة SMS هنا', height=110, placeholder='الصق الرسالة كاملة كما وصلت إلى الهاتف')
    if st.button('تحليل الإشعار', key='parse_sms'):
        parsed = parse_payment_message(sms_text, channel)
        st.session_state['parsed_payment'] = parsed
    parsed = st.session_state.get('parsed_payment')
    if parsed and sms_text.strip():
        st.write('**البيانات المستخرجة — راجعها قبل الحفظ**')
        c1, c2, c3 = st.columns(3)
        c1.metric('المبلغ', f"{parsed['amount']:,.2f}" if parsed['amount'] is not None else 'لم يُقرأ')
        c2.metric('العملة', parsed['currency'] or 'حددها يدويًا')
        c3.metric('مرجع العملية', parsed['ref'] or 'غير موجود')
        with st.form('save_payment_form'):
            amount_value = st.number_input('المبلغ الصحيح', min_value=0.0, value=float(parsed['amount'] or 0), step=100.0)
            currency_value = st.selectbox('العملة', ['ريال يمني', 'ريال سعودي'], index=0 if parsed['currency'] != 'ريال سعودي' else 1)
            ref_value = st.text_input('رقم العملية / المرجع (مهم لمنع التكرار)', value=parsed['ref'])
            sender_value = st.text_input('معرّف المرسل أو الاسم الظاهر', value=parsed['sender'])
            customer_value = st.text_input('اسم العميل (اتركه فارغًا إن لم يُعرف)')
            verified_value = st.checkbox('تم التأكد من هوية العميل')
            submitted = st.form_submit_button('حفظ الإشعار في قاعدة البيانات')
            if submitted:
                if amount_value <= 0:
                    st.error('أدخل مبلغًا صحيحًا أكبر من صفر.')
                elif not ref_value.strip():
                    st.error('أدخل مرجع العملية إن وجد. إذا لم توفر الخدمة مرجعًا ثابتًا، لا يمكن ضمان كشف التكرار بصورة كاملة.')
                elif verified_value and not customer_value.strip():
                    st.error('لا يمكن تأكيد الهوية دون إدخال اسم العميل.')
                else:
                    now = datetime.now().isoformat(timespec='seconds')
                    conn = db_conn()
                    try:
                        conn.execute('INSERT INTO transactions(channel,transaction_ref,sender_identifier,sender_text,amount,currency,message_text,customer_name,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (channel, ref_value.strip(), sender_value.strip() if channel != 'الإكسبرس' else '', sender_value.strip() if channel == 'الإكسبرس' else '', amount_value, currency_value, sms_text.strip(), customer_value.strip(), 'مؤكد' if verified_value else 'مجهول', now))
                        if verified_value and sender_value.strip():
                            conn.execute('''INSERT INTO identifiers(channel,identifier,customer_name,customer_phone,note,verified,created_at,updated_at)
                                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(channel,identifier) DO UPDATE SET customer_name=excluded.customer_name, verified=1, updated_at=excluded.updated_at''',
                                (channel, sender_value.strip(), customer_value.strip(), '', 'تم التعريف من خلال إشعار تحصيل', 1, now, now))
                        conn.commit()
                        st.success('تم حفظ العملية. إذا تم تأكيد العميل، حُفظ الربط أيضًا في سجل المعرفات.')
                    except sqlite3.IntegrityError:
                        st.error('هذا المرجع مسجل مسبقًا لهذا المصدر؛ لم نكرر العملية.')
                    finally:
                        conn.close()
with tab_registry:
    st.subheader('إضافة أو تحديث معرف عميل')
    with st.form('identifier_form'):
        reg_channel = st.selectbox('مصدر المعرف', ['جيب', 'جوالي', 'الإكسبرس', 'شركة حوالات أخرى', 'إيداع إلكتروني آخر'], key='reg_channel')
        reg_id = st.text_input('معرف المرسل كما يظهر في الرسالة', placeholder='مثال: 6679435')
        reg_name = st.text_input('اسم العميل الكامل', placeholder='مثال: محمد أحمد علي')
        reg_phone = st.text_input('رقم هاتف العميل (اختياري)')
        reg_verified = st.checkbox('تحققت من هوية العميل خارج نص الرسالة')
        reg_note = st.text_input('ملاحظة (اختياري)')
        reg_submit = st.form_submit_button('حفظ المعرف')
        if reg_submit:
            if not reg_id.strip() or not reg_name.strip():
                st.error('أدخل المعرف واسم العميل.')
            elif not reg_verified:
                st.warning('لمنع ربط الأموال بالشخص الخطأ، أكد التحقق من هوية العميل قبل حفظ الربط الموثوق.')
            else:
                now = datetime.now().isoformat(timespec='seconds')
                conn = db_conn()
                conn.execute('''INSERT INTO identifiers(channel,identifier,customer_name,customer_phone,note,verified,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(channel,identifier) DO UPDATE SET customer_name=excluded.customer_name,customer_phone=excluded.customer_phone,note=excluded.note,verified=excluded.verified,updated_at=excluded.updated_at''',
                    (reg_channel, reg_id.strip(), reg_name.strip(), reg_phone.strip(), reg_note.strip(), 1, now, now))
                conn.commit(); conn.close()
                st.success('تم حفظ المعرف. ستظهر المطابقة مستقبلًا عند ورود معرف مطابق من المصدر نفسه.')
    conn = db_conn()
    identifiers = conn.execute('SELECT * FROM identifiers ORDER BY updated_at DESC').fetchall()
    conn.close()
    if identifiers:
        id_df = pd.DataFrame([dict(r) for r in identifiers])
        st.dataframe(id_df[['channel','identifier','customer_name','customer_phone','verified','note','updated_at']], use_container_width=True, hide_index=True)
        st.download_button('تصدير جهات الاتصال بصيغة VCF لهاتف أندرويد', export_vcard(identifiers).encode('utf-8'), 'جهات_اتصال_معرفات_التحصيل.vcf', 'text/vcard')
        st.caption('التصدير ينشئ ملفًا يمكنك فتحه على أندرويد واستيراده يدويًا إلى جهات الاتصال. لا يكتب التطبيق مباشرة إلى دفتر الهاتف.')
        st.download_button('تنزيل نسخة CSV من سجل المعرفات', id_df.to_csv(index=False).encode('utf-8-sig'), 'سجل_معرفات_التحصيل.csv', 'text/csv')
    else:
        st.info('لا توجد معرفات محفوظة بعد. أضف أول معرف بعد التحقق من هوية صاحبه.')
with tab_history:
    conn = db_conn()
    tx_rows = conn.execute('SELECT * FROM transactions ORDER BY id DESC').fetchall()
    conn.close()
    if tx_rows:
        tx_df = pd.DataFrame([dict(r) for r in tx_rows])
        st.dataframe(tx_df[['created_at','channel','amount','currency','sender_identifier','sender_text','transaction_ref','customer_name','status','message_text']], use_container_width=True, hide_index=True)
        st.download_button('تنزيل سجل العمليات CSV', tx_df.to_csv(index=False).encode('utf-8-sig'), 'سجل_عمليات_التحصيل.csv', 'text/csv')
    else:
        st.info('لم تُسجل أي عمليات تحصيل حتى الآن.')
