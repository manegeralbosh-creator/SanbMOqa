import sqlite3
import re
import pandas as pd
import streamlit as st
import xml.etree.ElementTree as ET
import io

# --- 1. تهيئة وترقية قاعدة البيانات تلقائياً ---
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
    try:
        c.execute("ALTER TABLE persons ADD COLUMN analytical_account TEXT")
    except sqlite3.OperationalError:
        pass
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
        return {"account": str(row[0]), "analytical": str(row[1]) if (len(row) > 1 and row[1]) else ""}
    return None

def get_all_persons():
    conn = sqlite3.connect("accounts_db.db")
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
    conn.close()
    return df

init_db()

st.set_page_config(page_title="نظام قيود أونكس برو - SMS", layout="wide")
st.title("نظام استخراج قيود أونكس برو من رسائل الحوالات")

# --- 2. إدارة دليل الأشخاص وتحديد حساب النقدية/الصندوق المقابل ---
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
    
    if submit_btn and new_name and new_account:
        if add_person(new_name.strip(), new_account.strip(), new_analytical.strip()):
            st.success(f"تم حفظ {new_name} بنجاح!")
            st.rerun()
        else:
            st.warning("الاسم مكرر في قاعدة البيانات.")

st.sidebar.dataframe(get_all_persons(), use_container_width=True)

# --- 3. استخراج رقم الحوالة/المرجع للفلترة ---
def extract_ref_number(raw_text):
    ref_match = re.search(r'/\s*(\d+)', raw_text) or re.search(r'حوالة\s*(\d+)', raw_text)
    if ref_match:
        return int(ref_match.group(1))
    return None

# --- 4. دالة الفصل الذكي للرسائل المتصلة الملصقة دفعة واحدة ---
def split_bulk_messages(text):
    pattern = r'(?=(?:خصم|إيداع|ايداع)\s*[\d\.,]+)'
    parts = re.split(pattern, text)
    messages = [p.strip() for p in parts if p.strip()]
    return messages

# --- 5. محرك تحليل النص واستخراج القيود ---
def parse_single_message(raw_text, main_cash_acc, main_cash_ana):
    entry_rows = []
    
    balance_match = re.search(r'رصيدك:\s*([\d\.,]+)', raw_text) or re.search(r'الرصيد:\s*([\d\.,]+)', raw_text)
    balance_str = f" | الرصيد: {balance_match.group(1)}" if balance_match else ""
    
    if "خصم" in raw_text:
        amount_match = re.search(r'خصم\s*([\d\.,]+)\s*(ر\s*ي|ر\s*س)', raw_text)
        fee_match = re.search(r'ع:\s*([\d\.,]+)', raw_text)
        person_ref_match = re.search(r'/\s*(.*?)\s*/\s*(\d+)', raw_text)
        
        if amount_match and person_ref_match:
            amount = float(amount_match.group(1).replace(',', ''))
            currency_raw = amount_match.group(2).replace(" ", "")
            currency_code = "1" if "ري" in currency_raw else "2" # 1 محلي، 2 أجنبي
            currency_label = "YR" if "ري" in currency_raw else "SR"
            
            fee = float(fee_match.group(1).replace(',', '')) if fee_match else 0.0
            person_name = person_ref_match.group(1).strip()
            reference_no = person_ref_match.group(2).strip()
            
            header_description = f"خصم تحويل للمستلم {person_name} مرجع {reference_no} ({currency_label}){balance_str}"
            
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
            
            # سطر عمولة
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
        amount_match = re.search(r'إيداع\s*([\d\.,]+)\s*(ر\s*ي|ر\s*س)', raw_text) or re.search(r'ايداع\s*([\d\.,]+)\s*(ر\s*ي|ر\s*س)', raw_text)
        transfer_match = re.search(r'حوالة من:\s*(.*?)/(\d+)', raw_text)
        
        if amount_match and transfer_match:
            amount = float(amount_match.group(1).replace(',', ''))
            currency_raw = amount_match.group(2).replace(" ", "")
            currency_code = "1" if "ري" in currency_raw else "2"
            currency_label = "YR" if "ري" in currency_raw else "SR"
            
            person_name = transfer_match.group(1).strip()
            reference_no = transfer_match.group(2).strip()
            
            header_description = f"إيداع حوالة من {person_name} مرجع {reference_no} ({currency_label}){balance_str}"
            
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

# --- 6. واجهة الأداء ---
tab1, tab2 = st.tabs(["رفع ملف SMS Backup (.xml / .txt)", "لصق رسائل متعددة دفعة واحدة"])

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
                st.error("حدث خطأ أثناء قراءة ملف XML.")
        else:
            content = uploaded_file.read().decode("utf-8")
            messages_text = split_bulk_messages(content)
            
        st.info(f"إجمالي الرسائل المقروءة: {len(messages_text)} رسالة.")
        
        if st.button("توليد ومعالجة القيود من الملف"):
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
            st.success(f"تم معالجة الرسائل بنجاح! عدد الأسطر المستخرجة: {len(parsed_rows)}")

with tab2:
    st.subheader("إدخال/لصق مجموعة رسائل دفعة واحدة")
    bulk_msg = st.text_area("انسخ والصق نصوص الرسائل هنا:", height=200)
    
    if st.button("تحويل جميع الرسائل الملصقة إلى قيود"):
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

# --- 7. التصدير المباشر المتوافق مع شاشة أونكس برو ---
if st.session_state.all_entries:
    st.markdown("---")
    st.subheader("🔍 شاشة مراجعة وتصدير القيود")
    
    df_all = pd.DataFrame(st.session_state.all_entries)
    st.dataframe(df_all[['رقم الحساب', 'الحساب التحليلي', 'البيان', 'المدين', 'الدائن', 'رقم المرجع']], use_container_width=True)
    
    # بناء الجدول المخصص لشاشة استيراد القيود في أونكس برو بالترتيب المطلوب تماماً
    # ترتيب أونكس: رقم الحساب - الحساب التحليلي - البيان - مدين محلي - مدين أجنبي - دائن محلي - دائن أجنبي - العملة - مركز التكلفة - المشروع - النشاط
    onyx_rows = []
    for idx, row in df_all.iterrows():
        is_foreign = (row['العملة'] == "2")
        onyx_rows.append({
            "رقم الحساب": row['رقم الحساب'],
            "الحساب التحليلي": row['الحساب التحليلي'],
            "البيان": row['البيان'],
            "مدين محلي": 0.0 if is_foreign else row['المدين'],
            "مدين أجنبي": row['المدين'] if is_foreign else 0.0,
            "دائن محلي": 0.0 if is_foreign else row['الدائن'],
            "دائن أجنبي": row['الدائن'] if is_foreign else 0.0,
            "العملة": row['العملة'],
            "مركز التكلفة": "",
            "المشروع": "",
            "النشاط": ""
        })
    
    df_onyx_direct = pd.DataFrame(onyx_rows)
    
    # تحضير ملف الإكسل للتنزيل
    buffer_onyx = io.BytesIO()
    with pd.ExcelWriter(buffer_onyx, engine='openpyxl') as writer:
        df_onyx_direct.to_excel(writer, index=False, sheet_name='Onyx_Import')
    buffer_onyx.seek(0)
    
    st.download_button(
        label="📥 تنزيل ملف الإكسل المباشر (المطابق لشاشة استيراد أونكس برو لديك)",
        data=buffer_onyx,
        file_name=f"OnyxPro_Direct_Import_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
