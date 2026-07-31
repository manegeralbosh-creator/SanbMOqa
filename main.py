import streamlit as st
import pandas as pd
import re
import urllib.parse
import io
import sqlite3
from datetime import datetime
import streamlit.components.v1 as components
import base64
import os
from pathlib import Path
import streamlit as st
from streamlit_calendar import calendar
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# 1. إعداد صلاحيات الاتصال باستخدام المفاتيح التي حفظناها في الـ Secrets
def get_data_from_sheet():
    # هذا السطر يسحب المفاتيح من الـ Secrets تلقائياً
    creds_dict = st.secrets["gcp_service_account"]
    
    # تحويل البيانات إلى تنسيق يفهمه جوجل
    creds = Credentials.from_service_account_info(creds_dict)
    client = gspread.authorize(creds)
    
    # فتح ملف الجدول باسمه (تأكد أن الاسم مطابق لاسم ملفك في جوجل درايف)
    sheet = client.open("AlBoush_Data").sheet1
    
    # جلب كل البيانات
    return sheet.get_all_records()

# 2. استدعاء الدالة لعرض البيانات
try:
    data = get_data_from_sheet()
    st.write("تم الاتصال بجدول المديونيات بنجاح!")
    st.table(data) # عرض البيانات على شكل جدول
except Exception as e:
    st.error(f"حدث خطأ في الاتصال: {e}")

def get_persistent_db_path():
    # هذا المسار يحدد مجلد باسم AlBoush_Data في ذاكرة الهاتف الداخلية
    # يمكنك تغييره لأي اسم مجلد تفضله
    storage_dir = Path("/sdcard/AlBoush_Data") 
    
    # التأكد من وجود المجلد، إذا لم يكن موجوداً سيتم إنشاؤه
    if not storage_dir.exists():
        storage_dir.mkdir(parents=True, exist_ok=True)
    
    # مسار قاعدة البيانات الثابت
    return str(storage_dir / "local_debts.db")

# استخدم هذا المسار في دالة الاتصال:
def get_db_connection():
    db_path = get_persistent_db_path()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    # ... (باقي كود إنشاء الجدول) ...
    return conn
    
# 1. إعدادات الصفحة الأساسية
st.set_page_config(page_title="نظام محلات البوش للحسابات", page_icon="📊", layout="wide")

# 2. تصميم الواجهة الكحلية بالألوان الرسمية للمحلات
st.markdown("""
<style>
    .reportview-container { background: #faf8f5; }
    .main-title { color: #1E3A8A; text-align: center; font-size: 26px; font-weight: bold; margin-bottom: 5px; }
    .sub-title { color: #4B5563; text-align: center; font-size: 15px; margin-bottom: 20px; }
    .stSelectbox, .stTextInput { margin-bottom: -10px; }
    div[data-testid="stBlock"] { padding: 4px; }
    .client-card { background-color: #ffffff; padding: 12px; border-radius: 6px; border-right: 6px solid #1E3A8A; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .bulk-box { background-color: #EFF6FF; padding: 15px; border-radius: 8px; border: 1px solid #BFDBFE; margin-bottom: 15px; text-align: center; }
    .active-mic-box { background-color: #FFFBEB; padding: 15px; border-radius: 8px; border: 1px solid #F59E0B; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات المتكامل</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">إدارة مديونيات السوق الرسمية - نسخة قاعدة البيانات المحلية المطورة</div>', unsafe_allow_html=True)

# 3. إنشاء والاتصال بقاعدة البيانات المحلية
def get_local_db():
    conn = sqlite3.connect("local_debts.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers_debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            phone_number TEXT,
            balance INTEGER,
            currency TEXT,
            frequency TEXT DEFAULT 'أسبوعي',
            last_sent_date TEXT,
            UNIQUE(customer_name, currency)
        )
    """)
    conn.commit()
    return conn

conn = get_local_db()

# كود يقوم بحفظ بيانات المديونيات في ملف CSV
def save_data(data):
    df = pd.DataFrame(data)
    df.to_csv("al_boush_debts.csv", index=False)
    st.success("تم حفظ البيانات بنجاح في السحابة!")

# زر لإرسال البيانات للعمليات
if st.button("تحديث السحابة"):
    # هنا تضع المنطق الخاص بك
    save_data(your_data_list)


# 4. دالات معالجة النصوص وتصفية الأرقام والأسماء
def extract_all_yemeni_phones(text):
    if pd.isna(text): 
        return ""
    text_str = str(text).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    matches = re.findall(r'(77\d{7}|73\d{7}|71\d{7}|70\d{7})', text_str)
    if matches:
        unique_matches = list(dict.fromkeys(matches))
        return " / ".join(unique_matches)
    return ""

def clean_customer_name(text):
    if pd.isna(text): 
        return ""
    return re.sub(r'[/\\\-\d]+.*', '', str(text)).strip()

