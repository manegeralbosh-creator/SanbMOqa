import streamlit as st
import requests
import json

# --- إعدادات الصفحة ---
st.set_page_config(page_title="إشعارات محلات البوش", page_icon="📦", layout="centered")

st.title("📦 محلات البوش لقطع غيار الشاحنات")
st.subheader("نظام إرسال الفواتير عبر WhatsApp API")

# --- المتغيرات الأساسية (يتم تعبئتها بمجرد استخراج المفاتيح) ---
st.sidebar.header("⚙️ إعدادات Meta API")
ACCESS_TOKEN = st.sidebar.text_input("Access Token", type="password", help="ضع رمز الوصول الخاص بك هنا")
PHONE_NUMBER_ID = st.sidebar.text_input("Phone Number ID", help="ضع معرف رقم الهاتف هنا")

# --- واجهة مدخلات الفاتورة ---
st.markdown("---")
st.write("### 📝 بيانات الفاتورة والعميل")

col1, col2 = st.columns(2)
with col1:
    customer_name = st.text_input("اسم العميل", placeholder="مثال: أحمد علي")
    invoice_number = st.text_input("رقم الفاتورة", placeholder="INV-1001")

with col2:
    # إدخال رقم هاتف العميل بالصيغة الدولية (بدون + أو 00)
    customer_phone = st.text_input("رقم هاتف العميل (مع رمز الدولة)", placeholder="9677XXXXXXX")
    total_amount = st.number_input("إجمالي المبلغ (ر.ي / $)", min_value=0.0, step=100.0)

items_details = st.text_area("تفاصيل قطع الغيار", placeholder="مثال: طقم فحمات فرامل - فلتر زيت سينوتروك HOWO")

# --- دالة إرسال الرسالة عبر WhatsApp API ---
def send_whatsapp_message(phone, token, phone_id, name, inv_num, amount, details):
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # نص الرسالة المصممة بشكل احترافي
    message_text = (
        f"مرحباً بك {name} 👋\n\n"
        f"نشكر اختيارك *محلات البوش لقطع غيار الشاحنات*.\n\n"
        f"📄 *تفاصيل الفاتورة:* #{inv_num}\n"
        f"🛠️ *القطع:* {details}\n"
        f"💰 *الإجمالي:* {amount:,.2f}\n\n"
        f"لأي استفسار يمكنك التواصل معنا عبر هذا الرقم."
    )
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message_text
        }
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    return response

# --- زر الإرسال ---
if st.button("🚀 إرسال الفاتورة للعميل"):
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        st.error("⚠️ يرجى إدخال Access Token و Phone Number ID في الشريط الجانبي أولاً.")
    elif not customer_phone or not customer_name or not invoice_number:
        st.warning("⚠️ يرجى تعبئة كافة البيانات المطلوبة.")
    else:
        with st.spinner("جاري إرسال الفاتورة..."):
            res = send_whatsapp_message(
                customer_phone, ACCESS_TOKEN, PHONE_NUMBER_ID,
                customer_name, invoice_number, total_amount, items_details
            )
            
            if res.status_code == 200:
                st.success(f"✅ تم إرسال الفاتورة بنجاح إلى {customer_name} ({customer_phone})!")
            else:
                st.error(f"❌ فشل الإرسال. رمز الخطأ: {res.status_code}")
                st.json(res.json())
