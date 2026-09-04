import sqlite3
import re
import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET

# --- 1. تهيئة قاعدة البيانات المدمجة للأشخاص ---
def init_db():
    conn = sqlite3.connect("accounts_db.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS persons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_name TEXT UNIQUE,
            account_number TEXT,
            analytical_account TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_person(name, account_no, analytical_acc=""):
    conn = sqlite3.connect("accounts_db.db")
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO persons (person_name, account_number, analytical_account) VALUES (?, ?, ?)",
            (name, account_no, analytical_acc)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_person_info(name):
    conn = sqlite3.connect("accounts_db.db")
    c = conn.cursor()
    c.execute("SELECT account_number, analytical_account FROM persons WHERE person_name = ?", (name,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"account": row[0], "analytical": row[1]}
    return None

def get_all_persons():
    conn = sqlite3.connect("accounts_db.db")
    df = pd.read_sql_query(
        "SELECT person_name AS 'اسم الشخص', account_number AS 'رقم الحساب', analytical_account AS 'الحساب التحليلي' FROM persons",
        conn
    )
    conn.close()
    return df

init_db()

st.set_page_config(page_title="قيود أونكس برو - SMS", layout="wide")
st.title("نظام استخراج قيود أونكس برو من رسائل الحوالات")

# --- 2. إدارة دليل الأشخاص والحسابات ---
st.sidebar.header("دليل حسابات أونكس للأشخاص")
with st.sidebar.form("add_person_form"):
    new_name = st.text_input("اسم الشخص (كما يظهر بالرسالة)")
    new_account = st.text_input("رقم الحساب في أونكس (مثال: 1221000)")
    new_analytical = st.text_input("الحساب التحليلي (اختياري - مثال: 701)")
    submit_btn = st.form_submit_button("حفظ الحساب")
    
    if submit_btn and new_name and new_account:
        if add_person(new_name.strip(), new_account.strip(), new_analytical.strip()):
            st.success(f"تم حفظ {new_name} بنجاح!")
        else:
            st.warning("الاسم مكرر في قاعدة البيانات.")

st.sidebar.dataframe(get_all_persons(), use_container_width=True)

# --- 3. محرك تحليل نص الرسالة بفريمة أونكس برو ---
def parse_single_message(raw_text):
    entry_rows = []
    today_str = pd.Timestamp.now().strftime('%d/%m/%Y')
    
    # --- حالة 1: خصم / حوالة صادرة ---
    if "خصم" in raw_text:
        amount_match = re.search(r'خصم\s*([\d\.,]+)\s*(ر\s*ي|ر\s*س)', raw_text)
        fee_match = re.search(r'ع:\s*([\d\.,]+)', raw_text)
        person_ref_match = re.search(r'/\s*(.*?)\s*/\s*(\d+)', raw_text)
        
        if amount_match and person_ref_match:
            amount = float(amount_match.group(1).replace(',', ''))
            currency_raw = amount_match.group(2).replace(" ", "")
            currency = "YR" if "ري" in currency_raw else "SR"
            
            fee = float(fee_match.group(1).replace(',', '')) if fee_match else 0.0
            person_name = person_ref_match.group(1).strip()
            reference_no = person_ref_match.group(2).strip()
            
            # صيغة البيان المطابقة لشاشة أونكس
            description = f"تحويل للمستلم {person_name} مرجع {reference_no}"
            
            p_info = get_person_info(person_name)
            debit_account = p_info["account"] if p_info else "1211013"
            analytical_acc = p_info["analytical"] if (p_info and p_info["analytical"]) else "701"
            
            # 1. جانب المدين (حساب الشخص أو الحساب العادي)
            entry_rows.append({
                "رقم المستند": reference_no,
                "التاريخ": today_str,
                "رقم الحساب": debit_account,
                "الاسم": person_name if p_info else "صندوق جيبي",
                "الحساب التحليلي": analytical_acc,
                "البيان": description,
                "العملة": currency,
                "معدل الصرف": 1,
                "مدين": amount,
                "دائن": 0.0
            })
            
            # 2. عمولة البنك (إن وجدت)
            if fee > 0:
                entry_rows.append({
                    "رقم المستند": reference_no,
                    "التاريخ": today_str,
                    "رقم الحساب": "321003",
                    "الاسم": "مصروفات العمولات البنكية",
                    "الحساب التحليلي": "",
                    "البيان": f"عمولة تحويل {person_name} مرجع {reference_no}",
                    "العملة": currency,
                    "معدل الصرف": 1,
                    "مدين": fee,
                    "دائن": 0.0
                })
                
            # 3. جانب الدائن (الصرافة / البنك)
            total_credit = amount + fee
            entry_rows.append({
                "رقم المستند": reference_no,
                "التاريخ": today_str,
                "رقم الحساب": "1212032",
                "الاسم": "الصرافة العالمية",
                "الحساب التحليلي": "",
                "البيان": description,
                "العملة": currency,
                "معدل الصرف": 1,
                "مدين": 0.0,
                "دائن": total_credit
            })

    # --- حالة 2: إيداع / حوالة واردة ---
    elif "إيداع" in raw_text or "ايداع" in raw_text:
        amount_match = re.search(r'إيداع\s*([\d\.,]+)\s*(ر\s*ي|ر\s*س)', raw_text)
        transfer_match = re.search(r'حوالة من:\s*(.*?)/(\d+)', raw_text)
        
        if amount_match and transfer_match:
            amount = float(amount_match.group(1).replace(',', ''))
            currency_raw = amount_match.group(2).replace(" ", "")
            currency = "YR" if "ري" in currency_raw else "SR"
            
            person_name = transfer_match.group(1).strip()
            reference_no = transfer_match.group(2).strip()
            
            # صيغة البيان المطابقة لأونكس (مثال: من نايف ناصر الهادي...)
            description = f"من {person_name} حوالة {reference_no}"
            
            p_info = get_person_info(person_name)
            credit_account = p_info["account"] if p_info else "1211013"
            analytical_acc = p_info["analytical"] if (p_info and p_info["analytical"]) else "701"
            
            # 1. مدين: حساب الصرافة / الصندوق
            entry_rows.append({
                "رقم المستند": reference_no,
                "التاريخ": today_str,
                "رقم الحساب": "1212032",
                "الاسم": "الصرافة العالمية",
                "الحساب التحليلي": "",
                "البيان": description,
                "العملة": currency,
                "معدل الصرف": 1,
                "مدين": amount,
                "دائن": 0.0
            })
            
            # 2. دائن: حساب العميل / الشخص
            entry_rows.append({
                "رقم المستند": reference_no,
                "التاريخ": today_str,
                "رقم الحساب": credit_account,
                "الاسم": person_name if p_info else "صندوق جيبي",
                "الحساب التحليلي": analytical_acc,
                "البيان": description,
                "العملة": currency,
                "معدل الصرف": 1,
                "مدين": 0.0,
                "دائن": amount
            })
            
    return entry_rows

# --- 4. واجهة المستخدم ---
tab1, tab2 = st.tabs(["رفع ملف SMS Backup (.xml / .txt)", "إدخال يدوي لرسالة"])

all_final_rows = []

with tab1:
    st.subheader("رفع ملف النسخة الاحتياطية للرسائل")
    uploaded_file = st.file_uploader("اختر ملف XML المنسوخ من التطبيق:", type=["xml", "txt"])
    
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
                st.error("حدث خطأ أثناء قراءة ملف XML.")
        else:
            content = uploaded_file.read().decode("utf-8")
            messages_text = [m.strip() for m in re.split(r'={3,}|-{3,}|\n\s*\n', content) if m.strip()]
            
        st.info(f"تم تحليل الملف وإيجاد {len(messages_text)} رسالة.")
        
        if st.button("توليد قيود أونكس برو"):
            for msg in messages_text:
                rows = parse_single_message(msg)
                all_final_rows.extend(rows)

with tab2:
    st.subheader("إدخال رسالة واحدة")
    single_msg = st.text_area("أدخل نص الرسالة:", height=120)
    if st.button("تحويل إلى قيد"):
        if single_msg.strip():
            rows = parse_single_message(single_msg)
            all_final_rows.extend(rows)

# --- 5. عرض القيود وتصدير الإكسل المطابق لأونكس ---
if all_final_rows:
    df_result = pd.DataFrame(all_final_rows)
    st.success(f"تم توليد {len(df_result)} أسطر قيود جاهزة للاستيراد!")
    
    st.dataframe(df_result, use_container_width=True)
    
    export_file_name = f"OnyxPro_Entries_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx"
    df_result.to_excel(export_file_name, index=False)
    
    with open(export_file_name, "rb") as f:
        st.download_button(
            label="تنزيل ملف الإكسل المطابق لشاشة أونكس برو",
            data=f,
            file_name=export_file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
