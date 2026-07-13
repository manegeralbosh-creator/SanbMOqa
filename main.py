import streamlit as st
import pandas as pd
import re
import urllib.parse
import io
import sqlite3
from datetime import datetime

# إعدادات الصفحة بطابع رسمي مريح لشاشات الجوال والكمبيوتر
st.set_page_config(page_title="نظام محلات البوش للحسابات", page_icon="📊", layout="wide")

# تصميم الواجهة بالألوان الرسمية للمحلات (الكحلي والأبيض)
st.markdown("""
    <style>
    .reportview-container { background: #faf8f5; }
    .main-title { color: #1E3A8A; text-align: center; font-size: 26px; font-weight: bold; margin-bottom: 5px; }
    .sub-title { color: #4B5563; text-align: center; font-size: 15px; margin-bottom: 20px; }
    .stSelectbox, .stTextInput { margin-bottom: -10px; }
    div[data-testid="stBlock"] { padding: 4px; }
    .client-card { background-color: #ffffff; padding: 12px; border-radius: 6px; border-right: 6px solid #1E3A8A; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات المتكامل</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">إدارة مديونيات السوق الرسمية - نسخة قاعدة البيانات المحلية المطورة</div>', unsafe_allow_html=True)

# 🛠️ إنشاء والاتصال بقاعدة البيانات المحلية داخل الكمبيوتر
def get_local_db():
    conn = sqlite3.connect("local_debts.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers_debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT UNIQUE,
            phone_number TEXT,
            balance INTEGER,
            currency TEXT,
            frequency TEXT DEFAULT 'أسبوعي',
            last_sent_date TEXT
        )
    """)
    conn.commit()
    return conn

conn = get_local_db()

# دالة مطورة لاستخراج "جميع" أرقام الهواتف اليمنية الموجودة في النص (77, 73, 71, 70) والربط بينها بـ " / "
def extract_all_yemeni_phones(text):
    if pd.isna(text): return ""
    text_str = str(text).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    matches = re.findall(r'(77\d{7}|73\d{7}|71\d{7}|70\d{7})', text_str)
    if matches:
        unique_matches = list(dict.fromkeys(matches))
        return " / ".join(unique_matches)
    return ""

# دالة تنظيف اسم العميل من الرموز والتواريخ المستخرجة من أونكس
def clean_customer_name(text):
    if pd.isna(text): return ""
    return re.sub(r'[/\\\-\d]+.*', '', str(text)).strip()

# دالة تحديث ومزامنة الحسابات في القاعدة المحلية
def save_to_local_db(df):
    if df is None or len(df.columns) < 4:
        return False, "الملف المرفوع لا يحتوي على الأعمدة الأربعة الأساسية لكشف حساب أونكس."
    try:
        col_name, col_currency, col_balance = df.columns[1], df.columns[2], df.columns[3]
        success_count = 0
        cursor = conn.cursor()
        
        for idx, row in df.iterrows():
            raw_name = row[col_name]
            if pd.isna(raw_name) or "اسم العميل" in str(raw_name) or "الاسم" in str(raw_name): continue
            
            clean_name = clean_customer_name(raw_name)
            if not clean_name: continue
            
            phones = extract_all_yemeni_phones(raw_name)
            
            try: 
                balance_str = str(row[col_balance]).replace(',', '').strip()
                balance_val = int(float(balance_str))
            except: balance_val = 0
            
            if balance_val > 0:
                cursor.execute("SELECT id, phone_number FROM customers_debts WHERE customer_name = ?", (clean_name,))
                existing = cursor.fetchone()
                
                if existing:
                    existing_phone = existing[1]
                    final_phone = existing_phone if existing_phone and existing_phone != "لا يوجد رقم" else (phones if phones else "لا يوجد رقم")
                    cursor.execute("""
                        UPDATE customers_debts 
                        SET balance = ?, currency = ?, phone_number = ?
                        WHERE customer_name = ?
                    """, (balance_val, str(row[col_currency]).strip(), final_phone, clean_name))
                else:
                    cursor.execute("""
                        INSERT INTO customers_debts (customer_name, phone_number, balance, currency, frequency) 
                        VALUES (?, ?, ?, ?, 'أسبوعي')
                    """, (clean_name, phones if phones else "لا يوجد رقم", balance_val, str(row[col_currency]).strip()))
                success_count += 1
                
        conn.commit()
        # تم فصل النصوص العربية لتجنب مشاكل تشفير المنصة المسببة للشاشات البيضاء
        return True, str(success_count)
    except Exception as e:
        return False, str(e)

# خيارات فترات المتابعة والتذكير اليومي
frequency_options = ["كل 3 أيام", "أسبوعي", "كل أسبوعين", "شهري", "إيقاف التذكير"]
freq_days_map = {"كل 3 أيام": 3, "أسبوعي": 7, "كل أسبوعين": 14, "شهري": 30, "إيقاف التذكير": 99999}