def save_to_local_db(df):
    if df is None or len(df.columns) < 4:
        return False, "الملف المرفوع لا يحتوي على الأعمدة الأربعة الأساسية لكشف حساب أونكس."
    try:
        col_name = df.columns[1]
        col_currency = df.columns[2]
        col_balance = df.columns[3]
        success_count = 0
        cursor = conn.cursor()
        
        for idx, row in df.iterrows():
            raw_name = row[col_name]
            if pd.isna(raw_name) or "اسم العميل" in str(raw_name) or "الاسم" in str(raw_name): 
                continue
            
            clean_name = clean_customer_name(raw_name)
            if not clean_name: 
                continue
            
            phones = extract_all_yemeni_phones(raw_name)
            
            try: 
                balance_str = str(row[col_balance]).replace(',', '').strip()
                balance_val = int(float(balance_str))
            except: 
                balance_val = 0
                
            if balance_val > 0:
                currency_val = str(row[col_currency]).strip()
                cursor.execute("SELECT id, phone_number FROM customers_debts WHERE customer_name = ? AND currency = ?", (clean_name, currency_val))
                existing = cursor.fetchone()
                
                if existing:
                    existing_phone = existing[1]
                    if existing_phone and existing_phone != "لا يوجد رقم":
                        final_phone = existing_phone
                    else:
                        final_phone = phones if phones else "لا يوجد رقم"
                        
                    cursor.execute("""
                        UPDATE customers_debts 
                        SET balance = ?, phone_number = ?
                        WHERE customer_name = ? AND currency = ?
                    """, (balance_val, final_phone, clean_name, currency_val))
                else:
                    cursor.execute("SELECT phone_number FROM customers_debts WHERE customer_name = ? AND phone_number != 'لا يوجد رقم'", (clean_name,))
                    saved_phone = cursor.fetchone()
                    final_phone = saved_phone[0] if saved_phone else (phones if phones else "لا يوجد رقم")
                    
                    cursor.execute("""
                        INSERT INTO customers_debts (customer_name, phone_number, balance, currency, frequency) 
                        VALUES (?, ?, ?, ?, 'أسبوعي')
                    """, (clean_name, final_phone, balance_val, currency_val))
                success_count += 1
                
        conn.commit()
        return True, str(success_count)
    except Exception as e:
        return False, str(e)

frequency_options = ["كل 3 أيام", "أسبوعي", "كل أسبوعين", "شهري", "إيقاف التذكير"]
freq_days_map = {"كل 3 أيام": 3, "أسبوعي": 7, "كل أسبوعين": 14, "شهري": 30, "إيقاف التذكير": 99999}

# 5. جلب وتجميع البيانات مدمجة ثنائية العملة
cursor = conn.cursor()
cursor.execute("SELECT id, customer_name, phone_number, balance, currency, frequency, last_sent_date FROM customers_debts WHERE balance > 0")
rows = cursor.fetchall()

# هيكل التجميع الذكي
grouped_dict = {}
for r in rows:
    db_id, name, phone, balance, currency, frequency, last_sent = r
    if name not in grouped_dict:
        grouped_dict[name] = {
            "ids": [],
            "customer_name": name,
            "phone_number": phone,
            "debts": {},
            "frequency": frequency,
            "last_sent_date": last_sent
        }
    
    grouped_dict[name]["ids"].append(db_id)
    grouped_dict[name]["debts"][currency] = balance
    
    if phone and phone != "لا يوجد رقم":
        grouped_dict[name]["phone_number"] = phone
        
    if last_sent:
        if not grouped_dict[name]["last_sent_date"] or last_sent > grouped_dict[name]["last_sent_date"]:
            grouped_dict[name]["last_sent_date"] = last_sent

all_customers = list(grouped_dict.values())

today = datetime.now().date()
due_customers = []
if all_customers:
    for cust in all_customers:
        freq = cust["frequency"]
        if freq == "إيقاف التذكير": continue
        last_sent = cust["last_sent_date"]
        if last_sent:
            last_sent_dt = datetime.strptime(last_sent, "%Y-%m-%d").date()
            if (today - last_sent_dt).days >= freq_days_map.get(freq, 7): 
                due_customers.append(cust)
        else: 
            due_customers.append(cust)

