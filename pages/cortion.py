import io
import re
import pandas as pd
import streamlit as st

# استيراد المكتبات بشكل آمن مع التعامل مع الأخطاء
try:
  import pdfplumber

  PDFPLUMBER_AVAILABLE = True
except ImportError:
  PDFPLUMBER_AVAILABLE = False

try:
  from pypdf import PdfReader

  PYPDF_AVAILABLE = True
except ImportError:
  PYPDF_AVAILABLE = False

# --- 1. إعدادات الصفحة ---
st.set_page_config(
    page_title="كاشف أرقام الحوالات المفقودة", page_icon="🚨", layout="wide"
)

st.title("🚨 كاشف أرقام الحوالات غير المقيدة في كشف الحساب (PDF)")
st.write(
    "يستخرج الكود رقم الحوالة من الرسائل النصية ويتحقق من وجوده حصراً في"
    " البيانات المدخلة بعمود البيان بملف الـ PDF."
)

# التأكد من وجود المكتبات المطلوبة
if not PDFPLUMBER_AVAILABLE and not PYPDF_AVAILABLE:
  st.error(
      "⚠️ يرجى تثبيت مكتبات قراءة الـ PDF عبر تشغيل هذا الأمر في الطرفية:"
      " `pip install pdfplumber pypdf openpyxl pandas streamlit`"
  )
  st.stop()

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


# --- 3. دالة دقيقة لاستخراج رقم الحوالة من الرسالة ---
def extract_transfer_number(text):
  if not text or not isinstance(text, str):
    return None

  # 1. رقم يسبق عبارة "رقم حوالتك"
  match_before = re.search(r'(\d+)\s*رقم\s*حوالتك', text)
  if match_before:
    return match_before.group(1).strip()

  # 2. رقم يأتي بعد كلمة "برقم" أو "رقم" أو "الرقم"
  match_after = re.search(r'(?:برقم|رقم|الرقم)\s*:?\s*(\d+)', text)
  if match_after:
    return match_after.group(1).strip()

  return None


# --- 4. معالجة الـ PDF ومطابقة البيانات ---
if st.button(
    "🔍 بدء الفحص والمطابقة في عمود البيان",
    type="primary",
    use_container_width=True,
):
  if bulk_ref_text.strip() and uploaded_pdf is not None:

    pdf_full_text = ""
    pdf_bytes = uploaded_pdf.read()

    with st.spinner("جاري قراءة وتحليل بيانات كشف الحساب..."):
      # الطريقة الأولى: باستخدام pdfplumber لقراءة الجداول والأعمدة
      if PDFPLUMBER_AVAILABLE:
        try:
          with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
              # استخراج نصوص الجداول
              tables = page.extract_tables()
              for table in tables:
                for row in table:
                  if row:
                    # تجميع خلايا السطر للتأكد من شمول البيان والأرقام الملحقة
                    row_clean = [
                        str(cell).strip() for cell in row if cell is not None
                    ]
                    pdf_full_text += " ".join(row_clean) + "\n"

              # إضافة نص الصفحة كاملاً للتأكد
              page_raw = page.extract_text()
              if page_raw:
                pdf_full_text += page_raw + "\n"
        except Exception as e:
          st.warning(
              "حدث تنبيه عند قراءة الجداول، جاري الانتقال لمُحرك القراءة"
              " الاحتياطي..."
          )

      # الطريقة الثانية الاحتياطية: باستخدام pypdf إذا كان pdfplumber غير كافٍ
      if len(pdf_full_text.strip()) < 10 and PYPDF_AVAILABLE:
        pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in pdf_reader.pages:
          text = page.extract_text()
          if text:
            pdf_full_text += text + "\n"

    # معالجة الرسائل المقابلة
    raw_lines = [
        line.strip() for line in bulk_ref_text.splitlines() if line.strip()
    ]

    missing_entries = []
    all_entries = []

    for line in raw_lines:
      clean_line = re.sub(r'^\d+[\/\.-]\s*', '', line).strip()
      ref_number = extract_transfer_number(clean_line)

      if ref_number:
        # البحث عن الرقم المباشر داخل نص الكشف
        found_in_pdf = ref_number in pdf_full_text

        entry_data = {
            'رقم الحوالة المستخرج': ref_number,
            'نص الرسالة كاملة': clean_line,
            'الحالة': (
                '✅ مقيدة بالبيان' if found_in_pdf else '❌ غير مقيدة بالبيان'
            ),
        }

        all_entries.append(entry_data)

        if not found_in_pdf:
          missing_entries.append({
              'رقم الحوالة المفقود': ref_number,
              'نص الرسالة كاملة': clean_line,
          })
      else:
        all_entries.append({
            'رقم الحوالة المستخرج': '⚠️ تعذر استخراج الرقم',
            'نص الرسالة كاملة': clean_line,
            'الحالة': '❌ لم ينطبق شرط الكلمات (برقم / رقم / رقم حوالتك)',
        })

    # --- 5. عرض النتائج والجداول ---
    st.markdown('---')

    df_missing = pd.DataFrame(missing_entries)
    df_all = pd.DataFrame(all_entries)

    total_input = len(all_entries)
    total_missing = len(missing_entries)
    total_found = (
        total_input
        - total_missing
        - len(df_all[df_all['الحالة'].str.contains('تعذر')])
    )

    c1, c2, c3 = st.columns(3)
    c1.metric('إجمالي الرسائل المدخلة', total_input)
    c2.metric('حوالات موجودة في الـ PDF', total_found)
    c3.metric('🚨 حوالات مفقودة وغير مقيدة', total_missing)

    st.markdown(
        '### 🚨 جدول أرقام الحوالات غير الموجودة في ملف الـ PDF (البيان):'
    )

    if not df_missing.empty:
      st.warning(
          f'تم العثور على ({total_missing}) رقم حوالة مفقود لم يظهر في كشف'
          ' الحساب:'
      )
      st.dataframe(df_missing, use_container_width=True)

      excel_buf = io.BytesIO()
      with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
        df_missing.to_excel(
            writer, index=False, sheet_name='Missing_Transfer_Numbers'
        )
      excel_buf.seek(0)

      st.download_button(
          label='📥 تنزيل جدول الحوالات المفقودة فقط (Excel)',
          data=excel_buf,
          file_name=(
              'Missing_Transfers_'
              f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx"
          ),
          mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          type='primary',
      )
    else:
      st.success(
          '🎉 جميع أرقام الحوالات المستخرجة من النافذة النصية موجودة ومقيدة'
          ' بالكامل داخل الـ PDF!'
      )

    with st.expander('📋 اضغط هنا لاستعراض تقرير الفحص الكامل لجميع الرسائل'):
      st.dataframe(df_all, use_container_width=True)

  else:
    st.error('⚠️ يرجى لصق الرسائل النصية ورفع ملف الـ PDF أولاً.')

