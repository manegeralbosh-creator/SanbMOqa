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

# ---- Persistent collection registry and editable SMS formats ----
import sqlite3, hashlib
from datetime import datetime
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'collection_registry.sqlite3')

CHANNELS = ['جيب', 'جوالي', 'الكريمي', 'الإكسبرس', 'شركة حوالات أخرى', 'إيداع إلكتروني آخر']

def db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS identifiers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT NOT NULL, identifier TEXT NOT NULL,
        customer_name TEXT NOT NULL, customer_phone TEXT DEFAULT '', note TEXT DEFAULT '',
        verified INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(channel, identifier))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT NOT NULL, transaction_ref TEXT NOT NULL,
        sender_identifier TEXT DEFAULT '', sender_text TEXT DEFAULT '', amount REAL NOT NULL,
        currency TEXT NOT NULL, message_text TEXT NOT NULL, customer_name TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'مجهول', created_at TEXT NOT NULL,
        UNIQUE(channel, transaction_ref))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS payment_formats (
        id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT NOT NULL, label TEXT NOT NULL,
        contains_text TEXT DEFAULT '', amount_pattern TEXT NOT NULL, currency_pattern TEXT DEFAULT '',
        identifier_pattern TEXT DEFAULT '', name_pattern TEXT DEFAULT '', reference_pattern TEXT DEFAULT '',
        balance_pattern TEXT DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
        UNIQUE(channel, label))''')
    # Seed known formats only once; each regex extracts its value from capture group 1.
    seeds = [
      ('جيب','إضافة - مشتريات (معرف نقطة)','مشتريات',r'(?:اضيف|أضيف|إضافة)\s*([\d,]+(?:\.\d+)?)',r'(ر\.?\s*ي|YER|ر\.?\s*س|SAR)',r'\bمن\s+(\d{4,})',r'',r'\bم\s*:\s*(\d{6,})',r'رص\s*:\s*([\d,.]+)'),
      ('جيب','إضافة - تحويل مشترك','تحويل مشترك',r'(?:اضيف|أضيف|إضافة)\s*([\d,]+(?:\.\d+)?)',r'(ر\.?\s*ي|YER|ر\.?\s*س|SAR)',r'من\s+.+?\s+(\d{7,})',r'من\s+(.+?)\s+\d{7,}',r'\bم\s*:\s*(\d{6,})',r'رص\s*:\s*([\d,.]+)'),
      ('جوالي','استلمت مبلغ','استلمت مبلغ',r'استلمت\s+مبلغ\s+([\d,]+(?:\.\d+)?)',r'(YER|SAR|ر\.?\s*ي|ر\.?\s*س)',r'من\s+(\d{7,})',r'',r'رقم\s*(?:العملية|مرجع)\s*[:：]?\s*(\d+)',r'رصيدك\s+هو\s+([\d,.]+)'),
      ('الكريمي','إيداع باسم مودع','لحسابك',r'مبلغ\s+([\d,]+(?:\.\d+)?)',r'(YER|SAR|ر\.?\s*ي|ر\.?\s*س)',r'',r'(?:أودع|اودع|إيداع|ايداع)\s*/?\s*(.+?)\s+لحسابك',r'(?:رقم العملية|مرجع)\s*[:：]?\s*(\d+)',r'رصيد\s+([\d,.]+)'),
      ('الإكسبرس','حوالة من','حوالة من',r'([\d,]+(?:\.\d+)?)\s*ر\s*\.?\s*(?:ي|س)',r'(ر\s*\.?\s*ي|ر\s*\.?\s*س)',r'(\d{10,})',r'حوالة\s+من\s*:?\s*(.+?)(?:\s*//|\s+\d{10,}|$)',r'(\d{10,})',r'رصيد\s*[:：]?\s*([\d,.]+)')
    ]
    for row in seeds:
        conn.execute('''INSERT OR IGNORE INTO payment_formats(channel,label,contains_text,amount_pattern,currency_pattern,identifier_pattern,name_pattern,reference_pattern,balance_pattern,enabled,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,1,?)''', (*row, datetime.now().isoformat(timespec='seconds')))
    conn.commit()
    return conn

def _extract(pattern, text):
    if not pattern or not pattern.strip(): return ''
    try:
        m = re.search(pattern, text, flags=re.I)
        return m.group(1).strip() if m and m.lastindex else (m.group(0).strip() if m else '')
    except re.error:
        return ''

def parse_payment_message(message, channel, formats=None):
    msg = norm_text(message).strip()
    result = {'amount': None, 'currency': '', 'ref': '', 'sender_id': '', 'sender_name': '', 'balance': '', 'message': msg, 'format_label': ''}
    candidates = formats or []
    for f in candidates:
        if not f['enabled'] or (f['channel'] not in (channel, 'أي مصدر')): continue
        contains = (f['contains_text'] or '').strip()
        if contains and contains.casefold() not in msg.casefold(): continue
        amt = _extract(f['amount_pattern'], msg)
        if not amt: continue
        try: result['amount'] = float(amt.replace(',', ''))
        except ValueError: continue
        cur = _extract(f['currency_pattern'], msg).strip().upper().replace(' ', '').replace('.', '')
        if cur in ('ي','YR','YER','ر.ي','ري'): result['currency'] = 'ريال يمني'
        elif cur in ('س','SR','SAR','ر.س','رس'): result['currency'] = 'ريال سعودي'
        elif re.search(r'YER|ر\s*\.?\s*ي|يمني', msg, re.I): result['currency'] = 'ريال يمني'
        elif re.search(r'SAR|SR|ر\s*\.?\s*س|سعودي', msg, re.I): result['currency'] = 'ريال سعودي'
        result['sender_id'] = _extract(f['identifier_pattern'], msg)
        result['sender_name'] = _extract(f['name_pattern'], msg)
        result['ref'] = _extract(f['reference_pattern'], msg)
        result['balance'] = _extract(f['balance_pattern'], msg)
        result['format_label'] = f['label']
        break
    # General fallback for messages not yet covered by a saved template.
    if result['amount'] is None:
        m = re.search(r'(?<!\d)([\d,]+(?:\.\d+)?)\s*(?:ر\s*\.?\s*[يس]|YER|SAR|SR)', msg, re.I)
        if not m: m = re.search(r'(?:مبلغ|اضيف|أضيف|إيداع|ايداع|استلمت)\s*([\d,]+(?:\.\d+)?)', msg, re.I)
        if m:
            try: result['amount'] = float(m.group(1).replace(',', ''))
            except ValueError: pass
    if not result['currency']:
        if re.search(r'YER|\bYR\b|ر\s*\.?\s*ي|يمني', msg, re.I): result['currency'] = 'ريال يمني'
        elif re.search(r'\bSAR\b|\bSR\b|ر\s*\.?\s*س|سعودي', msg, re.I): result['currency'] = 'ريال سعودي'
    if not result['ref']:
        m = re.search(r'\bم\s*:\s*(\d{6,})', msg)
        if m: result['ref'] = m.group(1)
        elif channel == 'الإكسبرس':
            nums = re.findall(r'(?<!\d)(\d{10,})(?!\d)', msg)
            if nums: result['ref'] = nums[-1]
    if not result['sender_id']:
        m = re.search(r'\bمن\s+(\d{7,})', msg)
        if m: result['sender_id'] = m.group(1)
    if not result['sender_name']:
        m = re.search(r'(?:أودع|اودع|إيداع|ايداع)\s*/?\s*(.+?)\s+لحسابك', msg)
        if m: result['sender_name'] = m.group(1).strip()
    if not result['balance']:
        m = re.search(r'(?:رص\s*:\s*|رصيدك\s+هو\s+|رصيد\s*)([\d,.]+)', msg, re.I)
        if m: result['balance'] = m.group(1)
    if not result['sender_id'] and not result['sender_name'] and channel == 'الإكسبرس':
        m = re.search(r'حوالة\s+من\s*:?\s*(.*?)(?:\s*//|$)', msg)
        if m: result['sender_name'] = m.group(1).strip()
    return result

def export_vcard(rows):
    cards=[]
    for r in rows:
        display = f"{r['channel']} رقم {r['identifier']} - {r['customer_name']}"
        phone = re.sub(r'[^+0-9]', '', r['customer_phone'] or '')
        cards += ['BEGIN:VCARD', 'VERSION:3.0', f'FN:{display}', f'ORG:{r["channel"]}', f'NOTE:معرّف التحصيل: {r["identifier"]}; تم التأكد: {"نعم" if r["verified"] else "لا"}']
        if phone: cards.append(f'TEL;TYPE=CELL:{phone}')
        cards.append('END:VCARD')
    return '\r\n'.join(cards) + ('\r\n' if cards else '')

conn = db_conn()
all_formats = [dict(r) for r in conn.execute('SELECT * FROM payment_formats ORDER BY channel,label').fetchall()]
conn.close()

st.divider()
st.header('إدارة التحصيلات ورسائل SMS')
st.caption('يمكن حفظ صيغ متعددة لكل محفظة أو بنك. تتم قراءة كل صيغة عبر أنماط قابلة للتعديل، مع معاينة قبل حفظ أي عملية.')
tab_import, tab_registry, tab_history, tab_formats = st.tabs(['استيراد إشعار', 'قاعدة المعرفات', 'سجل العمليات', 'إدارة صيغ الرسائل'])
with tab_import:
    channel = st.selectbox('مصدر الإشعار', CHANNELS, key='pay_channel')
    sms_text = st.text_area('الصق نص رسالة SMS هنا', height=115, placeholder='الصق الرسالة كاملة كما وصلت إلى الهاتف')
    if st.button('تحليل الإشعار', key='parse_sms'):
        parsed = parse_payment_message(sms_text, channel, all_formats)
        st.session_state['parsed_payment'] = parsed
        st.session_state['parsed_payment_raw'] = sms_text
    parsed = st.session_state.get('parsed_payment')
    if parsed and st.session_state.get('parsed_payment_raw') == sms_text and sms_text.strip():
        st.caption('الصيغة المستخدمة: ' + (parsed['format_label'] or 'استخراج عام — يُفضّل إضافة صيغة إذا لم تُقرأ الحقول بدقة'))
        a,b,c = st.columns(3)
        a.metric('المبلغ', f"{parsed['amount']:,.2f}" if parsed['amount'] is not None else 'لم يُقرأ')
        b.metric('العملة', parsed['currency'] or 'غير محددة')
        c.metric('رقم العملية', parsed['ref'] or 'غير مستخرج')
        d,e,f = st.columns(3)
        d.metric('معرف المرسل/النقطة', parsed['sender_id'] or 'غير مستخرج')
        e.metric('اسم المرسل الظاهر', parsed['sender_name'] or 'غير موجود')
        f.metric('الرصيد بعد العملية', parsed['balance'] or 'غير موجود')
        # Suggest a customer from the verified registry.
        suggested = ''
        if parsed['sender_id']:
            conn = db_conn()
            hit = conn.execute('SELECT customer_name FROM identifiers WHERE channel=? AND identifier=? AND verified=1', (channel, parsed['sender_id'])).fetchone()
            conn.close()
            if hit: suggested = hit['customer_name']
        if suggested: st.success(f'معرف محفوظ سابقًا: {suggested} — راجع الهوية قبل اعتماد التحصيل.')
        with st.form('save_payment_form'):
            amount_value = st.number_input('المبلغ الصحيح', min_value=0.0, value=float(parsed['amount'] or 0), step=100.0)
            default_cur = 1 if parsed['currency'] == 'ريال سعودي' else 0
            currency_value = st.selectbox('العملة', ['ريال يمني', 'ريال سعودي'], index=default_cur)
            ref_value = st.text_input('رقم العملية / المرجع', value=parsed['ref'])
            sender_id_value = st.text_input('معرف المرسل أو النقطة', value=parsed['sender_id'])
            sender_name_value = st.text_input('اسم المرسل كما يظهر في الرسالة', value=parsed['sender_name'])
            customer_value = st.text_input('اسم العميل المعروف (اتركه فارغًا إن لم يُعرف)', value=suggested)
            verified_value = st.checkbox('تم التحقق من هوية العميل فعليًا')
            submitted = st.form_submit_button('حفظ الإشعار')
            if submitted:
                if amount_value <= 0: st.error('أدخل مبلغًا صحيحًا أكبر من صفر.')
                elif verified_value and not customer_value.strip(): st.error('لا يمكن تأكيد الهوية دون اسم العميل.')
                else:
                    # Some wallet SMS messages have no transaction reference. Create a deterministic fingerprint of the normalized message.
                    saved_ref = ref_value.strip() or ('AUTO-' + hashlib.sha256((channel + '|' + norm_text(sms_text).strip()).encode('utf-8')).hexdigest()[:24])
                    now = datetime.now().isoformat(timespec='seconds')
                    status = 'مؤكد' if verified_value else 'مجهول'
                    conn = db_conn()
                    try:
                        conn.execute('INSERT INTO transactions(channel,transaction_ref,sender_identifier,sender_text,amount,currency,message_text,customer_name,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (channel, saved_ref, sender_id_value.strip(), sender_name_value.strip(), amount_value, currency_value, sms_text.strip(), customer_value.strip() if verified_value else '', status, now))
                        if verified_value and sender_id_value.strip():
                            conn.execute('''INSERT INTO identifiers(channel,identifier,customer_name,customer_phone,note,verified,created_at,updated_at)
                                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(channel,identifier) DO UPDATE SET customer_name=excluded.customer_name,verified=1,updated_at=excluded.updated_at''',
                                (channel, sender_id_value.strip(), customer_value.strip(), '', 'تم التحقق أثناء تسجيل التحصيل', 1, now, now))
                        conn.commit(); st.success('تم حفظ الإشعار، وحُفظ المعرف إذا تم تأكيد العميل.' + (' استخدم التطبيق بصمة داخلية لأن الرسالة لا تحتوي على مرجع واضح.' if not ref_value.strip() else ''))
                    except sqlite3.IntegrityError: st.error('هذا المرجع مسجل مسبقًا لهذا المصدر؛ لم نكرر العملية.')
                    finally: conn.close()
with tab_registry:
    st.subheader('إضافة أو تحديث معرف عميل')
    with st.form('identifier_form'):
        reg_channel = st.selectbox('مصدر المعرف', CHANNELS, key='reg_channel')
        reg_id = st.text_input('المعرف كما يظهر في الرسالة (رقم نقطة أو رقم مرسل)', placeholder='مثال: 6679435')
        reg_name = st.text_input('اسم العميل الكامل', placeholder='مثال: محمد أحمد علي')
        reg_phone = st.text_input('رقم هاتف العميل (اختياري)')
        reg_verified = st.checkbox('تحققت من هوية العميل خارج نص الرسالة')
        reg_note = st.text_input('ملاحظة (اختياري)')
        reg_submit = st.form_submit_button('حفظ المعرف')
        if reg_submit:
            if not reg_id.strip() or not reg_name.strip(): st.error('أدخل المعرف واسم العميل.')
            elif not reg_verified: st.warning('أكد التحقق من الهوية قبل حفظ ربط موثوق.')
            else:
                now = datetime.now().isoformat(timespec='seconds'); conn = db_conn()
                conn.execute('''INSERT INTO identifiers(channel,identifier,customer_name,customer_phone,note,verified,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)
                    ON CONFLICT(channel,identifier) DO UPDATE SET customer_name=excluded.customer_name,customer_phone=excluded.customer_phone,note=excluded.note,verified=excluded.verified,updated_at=excluded.updated_at''',
                    (reg_channel,reg_id.strip(),reg_name.strip(),reg_phone.strip(),reg_note.strip(),1,now,now))
                conn.commit(); conn.close(); st.success('تم حفظ المعرف في قاعدة البيانات.')
    conn = db_conn(); identifiers = conn.execute('SELECT * FROM identifiers ORDER BY updated_at DESC').fetchall(); conn.close()
    if identifiers:
        id_df = pd.DataFrame([dict(r) for r in identifiers])
        st.dataframe(id_df[['channel','identifier','customer_name','customer_phone','verified','note','updated_at']], use_container_width=True, hide_index=True)
        st.download_button('تصدير جهات الاتصال VCF لأندرويد', export_vcard(identifiers).encode('utf-8'), 'جهات_اتصال_معرفات_التحصيل.vcf', 'text/vcard')
        st.download_button('تنزيل سجل المعرفات CSV', id_df.to_csv(index=False).encode('utf-8-sig'), 'سجل_معرفات_التحصيل.csv', 'text/csv')
    else: st.info('لا توجد معرفات محفوظة بعد.')
with tab_history:
    conn = db_conn(); tx_rows = conn.execute('SELECT * FROM transactions ORDER BY id DESC').fetchall(); conn.close()
    if tx_rows:
        tx_df = pd.DataFrame([dict(r) for r in tx_rows])
        st.dataframe(tx_df[['created_at','channel','amount','currency','sender_identifier','sender_text','transaction_ref','customer_name','status','message_text']], use_container_width=True, hide_index=True)
        st.download_button('تنزيل سجل العمليات CSV', tx_df.to_csv(index=False).encode('utf-8-sig'), 'سجل_عمليات_التحصيل.csv', 'text/csv')
    else: st.info('لم تسجل عمليات تحصيل حتى الآن.')
with tab_formats:
    st.subheader('الصيغ المحفوظة')
    st.write('كل تعبير منتظم يستخرج القيمة من المجموعة الأولى `( ... )`. اترك الحقل فارغًا إذا لم يظهر في هذه الصيغة. كلمة المطابقة تساعد على تمييز النمط عند وجود أكثر من نموذج للمصدر نفسه.')
    conn = db_conn(); fmt_rows = conn.execute('SELECT * FROM payment_formats ORDER BY channel,label').fetchall(); conn.close()
    if fmt_rows:
        fmt_df = pd.DataFrame([dict(r) for r in fmt_rows])
        st.dataframe(fmt_df[['id','channel','label','contains_text','enabled']], use_container_width=True, hide_index=True)
        chosen_id = st.selectbox('اختر صيغة لتعديلها أو تعطيلها', [r['id'] for r in fmt_rows], format_func=lambda x: next(f"{r['channel']} — {r['label']}" for r in fmt_rows if r['id']==x))
        chosen = next(dict(r) for r in fmt_rows if r['id']==chosen_id)
        with st.form('edit_format_form'):
            ed_channel = st.selectbox('المصدر', CHANNELS + ['أي مصدر'], index=(CHANNELS+['أي مصدر']).index(chosen['channel']) if chosen['channel'] in CHANNELS+['أي مصدر'] else 0)
            ed_label = st.text_input('اسم الصيغة', value=chosen['label'])
            ed_contains = st.text_input('نص يجب أن يظهر لتمييز الصيغة', value=chosen['contains_text'])
            ed_amount = st.text_input('Regex المبلغ — المجموعة 1', value=chosen['amount_pattern'])
            ed_currency = st.text_input('Regex العملة — المجموعة 1', value=chosen['currency_pattern'])
            ed_ident = st.text_input('Regex المعرف/رقم النقطة — المجموعة 1', value=chosen['identifier_pattern'])
            ed_name = st.text_input('Regex اسم المرسل — المجموعة 1', value=chosen['name_pattern'])
            ed_ref = st.text_input('Regex مرجع العملية — المجموعة 1', value=chosen['reference_pattern'])
            ed_balance = st.text_input('Regex الرصيد بعد العملية — المجموعة 1', value=chosen['balance_pattern'])
            ed_enabled = st.checkbox('الصيغة مفعلة', value=bool(chosen['enabled']))
            save_fmt = st.form_submit_button('حفظ تعديلات الصيغة')
            if save_fmt:
                try:
                    for pat in [ed_amount,ed_currency,ed_ident,ed_name,ed_ref,ed_balance]:
                        if pat.strip(): re.compile(pat, re.I)
                    if not ed_label.strip() or not ed_amount.strip(): raise ValueError('اسم الصيغة وRegex المبلغ مطلوبان.')
                    conn = db_conn()
                    conn.execute('''UPDATE payment_formats SET channel=?,label=?,contains_text=?,amount_pattern=?,currency_pattern=?,identifier_pattern=?,name_pattern=?,reference_pattern=?,balance_pattern=?,enabled=? WHERE id=?''',
                      (ed_channel,ed_label.strip(),ed_contains.strip(),ed_amount.strip(),ed_currency.strip(),ed_ident.strip(),ed_name.strip(),ed_ref.strip(),ed_balance.strip(),int(ed_enabled),chosen_id))
                    conn.commit(); conn.close(); st.success('تم تحديث الصيغة. أعد تحليل الرسالة لاختبارها.')
                except (re.error, ValueError) as ex: st.error(f'تعذر حفظ الصيغة: {ex}')
    st.subheader('إضافة صيغة جديدة')
    with st.form('add_format_form'):
        nf_channel = st.selectbox('مصدر الصيغة الجديدة', CHANNELS + ['أي مصدر'], key='new_fmt_channel')
        nf_label = st.text_input('اسم مميز للصيغة الجديدة', placeholder='مثال: جوالي - تحويل وارد')
        nf_contains = st.text_input('عبارة تميز هذه الرسالة', placeholder='مثال: استلمت مبلغ')
        nf_amount = st.text_input('Regex المبلغ — المجموعة 1', placeholder=r'استلمت مبلغ\s+([\d,]+(?:\.\d+)?)')
        nf_currency = st.text_input('Regex العملة — المجموعة 1', placeholder=r'(YER|SAR)')
        nf_ident = st.text_input('Regex المعرف — المجموعة 1', placeholder=r'من\s+(\d{7,})')
        nf_name = st.text_input('Regex اسم المرسل — المجموعة 1 (اختياري)')
        nf_ref = st.text_input('Regex مرجع العملية — المجموعة 1 (اختياري)')
        nf_balance = st.text_input('Regex الرصيد — المجموعة 1 (اختياري)')
        nf_submit = st.form_submit_button('إضافة الصيغة')
        if nf_submit:
            try:
                for pat in [nf_amount,nf_currency,nf_ident,nf_name,nf_ref,nf_balance]:
                    if pat.strip(): re.compile(pat, re.I)
                if not nf_label.strip() or not nf_amount.strip(): raise ValueError('اسم الصيغة وRegex المبلغ مطلوبان.')
                conn = db_conn()
                conn.execute('''INSERT INTO payment_formats(channel,label,contains_text,amount_pattern,currency_pattern,identifier_pattern,name_pattern,reference_pattern,balance_pattern,enabled,created_at) VALUES(?,?,?,?,?,?,?,?,?,1,?)''',
                    (nf_channel,nf_label.strip(),nf_contains.strip(),nf_amount.strip(),nf_currency.strip(),nf_ident.strip(),nf_name.strip(),nf_ref.strip(),nf_balance.strip(),datetime.now().isoformat(timespec='seconds')))
                conn.commit(); conn.close(); st.success('تمت إضافة الصيغة. ستظهر في القائمة بعد تحديث الصفحة.')
            except (re.error, ValueError, sqlite3.IntegrityError) as ex: st.error(f'تعذر إضافة الصيغة: {ex}')
    st.info('مهم: جرّب كل صيغة على رسالة حقيقية قبل اعتمادها. الأرقام في رسائل البنوك قد تكون رقم حساب أو مرجعًا وليست بالضرورة رقم هاتف العميل.')
