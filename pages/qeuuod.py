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
            account_number TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_person(name, account_no):
    conn = sqlite3.connect("accounts_db.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO persons (person_name, account_number) VALUES (?, ?)", (name, account_no))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_person_account(name):
    conn = sqlite3.connect("accounts_db.db")
    c = conn.cursor()
    c.execute("SELECT account_number FROM persons WHERE person_name = ?", (name,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_all_persons():
    conn = sqlite3.connect("accounts_db.db")
    df = pd.read_sql_query("SELECT person_name AS 'اسم الشخص', account_number AS 'رقم الحساب' FROM persons", conn)
    conn.close()
    return df

init_db()

st.set_page_config(page_title="معالج قيود أونكس - SMS", layout="wide")
st.title("نظام تحويل رسائل الحوالات إلى قيود أونكس برو")

# --- 2. إدارة دليل الأشخاص ---
st.sidebar.header("دليل حسابات الأشخاص")
with st.sidebar.form("add_person_form"):
    new_name = st.text_input("اسم الشخص")
    new_account = st.text_input("رقم الحساب في أونكس")
    submit_btn = st.form_submit_button("حفظ الحساب")
    
    if submit_btn and new_name and new_account:
        if add_person(new_name.strip(), new_account.strip()):
            st.success(f"تم حفظ {new_name} بنجاح!")
        else:
            st.warning("الاسم مكرر في قاعدة البيانات.")

st.sidebar.dataframe(get_all_persons(), use_container_width=True)

# --- 3. محرك تحليل نص الرسالة ---
def parse_single_message(raw_text):
    entry_rows = []
    today_str = pd.Timestamp.now().strftime('%Y/%m/%d')
    
    # --- حالة 1: خصم / حوالة صادرة ---
    if "خصم" in raw_text:
        amount_match = re.search(r'خصم\s*([\d\.,]+)\s*(ر\s*ي|ر\s*س)', raw_text)
        fee_match = re.search(r'ع:\s*([\d\.,]+)', raw_text)
        person_ref_match = re.search(r'/\s*(.*?)\s*/\s*(\d+)', raw_text)
        
        if amount_match and person_ref_match:
            amount = float(amount_match.group(1).replace(',', ''))
            currency_raw = amount_match.group(2).replace(" ", "")
            currency = "RY" if currency_raw == "ري" else "SR"
            
            fee = float(fee_match.group(1).replace(',', '')) if fee_match else 0.0
            person_name = person_ref_match.group(1).strip()
            reference_no = person_ref_match.group(2).strip()
            
            description = f"تحويل المستلم {person_name} {reference_no}"
            custom_acc = get_person_account(person_name)
            debit_account = custom_acc if custom_acc else "121103"
            
            entry_rows.append({
                "رقم السند": reference_no, "التاريخ": today_str, "رقم الحساب": debit_account,
                "اسم الحساب": person_name if custom_acc else "صندوق المبيعات",
                "مدين": amount, "دائن": 0, "العملة": currency, "البيان": description, "رقم المرجع": reference_no
            })
            if fee > 0:
                entry_rows.append({
                    "رقم السند": reference_no, "التاريخ": today_str, "رقم الحساب": "321003",
                    "اسم الحساب": "مصروفات العمولات البنكية",
                    "مدين": fee, "دائن": 0, "العملة": currency, "البيان": description, "رقم المرجع": reference_no
                })
            entry_rows.append({
                "رقم السند": reference_no, "التاريخ": today_str, "رقم الحساب": "1212032",
                "اسم الحساب": "الصرافة العالمية",
                "مدين": 0, "دائن": amount, "العملة": currency, "البيان": description, "رقم المرجع": reference_no
            })
            if fee > 0:
                entry_rows.append({
                    "رقم السند": reference_no, "التاريخ": today_str, "رقم الحساب": "1212032",
                    "اسم الحساب": "الصرافة العالمية",
                    "مدين": 0, "دائن": fee, "العملة": currency, "البيان": description, "رقم المرجع": reference_no
                })

    # --- حالة 2: إيداع ---
    elif "إيداع" in raw_text or "ايداع" in raw_text:
        amount_match = re.search(r'إيداع\s*([\d\.,]+)\s*(ر\s*ي|ر\s*س)', raw_text)
        transfer_match = re.search(r'حوالة من:\s*(.*?)/(\d+)', raw_text)
        
        if amount_match and transfer_match:
            amount = float(amount_match.group(1).replace(',', ''))
            currency_raw = amount_match.group(2).replace(" ", "")
            currency = "RY" if currency_raw == "ري" else "SR"
            
            person_name = transfer_match.group(1).strip()
            reference_no = transfer_match.group(2).strip()
            
            description = f"ايداع من {person_name} {reference_no}"
            custom_acc = get_person_account(person_name)
            credit_account = custom_acc if custom_acc else "121103"
            
            entry_rows = [
                {
                    "رقم السند": reference_no, "التاريخ": today_str, "رقم الحساب": "1212032",
                    "اسم الحساب": "الصرافة العالمية", "مدين": amount, "دائن": 0,
                    "العملة": currency, "البيان": description, "رقم المرجع": reference_no
                },
                {
                    "رقم السند": reference_no, "التاريخ": today_str, "رقم الحساب": credit_account,
                    "اسم الحساب": person_name if custom_acc else "صندوق المبيعات", "مدين": 0, "دائن": amount,
                    "العملة": currency, "البيان": description, "رقم المرجع": reference_no
                }
            ]
            
    return entry_rows

# --- 4. واجهة المستخدم ---
tab1, tab2 = st.tabs(["رفع ملف SMS Backup (.xml / .txt)", "إدخال يدوي لرسالة"])

all_final_rows = []

with tab1:
    st.subheader("رفع الملف المصدّر من تطبيق SMS Backup & Restore")
    uploaded_file = st.file_uploader("اختر ملف النسخة الاحتياطية (.xml أو .txt):", type=["xml", "txt"])
    
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
            
        st.info(f"تم تمييز {len(messages_text)} رسالة داخل الملف.")
        
        if st.button("توليد القيود وتجهيز ملف أونكس"):
            for msg in messages_text:
                rows = parse_single_message(msg)
                all_final_rows.extend(rows)

with tab2:
    st.subheader("إدخال نص رسالة واحدة")
    single_msg = st.text_area("أدخل الرسالة هنا:", height=150)
    if st.button("معالجة الرسالة الفردية"):
        if single_msg.strip():
            rows = parse_single_message(single_msg)
            all_final_rows.extend(rows)

# --- 5. عرض التقرير والتنزيل ---
if all_final_rows:
    df_result = pd.DataFrame(all_final_rows)
    st.success(f"تم استخراج وتجهيز {len(df_result)} أسطر قيود يومية بنجاح!")
    st.dataframe(df_result, use_container_width=True)
    
    export_file_name = f"Onyx_SMS_Entries_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx"
    df_result.to_excel(export_file_name, index=False)
    
    with open(export_file_name, "rb") as f:
        st.download_button(
            label="تنزيل ملف الإكسل الجاهز للاستيراد في أونكس برو",
            data=f,
            file_name=export_file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