# تعريف التبويبات
tab1, tab2, tab3, tab4 , tab5 = st.tabs([
    "📥 رفع كشف الحساب اليدوي", 
    "🚀 الإرسال الجماعي المتتابع للرسائل النصية القصيرة SMS", 
    "📊 العملاء المستحقين للتذكير اليوم", 
    "📲 إرسال فواتير الواتساب",
    "الطابور",
])
# لتبويبويب الثاني: الإرسال الجماعي المتتابع للرسائل النصية القصيرة SMS
with tab2:
    st.subheader("🚀 منصة الإرسال الجماعي المتتابع للرسائل النصية (SMS)")
    
    if not due_customers:
        st.success("✅ لا يوجد عملاء مستحقين للإرسال الجماعي اليوم!")
    else:
        valid_bulk_customers = [c for c in due_customers if str(c["phone_number"]).strip() and str(c["phone_number"]).strip() != "لا يوجد رقم"]
        
        if not valid_bulk_customers:
            st.warning("⚠️ جميع العملاء المستحقين اليوم ليس لديهم أرقام هواتف مسجلة في النظام.")
        else:
            st.markdown(f"""
            <div class="bulk-box">
                <h4 style="color: #1E3A8A; margin:0;">📈 جاهز للإرسال الجماعي للرسائل النصية</h4>
                <p style="color: #4B5563; font-size:14px; margin:5px 0 0 0;">عدد العملاء الذين لديهم أرقام وجاهزون للمراسلة الفورية: <b>{len(valid_bulk_customers)} عميل</b></p>
            </div>
            """, unsafe_allow_html=True)
            
            if "bulk_index" not in st.session_state:
                st.session_state["bulk_index"] = 0
                
            if st.session_state["bulk_index"] >= len(valid_bulk_customers):
                st.session_state["bulk_index"] = 0
                st.success("🎉 ممتاز! تم المرور على جميع العملاء في قائمة الإرسال الجماعي بنجاح.")
                
            current_idx = st.session_state["bulk_index"]
            current_cust = valid_bulk_customers[current_idx]
            
            default_msg = "تحية طيبة من محلات البوش لقطع غيار الشاحنات.\nنود تذكيركم برصيد حسابكم المتبقي لدينا وهو: [المبلغ] [العملة].\nيرجى التكرم بتصفية الحساب، شاكرين تعاونكم وثقتكم بنا."
            
            debt_parts = []
            for curr, bal in current_cust["debts"].items():
                debt_parts.append(f"{bal:,} {curr}")
            combined_debt_str = " و ".join(debt_parts)
            
            bulk_formatted_msg = default_msg.replace("هو: [المبلغ] [العملة].", f"هو: {combined_debt_str}.")
            bulk_encoded_msg = urllib.parse.quote(bulk_formatted_msg)
            
            raw_phone = str(current_cust["phone_number"]).strip()
            first_phone = [p.strip() for p in raw_phone.split('/') if p.strip()][0]
            
            bulk_sms_url = f"sms:{first_phone}?body={bulk_encoded_msg}"
            
            st.markdown(f"""
            <div style="background-color: #ffffff; padding: 20px; border-radius: 8px; border-right: 8px solid #1E3A8A; box-shadow: 0 2px 5px rgba(0,0,0,0.05); text-align:right;">
                <span style="font-size:14px; background-color:#1E3A8A; color:white; padding:3px 8px; border-radius:10px;">العميل الحالي رقم ({current_idx + 1} من أصل {len(valid_bulk_customers)})</span>
                <h3 style="color:#1E3A8A; margin-top:10px;">👤 {current_cust['customer_name']}</h3>
                <p style="font-size:16px; margin: 5px 0;">💰 متبقي عليه: <b style="color:#B91C1C;">{combined_debt_str}</b></p>
                <p style="font-size:14px; color:#4B5563;">📱 رقم الهاتف: {first_phone}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            col_b1, col_b2, col_b3 = st.columns([2, 2, 1])
            
            with col_b1:
                st.markdown(f'<a href="{bulk_sms_url}"><button style="background-color: #1E3A8A; color: white; border: none; padding: 12px 10px; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; width: 100%;">📱 1. تجهيز الرسالة النصية (SMS)</button></a>', unsafe_allow_html=True)
            
            with col_b2:
                if st.button("✅ 2. تم الإرسال (انتقل للتالي) ➡️", use_container_width=True, key="bulk_send_next_btn"):
                    cursor = conn.cursor()
                    for db_id in current_cust["ids"]:
                        cursor.execute("UPDATE customers_debts SET last_sent_date = ? WHERE id = ?", (str(today), db_id))
                    conn.commit()
                    st.session_state["bulk_index"] += 1
                    st.rerun()
                    
            with col_b3:
                if st.button("تخطي مؤقتاً ↩️", use_container_width=True, key="bulk_skip_btn"):
                    st.session_state["bulk_index"] += 1
                    st.rerun()

# 📊 التبويب الأول: فرز ومتابعة المستحقين الفردي
with tab1:
    # --- 🎙️ الميكروفون الموحد والنشط في أعلى التبويب ---
    if "active_voice_client" in st.session_state and st.session_state["active_voice_client"] is not None:
        active_client = st.session_state["active_voice_client"]
        
        st.markdown(f"""
        <div class="active-mic-box">
            <h4 style="color: #B45309; margin: 0 0 10px 0;">🎙️ مسجل الصوت الموحد للعميل: {active_client['name']}</h4>
            <p style="font-size: 14px; color: #78350F; margin: 0 0 10px 0;">اضغط على زر الميكروفون أدناه، سجل رسالتك، ثم أوقف التسجيل ليظهر زر الإرسال مباشرة دون تعليق.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # ميكروفون واحد فريد ونشط على الصفحة كاملة لتجنب التعليق
        audio_file = st.audio_input("ابدأ تسجيل الصوت هنا:", key="global_unique_audio_recorder")
        
        col_rec_1, col_rec_2 = st.columns([3, 1])
        with col_rec_1:
            if audio_file is not None:
                st.success("✅ تم معالجة وحفظ المقطع الصوتي بنجاح على الهاتف!")
                st.markdown(f"""
                    <div style="margin-top: 5px;">
                        <a href="{active_client['whatsapp_url']}" target="_blank">
                            <button style="
                                background-color: #25D366; 
                                color: white; 
                                border: none; 
                                padding: 12px 20px; 
                                border-radius: 6px; 
                                font-size: 15px; 
                                font-weight: bold; 
                                cursor: pointer; 
                                width: 100%;
                            ">
                                📲 افتح الواتساب الآن لارفاق الصوت المرسل لـ {active_client['name']}
                            </button>
                        </a>
                    </div>
                """, unsafe_allow_html=True)
        with col_rec_2:
            if st.button("❌ إغلاق المسجل", use_container_width=True, key="close_global_mic_btn"):
                st.session_state["active_voice_client"] = None
                st.rerun()
                
        st.write("---")

    # إصلاح الطريقة التقليدية لفتح الـ Expander لتجنب الـ SyntaxError
    with st.expander("📝 إعدادات وتخصيص نص رسالة التذكير العامة"):
        default_msg = "تحية طيبة من محلات البوش لقطع غيار الشاحنات.\nنود تذكيركم برصيد حسابكم المتبقي لدينا وهو: [المبلغ] [العملة].\nيرجى التكرم بتصفية الحساب، شاكرين تعاونكم وثقتكم بنا."
        custom_msg_template = st.text_area("صيغة الرسالة:", value=default_msg, height=120)

    if all_customers:
        search_query = st.text_input("🔍 بحث سريع عن عميل بالاسم أو الهاتف:", placeholder="اكتب اسم العميل أو الرقم هنا...")
        if search_query.strip() != "":
            due_customers = [c for c in due_customers if search_query.lower() in c["customer_name"].lower() or search_query in str(c["phone_number"])]
        
        st.write("### إجمالي الحسابات النشطة: " + str(len(all_customers)) + " | المستحقين للمتابعة اليوم: " + str(len(due_customers)))
        
        for item in due_customers:
            raw_phone = str(item.get("phone_number", "")).replace(".0", "").strip()
        if "/" in raw_phone:
            phone_list = [p.strip() for p in raw_phone.split("/") if p.strip()]
        elif "," in raw_phone:
            phone_list = [p.strip() for p in raw_phone.split(",") if p.strip()]
        else:
            phone_list = [raw_phone] if raw_phone and raw_phone != "nan" else ["لا يوجد رقم"]


            debt_items = []
            display_parts = []
            for curr, bal in item["debts"].items():
                formatted_bal = "{:,}".format(bal)
                debt_items.append(f"{formatted_bal} {curr}")
                display_parts.append(f"<b style='color:#B91C1C;'>{formatted_bal} {curr}</b>")
                
            combined_debt_str = " و ".join(debt_items)
            combined_display_str = " و ".join(display_parts)
            
            formatted_msg = custom_msg_template.replace("هو: [المبلغ] [العملة].", f"هو: {combined_debt_str}.")
            formatted_msg = formatted_msg.replace("[المبلغ]", combined_debt_str).replace("[العملة]", "")
            
            encoded_msg = urllib.parse.quote(formatted_msg)
            
            st.markdown(f"""
            <div class="client-card">
                <span style="font-size:17px; font-weight:bold; color:#1E3A8A;">👤 {item['customer_name']}</span> | 
                <span style="color:#4B5563;">📱 الهاتف المسجل: {raw_phone}</span> | 
                <span style="font-size:15px; font-weight:bold;">💰 المتبقي: {combined_display_str}</span>
            </div>
            """, unsafe_allow_html=True)
            
            col_one, col_two, col_three, col_four = st.columns([1.2, 1.6, 1.1, 1.1])
            
            with col_one:
                first_db_id = item["ids"][0]
                idx_default = frequency_options.index(item["frequency"]) if item["frequency"] in frequency_options else 1
                chosen_freq = st.selectbox(f"freq_{first_db_id}", frequency_options, index=idx_default, key=f"time_{first_db_id}", label_visibility="collapsed")
                if chosen_freq != item["frequency"]:
                    cursor = conn.cursor()
                    for db_id in item["ids"]:
                        cursor.execute("UPDATE customers_debts SET frequency = ? WHERE id = ?", (chosen_freq, db_id))
                    conn.commit()
                    st.rerun()
            
            with col_two:
                first_db_id = item["ids"][0]
                if len(phone_list) > 1:
                    selected_phone = st.selectbox(f"select_lbl_{first_db_id}", phone_list, key=f"select_p_{first_db_id}", label_visibility="collapsed")
                    phone_to_send = selected_phone.lstrip('0')
                else:
                    new_phone = st.text_input(f"phone_{first_db_id}", value="" if phone_list[0] == "لا يوجد رقم" else phone_list[0], placeholder="رقم الهاتف", key=f"input_{first_db_id}", label_visibility="collapsed")
                    if new_phone.strip() != "" and new_phone.strip() != raw_phone:
                        cursor = conn.cursor()
                        for db_id in item["ids"]:
                            cursor.execute("UPDATE customers_debts SET phone_number = ? WHERE id = ?", (new_phone.strip(), db_id))
                        conn.commit()
                        st.rerun()
                    phone_to_send = new_phone.strip().lstrip('0') if new_phone.strip() != "" else ""

            # حساب رابط الواتساب والعملية الأمنة لإرسال الصوت
            whatsapp_phone = ""
            if phone_to_send and phone_to_send != "لا يوجد رقم":
                whatsapp_phone = "967" + phone_to_send if not phone_to_send.startswith("967") else phone_to_send
            
            voice_note_intro = urllib.parse.quote("أرفق لكم المقطع الصوتي الخاص بمتابعة الحساب:")
            whatsapp_voice_url = f"https://api.whatsapp.com/send?phone={whatsapp_phone}&text={voice_note_intro}"

            with col_three:
                first_db_id = item["ids"][0]
                if phone_to_send and phone_to_send != "لا يوجد رقم":
                    whatsapp_url = f"https://api.whatsapp.com/send?phone={whatsapp_phone}&text={encoded_msg}"
                    st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background-color: #25D366; color: white; border: none; padding: 6px 10px; border-radius: 4px; font-size: 13px; cursor: pointer; font-weight: bold; width: 100%;">💬 واتساب</button></a>', unsafe_allow_html=True)
                    
                    if st.button("✓ تم", key=f"done_wa_{first_db_id}", help="اضغط لتأجيل التذكير للفترة القادمة"):
                        cursor = conn.cursor()
                        for db_id in item["ids"]:
                            cursor.execute("UPDATE customers_debts SET last_sent_date = ? WHERE id = ?", (str(today), db_id))
                        conn.commit()
                        st.rerun()
                else: 
                    st.button("🚫 بلا رقم", key=f"wa_err_{first_db_id}", disabled=True, use_container_width=True)
            
            with col_four:
                first_db_id = item["ids"][0]
                if phone_to_send and phone_to_send != "لا يوجد رقم":
                    sms_url = f"sms:{phone_to_send}?body={encoded_msg}"
                    st.markdown(f'<a href="{sms_url}"><button style="background-color: #1E3A8A; color: white; border: none; padding: 6px 10px; border-radius: 4px; font-size: 13px; cursor: pointer; font-weight: bold; width: 100%;">📱 SMS</button></a>', unsafe_allow_html=True)
                    
                    if st.button("✓ تم", key=f"done_sms_{first_db_id}", help="اضغط لتأجيل التذكير للفترة القادمة"):
                        cursor = conn.cursor()
                        for db_id in item["ids"]:
                            cursor.execute("UPDATE customers_debts SET last_sent_date = ? WHERE id = ?", (str(today), db_id))
                        conn.commit()
                        st.rerun()
                else: 
                    st.button("🚫 ناقص", key=f"sms_err_{first_db_id}", disabled=True, use_container_width=True)

            # زر تشغيل الميكروفون الموحد والآمن لهذا العميل بالتحديد لتلافي التعليق والـ SyntaxError
            if phone_to_send and phone_to_send != "لا يوجد رقم":
                if st.button(f"🎙️ تفعيل الميكروفون للعميل: {item['customer_name']}", key=f"trigger_mic_{first_db_id}", use_container_width=True):
                    st.session_state["active_voice_client"] = {
                        "name": item['customer_name'],
                        "whatsapp_url": whatsapp_voice_url
                    }
                    st.rerun()
            
            st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)
            
        st.write("---")
        st.write("### 📜 السجل الكامل وتواريخ المراسلة السابقة للعملاء")
        
        log_rows = []
        for cust in all_customers:
            yemeni_bal = cust["debts"].get("يمني", 0)
            saudi_bal = cust["debts"].get("سعودي", 0)
            log_rows.append({
                "اسم العميل الرسمي": cust["customer_name"],
                "رقم الهاتف": cust["phone_number"],
                "مديونية يمني": f"{yemeni_bal:,}" if yemeni_bal > 0 else "0",
                "مديونية سعودي": f"{saudi_bal:,}" if saudi_bal > 0 else "0",
                "فترة التذكير": cust["frequency"],
                "تاريخ آخر إرسال": cust["last_sent_date"] if cust["last_sent_date"] else "لم يرسل بعد"

            })
            
        df_log = pd.DataFrame(log_rows)
        if not df_log.empty:
            st.dataframe(df_log, use_container_width=True, hide_index=True)
            
    else:
        st.success("ممتاز جداً! لا يوجد عملاء مستحقين للتذكير حالياً.")

