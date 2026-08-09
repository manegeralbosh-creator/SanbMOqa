import streamlit as st
import pandas as pd
import urllib.parse
import zipfile

st.set_page_config(page_title="طابور رسائل الشريحة", page_icon="📱", layout="wide")

st.title("📱 طابور إرسال الفواتير عبر شريحة الهاتف (SMS)")
st.write("أرسل الفواتير لعملائك مباشرة من شريحة هاتفك بأمان تام وبدون أي تكاليف إضافية.")

# 1. قسم رفع الملفات
st.subheader("📂 رفع ملفات الفواتير")
col_file1, col_file2 = st.columns(2)

with col_file1:
    excel_file = st.file_uploader("اختر ملف الفواتير (Excel)", type=["xlsx", "xls"])

with col_file2:
    zip_file = st.file_uploader("اختر ملف الـ PDF المضغوط (ZIP - اختياري)", type=["zip"])

# قائمة الفواتير
invoices_data = []

if excel_file is not None:
    df = pd.read_excel(excel_file)
    st.success(f"تم تحميل {len(df)} فاتورة من ملف الإكسل بنجاح!")
    
    for idx, row in df.iterrows():
        invoices_data.append({
            "id": str(row.get("رقم الفاتورة", f"INV-{idx+1}")),
            "customer": str(row.get("اسم العميل", "عميل")),
            "phone": str(row.get("رقم الهاتف", "")),
            "items": str(row.get("التفاصيل", "قطع غيار/مستلزمات")),
            "amount": row.get("المبلغ", 0),
            "status": "معلق"
        })

st.divider()

# 2. عرض الطابور والإرسال عبر الشريحة
if invoices_data:
    st.subheader("📋 طابور الإرسال السريع (شريحة SIM)")
    
    for idx, inv in enumerate(invoices_data):
        with st.container():
            c1, c2, c3 = st.columns([3, 4, 3])
            
            # نص الفاتورة المحدد للرسالة النصية
            sms_text = (
                f"فواتير: عزيزي {inv['customer']}، "
                f"فاتورتك رقم {inv['id']} بمبلغ {inv['amount']} ريال جاهزة. "
                f"التفاصيل: {inv['items']}."
            )
            
            with c1:
                st.markdown(f"**{inv['customer']}** (`{inv['id']}`)")
                st.caption(f"📞 {inv['phone']} | 💰 {inv['amount']} ريال")
                
            with c2:
                st.code(sms_text, language="text")
                
            with c3:
                # تجهيز رابط SMS المباشر لشريحة الهاتف
                encoded_body = urllib.parse.quote(sms_text)
                sms_url = f"sms:{inv['phone']}?body={encoded_body}"
                
                # زر يفتح تطبيق الرسائل في الهاتف فوراً
                st.link_button("📲 إرسال عبر الشريحة", sms_url, use_container_width=True)
                
            st.divider()
else:
    st.info("💡 يرجى رفع ملف Excel يحتوي على أعمدة (اسم العميل، رقم الهاتف، رقم الفاتورة، المبلغ، التفاصيل) للبدء.")
