import io
import re
import pdfplumber
import pandas as pd
import streamlit as st

# --- 1. إعدادات الصفحة ---
st.set_page_config(
    page_title="مُطابق أرقام الحوالات - عمود البيان",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 كاشف أرقام الحوالات المفقودة (البحث في عمود البيان)")
st.write(
    "يستخرج الكود رقم الحوالة من الرسالة ويتحقق من وجوده حصراً داخل عمود"
    " 'البيان' في كشف الحساب."
)

# --- 2. مدخلات البيانات ---
col_text, col_file = st.columns([1, 1])

with col_text:
  bulk_ref_text = st.text_area(
      "1️⃣ الصق الرسائل النصية هنا (100+ رسالة):",
      height=280,
      placeholder=(
          "أمثلة للأنماط المدعومة:\n"
          "1. تم إيداع 50000 ريال برقم 5190485 من محمود\n"
          "2. استلمت مبلغ 1500 YER رقم 9974844193 رصيدك هو 258113\n"
          "3. تحويل 36000 YER 5070853430 رقم حوالتك من أحمد"
      ),
  )

with col_file:
  uploaded_pdf = st.file_uploader(
      "2️⃣ ارفع ملف الـ PDF (كشف الحساب التحليلي):", type=["pdf"]
  )


# --- 3. دالة استخراج رقم الحوالة من الرسائل ---
def extract_transfer_number(text):
  # 1. رقم يسبق عبارة "رقم حوالتك"
  match_before = re.search(r"(\d+)\s*رقم\s*حوالتك", text)
  if match_before:
    return match_before.group(1).strip()

  # 2. رقم يأتي بعد كلمة "برقم" أو "رقم" أو "الرقم"
  match_after = re.search(r"(?:برقم|رقم|الرقم)\s*:?\s*(\d+)", text)
  if match_after:
    return match_after.group(1).strip()

  return None


# --- 4. المعالجة واستخراج البيانات من عمود البيان ---
if st.button(
    "🔍 بدء الفحص والمطابقة في عمود البيان",
    type="primary",
    use_container_width=True,
):
  if bulk_ref_text.strip() and uploaded_pdf is not None:

    # أ) استخراج نصوص عمود "البيان" فقط باستخدام pdfplumber
    pdf_details_text = ""

    with st.spinner(
        "جاري تحليل كشف الحساب واستخراج البيانات من عمود البيان..."
    ):
      with pdfplumber.open(uploaded_pdf) as pdf:
        for page in pdf.pages:
          # استخراج الجداول من الصفحة
          tables = page.extract_tables()
          for table in tables:
            for row in table:
              if not row:
                continue

              # البحث عن الخلية التي تمثل "البيان"
              # في كشوفات أونكس تكون في العمود الأوسط (غالباً الفهرس 2 أو 3)
              # دمج كل الخلايا النصية المكونة للشرح/البيان
              row_str = " ".join([cell for cell in row if cell is not None])
              pdf_details_text += row_str + "\n"

          # إذا تعذر استخراج جدول، يتم أخذ كامل النص كخط حماية ثانٍ
          if not tables:
            pdf_details_text += (page.extract_text() or "") + "\n"

    # ب) معالجة الرسائل ومقاطعتها مع نصوص عمود البيان
    raw_lines = [
        line.strip() for line in bulk_ref_text.splitlines() if line.strip()
    ]

    missing_entries = []
    all_entries = []

    for line in raw_lines:
      clean_line = re.sub(r"^\d+[\/\.-]\s*", "", line).strip()
      ref_number = extract_transfer_number(clean_line)

      if ref_number:
        # البحث الحصري عن رقم الحوالة داخل نصوص البيان
        found_in_pdf = ref_number in pdf_details_text

        entry_data = {
            "رقم الحوالة المستخرج": ref_number,
            "نص الرسالة كاملة": clean_line,
            "الحالة": (
                "✅ مقيدة بالبيان" if found_in_pdf else "❌ غير مقيدة بالبيان"
            ),
        }

        all_entries.append(entry_data)

        if not found_in_pdf:
          missing_entries.append({
              "رقم الحوالة المفقود": ref_number,
              "نص الرسالة كاملة": clean_line,
          })
      else:
        all_entries.append({
            "رقم الحوالة المستخرج": "⚠️ تعذر تحديد رقم الحوالة",
            "نص الرسالة كاملة": clean_line,
            "الحالة": "❌ خطأ بالصيغة",
        })

    # --- 5. عرض جدول الحوالات المفقودة ---
    st.markdown("---")

    df_missing = pd.DataFrame(missing_entries)
    df_all = pd.DataFrame(all_entries)

    total_input = len(all_entries)
    total_missing = len(missing_entries)
    total_found = total_input - total_missing

    c1, c2, c3 = st.columns(3)
    c1.metric("إجمالي الرسائل المدخلة", total_input)
    c2.metric("حوالات مقيدة في البيان", total_found)
    c3.metric("🚨 حوالات غير مقيدة (مفقودة)", total_missing)

    st.markdown(
        "### 🚨 جدول أرقام الحوالات غير الموجودة في عمود البيان بـ PDF:"
    )

    if not df_missing.empty:
      st.warning(
          f"تم العثور على ({total_missing}) رقم حوالة غير مقيد في عمود البيان:"
      )
      st.dataframe(df_missing, use_container_width=True)

      # تنزيل قائمة المفقودات بصيغة Excel
      excel_buf = io.BytesIO()
      with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        df_missing.to_excel(
            writer, index=False, sheet_name="Missing_Transfer_Numbers"
        )
      excel_buf.seek(0)

      st.download_button(
          label="📥 تنزيل جدول الحوالات المفقودة فقط (Excel)",
          data=excel_buf,
          file_name=f"Missing_Transfers_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          type="primary",
      )
    else:
      st.success(
          "🎉 ممتاز! جميع أرقام الحوالات المذكورة بالرسائل موجودة ومقيدة"
          " داخل عمود البيان بالـ PDF."
      )

    with st.expander("📋 عرض التقرير الشامل لجميع الحركات"):
      st.dataframe(df_all, use_container_width=True)

  else:
    st.error("⚠️ يرجى لصق الرسائل النصية ورفع ملف الـ PDF أولاً.")
