import streamlit as st
import pandas as pd
import re
import urllib.parse

# إعدادات الصفحة الأساسية بطابع رسمي
st.set_page_config(page_title="نظام محلات البوش للحسابات", page_icon="📊", layout="wide")

# تصميم الواجهة الرسمية وإلغاء الزحمة الزائدة
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

st.markdown('<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات والتذكير الآلي</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">لوحة المتابعة الرسمية لمديونيات السوق وإرسال إشعارات السداد</div>', unsafe_allow_html=True)

# دالة استخراج رقم الهاتف وتجنب الأصفار الزائدة بالبداية
def extract_yemeni_phone(text):
    if pd.isna(text):
        return ""
    text_str = str(text)
    text_str = text_str.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    match = re.search(r'(77\d{7}|73\d{7}|71\d{7}|70\d{7})', text_str)
    if match:
        return match.group(1)
    return ""

# دالة لتنظيف اسم العميل من الرموز
def clean_customer_name(text):
    if pd.isna(text):
        return ""
    text_str = str(text)
    text_clean = re.sub(r'[/\\\-\d]+.*', '', text_str)
    return text_clean.strip()

# خيارات فئات التكرار المتاحة
frequency_options = ["كل 3 أيام", "أسبوعي", "كل أسبوعين", "شهري", "إيقاف التذكير"]

# تهيئة جلسة العمل
if 'raw_accounts' not in st.session_state:
    st.session_state.raw_accounts = []

if 'freq_dict' not in st.session_state:
    st.session_state.freq_dict = {}

if 'custom_phones' not in st.session_state:
    st.session_state.custom_phones = {}

tab1, tab2 = st.tabs(["📁 رفع ملف أونكس والتذكيرات", "⚙️ إعدادات الربط المباشر"])

