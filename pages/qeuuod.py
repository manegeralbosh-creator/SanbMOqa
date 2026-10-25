sqlite3
import re
import io
import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET

# --- إعدادات الصفحة ---
st.set_page_config(page_title="نظام قيود أونكس برو - SMS", layout="wide")

# --- 1. تهيئة وترقية قاعدة البيانات آمنة الاتصال ---
DB_NAME = "accounts_db.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS persons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_name TEXT UNIQUE,
                account_number TEXT,
                analytical_account TEXT
            )
        ''')
        try:
            c.execute("ALTER TABLE persons ADD COLUMN analytical_account TEXT")
        except sqlite3.OperationalError:
            pass
        conn.commit()

# دالة لتنظيف وتوحيد الهمزات للمقارنة الدقيقة
def normalize_arabic(text):
    if not text:
        return ""
    text = str(text).strip()
    # توحيد أشكال الهمزات والألف
    text = re.sub(r'[أإآا]', 'ا', text)
    # توحيد الهاء والتاء المربوطة إن أمكن، أو إزالة المسافات الزائدة
    text = re.sub(r'\s+', ' ', text)
    return text

def add_person(name, account_no, analytical_acc=""):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            cleaned_name = name.strip()
            c.execute(
                "INSERT OR REPLACE INTO persons (person_name, account_number, analytical_account) VALUES (?, ?, ?)",
                (cleaned_name, account_no.strip(), analytical_acc.strip())
            )
            conn.commit()
            return True
    except Exception:
        return False

# بحث ذكي يتجاهل الهمزات ويدعم المطابقة الجزئية
def get_person_info(name):
    if not name:
        return None
    
    target_normalized = normalize_arabic(name)
    
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # جلب جميع الأسماء من القاعدة للمقارنة الذكية متجاوزين الهمزات
        c.execute("SELECT person_name, account_number, analytical_account FROM persons")
        rows = c.fetchall()
        
        for row in rows:
            db_name = row[0]
            db_normalized = normalize_arabic(db_name)
            
            # مطابقة تامة بعد تنظيف الهمزات أو مطابقة جزئية (الاسم موجود داخل النص)
            if db_normalized == target_normalized or db_normalized in target_normalized or target_normalized in db_normalized:
                return {
                    "account": str(row[1]), 
                    "analytical": str(row[2]) if row[2] else ""
                }
    return None

def get_all_persons():
    with sqlite3.connect(DB_NAME) as conn:
        try:
            df = pd.read_sql_query(
                "SELECT person_name AS 'اسم الشخص', account_number AS 'رقم الحساب', analytical_account AS 'الحساب التحليلي' FROM persons",
                conn
            )
        except Exception:
            df = pd.read_sql_query(
                "SELECT person_name AS 'اسم الشخص', account_number AS 'رقم الحساب' FROM persons",
                conn
            )
    return df

init_db()

st.title("📊 نظام استخراج قيود أونكس برو من رسائل الحوالات (SMS)")

# --- 2. إدارة دليل الأشخاص والحساب المقابل (القائمة الجانبية) ---
st.sidebar.header("⚙️ إعدادات الحسابات")

st.sidebar.subheader("حساب النقدية / الصندوق المقابل")
cash_account_option = st.sidebar.selectbox(
    "اختر حساب النقدية/الصرافة المقابل:",
    [
        "1212021 - العالمية للصرافة (تحليلي: 1)",
        "1211003 - صندوق المبيعات (تحليلي: 3)",
        "مخصص (إدخال يدوي)"
    ]
)

if "العالمية" in cash_account_option:
    cash_acc_num = "1212021"
    cash_acc_ana = "1"
elif "صندوق المبيعات" in cash_account_option:
    cash_acc_num = "1211003"
    cash_acc_ana = "3"
else:
    cash_acc_num = st.sidebar.text_input("رقم الحساب المقابل الرئيسي:", value="1212021")
    cash_acc_ana = st.sidebar.text_input("الحساب التحليلي المقابل (إن وجد):", value="1")

st.sidebar.markdown("---")
st.sidebar.subheader("📁 استيراد دليل العملاء (Excel)")
excel_persons_file = st.sidebar.file_uploader("رفع ملف إكسل للعملاء (اسم الشخص, رقم الحساب, الحساب التحليلي):", type=["xlsx", "xls"])
if excel_persons_file is not None:
    try:
        df_import = pd.read_excel(excel_persons_file)
        if all(col in df_import.columns for col in ['اسم الشخص', 'رقم الحساب', 'الحساب التحليلي']):
            count = 0
            for _, row in df_import.iterrows():
                p_name = str(row['اسم الشخص']).strip()
                p_acc = str(row['رقم الحساب']).strip()
                p_ana = str(row['الحساب التحليلي']).strip() if pd.notna(row['الحساب التحليلي']) else ""
                if p_name and p_acc:
                    add_person(p_name, p_acc, p_ana)
                    count += 1
            st.sidebar.success(f"تم استيراد وتحديث {count} عميل بنجاح!")
            st.rerun()
        else:
            st.sidebar.error("يجب أن يحتوي ملف الإكسل على الأعمدة التالية بالضبط: اسم الشخص, رقم الحساب, الحساب التحليلي")
    except Exception as e:
        st.sidebar.error(f"خطأ في قراءة ملف الإكسل: {e}")

st.sidebar.markdown("---")
st.sidebar.subheader("إضافة عميل يدويًا")
with st.sidebar.form("add_person_form"):
    new_name = st.text_input("اسم الشخص (كما يظهر بالرسالة)")
    new_account = st.text_input("رقم الحساب الرئيسي (مثال: 1211013)")
    new_analytical = st.text_input("الحساب التحليلي (مثال: 701)")
    submit_btn = st.form_submit_button("حفظ الحساب")
    
    if submit_btn:
        if new_name and new_account:
            if add_person(new_name, new_account, new_analytical):
                st.success(f"تم حفظ {new_name} بنجاح!")
                st.rerun()
            else:
                st.warning("حدث خطأ أثناء الحفظ.")
        else:
            st.error("يرجى ملء اسم الشخص ورقم الحساب الرئيسي.")

st.sidebar.dataframe(get_all_persons(), use_container_width=True)

# --- 3. الدوال المساعدة للتحليل ---
def extract_ref_number(raw_text):
    ref_match = re.search(r'/\s*(\d+)', raw_text) or re.search(r'حوالة\s*(\d+)', raw_text) or re.search(r'مرجع\s*(\d+)', raw_text)
    if ref_match:
        return int(ref_match.group(1))
    return None

def split_bulk_messages(text):
    pattern = r'(?=(?:خصم|إيداع|ايداع|صرف|تحويل)\s*[\d\.,]+)'
    parts = re.split(pattern, text)
    messages = [p.strip() for p in parts if p.strip()]
    return messages

def parse_single_message(raw_text, main_cash_acc, main_cash_ana):
    entry_rows = []
    
    amount_match = re.search(r'(?:خصم|إيداع|ايداع|صرف|تحويل)\s*([\d\.,]+)\s*([^\d\s]*)', raw_text) or \
                   re.search(r'(?:خصم|إيداع|ايداع|صرف|تحويل)([\d\.,]+)\s*([^\d\s]*)', raw_text)
    
    if amount_match:
        amount = float(amount_match.group(1).replace(',', ''))
        currency_raw = amount_match.group(2).replace(" ", "") if amount_match.group(2) else ""
        
        if "رؤ" in currency_raw or "ري" in currency_raw:
            currency_code = "1"
            currency_label = "YR"
        elif "رس" in currency_raw or "سعودي" in currency_raw:
            currency_code = "2"
            currency_label = "SR"
        elif "$" in currency_raw or "دولار" in currency_raw or "د.ز" in currency_raw:
            currency_code = "3"
            currency_label = "د.ز"
        else:
            currency_code = "1"
            currency_label = "YR"

        fee_match = re.search(r'ع:\s*([\d\.,]+)', raw_text)
        fee = float(fee_match.group(1).replace(',', '')) if fee_match else 0.0

        person_ref_match = re.search(r'/\s*(.*?)\s*/\s*(\d+)', raw_text) or \
                           re.search(r'من:\s*(.*?)/(\d+)', raw_text) or \
                           re.search(r'حوالة من:\s*(.*?)/(\d+)', raw_text) or \
                           re.search(r'من:\s*(.*?)\s+(\d{5,})', raw_text)
        
        if "خصم" in raw_text or "صرف" in raw_text or "تحويل" in raw_text:
            if person_ref_match:
                person_name = person_ref_match.group(1).strip()
                reference_no = person_ref_match.group(2).strip()
            else:
                person_name = "عميل غير محدد"
                reference_no = "0000"

            header_description = f"خصم تحويل للمستلم {person_name} مرجع {reference_no} ({currency_label})"
            
            p_info = get_person_info(person_name)
            debit_account = p_info["account"] if p_info else "1211013"
            analytical_acc = p_info["analytical"] if (p_info and p_info["analytical"]) else "701"
            
            entry_rows.append({
                "رقم الحساب": debit_account,
                "الحساب التحليلي": analytical_acc,
                "البيان": header_description,
                "المدين": amount,
                "الدائن": 0.0,
                "العملة": currency_code,
                "رقم المرجع": reference_no
            })
            
            if fee > 0:
                entry_rows.append({
                    "رقم الحساب": "321003",
                    "الحساب التحليلي": "",
                    "البيان": f"عمولة تحويل {person_name} مرجع {reference_no}",
                    "المدين": fee,
                    "الدائن": 0.0,
                    "العملة": currency_code,
                    "رقم المرجع": reference_no
                })
                
            total_credit = amount + fee
            entry_rows.append({
                "رقم الحساب": main_cash_acc,
                "الحساب التحليلي": main_cash_ana,
                "البيان": header_description,
                "المدين": 0.0,
                "الدائن": total_credit,
                "العملة": currency_code,
                "رقم المرجع": reference_no
            })

        elif "إيداع" in raw_text or "ايداع" in raw_text:
            if person_ref_match:
                person_name = person_ref_match.group(1).strip()
                reference_no = person_ref_match.group(2).strip()
            else:
                person_name = "عميل غير محدد"
                reference_no = "0000"
            
            header_description = f"إيداع حوالة من {person_name} مرجع {reference_no} ({currency_label})"
            
            p_info = get_person_info(person_name)
            credit_account = p_info["account"] if p_info else "1211013"
            analytical_acc = p_info["analytical"] if (p_info and p_info["analytical"]) else "701"
            
            entry_rows.append({
                "رقم الحساب": main_cash_acc,
                "الحساب التحليلي": main_cash_ana,
                "البيان": header_description,
                "المدين": amount,
                "الدائن": 0.0,
                "العملة": currency_code,
                "رقم المرجع": reference_no
            })
            
            entry_rows.append({
                "رقم الحساب": credit_account,
                "الحساب التحليلي": analytical_acc,
                "البيان": header_description,
                "المدين": 0.0,
                "الدائن": amount,
                "العملة": currency_code,
                "رقم المرجع": reference_no
            })
            
    return entry_rows

# --- 4. واجهة الأداء والاستخراج (التبويبات) ---
tab1, tab2 = st.tabs(["📁 رفع ملف SMS Backup (.xml / .txt)", "📝 لصق رسائل متعددة"])

if "all_entries" not in st.session_state:
    st.session_state.all_entries = []

with tab1:
    st.subheader("رفع ملف النسخة الاحتياطية للرسائل")
    uploaded_file = st.file_uploader("اختر ملف XML أو TXT المنسوخ:", type=["xml", "txt"])
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        start_ref = st.text_input("من رقم حوالة:", value="")
    with col_f2:
        end_ref = st.text_input("إلى رقم حوالة:", value="")
        
    if uploaded_file is not None:
        messages_text = []
        filename = uploaded_file.name.lower()
        
        if filename.endswith(".xml"):
            try:
                tree = ET.parse(uploaded_file)
                root = tree.getroot()
                for sms in root.findall('sms'):
                    body = sms.get('body')
                    if body:
                        messages_text.append(body)
            except Exception as e:
                st.error(f"حدث خطأ أثناء قراءة ملف XML: {e}")
        else:
            content = uploaded_file.read().decode("utf-8")
            messages_text = split_bulk_messages(content)
            
        st.info(f"إجمالي الرسائل المقروءة: {len(messages_text)} رسالة.")
        
        if st.button("توليد ومعالجة القيود من الملف", type="primary"):
            parsed_rows = []
            s_ref = int(start_ref.strip()) if start_ref.strip().isdigit() else None
            e_ref = int(end_ref.strip()) if end_ref.strip().isdigit() else None
            
            for msg in messages_text:
                if s_ref is not None or e_ref is not None:
                    msg_ref = extract_ref_number(msg)
                    if msg_ref is not None:
                        if s_ref is not None and msg_ref < s_ref:
                            continue
                        if e_ref is not None and msg_ref > e_ref:
                            continue
                    else:
                        continue
                        
                rows = parse_single_message(msg, cash_acc_num, cash_acc_ana)
                parsed_rows.extend(rows)
                
            st.session_state.all_entries = parsed_rows
            st.success(f"تمت المعالجة بنجاح! عدد الأسطر المستخرجة: {len(parsed_rows)}")

with tab2:
    st.subheader("إدخال/لصق مجموعة رسائل دفعة واحدة")
    bulk_msg = st.text_area("انسخ والصق نصوص الرسائل هنا:", height=200, placeholder="قم بلصق رسائل الحوالات هنا...")
    
    if st.button("تحويل جميع الرسائل الملصقة إلى قيود", type="primary"):
        if bulk_msg.strip():
            split_messages = split_bulk_messages(bulk_msg)
            parsed_rows = []
            for msg in split_messages:
                rows = parse_single_message(msg, cash_acc_num, cash_acc_ana)
                if rows:
                    parsed_rows.extend(rows)
            if parsed_rows:
                st.session_state.all_entries.extend(parsed_rows)
                st.success("تم تحويل الرسائل بنجاح!")
        else:
            st.warning("الرجاء لصق بعض الرسائل أولاً.")

# --- 5. مراجعة وتصدير القيود لشاشة استيراد أونكس برو ---
if st.session_state.all_entries:
    st.markdown("---")
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.subheader("🔍 شاشة مراجعة وتصدير القيود")
    with col_t2:
        if st.button("🗑️ مسح الجدول وتصفيته"):
            st.session_state.all_entries = []
            st.rerun()

    df_all = pd.DataFrame(st.session_state.all_entries)
    
    total_debit = df_all['المدين'].sum()
    total_credit = df_all['الدائن'].sum()
    st.metric(label="إجمالي المدين", value=f"{total_debit:,.2f}")
    st.metric(label="إجمالي الدائن", value=f"{total_credit:,.2f}")
    
    st.dataframe(df_all[['رقم الحساب', 'الحساب التحليلي', 'البيان', 'المدين', 'الدائن', 'العملة', 'رقم المرجع']], use_container_width=True)
    
    onyx_rows = []
    for idx, row in df_all.iterrows():
        is_local = (row['العملة'] == "1")
        onyx_rows.append({
            "رقم الحساب": row['رقم الحساب'],
            "الحساب التحليلي": row['الحساب التحليلي'],
            "البيان": row['البيان'],
            "مدين محلي": row['المدين'] if is_local else 0.0,
            "مدين أجنبي": 0.0 if is_local else row['المدين'],
            "دائن محلي": row['الدائن'] if is_local else 0.0,
            "دائن أجنبي": 0.0 if is_local else row['الدائن'],
            "العملة": row['العملة'],
            "مركز التكلفة": "",
            "المشروع": "",
            "النشاط": ""
        })
    
    df_onyx_direct = pd.DataFrame(onyx_rows)
    
    buffer_onyx = io.BytesIO()
    with pd.ExcelWriter(buffer_onyx, engine='openpyxl') as writer:
        df_onyx_direct.to_excel(writer, index=False, sheet_name='Onyx_Import')
    buffer_onyx.seek(0)
    
    st.download_button(
        label="📥 تنزيل ملف الإكسل المباشر (المطابق لشاشة استيراد أونكس برو)",
        data=buffer_onyx,
        file_name=f"OnyxPro_Direct_Import_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
