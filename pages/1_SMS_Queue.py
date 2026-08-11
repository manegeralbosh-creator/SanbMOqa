import io
import re
import urllib.parse
import zipfile
import pandas as pd
import pdfplumber
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


def extract_clean_number(text):
    if not text:
        return ""
    return re.sub(r"\D", "", str(text))


def clean_arabic_words(text):
    if not text:
        return ""
    # عكس السطر بالكامل لتصحيح تشفير أونكس برو
    fixed_line = str(text)[::-1]
    arabic_words = re.findall(r"[\u0600-\u06FF]+", fixed_line)
    clean_words = [w for w in arabic_words if len(w) > 1]
    # أخذ أول 1 إلى 3 كلمات فقط
    return " ".join(clean_words[:3])


def format_quantity(qty_str):
    try:
        val = float(qty_str)
        if val.is_integer():
            return str(int(val))
        return f"{val:.2f}".rstrip("0").rstrip(".")
    except:
        return qty_str.strip()


def parse_pdf_content(pdf_bytes):
    items_formatted = []

    # قائمة استبعاد شاملة ومحكمة للترويسات والإجماليات والتفقيط
    ignore_keywords = [
        "البوش",
        "الرئيسي",
        "فاتورة",
        "الفاتورة",
        "إجمالي",
        "جمالي",
        "العميل",
        "الرصيد",
        "التاريخ",
        "المبلغ",
        "الصافي",
        "تلفن",
        "موبايل",
        "نوع",
        "العملة",
        "المخازن",
        "المبيعات",
        "المحاسب",
        "المستلم",
        "الصنف",
        "الوحدة",
        "الكمية",
        "السعر",
        "الخصم",
        "مصنع",
        "خمسمائة",
        "سبعة",
        "ريال",
        "سعودي",
        "يمني",
        "رقم",
        "Onyx",
    ]

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                for line in text.split("\n"):
                    line_str = line.strip()
                    if not line_str or len(line_str) < 3:
                        continue

                    # تصحيح النص المعكوس أولاً
                    reversed_line = line_str[::-1]

                    # فحص الاستبعاد على السطرين (الأصلي والمعكوس)
                    if any(
                        kw in line_str or kw in reversed_line
                        for kw in ignore_keywords
                    ):
                        continue

                    # استخراج وتصحيح اسم الصنف
                    item_name = clean_arabic_words(line_str)

                    # استبعاد إضافي في حال تسربت كلمة إدارية داخل اسم الصنف
                    if not item_name or any(
                        kw in item_name
                        for kw in [
                            "الفاتورة",
                            "المخازن",
                            "المبيعات",
                            "المحاسب",
                            "جمالي",
                            "خمسمائة",
                            "سعودي",
                        ]
                    ):
                        continue

                    # الشرط المتفق عليه: فحص القماش والطقوم فقط للكمية
                    is_fabric_item = any(
                        kw in item_name for kw in ["قماش", "طقم"]
                    )

                    if is_fabric_item:
                        numbers = re.findall(r"\b\d+(?:\.\d+)?\b", line_str)
                        possible_qtys = [
                            n for n in numbers if float(n) < 100
                        ]

                        if possible_qtys:
                            qty = format_quantity(possible_qtys[0])
                            items_formatted.append(f"{qty}/{item_name}")
                        else:
                            items_formatted.append(f"• {item_name}")
                    else:
                        # الأصناف العادية بدون أرقام
                        items_formatted.append(f"• {item_name}")

    except Exception:
        pass

    unique_items = list(dict.fromkeys(items_formatted))
    return (
        "\n".join(unique_items) if unique_items else "• راجع الفاتورة المرفقة"
    )


pdf_catalog = {}

if zip_file is not None:
    try:
        with zipfile.ZipFile(zip_file, "r") as z:
            pdf_count = 0
            for filename in z.namelist():
                if filename.lower().endswith(".pdf") and not filename.startswith(
                    "__MACOSX"
                ):
                    pdf_count += 1
                    pdf_bytes = z.read(filename)
                    content_summary = parse_pdf_content(pdf_bytes)

                    digits_in_name = extract_clean_number(
                        filename.split("/")[-1]
                    )

                    if digits_in_name:
                        pdf_catalog[digits_in_name] = content_summary
                        if len(digits_in_name) >= 5:
                            pdf_catalog[digits_in_name[-5:]] = content_summary
                        if len(digits_in_name) >= 6:
                            pdf_catalog[digits_in_name[-6:]] = content_summary

            st.success(f"✅ تم تحليل وتجهيز {pdf_count} ملف PDF.")
    except Exception as e:
        st.error(f"❌ خطأ أثناء قراءة ملف الـ ZIP: {e}")


def format_num(val):
    try:
        num = float(val)
        return f"{int(num):,}" if num.is_integer() else f"{num:,.2f}"
    except:
        return str(val)


invoices_list = []

if excel_file is not None:
    df = pd.read_excel(excel_file)
    for _, row in df.iterrows():
        try:
            raw_inv = str(row.iloc[0]).strip()
            digits_excel = extract_clean_number(raw_inv)

            if not digits_excel:
                continue

            items_details = (
                pdf_catalog.get(digits_excel)
                or pdf_catalog.get(digits_excel[-5:])
                or pdf_catalog.get(digits_excel[-6:])
                or "• راجع الفاتورة المرفقة"
            )

            raw_curr = str(row.iloc[4]).strip().upper()
            curr_str = (
                "ريال سعودي"
                if raw_curr == "SR"
                else ("ريال يمني" if raw_curr == "YR" else raw_curr)
            )

            customer = str(row.iloc[5]).strip()
            phone = str(row.iloc[6]).strip()
            inv_type_desc = str(row.iloc[7]).strip()

            amount = format_num(row.iloc[9])
            balance = format_num(row.iloc[10])

            sms_body = (
                f"محلات البوش للتجاره المركز الرئيسي جدر\n"
                f"الاخ: {customer}\n"
                f"عليكم فاتوره مبيعات: {inv_type_desc}\n"
                f"مبلغ الفاتوره: {amount} {curr_str}\n"
                f"وبهذا يكون الرصيد عليكم: {balance} {curr_str}\n"
                f"التفاصيل:\n"
                f"{items_details}"
            )

            invoices_list.append(
                {
                    "code": raw_inv,
                    "customer": customer,
                    "phone": phone,
                    "sms_text": sms_body,
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