# إنشاء التبويبات للشاشة الرئيسية
tab1, tab2 = st.tabs(["📊 العملاء المستحقين للتذكير اليوم", "📥 رفع وتحديث كشف الحساب الإكسل"])

# 📥 التبويب الثاني: رفع وتحديث كشف الحساب الإكسل
with tab2:
    st.subheader("📥 رفع كشف الحسابات اليدوي")
    st.info("💡 ملاحظة هامة: لتفادي أي أخطاء في بنية الملف، يرجى فتح كشف الحساب المستخرج من أونكس على الإكسل أولاً، ثم عمل (حفظ باسم - Save As) واختيار الصيغة الحديثة Excel Workbook (*.xlsx) ثم رفعه هنا.")
    
    uploaded_file = st.file_uploader("اختر ملف الإكسل المحدث للكشف", type=["xlsx", "xls", "csv"])
    
    if uploaded_file is not None:
        df_onyx = None
        file_bytes = uploaded_file.read()
        try:
            if uploaded_file.name.endswith('.csv'): 
                df_onyx = pd.read_csv(io.BytesIO(file_bytes))
            else:
                try: df_onyx = pd.read_excel(io.BytesIO(file_bytes))
                except: df_onyx = pd.read_excel(io.BytesIO(file_bytes), engine='xlrd')
        except Exception as read_err: 
            st.error("تعذر قراءة هذا الملف")
            
        if df_onyx is not None:
            success, result_msg = save_to_local_db(df_onyx)
            if success: 
                st.success("تم تحديث ومزامنة " + result_msg + " عميل بنجاح في قاعدة البيانات المحلية")
            else: 
                st.error("حدث خطأ أثناء الحفظ محلياً: " + result_msg)

