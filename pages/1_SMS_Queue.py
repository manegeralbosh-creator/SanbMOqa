import io
import re
import urllib.parse
import zipfile
import pandas as pd
import pypdf
import streamlit as st

st.set_page_config(page_title="طابور الفواتير", page_icon="📱", layout="wide")

st.title("📱 طابور إرسال الفواتير عبر الشريحة")

st.subheader("📂 رفع ملف الإكسل والأرشيف المضغوط")
col1, col2 = st.columns(2)

with col1:
    excel_file = st.file_uploader(
        "اختر ملف الفواتير (Excel)", type=["xlsx", "xls"]
    )

with col2:
    zip_file = st.file_uploader(
        "اختر الأرشيف المضغوط لملفات PDF (ZIP)", type=["zip"]
    )


def fix_reversed_text(text):
    """إصلاح اتجاه النص العربي المعكوس"""
    if not text:
        return ""
    words = text.split()
    fixed_words = []
    for w in words:
        if re.search(r"[\u0600-\u06FF]", w):
            fixed_words.append(w[::-1])
        else:
            fixed_words.append(w)
    return " ".join(fixed_words[::-1])


def extract_items_from_pdf(pdf_bytes):
    """استخراج اسم الصنف والكمية مع معالجة النص المعكوس"""
    extracted_items = []
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"

        lines = full_text.split("\n")
        for line in lines:
            line_str = line.strip()
            if not line_str or len(line_str) < 5:
                continue

            # استبعاد الترويسة والإجماليات
            if any(
                kw in line_str
                for kw in [
                    "البوش",
                    "الرئيسي",
                    "فاتورة",
                    "إجمالي",
                    "العميل",
                    "الرصيد",
                    "التاريخ",
                    "المبلغ",
                    "الصافي",
                    "تلفن",
                    "موبايل",
                    "نوع الفاتورة",
                    "العملة",
                    "المخازن",
                    "المبيعات",
                    "المحاسب",
                    "المستلم",
                    "Mohammad",
                ]
            ):
                continue

            # تصحيح اتجاه النص العربي المعكوس
            fixed_line = fix_reversed_text(line_str)

            if re.search(r"\d", fixed_line):
                extracted_items.append(f"• {fixed_line}")

    except Exception:
        pass

    unique_items = list(dict.fromkeys(extracted_items))
    return unique_items


# قاموس لحفظ بيانات الفواتير المستخرجة من الـ PDF
pdf_data_dict = {}

if zip_file is not None:
    try:
        with zipfile.ZipFile(zip_file, "r") as z:
            pdf_count = 0
            for filename in z.namelist():
                if filename.lower().endswith(".pdf") and not filename.startswith(
                    "__MACOSX"
                ):
                    pdf_count += 1
                    file_basename = filename.split("/")[-1]

                    # استخراج الأرقام من اسم ملف الـ PDF (يحتفظ بالرقم مع البادئة أو بدونها)
                    digits = re.sub(r"\D", "", file_basename)

                    if digits:
                        pdf_bytes = z.read(filename)
                        items = extract_items_from_pdf(pdf_bytes)

                        items_str = (
                            "\n".join(items)
                            if items
                            else "• راجع الفاتورة المرفقة"
                        )

                        # تخزين النتيجة بالأرقام كاملة وبدون البادئة لضمان التطابق 100%
                        pdf_data_dict[digits] = items_str
                        if digits.startswith("100110"):
                            pdf_data_dict[digits[6:]] = items_str

            st.success(f"✅ تم معالجة {pdf_count} ملف PDF بنجاح.")
    except Exception as e:
        st.error(f"❌ خطأ أثناء فتح ملف الـ ZIP: {e}")


def format_number(val):
    try:
        num = float(val)
        if num.is_integer():
            return f"{int(num):,}"
        else:
            return f"{num:,.2f}".rstrip("0").rstrip(".")
    except:
        return str(val)


invoices_list = []

if excel_file is not None:
    df = pd.read_excel(excel_file)
    for _, row in df.iterrows():
        try:
            raw_inv = str(row.iloc[0]).strip()
            inv_digits = re.sub(r"\D", "", raw_inv)  # استخراج الرقم المجرّد

            # مطابقة الرقم الكامل من الإكسل مع ملف الـ PDF
            # يبحث بالرقم الكامل أولاً (مثل 10011029774)، وإذا لم يجده يبحث بالرقم بدون البادئة (29774)
            short_inv_code = re.sub(r"^100110", "", inv_digits)

            items_text = pdf_data_dict.get(
                inv_digits,
                pdf_data_dict.get(short_inv_code, "• راجع الفاتورة المرفقة"),
            )

            raw_currency = str(row.iloc[4]).strip().upper()
            currency = (
                "ريال سعودي"
                if raw_currency == "SR"
                else (
                    "ريال يمني" if raw_currency == "YR" else raw_currency
                )
            )

            customer = str(row.iloc[5]).strip()
            phone = str(row.iloc[6]).strip()
            details = str(row.iloc[7]).strip()

            amount_formatted = format_number(row.iloc[9])
            balance_formatted = format_number(row.iloc[10])

            sms_text = (
                f"محلات البوش للتجاره المركز الرئيسي جدر\n"
                f"الاخ: {customer}\n"
                f"عليكم فاتوره مبيعات: {details}\n"
                f"مبلغ الفاتوره: {amount_formatted} {currency}\n"
                f"وبهذا يكون الرصيد عليكم: {balance_formatted} {currency}\n"
                f"التفاصيل:\n"
                f"{items_text}"
            )
            invoices_list.append(
                {
                    "code": raw_inv,
                    "customer": customer,
                    "phone": phone,
                    "sms_text": sms_text,
                }
            )
        except Exception:
            continue

    st.success(f"تم تجهيز {len(invoices_list)} فاتورة للإرسال.")

st.divider()

if invoices_list:
    st.subheader("📋 تفاصيل طابور الفواتير")
    for idx, inv in enumerate(invoices_list):
        with st.container():
            c1, c2, c3 = st.columns([3, 5, 2])
            with c1:
                st.markdown(f"**العميل:** {inv['customer']}")
                st.markdown(f"**رقم الفاتورة:** `{inv['code']}`")
                st.caption(f"📞 الهاتف: {inv['phone']}")
            with c2:
                st.text_area(
                    "نص الرسالة الجاهزة:",
                    value=inv["sms_text"],
                    height=180,
                    key=f"area_{idx}",
                )
            with c3:
                encoded_msg = urllib.parse.quote(inv["sms_text"])
                sms_url = f"sms:{inv['phone']}?body={encoded_msg}"
                st.link_button(
                    "📲 إرسال عبر الشريحة", sms_url, use_container_width=True
                )
            st.divider()
