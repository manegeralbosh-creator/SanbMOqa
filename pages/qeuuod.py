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

# --- 2. إدارة دليل الأشخاص بالحسابات التحليلية ---
st.sidebar.header("دليل حسابات أونكس للأشخاص")
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

# --- 3. استخراج رقم الحوالة/المرجع من الرسالة مباشرة للفلترة ---
def extract_ref_number(raw_text):
    ref_match = re.search(r'/\s*(\d+)', raw_text) or re.search(r'حوالة\s*(\d+)', raw_text)
    if ref_match:
        return int(ref_match.group(1))
    return None

# --- 4. محرك تحليل النص واستخراج الرصيد والبيان القياسي ---
def parse_single_message(raw_text):
    entry_rows = []
    
    balance_match = re.search(r'رصيدك:\s*([\d\.,]+)', raw_text) or re.search(r'الرصيد:\s*([\d\.,]+)', raw_text)
    balance_str = f" | الرصيد: {balance_match.group(1)}" if balance_match else ""
    
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
            
            header_description = f"خصم تحويل للمستلم {person_name} مرجع {reference_no} ({currency}){balance_str}"
            
            p_info = get_person_info(person_name)
            debit_account = p_info["account"] if p_info else "1211013"
            analytical_acc = p_info["analytical"] if (p_info and p_info["analytical"]) else "701"
            
            entry_rows.append({
                "رقم الحساب": debit_account,
                "الحساب التحليلي": analytical_acc,
                "البيان": header_description,
                "المدين": amount,
                "الدائن": 0.0,
                "رقم المرجع": reference_no
            })
            
            if fee > 0:
                entry_rows.append({
                    "رقم الحساب": "321003",
                    "الحساب التحليلي": "",
                    "البيان": f"عمولة تحويل {person_name} مرجع {reference_no}",
                    "المدين": fee,
                    "الدائن": 0.0,
                    "رقم المرجع": reference_no
                })
                
            total_credit = amount + fee
            entry_rows.append({
                "رقم الحساب": "1212032",
                "الحساب التحليلي": "",
                "البيان": header_description,
                "المدين": 0.0,
                "الدائن": total_credit,
                "رقم المرجع": reference_no
            })

    # --- حالة 2: إيداع / حوالة واردة ---
    elif "إيداع" in raw_text or "ايداع" in raw_text:
        amount_match = re.search(r'إيداع\s*([\d\.,]+)\s*(ر\s*ي|ر\s*س)', raw_text) or re.search(r'ايداع\s*([\d\.,]+)\s*(ر\s*ي|ر\s*س)', raw_text)
        transfer_match = re.search(r'حوالة من:\s*(.*?)/(\d+)', raw_text)
        
        if amount_match and transfer_match:
            amount = float(amount_match.group(1).replace(',', ''))
            currency_raw = amount_match.group(2).replace(" ", "")
            currency = "YR" if "ري" in currency_raw else "SR"
            
            person_name = transfer_match.group(1).strip()
            reference_no = transfer_match.group(2).strip()
            
            header_description = f"إيداع حوالة من {person_name} مرجع {reference_no} ({currency}){balance_str}"
            
            p_info = get_person_info(person_name)
            credit_account = p_info["account"] if p_info else "1211013"
            analytical_acc = p_info["analytical"] if (p_info and p_info["analytical"]) else "701"
            
            entry_rows.append({
                "رقم الحساب": "1212032",
                "الحساب التحليلي": "",
                "البيان": header_description,
                "المدين": amount,
                "الدائن": 0.0,
                "رقم المرجع": reference_no
            })
            
            entry_rows.append({
                "رقم الحساب": credit_account,
                "الحساب التحليلي": analytical_acc,
                "البيان": header_description,
                "المدين": 0.0,
                "الدائن": amount,
                "رقم المرجع": reference_no
            })
            
    return entry_rows

# --- 5. واجهة رفع الملفات مع الفلترة بمدى أرقام الحوالات ---
tab1, tab2 = st.tabs(["رفع ملف SMS Backup (.xml / .txt)", "إدخال يدوي لرسالة"])

if "all_entries" not in st.session_state:
    st.session_state.all_entries = []

with tab1:
    st.subheader("رفع ملف النسخة الاحتياطية للرسائل")
    uploaded_file = st.file_uploader("اختر ملف XML أو TXT المنسوخ:", type=["xml", "txt"])
    
    # إضافة خانات تصفية نطاق أرقام الحوالات
    st.markdown("### 🎯 فلترة النطاق (اختياري لتسريع التوليد وتقليل الحجم)")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        start_ref = st.text_input("من رقم حوالة (أول رقم باليوم):", value="")
    with col_f2:
        end_ref = st.text_input("إلى رقم حوالة (آخر رقم باليوم):", value="")
        
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
            
        st.info(f"إجمالي الرسائل في الملف: {len(messages_text)} رسالة.")
        
        if st.button("توليد ومعالجة القيود"):
            parsed_rows = []
            
            # تحويل المدخلات إلى أرقام إذا تم إدخالها
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
                        
                rows = parse_single_message(msg)
                parsed_rows.extend(rows)
                
            st.session_state.all_entries = parsed_rows
            st.success(f"تم معالجة المستندات بنجاح! عدد الأسطر المستخرجة: {len(parsed_rows)}")

with tab2:
    st.subheader("إدخال رسالة واحدة")
    single_msg = st.text_area("أدخل نص الرسالة هنا:", height=120)
    if st.button("تحويل الرسالة إلى قيد"):
        if single_msg.strip():
            rows = parse_single_message(single_msg)
            st.session_state.all_entries.extend(rows)
            st.success("تمت إضافة القيد بنجاح!")

# --- 6. شاشة المراجعة وتنزيل الإكسل المباشر ---
if st.session_state.all_entries:
    st.markdown("---")
    st.subheader("🔍 شاشة مراجعة والبحث في القيود المستخرجة")
    
    df_all = pd.DataFrame(st.session_state.all_entries)
    
    col_search1, col_search2 = st.columns(2)
    with col_search1:
        search_term = st.text_input("بحث في البيان أو اسم الشخص أو المرجع:")
    with col_search2:
        filter_acc = st.text_input("فلترة حسب رقم الحساب:")
        
    df_filtered = df_all.copy()
    if search_term:
        df_filtered = df_filtered[df_filtered['البيان'].str.contains(search_term, case=False, na=False) | 
                                  df_filtered['رقم المرجع'].str.contains(search_term, case=False, na=False)]
    if filter_acc:
        df_filtered = df_filtered[df_filtered['رقم الحساب'].astype(str).str.contains(filter_acc)]
        
    total_debit = df_filtered['المدين'].sum()
    total_credit = df_filtered['الدائن'].sum()
    st.markdown(f"**عدد الأسطر المعروضة:** `{len(df_filtered)}` | **إجمالي المدين:** `{total_debit:,.2f}` | **إجمالي الدائن:** `{total_credit:,.2f}`")
    
    df_export = df_filtered[['رقم الحساب', 'الحساب التحليلي', 'البيان', 'المدين', 'الدائن', 'رقم المرجع']]
    st.dataframe(df_export, use_container_width=True)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Onyx_Entries')
    
    buffer.seek(0)
    export_filename = f"OnyxPro_Entries_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx"
    
    st.download_button(
        label="📥 تنزيل ملف الإكسل النهائي (المطابق لشاشة أونكس برو)",
        data=buffer,
        file_name=export_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