# 📊 التبويب الأول: شاشة العرض والإرسال بالجوال
with tab1:
    # إعدادات وتخصيص نص رسالة التذكير
    with st.expander("📝 إعدادات وتخصيص نص رسالة التذكير"):
        default_msg = "تحية طيبة من محلات البوش لقطع غيار الشاحنات.\nنود تذكيركم برصيد حسابكم المتبقي لدينا وهو: [المبلغ] [العملة].\nيرجى التكرم بتصفية الحساب، شاكرين تعاونكم وثقتكم بنا."
        custom_msg_template = st.text_area("صيغة الرسالة:", value=default_msg, height=120)

    # جلب البيانات من القاعدة المحلية
    cursor = conn.cursor()
    cursor.execute("SELECT id, customer_name, phone_number, balance, currency, frequency, last_sent_date FROM customers_debts WHERE balance > 0")
    rows = cursor.fetchall()
    all_customers = [{"id": r[0], "customer_name": r[1], "phone_number": r[2], "balance": r[3], "currency": r[4], "frequency": r[5], "last_sent_date": r[6]} for r in rows]
    
    if all_customers:
        today = datetime.now().date()
        due_customers = []
        
        for cust in all_customers:
            freq = cust["frequency"]
            if freq == "إيقاف التذكير": continue
            last_sent = cust["last_sent_date"]
            if last_sent:
                last_sent_dt = datetime.strptime(last_sent, "%Y-%m-%d").date()
                if (today - last_sent_dt).days >= freq_days_map.get(freq, 7): due_customers.append(cust)
            else: due_customers.append(cust)
        
        # خانة البحث السريع
        search_query = st.text_input("🔍 بحث سريع عن عميل بالاسم أو الهاتف:", placeholder="اكتب اسم العميل أو الرقم هنا...")
        if search_query.strip() != "":
            due_customers = [c for c in due_customers if search_query.lower() in c["customer_name"].lower() or search_query in str(c["phone_number"])]
        
        st.write("### إجمالي الحسابات: " + str(len(all_customers)) + " | المستحقين للمتابعة اليوم: " + str(len(due_customers)))
        
        # عرض كروت العملاء
        for item in due_customers:
            raw_phone = str(item["phone_number"]).strip()
            
            # معالجة الأرقام المتعددة وتجهيز القائمة
            phone_list = [p.strip() for p in raw_phone.split('/') if p.strip()] if "/" in raw_phone else [raw_phone]
            if not phone_list or phone_list == ["لا يوجد رقم"]:
                phone_list = ["لا يوجد رقم"]

            # صياغة الرسالة والتنظيف الآمن من أخطاء التشكيل والمحاذاة
            formatted_balance = "{:,}".format(item['balance'])
            formatted_msg = custom_msg_template.replace("[المبلغ]", formatted_balance).replace("[العملة]", item['currency'])
            encoded_msg = urllib.parse.quote(formatted_msg)
            
            st.markdown(f"""
            <div class="client-card">
                <span style="font-size:17px; font-weight:bold; color:#1E3A8A;">👤 {item['customer_name']}</span> | 
                <span style="color:#4B5563;">📱 الهاتف المسجل: {raw_phone}</span> | 
                <span style="font-size:15px; font-weight:bold; color:#B91C1C;">💰 المتبقي: {formatted_balance} {item['currency']}</span>
            </div>
            """, unsafe_allow_html=True)
            
            col_one, col_two, col_three, col_four = st.columns([1.2, 1.6, 1.1, 1.1])
            
            with col_one:
                chosen_freq = st.selectbox(f"freq_{item['id']}", frequency_options, index=frequency_options.index(item["frequency"]) if item["frequency"] in frequency_options else 1, key=f"time_{item['id']}", label_visibility="collapsed")
                if chosen_freq != item["frequency"]:
                    cursor.execute("UPDATE customers_debts SET frequency = ? WHERE id = ?", (chosen_freq, item["id"]))
                    conn.commit()
                    st.rerun()
            
            with col_two:
                if len(phone_list) > 1:
                    selected_phone = st.selectbox(f"select_lbl_{item['id']}", phone_list, key=f"select_p_{item['id']}", label_visibility="collapsed")
                    phone_to_send = selected_phone.lstrip('0')
                else:
                    new_phone = st.text_input(f"phone_{item['id']}", value="" if phone_list[0] == "لا يوجد رقم" else phone_list[0], placeholder="رقم الهاتف", key=f"input_{item['id']}", label_visibility="collapsed")
                    if new_phone.strip() != "" and new_phone.strip() != raw_phone:
                        cursor.execute("UPDATE customers_debts SET phone_number = ? WHERE id = ?", (new_phone.strip(), item["id"]))
                        conn.commit()
                        st.rerun()
                    phone_to_send = new_phone.strip().lstrip('0') if new_phone.strip() != "" else ""

            # معالجة روابط الإرسال الآمنة
            with col_three:
                if phone_to_send and phone_to_send != "لا يوجد رقم":
                    whatsapp_phone = "967" + phone_to_send if not phone_to_send.startswith("967") else phone_to_send
                    whatsapp_url = f"https://api.whatsapp.com/send?phone={whatsapp_phone}&text={encoded_msg}"
                    st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background-color: #25D366; color: white; border: none; padding: 6px 10px; border-radius: 4px; font-size: 13px; cursor: pointer; font-weight: bold; width: 100%;">💬 واتساب</button></a>', unsafe_allow_html=True)
                    
                    if st.button("✓ تم", key=f"done_wa_{item['id']}", help="اضغط لتأجيل التذكير للفترة القادمة"):
                        cursor.execute("UPDATE customers_debts SET last_sent_date = ? WHERE id = ?", (str(today), item["id"]))
                        conn.commit()
                        st.rerun()
                else: 
                    st.button("🚫 بلا رقم", key=f"wa_err_{item['id']}", disabled=True, use_container_width=True)
            
            with col_four:
                if phone_to_send and phone_to_send != "لا يوجد رقم":
                    sms_url = f"sms:{phone_to_send}?body={encoded_msg}"
                    st.markdown(f'<a href="{sms_url}"><button style="background-color: #1E3A8A; color: white; border: none; padding: 6px 10px; border-radius: 4px; font-size: 13px; cursor: pointer; font-weight: bold; width: 100%;">📱 SMS</button></a>', unsafe_allow_html=True)
                    
                    if st.button("✓ تم", key=f"done_sms_{item['id']}", help="اضغط لتأجيل التذكير للفترة القادمة"):
                        cursor.execute("UPDATE customers_debts SET last_sent_date = ? WHERE id = ?", (str(today), item["id"]))
                        conn.commit()
                        st.rerun()
                else: 
                    st.button("🚫 ناقص", key=f"sms_err_{item['id']}", disabled=True, use_container_width=True)
            
            st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)
            
        # السجل الكامل وتواريخ المراسلة السابقة للعملاء
        st.write("---")
        st.write("### 📜 السجل الكامل وتواريخ المراسلة السابقة للعملاء")
        df_log = pd.DataFrame(all_customers)
        if not df_log.empty:
            df_log.columns = ["الرقم المعرف", "اسم العميل الرسمي", "رقم الهاتف", "المديونية المتبقية", "العملة", "فترة التذكير", "تاريخ آخر إرسال"]
            st.dataframe(df_log[["اسم العميل الرسمي", "رقم الهاتف", "المديونية المتبقية", "العملة", "فترة التذكير", "تاريخ آخر إرسال"]], use_container_width=True, hide_index=True)
            
    else:
        st.success("ممتاز جداً! لا يوجد عملاء مستحقين للتذكير حالياً.")