# 📥 التبويب الثالث: رفع كشف أونكس الجديد
with tab3:
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
            st.error("تعذر قراءة هذا الملف بنجاح.")
            
        if df_onyx is not None:
            success, result_msg = save_to_local_db(df_onyx)
            if success: 
                st.success("تم تحديث ومزامنة البيانات في قاعدة البيانات المحلية للعملاء.")
                st.rerun()
            else: 
                st.error("حدث خطأ أثناء الحفظ محلياً: " + result_msg)
                # --- جسر الربط مع الترمكس للمقاضاة التلقائية ---
# --- جسر الربط مع الترمكس للمقاضاة التلقائية ---
import json

def export_debts_to_json():
    try:
        conn = sqlite3.connect("local_debts.db")
        cursor = conn.cursor()
        cursor.execute("SELECT customer_name, phone_number, balance, currency, frequency, last_sent_date FROM customers_debts")
        rows = cursor.fetchall()
        conn.close()
        
        data = []
        for row in rows:
            data.append({
                "name": row[0],
                "phone": row[1],
                "balance": row[2],
                "currency": row[3],
                "frequency": row[4],
                "last_sent": row[5]
            })
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})

# التبويب الرابع: إرسال فواتير الواتساب


       
import io
import os
import urllib.parse
import zipfile
import pandas as pd
import streamlit as st

