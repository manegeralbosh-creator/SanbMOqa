import streamlit as st
import pandas as pd
import urllib.parse
import zipfile
import pdfplumber
import re

st.set_page_config(page_title="طابور الفواتير", page_icon="📱", layout="wide")

st.title("📱 طابور إرسال الفواتير عبر الشريحة")

# 1. قسم رفع الملفات
st.subheader("📂 رفع ملف الإكسل والأرشيف المضغوط")
col1, col2 = st.columns(2)

with col1:
    excel_file = st.file_uploader("اختر ملف الفواتير (Excel)", type=["xlsx", "xls"])

with col2:
    zip_file = st.file_uploader("اختر الأرشيف المضغوط لملفات PDF (صيغة ZIP حقيقية)", type=["zip"])

# دالة استخراج الأصناف والكميات من ملف الـ PDF
def extract_items_from_pdf(pdf_file_obj):
    items_list = []
    try:
        with pdfplumber.open(pdf_file_obj) as pdf:
            for page in pdf:
                # 1. البحث في الجداول أولاً
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row and len(row) >= 4:
                            # البحث عن العمود الذي يحتوي على اسم الصنف والكمية
                            row_str = [str(cell) for cell in row if cell is not None]
                            for idx, cell in enumerate(row_str):
                                # إذا وجدنا قيمة عددية (كمية)
                                clean_qty = cell.replace('\n', '').strip()
                                if clean_qty.replace('.', '').isdigit() and float(clean_qty) > 0:
                                    # نأخذ الخلية المجاوِرة كاسم للصنف
                                    if idx > 0:
                                        item_name = row_str[idx-1].replace('\n', ' ').strip()
                                    elif idx + 1 < len(row_str):
                                        item_name = row_str[idx+1].replace('\n', ' ').strip()
                                    else:
                                        continue
                                    
                                    if "اسم الصنف" not in item_name and "الإجمالي" not in item_name and len(item_name) > 3:
                                        words = item_name.split()
                                        short_name = " ".join(words[:3]) if len(words) >= 3 else item_name
                                        try:
                                            q_num = float(clean_qty)
                                            clean_qty = str(int(q_num)) if q_num.is_integer() else str(q_num)
                                        except:
                                            pass
                                        items_list.append(f"• {short_name} ({clean_qty})")
    except Exception:
        pass
    return list(dict.fromkeys(items_list)) # إزالة التكرار

pdf_items_dict = {}

if zip_file is not None:
    try:
        with zipfile.ZipFile(zip_file, 'r') as z:
            pdf_count = 0
            for filename in z.namelist():
                if filename.lower().endswith('.pdf') and not filename.startswith('__MACOSX'):
                    pdf_count += 1
                    # تنظيف اسم الملف لاستخدامه كمفتاح مطابقة
                    clean_name = filename.split('/')[-1].replace('.pdf', '').strip()
                    with z.open(filename) as pdf_file:
                        extracted = extract_items_from_pdf(pdf_file)
                        if extracted:
                            pdf_items_dict[clean_name] = "\n".join(extracted)
                        else:
                            pdf_items_dict[clean_name] = "• لم يتم التعرف على الاصناف داخل الجدول"
            st.success(f"تم قراءة {pdf_count} ملف PDF داخل الأرشيف المضغوط بنجاح.")
    except Exception as e:
        st.error("⚠️ ملف ZIP غير صالح. يرجى إعادة ضغط الملفات باستخدام برنامج WinRAR أو ZArchiver واختيار صيغة ZIP.")

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
            inv_code = str(row.iloc[0]).strip()
            
            raw_currency = str(row.iloc[4]).strip().upper()
            currency = "ريال سعودي" if raw_currency == "SR" else ("ريال يمني" if raw_currency == "YR" else raw_currency)
            
            customer = str(row.iloc[5]).strip()
            phone = str(row.iloc[6]).strip()
            details = str(row.iloc[7]).strip()
            
            amount_formatted = format_number(row.iloc[9])
            balance_formatted = format_number(row.iloc[10])
            
            # البحث عن الأصناف بواسطة رقم الفاتورة
            items_text = pdf_items_dict.get(inv_code)
            if not items_text:
                # محاولة المطابقة إذا كان الاسم يحتوي على الرقم جزئياً
                for k, v in pdf_items_dict.items():
                    if inv_code in k or k in inv_code:
                        items_text = v
                        break
            if not items_text:
                items_text = "• لا توجد تفاصيل أصناف"
            
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
