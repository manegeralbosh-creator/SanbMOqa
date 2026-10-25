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
                "INSERT OR REPLACE INTO persons (person_name, account_number, analytical_account) VALUES (?, ?, ?)",
                (name.strip(), account_no.strip(), analytical_acc.strip())
            )
            conn.commit()
            return True
    except Exception:
        return False

# بحث ذكي ومرن (يدعم المطابقة الجزئية للأسماء)
def get_person_info(name):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # 1. محاولة مطابقة تامة أولاً
        c.execute("SELECT account_number, analytical_account FROM persons WHERE person_name = ?", (name.strip(),))
        row = c.fetchone()
        
        # 2. إذا لم توجد مطابقة تامة، نبحث بمطابقة جزئية (داخل النص)
        if not row:
            c.execute("SELECT account_number, analytical_account FROM persons WHERE ? LIKE '%' || person_name || '%'", (name.strip(),))
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

# --- 3. استخراج رقم الحوالة/المرجع للفلترة ---
def extract_ref_number(raw_text):
    ref_match = re.search(r'/\s*(\d+)', raw_text) or re.search(r'حوالة\s*(\d+)', raw_text) or re.search(r'مرجع\s*(\d+)', raw_text)
    if ref_match:
        return int(ref_match.group(1))
    return None

# --- 4. دالة الفصل الذكي الشاملة لعدم فقدان أي رسالة ---
def split_bulk_messages(text):
    pattern = r'(?=(?:خصم|إيداع|ايداع|صرف|تحويل)\s*[\d\.,]+)'
    parts = re.split(pattern, text)
    messages = [p.strip() for p in parts if p.strip()]
    return messages

# --- 5. محرك تحليل النص المحدث (بدون رصيد + دعم عملة د.ز + ربط ذكي للأسماء) ---
def parse_single_message(raw_text, main_cash_acc, main_cash_ana):
    entry_rows = []
    
    amount_match = re.search(r'(?:خصم|إيداع|ايداع|صرف|تحويل)\s*([\d\.,]+)\s*([^\d\s]+)', raw_text)
    
    if amount_match:
        amount = float(amount_match.group(1).replace(',', ''))
        currency_raw = amount_match.group(2).replace(" ", "")
        
        # تحديد العملة وكودها في أونكس
        if "رؤ" in currency_raw or "ري" in currency_raw:
            currency_code = "1"
            currency_label = "YR"
        elif "رس" in currency_raw or "سعودي" in currency_raw:
            currency_code = "2"
            currency_label = "SR"
        elif "$" in currency_raw or "دولار" in currency_raw or "د.ز" in currency_raw:
            currency_code = "3"  # عملة الدولار (د.ز)
            currency_label = "د.ز"
        else:
            currency_code = "1"
            currency_label = "YR"

        fee_match = re.search(r'ع:\s*([\d\.,]+)', raw_text)
        fee = float(fee_match.group(1).replace(',', '')) if fee_match else 0.0

        person_ref_match = re.search(r'/\s*(.*?)\s*/\s*(\d+)', raw_text) or re.search(r'من:\s*(.*?)/(\d+)', raw_text)
        
        if "خصم" in raw_text or "صرف" in raw_text or "تحويل" in raw_text:
            if person_ref_match:
                person_name = person_ref_match.group(1).strip()
                reference_no = person_ref_match.group(2).strip()
            else:
                person_name = "عميل غير محدد"
                reference_no = "0000"

            header_description = f"خصم تحويل للمستلم {person_name} مرجع {reference_no} ({currency_label})"
            
            # البحث الذكي في قاعدة البيانات (مطابقة تامة أو جزئية)
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
                person_name = person_ref
