import streamlit as st
import pandas as pd
import zipfile

st.set_page_config(page_title="طابور الفواتير", page_icon="📲", layout="wide")

st.title("📲 طابور إرسال الفواتير والملفات")

# 1. قسم رفع الملفات (Excel و PDF)
st.subheader("📂 رفع بيانات الفواتير والملفات")

col_file1, col_file2 = st.columns(2)

with col_file1:
    excel_file = st.file_uploader("اختر ملف الفواتير (Excel)", type=["xlsx", "xls"])

with col_file2:
    zip_file = st.file_uploader("اختر ملف الـ PDF المضغوط (ZIP)", type=["zip"])

# 2. معالجة ملف الإكسل وإضافته للطابور
invoices_data = []

if excel_file is not None:
    df = pd.read_excel(excel_file)
    st.success("تم رفع ملف Excel بنجاح!")
    
    # تحويل بيانات الإكسل إلى قائمة فواتير
    for idx, row in df.iterrows():
        invoices_data.append({
            "id": str(row.get("رقم الفاتورة", f"INV-{idx+1}")),
            "customer": str(row.get("اسم العميل", "عميل")),
            "phone": str(row.get("رقم الهاتف", "")),
            "amount": row.get("المبلغ", 0),
            "status": "معلق"
        })

# قراءة أرشيف الـ PDF إن وجد
pdf_files_list = []
if zip_file is not None:
    with zipfile.ZipFile(zip_file, 'r') as z:
        pdf_files_list = [f for f in z.namelist() if f.endswith('.pdf')]
    st.success(f"تم التعرف على {len(pdf_files_list)} ملف PDF داخل الأرشيف.")

st.divider()

# 3. عرض الطابور عند وجود ملفات
st.subheader("🚀 الإرسال الجماعي")

if st.button("🔴 إرسال جميع الفواتير المعلقة عبر SMS الآن", type="primary", use_container_width=True):
    if not invoices_data:
        st.warning("يرجى رفع ملف Excel يحتوي على الفواتير أولاً.")
    else:
        st.info("جاري بدء الإرسال...")