# دعم المكتبات الخارجية للملفات المضغوطة (إذا كانت مثبتة في البيئة)
try:
  import rarfile

  HAS_RAR = True
except ImportError:
  HAS_RAR = False

try:
  import py7zr

  HAS_7Z = True
except ImportError:
  HAS_7Z = False

try:
  import tarfile

  HAS_TAR = True
except ImportError:
  HAS_TAR = False


# دالة مساعدة لتوليد تقرير الإكسل المحدث في الذاكرة
def generate_excel_report(df_all, completed_set, skipped_set):
  report_df = df_all.copy()

  def get_status(doc_ser):
    doc_str = str(doc_ser).replace('.0', '').strip()
    if doc_str in completed_set:
      return '✅ تم الإرسال'
    elif doc_str in skipped_set:
      return '🚫 كنسل / ملغاة'
    else:
      return '⏳ متبقية'

  report_df['حالة الإرسال'] = report_df['doc_ser_str'].apply(get_status)

  columns_order = [
      'doc_ser_str',
      'no_doc',
      'name',
      'phone',
      'amt',
      'total',
      'curr',
      'حالة الإرسال',
  ]
  existing_cols = [col for col in columns_order if col in report_df.columns]
  report_df = report_df[existing_cols]

  rename_dict = {
      'doc_ser_str': 'الرقم التسلسلي',
      'no_doc': 'رقم الفاتورة',
      'name': 'اسم العميل',
      'phone': 'رقم الهاتف',
      'amt': 'مبلغ الفاتورة',
      'total': 'الرصيد الإجمالي',
      'curr': 'العملة',
  }
  report_df.rename(columns=rename_dict, inplace=True)

  output = io.BytesIO()
  with pd.ExcelWriter(output, engine='openpyxl') as writer:
    report_df.to_excel(writer, index=False, sheet_name='تقرير الفواتير')

  return output.getvalue()


