import streamlit as st
import pandas as pd
import urllib.parse
import zipfile
import pdfplumber
import os
import tempfile

# حاول استدعاء rarfile لقراءة ملفات RAR
try:
    import rarfile
    HAS_RAR = True
except ImportError:
    HAS_RAR = False

st.set_page_config(page_title="طابور الفواتير", page_icon="📱", layout="wide")

st.title("📱 طابور إرسال الفواتير عبر الشريحة")

# 1. رفع الملفات
st.subheader("📂 رفع ملف الإكسل والأرشيف المضغوط")
col1, col2 = st.columns(2)

with col1:
    excel_file = st.file_uploader("اختر ملف الفواتير (Excel)", type=["xlsx", "xls"])

with col2:
    zip_file = st.file_uploader("اختر الأرشيف المضغوط لملفات PDF (ZIP أو RAR)", type=None)

def extract_items_from_pdf(pdf_file_obj):
    items_list = []
    try:
        with pdfplumber.open(pdf_file_obj) as pdf:
            for page in pdf:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row and len(row) >= 5:
                            item_name = row[1]
                            qty = row[3]
                            if item_name and qty:
                                clean_item = str(item_name).replace('\n', ' ').strip()
                                clean_qty = str(qty).replace('\n', '').strip()
                                if "اسم الصنف" not in clean_item and clean_qty.replace('.', '').isdigit():
                                    words = clean_item.split()
                                    short_name = " ".join(words[:3]) if len(words) >= 3 else clean_item
                                    try:
                                        q_num = float(clean_qty)
                                        clean_qty = str(int(q_num)) if q_num.is_integer() else str(q_num)
                                    except:
                                        pass
                                    items_list.append(f"• {short_name} ({clean_qty})")
    except Exception:
        pass
    return items_list

pdf_items_dict = {}

if zip_file is not None:
    file_name = zip_file.name.lower()
    
    # التعامل مع ملفات ZIP
    if file_name.endswith('.zip'):
        try:
            with zipfile.ZipFile(zip_file, 'r') as z:
                for filename in z.namelist():
                    if filename.lower().endswith('.pdf'):
                        clean_name = filename.split('/')[-1].replace('.pdf', '').strip()
                        with z.open(filename) as pdf_file:
                            extracted = extract_items_from_pdf(pdf_file)
                            if extracted:
                                pdf_items_dict[clean_name] = "\n".join(extracted)
            st.success(f"تم تحليل {len(pdf_items_dict)} ملف PDF من ملف ZIP بنجاح.")
        except Exception as e:
            st.error(f"خطأ في قراءة ملف ZIP: {e}")

    # التعامل مع ملفات RAR
    elif file_name.endswith('.rar'):
        if not HAS_RAR:
            st.error("⚠️ يرجى إرشادات تثبيت مكتبة rarfile لقراءة ملفات RAR.")
        else:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".rar") as tmp:
                    tmp.write(zip_file.read())
                    tmp_path = tmp.name

                with rarfile.RarFile(tmp_path, 'r') as rf:
                    for filename in rf.namelist():
                        if filename.lower().endswith('.pdf'):
                            clean_name = filename.split('/')[-1].replace('.pdf', '').strip()
                            with rf.open(filename) as pdf_file:
                                extracted = extract_items_from_pdf(pdf_file)
                                if extracted:
                                    pdf_items_dict[clean_name] = "\n".join(extracted)
                os.remove(tmp_path)
                st.success(f"تم تحليل {len(pdf_items_dict)} ملف PDF من ملف RAR بنجاح.")
            except Exception as e:
                st.error(f"خطأ أثناء فك ضغط RAR: يرجى تحويل الأرشيف إلى صيغة ZIP لضمان السرعة والتوافق.")

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
            items_text = pdf_items_dict.get(inv_code, "• لا توجد تفاصيل أصناف")
            
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
