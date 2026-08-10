import streamlit as st
import pandas as pd
import urllib.parse
import zipfile
import pypdf
import io
import re

st.set_page_config(page_title="طابور الفواتير", page_icon="📱", layout="wide")

st.title("📱 طابور إرسال الفواتير عبر الشريحة")

# 1. قسم رفع الملفات
st.subheader("📂 رفع ملف الإكسل والأرشيف المضغوط")
col1, col2 = st.columns(2)

with col1:
    excel_file = st.file_uploader("اختر ملف الفواتير (Excel)", type=["xlsx", "xls"])

with col2:
    zip_file = st.file_uploader("اختر الأرشيف المضغوط لملفات PDF (ZIP)", type=["zip"])

def extract_items_from_pdf_stream(pdf_bytes):
    items_list = []
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"
        
        if full_text:
            lines = full_text.split("\n")
            for line in lines:
                line_str = line.strip()
                # استبعاد العناوين والترويسات
                if any(kw in line_str for kw in ["محلات", "الرئيسي", "فاتورة", "إجمالي", "العميل", "الرصيد", "التاريخ", "المبلغ"]):
                    continue
                parts = line_str.split()
                if len(parts) >= 2:
                    for part in parts:
                        clean_p = part.replace(',', '').replace('.00', '')
                        if clean_p.isdigit() and 1 <= int(clean_p) <= 1000:
                            name_parts = [p for p in parts if not p.isdigit() and len(p) > 2]
                            if name_parts:
                                short_name = " ".join(name_parts[:3])
                                items_list.append(f"• {short_name} ({clean_p})")
                                break
    except Exception:
        pass
    
    return list(dict.fromkeys(items_list))

pdf_items_dict = {}

if zip_file is not None:
    try:
        with zipfile.ZipFile(zip_file, 'r') as z:
            pdf_count = 0
            for filename in z.namelist():
                if filename.lower().endswith('.pdf') and not filename.startswith('__MACOSX'):
                    pdf_count += 1
                    
                    # استخراج الأرقام فقط من اسم الملف (حذف DOCSER_ و .pdf)
                    file_basename = filename.split('/')[-1]
                    digits_only = re.sub(r'\D', '', file_basename) # يحول DOCSER_100110429774.pdf إلى 100110429774
                    
                    pdf_bytes = z.read(filename)
                    extracted = extract_items_from_pdf_stream(pdf_bytes)
                    
                    if extracted:
                        pdf_items_dict[digits_only] = "\n".join(extracted)
                    else:
                        pdf_items_dict[digits_only] = "• راجع الفاتورة المرفقة"
                        
            st.success(f"✅ تم التعرف على {pdf_count} ملف PDF داخل الأرشيف وإزالة بادئة (DOCSER_).")
    except Exception as e:
        st.error(f"❌ خطأ أثناء فتح ملف الـ ZIP: {e}")

def format_number(val):
    try:
        num = float(val)
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
            # تنظيف رقم الفاتورة من أي أشكال أو رموز للربط المباشر
            raw_inv = str(row.iloc[0]).strip()
            inv_code = re.sub(r'\D', '', raw_inv)
            
            raw_currency = str(row.iloc[4]).strip().upper()
            currency = "ريال سعودي" if raw_currency == "SR" else ("ريال يمني" if raw_currency == "YR" else raw_currency)
            
            customer = str(row.iloc[5]).strip()
            phone = str(row.iloc[6]).strip()
            details = str(row.iloc[7]).strip()
            
            amount_formatted = format_number(row.iloc[9])
            balance_formatted = format_number(row.iloc[10])
            
            # المطابقة باستخدام الرقم الصافي
            items_text = pdf_items_dict.get(inv_code)
            
            if not items_text:
                items_text = "• راجع الفاتورة المرفقة"
            
            sms_text = (
                f"محلات البوش للتجاره المركز الرئيسي جدر\n"
                f"الاخ: {customer}\n"
                f"عليكم فاتوره مبيعات: {details}\n"
                f"مبلغ الفاتوره: {amount_formatted} {currency}\n"
                f"وبهذا يكون الرصيد عليكم: {balance_formatted} {currency}\n"
                f"التفاصيل:\n"
                f"{items_text}"
            )
            invoices_list.append({"code": inv_code, "customer": customer, "phone": phone, "sms_text": sms_text})
        except Exception:
            continue
            
    st.success(f"تم تجهيز {len(invoices_list)} فاتورة للإرسال.")

st.divider()

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
                st.text_area("نص الرسالة الجاهزة:", value=inv['sms_text'], height=180, key=f"area_{idx}")
            with c3:
                encoded_msg = urllib.parse.quote(inv['sms_text'])
                sms_url = f"sms:{inv['phone']}?body={encoded_msg}"
                st.link_button("📲 إرسال عبر الشريحة", sms_url, use_container_width=True)
            st.divider()