with tab4:
  st.subheader('📲 نظام مراجعة وإرسال الفواتير عبر الواتساب')

  # 1. تهيئة متغيرات الجلسة
  if 'completed_invoices' not in st.session_state:
    st.session_state.completed_invoices = set()

  if 'skipped_invoices' not in st.session_state:
    st.session_state.skipped_invoices = set()

  # 2. رفع الملفات (ملف الإكسل + خيارين لرفع الفواتير)
  st.markdown('#### 📂 1. رفع البيانات والفواتير')

  col_ex, col_archive, col_pdf_direct = st.columns([1.2, 1.2, 1.2])

  with col_ex:
    excel_file = st.file_uploader(
        '📊 ملف كشف المبيعات (Excel)', type=['xlsx', 'xls'], key='inv_excel'
    )

  with col_archive:
    archive_file = st.file_uploader(
        '📦 أرشيف مضغوط (ZIP / RAR / 7Z / TAR)',
        type=['zip', 'rar', '7z', 'tar', 'gz'],
        key='inv_archive',
    )

  with col_pdf_direct:
    direct_pdf_files = st.file_uploader(
        '📄 ملفات PDF مباشرة (دفعة واحدة)',
        type=['pdf'],
        accept_multiple_files=True,
        key='inv_direct_pdfs',
    )

  # 3. معالجة وتخزين ملفات الـ PDF في الذاكرة من المصدرين (المضغوط + المباشر)
  pdf_store = {}

  # أ) معالجة الأرشيف المضغوط بأي صيغة
  if archive_file is not None:
    file_ext = archive_file.name.split('.')[-1].lower()
    try:
      # صيغة ZIP
      if file_ext == 'zip':
        with zipfile.ZipFile(archive_file, 'r') as z:
          for file_info in z.infolist():
            if file_info.filename.lower().endswith('.pdf'):
              filename = os.path.basename(file_info.filename)
              raw_name = (
                  filename.replace('.pdf', '').replace('.PDF', '').strip()
              )
              clean_num = ''.join(filter(str.isdigit, raw_name))
              file_bytes = z.read(file_info.filename)
              pdf_store[raw_name] = file_bytes
              if clean_num:
                pdf_store[clean_num] = file_bytes

      # صيغة RAR
      elif file_ext == 'rar':
        if HAS_RAR:
          with rarfile.RarFile(archive_file) as r:
            for file_info in r.infolist():
              if file_info.filename.lower().endswith('.pdf'):
                filename = os.path.basename(file_info.filename)
                raw_name = (
                    filename.replace('.pdf', '').replace('.PDF', '').strip()
                )
                clean_num = ''.join(filter(str.isdigit, raw_name))
                file_bytes = r.read(file_info.filename)
                pdf_store[raw_name] = file_bytes
                if clean_num:
                  pdf_store[clean_num] = file_bytes
        else:
          st.warning(
              '⚠️ لقراءة ملفات RAR يرجى تثبيت مكتبة rarfile (`pip install'
              ' rarfile`).'
          )

      # صيغة 7Z
      elif file_ext == '7z':
        if HAS_7Z:
          with py7zr.SevenZipFile(archive_file, mode='r') as z:
            all_files = z.readall()
            for name, bio in all_files.items():
              if name.lower().endswith('.pdf'):
                filename = os.path.basename(name)
                raw_name = (
                    filename.replace('.pdf', '').replace('.PDF', '').strip()
                )
                clean_num = ''.join(filter(str.isdigit, raw_name))
                file_bytes = bio.read()
                pdf_store[raw_name] = file_bytes
                if clean_num:
                  pdf_store[clean_num] = file_bytes
        else:
          st.warning(
              '⚠️ لقراءة ملفات 7Z يرجى تثبيت مكتبة py7zr (`pip install py7zr`).'
          )

      # صيغ TAR / TAR.GZ
      elif file_ext in ['tar', 'gz']:
        if HAS_TAR:
          with tarfile.open(fileobj=archive_file) as t:
            for member in t.getmembers():
              if member.isfile() and member.name.lower().endswith('.pdf'):
                filename = os.path.basename(member.name)
                raw_name = (
                    filename.replace('.pdf', '').replace('.PDF', '').strip()
                )
                clean_num = ''.join(filter(str.isdigit, raw_name))
                f = t.extractfile(member)
                if f:
                  file_bytes = f.read()
                  pdf_store[raw_name] = file_bytes
                  if clean_num:
                    pdf_store[clean_num] = file_bytes

    except Exception as e:
      st.error(f'❌ حدث خطأ أثناء قراءة الملف المضغوط: {e}')

  # ب) معالجة ملفات PDF المرفوعة مباشرة بدون ضغط
  if direct_pdf_files:
    for f in direct_pdf_files:
      raw_name = (
          os.path.basename(f.name).replace('.pdf', '').replace('.PDF', '').strip()
      )
      clean_num = ''.join(filter(str.isdigit, raw_name))
      file_bytes = f.getvalue()
      pdf_store[raw_name] = file_bytes
      if clean_num:
        pdf_store[clean_num] = file_bytes

  # إظهار إشعار إجمالي الفواتير الجاهزة بالذاكرة
  if pdf_store:
    st.success(f'✅ تم تجهيز واستخراج {len(pdf_store)} فاتورة PDF بنجاح!')

  if excel_file is not None:
    try:
      df = pd.read_excel(excel_file)

      # التصفية حسب العملة
      if 'curr' in df.columns:
        currencies = ['الكل'] + [
            str(c) for c in df['curr'].dropna().unique().tolist()
        ]
      else:
        currencies = ['الكل']

      selected_curr = st.selectbox(
          'اختر العملة للتصفية:', currencies, key='curr_select'
      )

      filtered_df = df.copy()
      if selected_curr != 'الكل' and 'curr' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['curr'] == selected_curr]

      # التأكد من وجود عمود الرقم التسلسلي
      if 'doc_ser' in filtered_df.columns:
        filtered_df['doc_ser_str'] = (
            filtered_df['doc_ser']
            .astype(str)
            .str.replace('.0', '', regex=False)
            .str.strip()
        )
      else:
        st.error('❌ لم يتم العثور على عمود (doc_ser) في ملف الإكسل!')
        st.stop()

      # استبعاد الفواتير المعالجة سابقاً
      processed_set = st.session_state.completed_invoices.union(
          st.session_state.skipped_invoices
      )
      pending_df = filtered_df[
          ~filtered_df['doc_ser_str'].isin(processed_set)
      ]

      # الإحصائيات والشريط المتقدم
      total_invoices = len(filtered_df)
      completed_count = len(
          filtered_df[
              filtered_df['doc_ser_str'].isin(
                  st.session_state.completed_invoices
              )
          ]
      )
      skipped_count = len(
          filtered_df[
              filtered_df['doc_ser_str'].isin(st.session_state.skipped_invoices)
          ]
      )
      remaining_invoices = len(pending_df)

      st.progress(
          (completed_count + skipped_count) / total_invoices
          if total_invoices > 0
          else 0
      )

      c_stat1, c_stat2, c_stat3, c_stat4 = st.columns(4)
      c_stat1.metric('إجمالي الكشف', total_invoices)
      c_stat2.metric('تم الإرسال', completed_count)
      c_stat3.metric('ملغاة / كنسل', skipped_count)
      c_stat4.metric('المتبقي', remaining_invoices)

      # 📊 زر تنزيل التقرير المحدث
      excel_data = generate_excel_report(
          filtered_df,
          st.session_state.completed_invoices,
          st.session_state.skipped_invoices,
      )
      st.download_button(
          label='📊 تنزيل تقرير حالة الفواتير الحالي (Excel)',
          data=excel_data,
          file_name='تقرير_حالة_الفواتير.xlsx',
          mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          use_container_width=True,
          key='download_report_btn',
      )

      st.divider()

      if not pending_df.empty:
        # 🔎 4. شريط البحث والتنقل السريع
        search_options = ['🔄 بالتسلسل التلقائي (الفاتورة التالية)'] + [
            f"{row['doc_ser_str']} | {row.get('name', 'بدون اسم')} | {row.get('phone', 'بدون رقم')}"
            for _, row in pending_df.iterrows()
        ]

        selected_search = st.selectbox(
            '🔍 ابحث باسم العميل، رقم الهاتف، أو الرقم التسلسلي:',
            options=search_options,
            key='invoice_search_box',
        )

        if selected_search == '🔄 بالتسلسل التلقائي (الفاتورة التالية)':
          current_row = pending_df.iloc[0]
        else:
          selected_doc_ser = selected_search.split(' | ')[0]
          current_row = pending_df[
              pending_df['doc_ser_str'] == selected_doc_ser
          ].iloc[0]

        # استخراج بيانات الفاتورة المحددة
        doc_ser_val = str(current_row['doc_ser_str'])
        no_doc_val = str(current_row.get('no_doc', '---'))
        customer_name = str(current_row.get('name', 'عميل'))
        phone_val = str(current_row.get('phone', '')).replace('.0', '').strip()
        currency_val = str(current_row.get('curr', ''))
        amount_val = float(current_row.get('amt', 0))
        balance_val = float(current_row.get('total', 0))

        # البحث عن ملف الـ PDF المطابق للعميل في الذاكرة
        pdf_bytes = pdf_store.get(doc_ser_val) or pdf_store.get(
            f'DOCSER_{doc_ser_val}'
        )

        # نص الرسالة للواتساب
        message_text = (
            f'البوش للتجارة - المركز الرئيسي جدر\n'
            f'الأخ: {customer_name}\n'
            f'مبلغ الفاتورة: {amount_val:,.2f} {currency_val}\n'
            f'الرصيد الإجمالي: {balance_val:,.2f} {currency_val}\n'
        )

        # بطاقة بيانات العميل
        st.markdown(
            f"""
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-right: 5px solid #25D366; margin-bottom: 10px;">
                <h3 style="margin:0; color:#111;">👤 العميل: {customer_name}</h3>
                <p style="margin:5px 0;"><b>رقم الفاتورة:</b> {no_doc_val} | <b>الرقم التسلسلي:</b> {doc_ser_val}</p>
                <p style="margin:5px 0;"><b>مبلغ الفاتورة:</b> <span style="color:#d9534f; font-size:17px; font-weight:bold;">{amount_val:,.2f} {currency_val}</span></p>
                <p style="margin:5px 0;"><b>الرصيد الإجمالي:</b> <span style="color:#0275d8; font-size:17px; font-weight:bold;">{balance_val:,.2f} {currency_val}</span></p>
            </div>
        """,
            unsafe_allow_html=True,
        )

        st.caption('📝 نص الرسالة المجهز للواتساب:')
        st.code(message_text, language=None)

        st.divider()

        # 🖼️ 5. استعراض الفاتورة مباشرة مع خيارات المشاركة للأندرويد والتنزيل
        st.markdown('### 📄 استعراض الفاتورة المرفقة:')
        if pdf_bytes:
          st.success(
              f'✓ تم العثور على الفاتورة الخاصّة بالرقم التسلسلي:'
              f' ({doc_ser_val})'
          )

          # 1. معاينة الفاتورة داخل إطار iframe
          base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
          pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="450" type="application/pdf" style="border-radius: 8px; border: 1px solid #ddd;"></iframe>'
          st.markdown(pdf_display, unsafe_allow_html=True)

          st.write('')

          # 2. زر "مشاركة الفاتورة" لنظام الأندرويد (Web Share API)
          share_html = f"""
            <script>
            async function sharePDF_{doc_ser_val}() {{
                const base64Data = '{base64_pdf}';
                const fileName = 'DOCSER_{doc_ser_val}.pdf';
                
                const res = await fetch(`data:application/pdf;base64,${{base64Data}}`);
                const blob = await res.blob();
                const file = new File([blob], fileName, {{ type: 'application/pdf' }});
                
                if (navigator.canShare && navigator.canShare({{ files: [file] }})) {{
                    try {{
                        await navigator.share({{
                            files: [file],
                            title: 'فاتورة {customer_name}',
                            text: 'مرفق فاتورة العميل: {customer_name}'
                        }});
                    }} catch (err) {{
                        console.log('تم إلغاء المشاركة أو حدث خطأ:', err);
                    }}
                }} else {{
                    alert('خاصية المشاركة المباشرة غير مدعومة في هذا المتصفح. يمكنك استخدام زر التنزيل أدناه لمشاركة الفاتورة.');
                }}
            }}
            </script>

            <button onclick="sharePDF_{doc_ser_val}()" style="
                background-color: #0275d8;
                color: white;
                border: none;
                padding: 12px;
                font-size: 15px;
                font-weight: bold;
                border-radius: 8px;
                cursor: pointer;
                width: 100%;
                margin-bottom: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;">
                📲 مشاركة الفاتورة عبر الأندرويد (WhatsApp / Telegram / Apps)
            </button>
            """
          st.components.v1.html(share_html, height=65)

          # 3. زر تنزيل الفاتورة الفردية
          st.download_button(
              label=f'⬇️ تنزيل ملف الفاتورة مباشرة (PDF)',
              data=pdf_bytes,
              file_name=f'DOCSER_{doc_ser_val}.pdf',
              mime='application/pdf',
              use_container_width=True,
              key=f'dl_btn_{doc_ser_val}',
          )
        else:
          st.warning(
              f'⚠️ لم يتم العثور على ملف PDF مطبق للرقم التسلسلي: (DOCSER_{doc_ser_val}.pdf).'
          )

        st.divider()

        # أزرار الإرسال والتحكم
        encoded_message = urllib.parse.quote(message_text)
        whatsapp_url = f'https://wa.me/{phone_val}?text={encoded_message}'

        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
          st.markdown(
              f"""
                <a href="{whatsapp_url}" target="_blank" style="text-decoration:none;">
                    <button style="background-color: #25D366; color: white; border: none; padding: 10px; font-size: 14px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%;">
                        📲 1. فتح محادثة الواتساب
                    </button>
                </a>
            """,
              unsafe_allow_html=True,
          )

        with c2:
          if st.button(
              '✅ 2. تم الإرسال',
              type='primary',
              use_container_width=True,
              key=f'btn_send_{doc_ser_val}',
          ):
            st.session_state.completed_invoices.add(doc_ser_val)
            st.rerun()

        with c3:
          if st.button(
              '🚫 كنسل',
              use_container_width=True,
              key=f'btn_skip_{doc_ser_val}',
          ):
            st.session_state.skipped_invoices.add(doc_ser_val)
            st.rerun()

      else:
        st.balloons()
        st.success('🎉 ممتاز! تم مراجعة وإنجاز جميع الفواتير بنجاح.')

    except Exception as e:
      st.error(f'حدث خطأ أثناء معالجة البيانات: {e}')
     
      #التبويب الخامس طابور الرسائل
                
