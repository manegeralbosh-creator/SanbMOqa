import sqlite3
import re
import io
import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET

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

def add_person(name, account_no, analytical_acc=""):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO persons (person_name, account_number, analytical_account) VALUES (?, ?, ?)",
                (name.strip(), account_no.strip(), analytical_acc.strip())
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False

def get_person_info(name):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT account_number, analytical_account FROM persons WHERE person_name = ?", (name.strip(),))
        row = c.fetchone()
        if row:
            return {"account": str(row[0]), "analytical": str(row[1]) if row[1] else ""}
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

# --- إعدادات الصفحة ---
st.set_page_config(page_title="نظام قيود أونكس برو - SMS", layout="wide")
st.title("📊 نظام استخراج قيود أونكس برو من رسائل الحوالات (SMS)")

# --- 2. إدارة دليل الأشخاص والحساب المقابل ---
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
st.sidebar.subheader("دليل حسابات أونكس للأشخاص")
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
                st.warning("الاسم مكرر في قاعدة البيانات.")
        else:
            st.error("يرجى ملء اسم الشخص ورقم الحساب الرئيسي.")

st.sidebar.dataframe(get_all_persons(), use_container_width=True)

# --- 3. استخراج رقم الحوالة/المرجع للفلترة ---
def extract_ref_number(raw_text):
    ref_match = re.search(r'/\s*(\d+)', raw_text) or re.search(r'حوالة\s*(\d+)', raw_text) or re.search(r'مرجع\s*(\d+)', raw_text)
    if ref_match:
        return int(ref_match.group(1))
    return None

# --- 4. دالة الفصل الذكي الشاملة لعدم فقدان أي رسالة ---
def split_bulk_messages(text):
    # نمط مرن لتقسيم الرسائل بناءً على الكلمات المفتاحية الشائعة للعمليات المالية
    pattern = r'(?=(?:خصم|إيداع|ايداع|صرف|تحويل)\s*[\d\.,]+)'
    parts = re.split(pattern, text)
    messages = [p.strip() for p in parts if p.strip()]
    return messages

# --- 5. محرك تحليل النص المحدث (بدون رصيد + دعم عملة د.ز) ---
def parse_single_message(raw_text, main_cash_acc, main_cash_ana):
    entry_rows = []
    
    # تحديد العملة والمبلغ
    # يدعم: ري (ريال يمني/محلي)، رس (ريال سعودي)، أو $ / دولار / د.ز
    amount_match = re.search(r'(?:خصم|إيداع|ايداع|صرف|تحويل)\s*([\d\.,]+)\s*([^\d\s]+)', raw_text)
    
    if amount_match:
        amount = float(amount_match.group(1).replace(',', ''))
        currency_raw = amount_match.group(2).replace(" ", "")
        
        # تحديد كود العملة وتسميتها
        if "رؤ" in currency_raw or "ري" in currency_raw:
            currency_code = "1"
            currency_label = "YR"
        elif "رس" in currency_raw or "سعودي" in currency_raw:
            currency_code = "2"
            currency_label = "SR"
        elif "$" in currency_raw or "دولار" in currency_raw or "د.ز" in currency_raw:
            currency_code = "3"  # كود العملة الأجنبية الثالثة (الدولار)
            currency_label = "د.ز"
        else:
            currency_code = "1"
            currency_label = "YR"

        fee_match = re.search(r'ع:\s*([\d\.,]+)', raw_text)
        fee = float(fee_match.group(1).replace(',', '')) if fee_match else 0.0

        # استخراج اسم الشخص ورقم المرجع بمرونة أعلى لمنع الفقدان
        person_ref_match = re.search(r'/\s*(.*?)\s*/\s*(\d+)', raw_text) or re.search(r'من:\s*(.*?)/(\d+)', raw_text)
        
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
            
            # سطر مدين للشخص
            entry_rows.append({
                "رقم الحساب": debit_account,
                "الحساب التحليلي": analytical_acc,
                "البيان": header_description,
                "المدين": amount,
                "الدائن": 0.0,
                "العملة": currency_code,
                "رقم المرجع": reference_no
            })
            
            # سطر عمولة (إن وجد)
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
            # سطر دائن للصندوق/العالمية
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
            
            # سطر مدين للصندوق/العالمية
            entry_rows.append({
                "رقم الحساب": main_cash_acc,
                "الحساب التحليلي": main_cash_ana,
                "البيان": header_description,
                "المدين": amount,
                "الدائن": 0.0,
                "العملة": currency_code,
                "رقم المرجع": reference_no
            })
            
            # سطر دائن للشخص
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

# --- 6. واجهة الأداء والاستخراج ---
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
        
        if st.button("تول
