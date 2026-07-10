import streamlit as st
import pandas as pd
import requests
import urllib.parse

# إعدادات الصفحة لتناسب شاشة الجوال والكمبيوتر
st.set_page_config(page_title="نظام البوش للحسابات", page_icon="📊", layout="centered")

# تصميم مخصص لتحسين المظهر على الجوال (باللون الأزرق المريح والرمادي)
st.markdown("""
    <style>
    .main { text-align: right; direction: rtl; }
    div.stButton > button:first-child {
        background-color: #1A5276;
        color: white;
        border-radius: 8px;
        width: 100%;
        height: 50px;
        font-size: 18px;
    }
    th, td { text-align: right !important; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 نظام محلات البوش لخدمات الحسابات")
st.write("أهلاً بك يا أبو تميم. أداة إدارة مديونيات العملاء والتذكير الآلي عبر الواتساب.")

# القائمة الجانبية أو التبويبات
tab1, tab2 = st.tabs(["📱 إرسال التذكيرات", "➕ إضافة/تعديل البيانات"])

with tab1:
    st.subheader("🔗 كشف حسابات العملاء وإرسال الإشعارات")
    
    # نموذج لبيانات تجريبية (يمكن ربطها بملف Excel أو قاعدة بيانات Onyx ERP لاحقاً)
    if 'data' not in st.session_state:
        st.session_state.data = pd.DataFrame([
            {"العميل": "مؤسسة النجاح للتجارة", "الهاتف": "967770000000", "المبلغ المتبقي": 150000, "العملة": "YER"},
            {"العميل": "شركة شمسان للمرطبات", "الهاتف": "967730000000", "المبلغ المتبقي": 2500, "العملة": "USD"},
        ])
    
    df = st.session_state.data
    
    # عرض البيانات في جدول تفاعلي مريح جداً على الجوال
    st.dataframe(df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("🚀 إرسال تذكير سريع")
    
    # اختيار العميل لإرسال الرسالة له
    client_names = df["العميل"].tolist()
    selected_client = st.selectbox("اختر العميل المُراد مراسلته:", client_names)
    
    # جلب بيانات العميل المختار
    client_row = df[df["العميل"] == selected_client].iloc[0]
    phone = client_row["الهاتف"]
    balance = client_row["المبلغ المتبقي"]
    currency = client_row["العملة"]
    
    # نص الرسالة التلقائي (صيغة احترافية ومحترمة)
    default_msg = f"عزيزي العميل ({selected_client})، يرجى التكرم بالعلم بأن الرصيد المستحق لحسابكم طرفنا هو {balance:,} {currency}. شاكرين حسن تعاونكم الدائم - محلات البوش لقطع غيار الشاحنات."
    
    message = st.text_area("نص رسالة التذكير:", value=default_msg, height=120)
    
    # تجهيز رابط الواتساب المباشر
    encoded_msg = urllib.parse.quote(message)
    whatsapp_url = f"https://api.whatsapp.com/send?phone={phone}&text={encoded_msg}"
    
    # زر الإرسال المباشر
    if st.button(f"📲 إرسال إلى {selected_client} عبر الواتساب"):
        st.markdown(f'<a href="{whatsapp_url}" target="_blank" style="text-decoration:none;"><div style="background-color:#25D366;color:white;padding:10px;text-align:center;border-radius:8px;font-weight:bold;">انقر هنا لفتح الواتساب وإرسال الرسالة فوراً</div></a>', unsafe_allow_html=True)
        st.success("تم تجهيز الرابط بنجاح! اضغط على الزر الأخضر بالأعلى للانتقال للواتساب.")

with tab2:
    st.subheader("📝 إدارة قاعدة البيانات المؤقتة")
    with st.form("add_client_form"):
        new_name = st.text_input("اسم العميل الجديد:")
        new_phone = st.text_input("رقم الهاتف (مع رمز الدولة، مثال: 96777...):")
        new_balance = st.number_input("المبلغ المستحق:", min_value=0, step=500)
        new_currency = st.selectbox("العملة:", ["YER", "USD", "SAR"])
        
        submit_btn = st.form_submit_button("💾 حفظ العميل في القائمة")
        
        if submit_btn and new_name and new_phone:
            new_row = {"العميل": new_name, "الهاتف": new_phone, "المبلغ المتبقي": new_balance, "العملة": new_currency}
            st.session_state.data = pd.concat([st.session_state.data, pd.DataFrame([new_row])], ignore_index=True)
            st.success(f"تمت إضافة {new_name} بنجاح إلى القائمة!")
            st.rerun()