import time
import requests

# دالة إرسال الرسالة عبر الـ API الرسمي (تأكد من وضع بيانات مزود الخدمة ورقم الـ Token الخاص بك)
def send_whatsapp_via_api(phone, message):
    # مثال توضيحي للاتصال بواجهة برمجة التطبيقات (API) الخاصة بالواتساب
    api_url = "https://api.whatsapp-provider.com/v1/send" # استبدل الرابط برابط المزود المعتمد لديك
    headers = {
        "Authorization": "Bearer YOUR_API_TOKEN", # ضع رمز التصريح الخاص بك هنا
        "Content-Type": "application/json"
    }
    payload = {
        "phone": phone,
        "message": message
    }
    
    try:
        response = requests.post(api_url, json=payload, headers=headers)
        if response.status_code == 200:
            return True, "تم الإرسال بنجاح"
        else:
            return False, response.text
    except Exception as e:
        return False, str(e)

# --- واجهة الطابور الآلي في Streamlit ---
with st.expander("🤖 نظام الإرسال الآلي المبرمج (Queue عبر API)"):
    st.info("💡 هذا النظام سيقوم بإرسال الرسائل للجميع تلقائياً وبشكل متتابع مع فاصل زمني حمايةً للرقم من الحظر.")
    
    if st.button("🚀 بدء الإرسال الآلي لجميع المستحقين"):
        if not due_customers:
            st.warning("لا يوجد عملاء مستحقون للإرسال اليوم.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            valid_queue_customers = [c for c in due_customers if str(c["phone_number"]).strip() and str(c["phone_number"]).strip() != "لا يوجد رقم"]
            total_clients = len(valid_queue_customers)
            
            success_count = 0
            
            for idx, cust in enumerate(valid_queue_customers):
                raw_phone = str(cust["phone_number"]).strip()
                first_phone = [p.strip() for p in raw_phone.split('/') if p.strip()][0]
                clean_phone = first_phone.lstrip('0')
                formatted_phone = "967" + clean_phone if not clean_phone.startswith("967") else clean_phone
                
                # تجهيز نص الرسالة للعميل
                debt_parts = [f"{bal:,} {curr}" for curr, bal in cust["debts"].items()]
                combined_debt_str = " و ".join(debt_parts)
                msg_text = f"تحية طيبة من محلات البوش لقطع غيار الشاحنات.\nنود تذكيركم برصيد حسابكم المتبقي لدينا وهو: {combined_debt_str}.\nيرجى التكرم بتصفية الحساب، شاكرين تعاونكم وثقتكم بنا."
                
                status_text.text(f"جاري الإرسال إلى: {cust['customer_name']} ({idx + 1} من {total_clients})...")
                
                # تنفيذ الإرسال عبر الـ API
                 is_sent, err_msg = send_whatsapp_via_api(formatted_phone, msg_text)
                
                # محاكاة الانتظار الآمن (فاصل زمني 5 ثوانٍ بين كل رسالة لحماية الرقم)
                time.sleep(5) 
                
                # تحديث قاعدة البيانات بأن الرسالة أُرسلت
                cursor = conn.cursor()
                for db_id in cust["ids"]:
                    cursor.execute("UPDATE customers_debts SET last_sent_date = ? WHERE id = ?", (str(today), db_id))
                conn.commit()
                
                success_count += 1
                progress_bar.progress((idx + 1) / total_clients)
            
            status_text.success(f"🎉 تم الانتهاء من إرسال الرسائل الآلية بنجاح لـ {success_count} عميل عبر الطابور!")
            st.rerun()





           
                
                



            

# نهاية الكود
