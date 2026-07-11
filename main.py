import streamlit as st
import pandas as pd
import re
import urllib.parse

# إعدادات الصفحة
st.set_page_config(page_title="نظام محلات البوش لخدمات الحسابات", page_icon="📊", layout="wide")

# تصميم الواجهة والعناوين
st.markdown("""
    <style>
    .reportview-container { background: #faf8f5; }
    .main-title { color: #1E3A8A; text-align: center; font-size: 32px; font-weight: bold; margin-bottom: 20px; }
    .sub-title { color: #4B5563; text-align: center; font-size: 18px; margin-bottom: 30px; }
    .stSelectbox { margin-bottom: -15px; }
    div[data-testid="stBlock"] { padding: 5px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات والتذكير الآلي</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">إدارة مديونيات السوق، تحديد الفئات، واستثناء وتفعيل العملاء بأمان كامل</div>', unsafe_allow_html=True)

# دالة ذكية لاستخراج رقم الهاتف من اسم العميل (أونكس)
def extract_yemeni_phone(text):
    if pd.isna(text):
        return ""
    text_str = str(text)
    text_str = text_str.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    match = re.search(r'(77\d{7}|73\d{7}|71\d{7}|70\d{7})', text_str)
    if match:
        return match.group(1)
    return ""

# دالة لتنظيف اسم العميل من الأرقام والرموز الزائدة
def clean_customer_name(text):
    if pd.isna(text):
        return ""
    text_str = str(text)
    text_clean = re.sub(r'[/\\\-\d]+.*', '', text_str)
    return text_clean.strip()

# خيارات فئات التكرار المتاحة
frequency_options = ["كل 3 أيام", "أسبوعي", "كل أسبوعين", "شهري", "إيقاف التذكير"]

# تهيئة البيانات الأساسية في جلسة العمل
if 'raw_accounts' not in st.session_state:
    st.session_state.raw_accounts = []

if 'excluded_set' not in st.session_state:
    st.session_state.excluded_set = set()

if 'freq_dict' not in st.session_state:
    st.session_state.freq_dict = {}

tab1, tab2 = st.tabs(["📁 الطريقة الأولى: رفع ملف أونكس وتعديل الخيارات", "⚙️ إعدادات الربط التلقائي (المباشر)"])

with tab1:
    st.subheader("📥 معالجة كشف حساب أونكس ERP")
    uploaded_file = st.file_uploader("قم برفع ملف الإكسل المستخرج من أونكس (Excel / CSV)", type=["xlsx", "xls", "csv"])
    
    if uploaded_file is not None:
        try:
            # قراءة مرنة للملف تتفادى نقص مكتبة xlrd لملفات xls
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
                        balance_val = float(str(raw_balance).replace(',', ''))
                    except:
                        balance_val = 0.0
                        
                    if balance_val > 0:
                        cust_id = f"{clean_name if clean_name else raw_name}_{idx}"
                        parsed_list.append({
                            "id": cust_id,
                            "customer": clean_name if clean_name else raw_name,
                            "phone": phone if phone else "لا يوجد رقم",
                            "balance": balance_val,
                            "currency": str(raw_currency).strip()
                        })
                
                if parsed_list:
                    st.session_state.raw_accounts = parsed_list
                    st.session_state.excluded_set = set() # تصفير الاستثناءات للملف الجديد
                    st.success(f"✅ تم بنجاح استيراد {len(parsed_list)} عميل من ملف أونكس!")
                else:
                    st.warning("⚠️ لم يتم العثور على مبالغ متبقية أكبر من الصفر.")
            else:
                st.error("❌ بنية الملف غير مطابقة لتقرير أونكس القياسي.")
        except Exception as e:
            st.error(f"❌ حدث خطأ أثناء معالجة الملف، يرجى حفظ الملف كـ Excel Workbook (.xlsx) وإعادة رفعه. تفاصيل: {str(e)}")

    st.write("### 📋 كشف حسابات السوق النشطة:")
    
    if st.session_state.raw_accounts:
        # تصنيف البيانات بصورة آمنة تماماً خارج حلقة العرض
        active_items = [item for item in st.session_state.raw_accounts if item["id"] not in st.session_state.excluded_set]
        banned_items = [item for item in st.session_state.raw_accounts if item["id"] in st.session_state.excluded_set]
        
        if active_items:
            col_c1, col_c2, col_c3, col_c4, col_c5, col_c6 = st.columns([3, 1.5, 1.5, 1, 1.5, 1.5])
            with col_c1: st.markdown("**العميل**")
            with col_c2: st.markdown("**الهاتف**")
            with col_c3: st.markdown("**المبلغ المتبقي**")
            with col_c4: st.markdown("**العملة**")
            with col_c5: st.markdown("**فئة التكرار ⚙️**")
            with col_c6: st.markdown("**إجراء الاستثناء 🛠️**")
            st.markdown("---")
            
            for item in active_items:
                c1, c2, c3, c4, c5, c6 = st.columns([3, 1.5, 1.5, 1, 1.5, 1.5])
                with c1: st.write(item['customer'])
                with c2: st.write(item['phone'])
                with c3: st.write(f"{item['balance']:,.2f}")
                with c4: st.write(item['currency'])
                
                with c5:
                    current_freq = st.session_state.freq_dict.get(item["id"], "أسبوعي")
                    chosen_freq = st.selectbox(
                        f"فئة {item['id']}", 
                        frequency_options, 
                        index=frequency_options.index(current_freq) if current_freq in frequency_options else 1,
                        key=f"sel_{item['id']}",
                        label_visibility="collapsed"
                    )
                    st.session_state.freq_dict[item["id"]] = chosen_freq
                
                with c6:
                    if st.button("🚫 استثناء العميل", key=f"btn_ban_{item['id']}", use_container_width=True):
                        st.session_state.excluded_set.add(item["id"])
                        st.toast(f"📌 تم استثناء العميل [{item['customer']}] بنجاح!")
                        st.rerun()
        else:
            st.warning("💡 القائمة الرئيسية فارغة، جميع العملاء في قائمة الاستثناء.")

        # --- شاشة التفعيل الفردية للعملاء المستثنيين ---
        if banned_items:
            st.markdown("---")
            with st.expander("👁️ تفقد وإعادة تفعيل العملاء المستثنيين من الإرسال"):
                st.write("القائمة التالية تحتوي على العملاء المستثنيين حالياً:")
                
                col_b1, col_b2, col_b3, col_b4 = st.columns([4, 2, 2, 2])
                with col_b1: st.markdown("**اسم العميل المستثنى**")
                with col_b2: st.markdown("**المبلغ**")
                with col_b3: st.markdown("**العملة**")
                with col_b4: st.markdown("**إجراء التفعيل ⚡**")
                
                for item in banned_items:
                    b1, b2, b3, b4 = st.columns([4, 2, 2, 2])
                    with b1: st.write(f"<span style='color:gray;'>{item['customer']}</span>", unsafe_allow_html=True)
                    with b2: st.write(f"<span style='color:gray;'>{item['balance']:,.2f}</span>", unsafe_allow_html=True)
                    with b3: st.write(f"<span style='color:gray;'>{item['currency']}</span>", unsafe_allow_html=True)
                    with b4:
                        if st.button("✅ تفعيل العميل", key=f"btn_act_{item['id']}", use_container_width=True):
                            st.session_state.excluded_set.remove(item["id"])
                            st.toast(f"🔄 تم إعادة تفعيل العميل [{item['customer']}]")
                            st.rerun()

        # --- قسم إرسال التذكيرات والمتابعة الجاهزة (للنشطين فقط) ---
        st.markdown("---")
        st.write("### 🚀 إرسال التذكيرات والمتابعة الجاهزة")
        
        if active_items:
            client_map = {item["customer"]: item for item in active_items}
            selected_customer_name = st.selectbox("اختر العميل المراد مراسلته وتفقد خياراته الحالية:", list(client_map.keys()))
            
            selected_item = client_map[selected_customer_name]
            client_phone = selected_item["phone"]
            client_amount = selected_item["balance"]
            client_curr = selected_item["currency"]
            
            msg = f"تحية طيبة من محلات البوش لقطع غيار الشاحنات.\nنود تذكيركم برصيد حسابكم المتبقي لدينا وهو: {client_amount:,.2f} {client_curr}.\nيرجى التكرم بتصفية الحساب، شاكرين تعاونكم وثقتكم بنا."
            encoded_msg = urllib.parse.quote(msg)
            
            if client_phone and client_phone != "لا يوجد رقم":
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    whatsapp_phone = "967" + client_phone if not client_phone.startswith("967") else client_phone
                    whatsapp_url = f"https://api.whatsapp.com/send?phone={whatsapp_phone}&text={encoded_msg}"
                    st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background-color: #25D366; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; width: 100%;">💬 إرسال عبر واتساب</button></a>', unsafe_allow_html=True)
                
                with col_btn2:
                    sms_url = f"sms:{client_phone}?body={encoded_msg}"
                    st.markdown(f'<a href="{sms_url}"><button style="background-color: #1E3A8A; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; width: 100%;">📱 إرسال SMS مجاني من الشريحة</button></a>', unsafe_allow_html=True)
            else:
                st.warning("⚠️ هذا العميل لا يمتلك رقم هاتف مستخرج من النظام.")
        else:
            st.warning("💡 لا توجد أسماء في قائمة الإرسال السريع، جميع العملاء مستثنون حالياً.")
    else:
        st.info("💡 الجدول فارغ حالياً، قم برفع ملف أونكس بالأعلى.")

with tab2:
    st.subheader("🔌 إعدادات الربط الآلي المباشر (API)")
    st.info("🔗 هذا القسم مخصص لربط سيرفر أونكس في المحل مباشرة بالويب لرفع المديونيات تلقائياً.")
