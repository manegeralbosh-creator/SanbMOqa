import streamlit as st
import pandas as pd
import urllib.parse
import zipfile
import io
import re
from PIL import Image

# استخدام pypdf و pdf2image أو fitz لقراءة الـ PDF كصورة
try:
    import fitz  # PyMuPDF تحويل سريع لـ PDF إلى صورة
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    import easyocr
    import numpy as np
    # تحميل محرك التعرف الضوئي للغة العربية والإنجليزي
    @st.cache_resource
    def load_ocr_reader():
        return easyocr.Reader(['ar', 'en'], gpu=False)
    reader = load_ocr_reader()
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

st.set_page_config(page_title="طابور الفواتير - OCR", page_icon="📱", layout="wide")

st.title("📱 طابور إرسال الفواتير عبر الشريحة (مع تقنية استخراج الصور)")

# 1. قسم رفع الملفات
st.subheader("📂 رفع ملف الإكسل والأرشيف المضغوط")
col1, col2 = st.columns(2)

with col1:
    excel_file = st.file_uploader("اختر ملف الفواتير (Excel)", type=["xlsx", "xls"])

with col2:
    zip_file = st.file_uploader("اختر الأرشيف المضغوط لملفات PDF (ZIP)", type=["zip"])

def process_pdf_bytes_to_items(pdf_bytes):
    items_list = []
    
    # تحويل الـ PDF إلى صور
    images = []
    if HAS_FITZ:
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img = Image.open(io.BytesIO(pix.tobytes()))
                images.append(img)
        except Exception:
            pass

    # إذا توفرت مكتبة EasyOCR وتم استخراج الصور
    if HAS_OCR and images:
        for img in images:
            img_np = np.array(img)
            results = reader.readtext(img_np)
            
            # تجميع النصوص المستخرجة
            extracted_lines = [res[1] for res in results]
            
            for line in extracted_lines:
                line_clean = line.strip()
                # تجاهل العناوين والرؤوس
                if any(kw in line_clean for kw in ["محلات", "الرئيسي", "فاتورة", "إجمالي", "العميل", "الرصيد", "التاريخ"]):
                    continue
                
                parts = line_clean.split()
                if len(parts) >= 2:
                    for part in parts:
                        clean_p = re.sub(r'\D', '', part)
                        if clean_p.isdigit() and 1 <= int(clean_p) <= 500:
                            name_words = [p for p in parts if not re.sub(r'\D', '', p).isdigit() and len(p) > 2]
                            if name_words:
                                short_name = " ".join(name_words[:3])
                                items_list.append(f"• {short_name} ({clean_p})")
                                break
    return list(dict.fromkeys(items_list))

pdf_items_dict = {}

if zip_file is not None:
    try:
        with zipfile.ZipFile(zip_file, 'r') as z:
            pdf_count = 0
            for filename in z.namelist():
                if filename.lower().endswith('.pdf') and not filename.startswith('__MACOSX'):
                    pdf_count += 1
                    clean_name = filename.split('/')[-1].replace('.pdf', '').replace('.PDF', '').strip()
                    pdf_bytes = z.read(filename)
                    
                    extracted = process_pdf_bytes_to_items(pdf_bytes)
                    if extracted:
                        pdf_items_dict[clean_name] = "\n".join(extracted)
                    else:
                        pdf_items_dict[clean_name] = "• التفاصيل حسب الفاتورة المرفقة"
                        
            st.success(f"✅ تم معالجة وتحليل {pdf_count} ملف PDF بالصور والذكاء الاصطناعي بنجاح.")
    except Exception as e:
        st.error(f"⚠️ خطأ أثناء قراءة الملفات: {e}")

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
            
            items_text = None
            for key_name, text_val in pdf_items_dict.items():
                if inv_code == key_name or inv_code in key_name or key_name in inv_code:
                    items_text = text_val
                    break
            
            if not items_text:
                items_text = "• التفاصيل حسب الفاتورة المرفقة"
            
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
