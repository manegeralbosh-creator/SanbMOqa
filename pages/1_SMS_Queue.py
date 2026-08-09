import streamlit as st
import pandas as pd
import urllib.parse
import zipfile
import pypdf

st.set_page_config(page_title="طابور الفواتير", page_icon="📱", layout="wide")

st.title("📱 طابور إرسال الفواتير عبر الشريحة")

# 1. قسم رفع الملفات
st.subheader("📂 رفع ملف الإكسل والأرشيف المضغوط")
col1, col2 = st.columns(2)

with col1:
    excel_file = st.file_uploader("اختر ملف الفواتير (Excel)", type=["xlsx", "xls"])

with col2:
    zip_file = st.file_uploader("اختر الأرشيف المضغوط لملفات PDF", type=None)

# قراءة نصوص الـ PDF
pdf_texts = {}
if zip_file is not None:
    try:
        with zipfile.ZipFile(zip_file, 'r') as z:
            for filename in z.namelist():
                if filename.lower().endswith('.pdf'):
                    clean_name = filename.split('/')[-1].replace('.pdf', '').strip()
                    with z.open(filename) as pdf_file:
                        reader = pypdf.PdfReader(pdf_file)
                        text = ""
                        for page in reader.pages:
                            text += page.extract_text() or ""
                        pdf_texts[clean_name] = text.strip()
        st.success(f"تم قراءة {len(pdf_texts)} ملف PDF بنجاح.")
    except Exception as e:
        st.error(f"خطأ أثناء قراءة الملف المضغوط: {e}")

# دالة تنسيق المبالغ وإزالة الأصفار بعد البوينت مع إضافة الفواصل
def format_number(val):
    try:
        num = float(val)
        # إذا كان الرقم صحيحاً يتم تجريده من الأصفار بعد البوينت
        if num.is_integer():
            return f"{int(num):,}"
        else:
            return f"{num:,.2f}".rstrip('0').rstrip('.')
    except:
        return str(val)

invoices_list = []

if excel_file is not None:
    df = pd.read_excel(excel_file)
    
    for _, row in df.iterrows():
        try:
            inv_code = str(row.iloc[0]).strip() # العمود الأول (رقم الفاتورة)
            
            # العمود الخامس (العملة)
            raw_currency = str(row.iloc[4]).strip().upper()
            if raw_currency == "SR":
                currency = "ريال سعودي"
            elif raw_currency == "YR":
                currency = "ريال يمني"
            else:
                currency = raw_currency
            
            customer = str(row.iloc[5]).strip()        # العمود السادس (اسم العميل)
            phone = str(row.iloc[6]).strip()           # العمود السابع (رقم الهاتف)
            details = str(row.iloc[7]).strip()         # العمود الثامن (التفاصيل)
            
            amount_formatted = format_number(row.iloc[9])   # العمود العاشر (المبلغ)
            balance_formatted = format_number(row.iloc[10]) # العمود الحادي عشر (الرصيد)
            
            # تفاصيل الـ PDF
            pdf_details = pdf_texts.get(inv_code, "لم يتم العثور على ملف PDF المطابق")
            
            # صياغة الرسالة النهائية
            sms_text = (
                f"محلات البوش للتجاره المركز الرئيسي جدر\n"
                f"الاخ: {customer}\n"
                f"عليكم فاتوره مبيعات: {details}\n"
                f"مبلغ الفاتوره: {amount_formatted} {currency}\n"
                f"وبهذا يكون الرصيد عليكم: {balance_formatted} {currency}\n"
                f"تفاصيل الفاتورة من الـ PDF:\n{pdf_details}"
            )
            
            invoices_list.append({
                "code": inv_code,
                "customer": customer,
                "phone": phone,
                "sms_text": sms_text
            })
        except Exception as e:
            continue

    st.success(f"تم تجهيز {len(invoices_list)} فاتورة للإرسال.")

st.divider()

# 2. عرض طابور الفواتير
if invoices_list:
    st.subheader("📋 تفاصيل طابور الفواتير")
    
    for idx, inv in enumerate(invoices_list):
        with st.container():
            c1, c2, c3 = st.columns([3, 4, 3])
            
            with c1:
                st.markdown(f"**العميل:** {inv['customer']}")
                st.markdown(f"**رقم الفاتورة:** `{inv['code']}`")
                st.caption(f"📞 الهاتف: {inv['phone']}")
                
            with c2:
                st.text_area("نص الرسالة الجاهزة:", value=inv['sms_text'], height=150, key=f"area_{idx}")
                
            with c3:
                encoded_msg = urllib.parse.quote(inv['sms_text'])
                sms_url = f"sms:{inv['phone']}?body={encoded_msg}"
                st.link_button("📲 إرسال عبر الشريحة", sms_url, use_container_width=True)
                
            st.divider()
