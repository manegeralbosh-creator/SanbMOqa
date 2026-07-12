import streamlit as st
import pandas as pd
import re
import urllib.parse
import io
from datetime import datetime
from supabase import create_client, Client

# 🔑 تم وضع رابط مشروعك هنا، ضع مفتاح anon public KEY الخاص بك في السطر السفلي
SUPABASE_URL = "https://wtavxyfknypaintaggeq.supabase.co"
SUPABASE_KEY = " sb_publishable_r64A2FfAUHYF-L5On2DiCw_EEkJMsDY "

# إعدادات الصفحة الأساسية بطابع رسمي
st.set_page_config(page_title="نظام محلات البوش للحسابات", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .reportview-container { background: #faf8f5; }
    .main-title { color: #1E3A8A; text-align: center; font-size: 28px; font-weight: bold; margin-bottom: 5px; }
    .sub-title { color: #4B5563; text-align: center; font-size: 16px; margin-bottom: 25px; }
    .stSelectbox, .stTextInput { margin-bottom: -10px; }
    div[data-testid="stBlock"] { padding: 4px; }
    .client-card { background-color: #ffffff; padding: 14px; border-radius: 6px; border-right: 6px solid #1E3A8A; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .metric-box { background-color: #EFF6FF; padding: 12px; border-radius: 6px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05); border: 1px solid #BFDBFE; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات المتكامل</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">إدارة مديونيات السوق الرسمية المرتبطة بقاعدة بيانات سحابية دائمة</div>', unsafe_allow_html=True)

# الاتصال الآمن بقاعدة البيانات
@st.cache_resource
def get_supabase_client():
    if "ضع_هنا" in SUPABASE_KEY or SUPABASE_KEY == "":
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = get_supabase_client()

# دالات تنظيف واستخراج الأرقام والأسماء
def extract_yemeni_phone(text):
    if pd.isna(text):
        return ""
    text_str = str(text).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    match = re.search(r'(77\d{7}|73\d{7}|71\d{7}|70\d{7})', text_str)
    return match.group(1) if match else ""

def clean_customer_name(text):
    if pd.isna(text):
        return ""
    return re.sub(r'[/\\\-\d]+.*', '', str(text)).strip()

frequency_options = ["كل 3 أيام", "أسبوعي", "كل أسبوعين", "شهري", "إيقاف التذكير"]
freq_days_map = {"كل 3 أيام": 3, "أسبوعي": 7, "كل أسبوعين": 14, "شهري": 30, "إيقاف التذكير": 99999}

if supabase is None:
    st.warning("⚠️ يرجى إدخال مفتاح الربط الخاص بـ Supabase (SUPABASE_KEY) في السطر رقم 14 لتشغيل الحفظ الدائم.")
else:
    tab1, tab2 = st.tabs(["📊 العملاء المستحقين للتذكير اليوم", "📥 رفع وتحديث بيانات أونكس"])
    
    with tab2:
        st.subheader("📥 تحديث قاعدة البيانات من ملف أونكس")
        uploaded_file = st.file_uploader("قم برفع ملف الإكسل المستخرج حديثاً", type=["xlsx", "xls", "csv"])
        
        if uploaded_file is not None:
            df_onyx = None
            file_bytes = uploaded_file.read()
            
            # محاولة القراءة بطرق متعددة متوافقة مع ترميز أونكس الخاص
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_onyx = pd.read_csv(io.BytesIO(file_bytes))
                else:
                    try:
                        # المحاولة الأولى: كملف إكسل قياسي
                        df_onyx = pd.read_excel(io.BytesIO(file_bytes))
                    except Exception:
                        try:
                            # المحاولة الثانية: بمحرك xlrd للملفات القديمة xls
                            df_onyx = pd.read_excel(io.BytesIO(file_bytes), engine='xlrd')
                        except Exception:
                            try:
                                # المحاولة الثالثة: إذا كان ملف أونكس عبارة عن HTML متنكر بصيغة إكسل
                                dfs = pd.read_html(io.BytesIO(file_bytes))
                                if dfs:
                                    df_onyx = dfs[0]
                            except Exception:
                                # المحاولة الرابعة: كملف نصي عادي
                                df_onyx = pd.read_csv(io.BytesIO(file_bytes), sep='\t')
            except Exception as read_err:
                st.error(f"⚠️ تعذر قراءة بنية هذا الملف: {read_err}")
                
            if df_onyx is not None:
                try:
                    if len(df_onyx.columns) < 4:
                        st.error("❌ ملف الإكسل المرفوع لا يحتوي على الأعمدة الأربعة المطلوبة لنظام أونكس.")
                    else:
                        col_name, col_currency, col_balance = df_onyx.columns[1], df_onyx.columns[2], df_onyx.columns[3]
                        
                        success_count = 0
                        for idx, row in df_onyx.iterrows():
                            raw_name = row[col_name]
                            if pd.isna(raw_name) or "اسم العميل" in str(raw_name) or "الاسم" in str(raw_name): 
                                continue
                            
                            clean_name = clean_customer_name(raw_name)
                            if not clean_name: 
                                continue
                                
                            phone = extract_yemeni_phone(raw_name)
                            
                            try: 
                                balance_str = str(row[col_balance]).replace(',', '').strip()
                                balance_val = int(float(balance_str))
                            except: 
                                balance_val = 0
                            
                            if balance_val > 0:
                                existing = supabase.table("customers_debts").select("*").eq("customer_name", clean_name).execute()
                                if existing.data:
                                    supabase.table("customers_debts").update({
                                        "balance": balance_val, 
                                        "currency": str(row[col_currency]).strip()
                                    }).eq("customer_name", clean_name).execute()
                                else:
                                    supabase.table("customers_debts").insert({
                                        "customer_name": clean_name, 
                                        "phone_number": phone if phone else "لا يوجد رقم",
                                        "balance": balance_val, 
                                        "currency": str(row[col_currency]).strip(),
                                        "frequency": "أسبوعي", 
                                        "last_sent_date": None
                                    }).execute()
                                success_count += 1
                        st.success(f"✅ تم تحديث ومزامنة {success_count} عميل في قاعدة البيانات بنجاح!")
                except Exception as parse_err:
                    st.error(f"⚠️ واجه النظام مشكلة في معالجة خلايا الملف: {parse_err}")
            else:
                if not st.session_state.get('error_shown', False):
                    st.error("❌ تنسيق هذا الملف غير مدعوم مباشرة، يرجى حفظ ملف أونكس بصيغة Excel Workbook (XLSX) وإعادة رفعه.")

    with tab1:
        try:
            response = supabase.table("customers_debts").select("*").gt("balance", 0).execute()
            all_customers = response.data if response else []
        except Exception as db_err:
            st.error("❌ لم يتم العثور على الجدول داخل قاعدة البيانات. هل قمت بتشغيل كود الـ SQL في موقع Supabase؟")
            all_customers = []
        
        if all_customers:
            today = datetime.now().date()
            due_customers = []
            
            for cust in all_customers:
                freq = cust.get("frequency", "أسبوعي")
                if freq == "إيقاف التذكير": continue
                
                last_sent = cust.get("last_sent_date")
                if last_sent:
                    last_sent_dt = datetime.strptime(last_sent, "%Y-%m-%d").date()
                    days_passed = (today - last_sent_dt).days
                    if days_passed >= freq_days_map.get(freq, 7):
                        due_customers.append(cust)
                else:
                    due_customers.append(cust)
            
            st.write(f"### 🎯 إجمالي الحسابات المخزنة: {len(all_customers)} | 🔔 المستحقين للمتابعة اليوم: {len(due_customers)}")
            
            if due_customers:
                for item in due_customers:
                    current_phone = item["phone_number"]
                    phone_to_send = str(current_phone).strip().lstrip('0') if current_phone != "لا يوجد رقم" else ""
                    
                    msg = f"تحية طيبة من محلات البوش لقطع غيار الشاحنات.\nنود تذكيركم برصيد حسابكم المتبقي لدينا وهو: {item['balance']:,} {item['currency']}.\nيرجى التكرم بتصفية الحساب، شاكرين تعاونكم وثقتكم بنا."
                    encoded_msg = urllib.parse.quote(msg)
                    
                    st.markdown(f"""
                    <div class="client-card">
                        <span style="font-size:18px; font-weight:bold; color:#1E3A8A;">👤 {item['customer_name']}</span> | 
                        <span style="color:#4B5563;">📱 الهاتف: {current_phone}</span> | 
                        <span style="font-size:16px; font-weight:bold; color:#B91C1C;">💰 المتبقي: {item['balance']:,} {item['currency']}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_one, col_two, col_three, col_four = st.columns([1.2, 1.5, 1.2, 1.2])
                    
                    with col_one:
                        chosen_freq = st.selectbox(
                            f"freq_{item['id']}", frequency_options, 
                            index=frequency_options.index(item["frequency"]) if item["frequency"] in frequency_options else 1,
                            key=f"time_{item['id']}", label_visibility="collapsed"
                        )
                        if chosen_freq != item["frequency"]:
                            supabase.table("customers_debts").update({"frequency": chosen_freq}).eq("id", item["id"]).execute()
                        
                    with col_two:
                        new_phone = st.text_input(
                            f"phone_{item['id']}", value="" if current_phone == "لا يوجد رقم" else current_phone,
                            placeholder="تعديل الرقم هنا", key=f"input_{item['id']}", label_visibility="collapsed"
                        )
                        if new_phone.strip() != "" and new_phone.strip() != current_phone:
                            supabase.table("customers_debts").update({"phone_number": new_phone.strip()}).eq("id", item["id"]).execute()
                            phone_to_send = new_phone.strip().lstrip('0')
                        
                    with col_three:
                        if phone_to_send:
                            whatsapp_phone = "967" + phone_to_send if not phone_to_send.startswith("967") else phone_to_send
                            whatsapp_url = f"https://api.whatsapp.com/send?phone={whatsapp_phone}&text={encoded_msg}"
                            st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background-color: #25D366; color: white; border: none; padding: 7px 12px; border-radius: 4px; font-size: 14px; cursor: pointer; font-weight: bold; width: 100%;">💬 تم بالواتساب</button></a>', unsafe_allow_html=True)
                        else:
                            st.button("🚫 بلا رقم", key=f"wa_err_{item['id']}", disabled=True, use_container_width=True)
                            
                    with col_four:
                        if phone_to_send:
                            sms_url = f"sms:{phone_to_send}?body={encoded_msg}"
                            st.markdown(f'<a href="{sms_url}"><button style="background-color: #1E3A8A; color: white; border: none; padding: 7px 12px; border-radius: 4px; font-size: 14px; cursor: pointer; font-weight: bold; width: 100%;">📱 تم بـ SMS</button></a>', unsafe_allow_html=True)
                        else:
                            st.button("🚫 ناقص", key=f"sms_err_{item['id']}", disabled=True, use_container_width=True)
                    
                    st.markdown("<div style='margin-bottom:15px;'></div>", unsafe_allow_html=True)
            else:
                st.success("🎉 ممتاز جداً! لا يوجد أي عملاء مستحقين للتذكير اليوم، تم تذكير الجميع بانتظام.")
        else:
            st.info("💡 قاعدة البيانات فارغة حالياً. رفع ملف أونكس بالتبويب الثاني وسيقوم النظام بقراءته وتغذية الحسابات تلقائياً.")
