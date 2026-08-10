import io
import re
import urllib.parse
import zipfile
import pandas as pd
import pdfplumber
import streamlit as st

st.set_page_config(page_title="طابور الفواتير", page_icon="📱", layout="wide")

st.title("📱 طابور إرسال الفواتير عبر الشريحة")

# 1. قسم رفع الملفات
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


# ---------------------------------------------------------
# الدالة المعدلة لاستخراج (اسم الصنف + الكمية) فقط من الـ PDF
# ---------------------------------------------------------
def extract_raw_and_clean_items(pdf_bytes):
    raw_text_debug = ""
    items_list = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                raw_text_debug += (
                    (page.extract_text() or "") + "\n--- نهاية الصفحة ---\n"
                )

                # استخراج الجداول
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        # التأكد من أن السطر يحتوي على بيانات صنف (يتضمن 3 أعمدة على الأقل)
                        if (
                            row
                            and len(row) >= 3
                            and row[0]
                            and row[0] != "رقم الصنف"
                        ):
                            # استبعاد أسطر الإجماليات والخصم
                            if any(
                                kw in str(row)
                                for kw in ["الإجمالي", "الخصم", "فقط لاغير"]
                            ):
                                continue

                            # العمود [1] يحتوي اسم الصنف، والعمود [2] يحتوي الكمية حسب تصميم الفاتورة
                            item_name = str(row[1]).strip() if row[1] else ""
                            qty = str(row[2]).strip() if row[2] else ""

                            # تحويل أرقام الكمية الفعالة إلى أرقام صحيحة إذا لم تكن كسوراً
                            if qty.endswith(".00") or qty.endswith(".0"):
                                qty = qty.split(".")[0]

                            if item_name:
                                items_list.append(f"• {item_name} (الكمية: {qty})")

    except Exception as e:
        raw_text_debug = f"خطأ في القراءة: {e}"

    # إزالة التكرارات مع الحفاظ على الترتيب
    unique_items = list(dict.fromkeys(items_list))
    return raw_text_debug, unique_items


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
                    digits_only = re.sub(r"\D", "", file_basename)

                    pdf_bytes = z.read(filename)
                    raw_debug, extracted_items = extract_raw_and_clean_items(
                        pdf_bytes
                    )

                    pdf_data_dict[digits_only] = {
                        "items_text": (
                            "\n".join(extracted_items)
                            if extracted_items
                            else "• راجع الفاتورة المرفقة"
                        ),
                        "raw_debug": (
                            raw_debug
                            if raw_debug
                            else "لم يتم استخراج أي نص خام من الملف (قد تكون الفاتورة عبارة عن صورة ممسوحة ضوئياً)."
                        ),
                    }

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
            inv_code = re.sub(r"\D", "", raw_inv)

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

            pdf_info = pdf_data_dict.get(
                inv_code,
                {
                    "items_text": "• راجع الفاتورة المرفقة",
                    "raw_debug": "لم يتم العثور على ملف PDF مطليق لهذا الرقم.",
                },
            )

            sms_text = (
                f"محلات البوش للتجاره المركز الرئيسي جدر\n"
                f"الاخ: {customer}\n"
                f"عليكم فاتوره مبيعات: {details}\n"
                f"مبلغ الفاتوره: {amount_formatted} {currency}\n"
                f"وبهذا يكون الرصيد عليكم: {balance_formatted} {currency}\n"
                f"التفاصيل:\n"
                f"{pdf_info['items_text']}"
            )
            invoices_list.append(
                {
                    "code": inv_code,
                    "customer": customer,
                    "phone": phone,
                    "sms_text": sms_text,
                    "raw_debug": pdf_info["raw_debug"],
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
            c1, c2, c3 = st.columns([3, 4, 3])
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
                with st.expander(
                    "🔍 معاينة النص الخام المستخرج من الـ PDF"
                ):
                    st.code(inv["raw_debug"], language="text")
            with c3:
                encoded_msg = urllib.parse.quote(inv["sms_text"])
                sms_url = f"sms:{inv['phone']}?body={encoded_msg}"
                st.link_button(
                    "📲 إرسال عبر الشريحة", sms_url, use_container_width=True
                )
            st.divider()