with tab1:
    st.subheader("📥 معالجة كشف حساب أونكس ERP")
    uploaded_file = st.file_uploader("قم برفع ملف الإكسل المستخرج من نظام أونكس", type=["xlsx", "xls", "csv"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_onyx = pd.read_csv(uploaded_file)
            else:
                df_onyx = pd.read_excel(uploaded_file, list(pd.read_excel(uploaded_file, sheet_name=None).keys())[0])
            
            if len(df_onyx.columns) >= 4:
                col_name = df_onyx.columns[1]   
                col_currency = df_onyx.columns[2] 
                col_balance = df_onyx.columns[3]
                
                parsed_list = []
                for idx, row in df_onyx.iterrows():
                    raw_name = row[col_name]
                    raw_currency = row[col_currency]
                    raw_balance = row[col_balance]
                    
                    if pd.isna(raw_name) or "اسم العميل" in str(raw_name):
                        continue
                        
                    phone = extract_yemeni_phone(raw_name)
                    clean_name = clean_customer_name(raw_name)
                    
                    try:
                        # تحويل الأرقام لأعداد صحيحة بدون بوينت
                        balance_val = int(float(str(raw_balance).replace(',', '')))
                    except:
                        balance_val = 0
                        
                    if balance_val > 0:
                        cust_id = f"customer_row_{idx}"
                        parsed_list.append({
                            "id": cust_id,
                            "customer": clean_name if clean_name else raw_name,
                            "phone": phone if phone else "لا يوجد رقم",
                            "balance": balance_val,
                            "currency": str(raw_currency).strip()
                        })
                
                if parsed_list:
                    st.session_state.raw_accounts = parsed_list
                    st.success(f"✅ تم بنجاح استيراد {len(parsed_list)} عميل من ملف أونكس!")
                else:
                    st.warning("⚠️ لم يتم العثور على مبالغ متبقية أكبر من الصفر.")
            else:
                st.error("❌ بنية الملف غير مطابقة لتقرير أونكس القياسي.")
        except Exception as e:
            st.error(f"❌ حدث خطأ أثناء معالجة الملف، يرجى التأكد من حفظ الملف بصيغة صالحة.")

    # 📊 لوحة الملخص الرقمية (Dashboard)
    if st.session_state.raw_accounts:
        st.write("### 📊 لوحة ملخص مديونيات السوق الحالية:")
        df_stats = pd.DataFrame(st.session_state.raw_accounts)
        currency_groups = df_stats.groupby('currency')['balance'].sum().to_dict()
        total_customers = len(df_stats)
        
        stat_cols = st.columns(len(currency_groups) + 1)
        with stat_cols[0]:
            st.markdown(f'<div class="metric-box"><span style="color:#4B5563; font-weight:bold;">👥 إجمالي العملاء</span><br><span style="font-size:22px; font-weight:bold; color:#1E3A8A;">{total_customers} عميل</span></div>', unsafe_allow_html=True)
        
        col_idx = 1
        for curr, total_amt in currency_groups.items():
            with stat_cols[col_idx]:
                st.markdown(f'<div class="metric-box"><span style="color:#4B5563; font-weight:bold;">💰 ديون السوق ({curr})</span><br><span style="font-size:22px; font-weight:bold; color:#B91C1C;">{total_amt:,}</span></div>', unsafe_allow_html=True)
            col_idx += 1
            
        st.markdown("<br>", unsafe_allow_html=True)

    st.write("### 📋 كشف مديونيات السوق وإرسال التذكيرات الفوري:")
    
    if st.session_state.raw_accounts:
        for item in st.session_state.raw_accounts:
            current_phone = st.session_state.custom_phones.get(item["id"], item["phone"])
            
            phone_to_send = str(current_phone).strip()
            if phone_to_send.startswith('0') and len(phone_to_send) > 1:
                phone_to_send = phone_to_send.lstrip('0')
            
            # نص رسالة رسمي ومحترف ومختصر بدون كسور
            msg = f"تحية طيبة من محلات البوش لقطع غيار الشاحنات.\nنود تذكيركم برصيد حسابكم المتبقي لدينا وهو: {item['balance']:,} {item['currency']}.\nيرجى التكرم بتصفية الحساب، شاكرين تعاونكم وثقتكم بنا."
            encoded_msg = urllib.parse.quote(msg)
            
            st.markdown(f"""
            <div class="client-card">
                <span style="font-size:18px; font-weight:bold; color:#1E3A8A;">👤 {item['customer']}</span> | 
                <span style="color:#4B5563;">📱 الهاتف: {current_phone}</span> | 
                <span style="font-size:16px; font-weight:bold; color:#B91C1C;">💰 المتبقي: {item['balance']:,} {item['currency']}</span>
            </div>
            """, unsafe_allow_html=True)
            
            # تقسيم رسمي ومختصر بـ 4 خانات فقط (الفترة، التعديل، واتساب، SMS)
            col_one, col_two, col_three, col_four = st.columns([1.2, 1.5, 1.2, 1.2])
            
            with col_one:
                current_freq = st.session_state.freq_dict.get(item["id"], "أسبوعي")
                chosen_freq = st.selectbox(
                    f"freq_select_{item['id']}", 
                    frequency_options, 
                    index=frequency_options.index(current_freq) if current_freq in frequency_options else 1,
                    key=f"time_{item['id']}",
                    label_visibility="collapsed"
                )
                st.session_state.freq_dict[item["id"]] = chosen_freq
                
            with col_two:
                new_phone_input = st.text_input(
                    f"phone_input_{item['id']}", 
                    value="" if current_phone == "لا يوجد رقم" else current_phone,
                    placeholder="تحديث رقم الجوال هنا",
                    key=f"input_{item['id']}",
                    label_visibility="collapsed"
                )
                if new_phone_input.strip() != "" and new_phone_input.strip() != "لا يوجد رقم":
                    st.session_state.custom_phones[item["id"]] = new_phone_input.strip()
                    current_phone = new_phone_input.strip()
                    phone_to_send = current_phone.lstrip('0')
                
            with col_three:
                if phone_to_send and phone_to_send != "لا يوجد رقم":
                    whatsapp_phone = "967" + phone_to_send if not phone_to_send.startswith("967") else phone_to_send
                    whatsapp_url = f"https://api.whatsapp.com/send?phone={whatsapp_phone}&text={encoded_msg}"
                    st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background-color: #25D366; color: white; border: none; padding: 7px 12px; border-radius: 4px; font-size: 14px; cursor: pointer; font-weight: bold; width: 100%;">💬 واتساب</button></a>', unsafe_allow_html=True)
                else:
                    st.button("🚫 بلا رقم", key=f"wa_err_{item['id']}", disabled=True, use_container_width=True)
                    
            with col_four:
                if phone_to_send and phone_to_send != "لا يوجد رقم":
                    sms_url = f"sms:{phone_to_send}?body={encoded_msg}"
                    st.markdown(f'<a href="{sms_url}"><button style="background-color: #1E3A8A; color: white; border: none; padding: 7px 12px; border-radius: 4px; font-size: 14px; cursor: pointer; font-weight: bold; width: 100%;">📱 SMS</button></a>', unsafe_allow_html=True)
                else:
                    st.button("🚫 ناقص", key=f"sms_err_{item['id']}", disabled=True, use_container_width=True)
            
            st.markdown("<div style='margin-bottom:15px;'></div>", unsafe_allow_html=True)
    else:
        st.info("💡 النظام جاهز، قم برفع ملف أونكس لاستعراض لوحة التحكم وبيانات العملاء الرسمية.")

with tab2:
    st.subheader("🔌 إعدادات الربط الآلي المباشر (API)")
    st.info("🔗 هذا القسم مخصص لربط سيرفر أونكس في المحل مباشرة بالويب لرفع المديونيات تلقائياً.")
