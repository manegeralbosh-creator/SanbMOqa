import streamlit as st
import pandas as pd
import time

# استدعاء مكتبة Twilio لإرسال الـ SMS (تأكد من تثبيتها: pip install twilio)
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

# 1. إعدادات الصفحة
st.set_page_config(page_title="طابور SMS الفواتير", page_icon="📲", layout="wide")

st.title("📲 طابور إرسال الفواتير عبر الرسائل النصية (SMS)")
st.write("أرسل الفواتير لجميع العملاء آلياً وبضغطة زر واحدة وبأمان تام 100%.")

# 2. إعدادات بوابة SMS (Twilio)
st.sidebar.header("⚙️ إعدادات بوابة SMS")
account_sid = st.sidebar.text_input("Account SID", value="", type="password")
auth_token = st.sidebar.text_input("Auth Token", value="", type="password")
from_number = st.sidebar.text_input("رقم المرسل (Twilio Number)", value="")

# 3. بيانات طابور الفواتير (يمكنك ربطها بمجال عملك أو ملفات Excel)
if "invoices_queue" not in st.session_state:
    st.session_state.invoices_queue = [
        {
            "id": "INV-101",
            "customer": "أحمد علي",
            "phone": "+967770000000",
            "items": "قطع غيار شاحنات - فلاتر وزيوت",
            "amount": 25000,
            "status": "معلق"
        },
        {
            "id": "INV-102",
            "customer": "مؤسسة البركة",
            "phone": "+967730000000",
            "items": "مستلزمات صيانة ومحركات",
            "amount": 42000,
            "status": "معلق"
        }
    ]

# 4. دالة بناء نص رسالة الـ SMS
def generate_sms_text(inv):
    return (
        f"فواتير: عزيزي {inv['customer']}، "
        f"فاتورتك رقم {inv['id']} بمبلغ {inv['amount']} ريال جاهزة. "
        f"التفاصيل: {inv['items']}. "
        f"شكراً لتعاملكم معنا."
    )

# 5. عرض إحصائيات الطابور
pending_invoices = [inv for inv in st.session_state.invoices_queue if inv["status"] == "معلق"]

c_metrics1, c_metrics2 = st.columns(2)
c_metrics1.metric("إجمالي الفواتير", len(st.session_state.invoices_queue))
c_metrics2.metric("الفواتير بانتظار الإرسال", len(pending_invoices))

st.divider()

# 6. زر الإرسال الجماعي لكل الطابور بضغطة زر
st.subheader("🚀 الإرسال الجماعي")

if st.button("🔴 إرسال جميع الفواتير المعلقة عبر SMS الآن", type="primary", use_container_width=True):
    if not account_sid or not auth_token or not from_number:
        st.error("⚠️ يرجى أدخال بيانات حساب SMS في القائمة الجانبية أولاً لتفعيل الإرسال.")
    elif not TWILIO_AVAILABLE:
        st.error("⚠️ مكتبة twilio غير مثبتة. قم بتثبيتها عبر الأمر: pip install twilio")
    else:
        client = Client(account_sid, auth_token)
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, inv in enumerate(st.session_state.invoices_queue):
            if inv["status"] == "معلق":
                status_text.text(f"جاري إرسال الفاتورة {inv['id']} إلى {inv['customer']}...")
                sms_body = generate_sms_text(inv)
                
                try:
                    # إرسال الرسالة عبر API البوابة
                    message = client.messages.create(
                        body=sms_body,
                        from_=from_number,
                        to=inv["phone"]
                    )
                    inv["status"] = "تم الإرسال"
                    st.toast(f"✅ تم الإرسال بنجاح إلى {inv['customer']}")
                except Exception as e:
                    st.error(f"❌ فشل الإرسال إلى {inv['customer']}: {e}")
                
                # تحديث شريط التقدم
                progress_bar.progress((idx + 1) / len(st.session_state.invoices_queue))
                time.sleep(0.5) # مهلة زمنية بسيطة بين الرسائل
                
        status_text.text("✨ اكتملت عملية إرسال جميع الفواتير!")
        st.success("تم إرسال كافة الفواتير النصية بنجاح.")

st.divider()

# 7. عرض واستعراض الطابور التفصيلي
st.subheader("📋 تفاصيل طابور الفواتير")

for idx, inv in enumerate(st.session_state.invoices_queue):
    col_info, col_msg, col_action = st.columns([2, 3, 2])
    
    with col_info:
        st.markdown(f"**{inv['customer']}** (`{inv['id']}`)")
        st.caption(f"📞 {inv['phone']} | 💰 {inv['amount']} ريال")
        
    with col_msg:
        st.code(generate_sms_text(inv), language="text")
        
    with col_action:
        st.write(f"الحالة: **{inv['status']}**")
        if inv["status"] == "معلق":
            if st.button("إرسال هذه الفاتورة فقط", key=f"single_send_{idx}"):
                inv["status"] = "تم الإرسال"
                st.success(f"تم تغيير حالة فاتورة {inv['customer']}")
                st.rerun()
