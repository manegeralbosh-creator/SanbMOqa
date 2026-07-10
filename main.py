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
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات والتذكير الآلي</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">أداة إدارة مديونيات السوق والربط الذكي مع نظام أونكس ERP عبر الواتساب</div>', unsafe_allow_html=True)

# دالة ذكية لاستخراج رقم الهاتف من اسم العميل (أونكس)
def extract_yemeni_phone(text):
    if pd.isna(text):
        return ""
    text_str = str(text)
    # البحث عن أي نمط لـ 9 أرقام تبدأ بـ 77 أو 73 أو 71 أو 70 (يدعم الأرقام العربية والهندية)
    text_str = text_str.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    match = re.search(r'(77\d{7}|73\d{7}|71\d{7}|70\d{7})', text_str)
    if match:
        return "967" + match.group(1)
    return ""

# دالة لتنظيف اسم العميل من الأرقام والرموز الزائدة
def clean_customer_name(text):
    if pd.isna(text):
        return ""
    text_str = str(text)
    # إزالة الأرقام الملتصقة بالاسم والشرطات الخاصة بالهاتف ليبقى الاسم صافياً
    text_clean = re.sub(r'[/\\\-\d]+.*', '', text_str)
    return text_clean.strip()

# تهيئة قاعدة البيانات المؤقتة في الجلسة
if 'accounts_data' not in st.session_state:
    # بيانات افتراضية أولية
    st.session_state.accounts_data = pd.DataFrame([
        {"العميل": "مؤسسة النجاح للتجارة", "الهاتف": "967770000000", "المبلغ المتبقي": 150000.0, "العملة": "YER"},
        {"شركة شمسان للمرطبات", "الهاتف": "967730000000", "المبلغ المتبقي": 2500.0, "العملة": "USD"}
    ])

# القائمة الجانبية أو التبويبات للتحكم الطريقتين
tab1, tab2 = st.tabs(["📁 الطريقة الأولى: رفع ملف أونكس", "⚙️ إعدادات الربط التلقائي (المباشر)"])

with tab1:
    st.subheader("📥 معالجة كشف حساب أونكس ERP")
    uploaded_file = st.file_uploader("قم برفع ملف الإكسل المستخرج من أونكس (Excel / CSV)", type=["xlsx", "xls", "csv"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_onyx = pd.read_csv(uploaded_file)
            else:
                df_onyx = pd.read_excel(uploaded_file)
            
            # محاولة التعرف على الأعمدة بناءً على الصورة المرسلة
            # العمود 1: رقم العميل، العمود 2: اسم العميل، العمود 3: العملة، العمود 4: الرصيد
            # سنعتمد على الترتيب لتلافي اختلاف الأسماء
            if len(df_onyx.columns) >= 4:
                col_name = df_onyx.columns[1]   # اسم العميل
                col_currency = df_onyx.columns[2] # العملة (Ac_Y)
                col_balance = df_onyx.columns[3]  # الرصيد الحالي
                
                parsed_list = []
                for idx, row in df_onyx.iterrows():
                    raw_name = row[col_name]
                    raw_currency = row[col_currency]
                    raw_balance = row[col_balance]
                    
                    phone = extract_yemeni_phone(raw_name)
                    clean_name = clean_customer_name(raw_name)
                    
                    # التحقق من وجود مديونية حقيقية
                    try:
                        balance_val = float(str(raw_balance).replace(',', ''))
                    except:
                        balance_val = 0.0
                        
                    if balance_val > 0:
                        parsed_list.append({
                            "العميل": clean_name if clean_name else raw_name,
                            "الهاتف": phone if phone else "لا يوجد رقم",
                            "المبلغ المتبقي": balance_val,
                            "العملة": str(raw_currency).strip()
                        })
                
                if parsed_list:
                    st.session_state.accounts_data = pd.DataFrame(parsed_list)
                    st.success(f"✅ تم بنجاح معالجة الملف واستيراد {len(parsed_list)} عميل لديهم مديونيات!")
                else:
                    st.warning("⚠️ تم قراءة الملف ولكن لم يتم العثور على مبالغ متبقية أكبر من الصفر.")
            else:
                st.error("❌ بنية الملف غير مطابقة لتقرير أونكس القياسي. يرجى التأكد من تصدير التقرير بأعمدته الأربعة كاملة.")
        except Exception as e:
            st.error(f"❌ حدث خطأ أثناء قراءة الملف: {str(e)}")

    # عرض جدول الحسابات الحالي المعتمد
    st.write("### 📋 كشف حسابات السوق الحالي:")
    st.dataframe(st.session_state.accounts_data, use_container_width=True)

    # قسم إرسال التذكيرات السريعة عبر الواتساب
    st.write("### 🚀 إرسال تذكير سريع بالمديونية")
    if not st.session_state.accounts_data.empty:
        client_options = st.session_state.accounts_data["العميل"].tolist()
        selected_client = st.selectbox("اختر العميل المراد مراسلته:", client_options)
        
        # جلب بيانات العميل المختار
        client_row = st.session_state.accounts_data[st.session_state.accounts_data["العميل"] == selected_client].iloc[0]
        client_phone = client_row["الهاتف"]
        client_amount = client_row["المبلغ المتبقي"]
        client_curr = client_row["العملة"]
        
        # صياغة نص الرسالة الاحترافي باسم محلات البوش
        msg = f"تحية طيبة من محلات البوش لقطع غيار الشاحنات.\n\nنود تذكيركم برصيد حسابكم المتبقي لدينا وهو: {client_amount:,.2f} {client_curr}.\n\nيرجى التكرم بزيارة المحل لتصفية الحساب أو التحويل، شاكرين تعاونكم وثقتكم بنا دائماً."
        encoded_msg = urllib.parse.quote(msg)
        
        if client_phone and client_phone != "لا يوجد رقم":
            whatsapp_url = f"https://api.whatsapp.com/send?phone={client_phone}&text={encoded_msg}"
            st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background-color: #25D366; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; width: 100%;">💬 إرسال التذكير عبر واتساب للعميل</button></a>', unsafe_allow_html=True)
        else:
            st.warning("⚠️ هذا العميل لا يمتلك رقم هاتف مستخرج من النظام، يمكنك تعديل الملف أو مراسلته يدوياً.")
    else:
        st.info("💡 الجدول فارغ حالياً، قم برفع ملف أونكس بالأعلى ليتم تعبئة البيانات تلقائياً.")

with tab2:
    st.subheader("🔌 إعدادات الربط الآلي المباشر (API)")
    st.info("🔗 هذا القسم مخصص لربط سيرفر أونكس في المحل مباشرة بالويب لرفع المديونيات بشكل تلقائي دوري وبدون تدخل يدوي.")
    
    st.write("#### 🛠️ معلومات المطور للربط المستقبلي:")
    st.code(f"""
# رابط الاستقبال (Webhook URL):
https://share.streamlit.io/⚙️_سيتم_تحديده_تلقائياً_عند_تفعيل_السكربت

# صيغة البيانات المطلوبة (JSON Payload):
{{
    "customer_name": "اسم العميل",
    "phone_number": "96777XXXXXXX",
    "balance": 50000,
    "currency": "YER"
}}
    """, language="python")
    st.write("💡 عند اكتمال التطوير ورغبتك في تفعيل هذا الربط التلقائي، سنقوم ببرمجة السكربت المحلي الصغير داخل سيرفر المحل ليقوم بالمهمة خلف الكواليس.")
