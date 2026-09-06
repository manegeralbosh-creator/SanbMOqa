import io
import re
import pandas as pd
import streamlit as st
from pypdf import PdfReader

# --- 1. إعدادات الصفحة ---
st.set_page_config(
    page_title="كاشف أرقام الحوالات غير المقيدة",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 كاشف أرقام الحوالات غير الموجودة في الـ PDF")
st.write("أداة مخصصة لاستخراج رقم الحوالة (الذي يأتي بعد كلمة 'رقم' مباشرة) ومطابقته مع ملف ה-PDF.")

# --- 2. مدخلات البيانات ---
col_text, col_file = st.columns([1, 1])

with col_text:
    bulk_ref_text = st.text_area(
        "1️⃣ الصق الرسائل هنا (100+ رسالة):",
        height=280,
        placeholder=(
            "أمثلة:\n"
            "تم إيداع 50000 ريال رقم 88412 من أحمد علي\n"
            "استلمت مبلغ 1500 YER رقم 773954922 رصيدك هو 258113\n"
            "حوالة رقم 335950184210 بمبلغ 36000 YER"
        )
    )

with col_file:
    uploaded_pdf = st.file_uploader(
        "2️⃣ ارفع ملف الـ PDF للمطابقة (كشف الحساب / تقرير الحركات):",
        type=["pdf"]
    )

# --- 3. المعالجة والبحث ---
if st.button("🔍 فحص أرقام الحوالات المطابقة وغير المطابقة", type="primary", use_container_width=True):
    if bulk_ref_text.strip() and uploaded_pdf is not None:
        
        # أ) استخراج نص ملف الـ PDF كاملاً
        with st.spinner("جاري قراءة واستخراج نص ملف الـ PDF..."):
            pdf_reader = PdfReader(uploaded_pdf)
            pdf_full_text = ""
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted:
                    pdf_full_text += extracted + "\n"

        raw_lines = [line.strip() for line in bulk_ref_text.splitlines() if line.strip()]
        
        missing_entries = []
        all_entries = []

        for line in raw_lines:
            clean_line = re.sub(r'^\d+[\/\.-]\s*', '', line).strip()
            
            # استخراج الرقم الذي يأتي بعد كلمة "رقم" أو "الرقم" مباشرة فقط
            num_match = re.search(r'(?:رقم|الرقم)\s*:?\s*(\d+)', clean_line)
            
            if num_match:
                ref_number = num_match.group(1).strip()
            else:
                ref_number = "لم يُعثر على رقم بعد كلمة 'رقم'"

            found_in_pdf = False

            # المطابقة في الـ PDF برقم الحوالة المستخرج فقط
            if ref_number.isdigit() and ref_number in pdf_full_text:
                found_in_pdf = True

            entry_data = {
                "رقم الحوالة المستخرج": ref_number,
                "نص الرسالة": clean_line,
                "الحالة": "✅ موجود بالملف" if found_in_pdf else "❌ غير موجود بالملف"
            }

            all_entries.append(entry_data)
            
            if not found_in_pdf:
                missing_entries.append({
                    "رقم الحوالة المفقود": ref_number,
                    "نص الرسالة كاملة": clean_line
                })

        # --- 4. عرض النتائج ---
        st.markdown("---")
        
        df_missing = pd.DataFrame(missing_entries)
        df_all = pd.DataFrame(all_entries)

        total_input = len(all_entries)
        total_missing = len(missing_entries)
        total_found = total_input - total_missing

        c1, c2, c3 = st.columns(3)
        c1.metric("إجمالي الرسائل المدخلة", total_input)
        c2.metric("حوالات موجودة ومقيدة", total_found)
        c3.metric("🚨 أرقام حوالات غير موجودة في الـ PDF", total_missing)

        st.markdown("### 🚨 قائمة أرقام الحوالات غير الموجودة في ملف الـ PDF:")

        if not df_missing.empty:
            st.warning(f"تم العثور على ({total_missing}) رقم حوالة مفقود لم يظهر في ملف الـ PDF:")
            st.dataframe(df_missing, use_container_width=True)

            # تنزيل قائمة المفقودات
            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                df_missing.to_excel(writer, index=False, sheet_name='Missing_Transfer_Numbers')
            excel_buf.seek(0)

            st.download_button(
                label="📥 تنزيل جدول أرقام الحوالات المفقودة فقط (Excel)",
                data=excel_buf,
                file_name=f"Missing_Transfer_Numbers_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.success("🎉 جميع أرقام الحوالات المذكورة بعد كلمة 'رقم' موجودة ومقيدة بالكامل داخل ملف الـ PDF!")

        # عرض التقرير الشامل
        with st.expander("📋 اضغط هنا لرؤية تقرير الفحص الشامل لجميع الحركات"):
            st.dataframe(df_all, use_container_width=True)

    else:
        st.error("⚠️ يرجى لصق الرسائل النصية ورفع ملف الـ PDF أولاً.")
