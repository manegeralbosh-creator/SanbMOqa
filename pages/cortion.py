import io
import re
import pandas as pd
import streamlit as st
from pypdf import PdfReader

# --- 1. إعدادات الصفحة ---
st.set_page_config(
    page_title="كاشف الحوالات غير المقيدة في PDF",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 كاشف أرقام الحوالات المفقودة غير الموجودة في الـ PDF")
st.write("أداة سريعة لاستخراج واستعراض أرقام الحوالات والمراجع التي لم يتم قيدها في تقرير الـ PDF.")

# --- 2. مدخلات البيانات ---
col_text, col_file = st.columns([1, 1])

with col_text:
    bulk_ref_text = st.text_area(
        "1️⃣ الصق الرسائل/أرقام الحوالات هنا (100+ رسالة):",
        height=280,
        placeholder=(
            "أمثلة:\n"
            "أضيف 30000ر.ي مشتريات رص:220611.7ر.ي من 9895218 م:17891983578541\n"
            "استلمت مبلغ 1500 YER من 773954922 رصيدك هو 258113.19\n"
            "لقد استلمت 36000 YER كقيمة مشتريات من بمرجع 335950184210 من فاروق علي مطهر الحميدي"
        )
    )

with col_file:
    uploaded_pdf = st.file_uploader(
        "2️⃣ ارفع ملف الـ PDF للمطابقة (كشف الحساب / تقرير الحركات):",
        type=["pdf"]
    )

# --- 3. المعالجة والبحث ---
if st.button("🔍 فحص وكشف الحوالات غير الموجودة بالـ PDF", type="primary", use_container_width=True):
    if bulk_ref_text.strip() and uploaded_pdf is not None:
        
        # أ) استخراج كل نصوص ملف الـ PDF
        with st.spinner("جاري قراءة واستخراج نص ملف الـ PDF..."):
            pdf_reader = PdfReader(uploaded_pdf)
            pdf_full_text = ""
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted:
                    pdf_full_text += extracted + "\n"

        # ب) معالجة الرسائل خطوة بخطوة
        raw_lines = [line.strip() for line in bulk_ref_text.splitlines() if line.strip()]
        
        missing_entries = []
        all_entries = []

        for line in raw_lines:
            clean_line = re.sub(r'^\d+[\/\.-]\s*', '', line).strip()
            
            # استخراج أرقام الحوالات/المراجع/الهواتف
            ref_numbers = re.findall(r'\b\d{4,16}\b', clean_line)

            # استخراج الاسم بعد كلمة "من"
            name_match = re.search(r'من\s*([^\d:\n\r]+)', clean_line)
            sender_name = name_match.group(1).strip() if name_match else ""
            sender_name = re.sub(r'\s*(رصيد|رص:|رصيدك|م:|مرجع).*$', '', sender_name, flags=re.IGNORECASE).strip()

            found_in_pdf = False
            matched_key = ""

            # مطابقة الأرقام
            for num in ref_numbers:
                if num in pdf_full_text:
                    found_in_pdf = True
                    matched_key = num
                    break

            # مطابقة الاسم إن لم يُعثر على رقم
            if not found_in_pdf and sender_name and len(sender_name) > 3:
                if sender_name in pdf_full_text:
                    found_in_pdf = True
                    matched_key = sender_name

            ref_primary = ", ".join(ref_numbers) if ref_numbers else (sender_name if sender_name else "غير محدد")

            entry_data = {
                "رقم الحوالة / المرجع المفقود": ref_primary,
                "نص الرسالة كاملة": clean_line,
                "الحالة": "❌ غير موجود بالملف" if not found_in_pdf else "✅ موجود"
            }

            all_entries.append(entry_data)
            if not found_in_pdf:
                missing_entries.append({
                    "رقم الحوالة / المرجع المفقود": ref_primary,
                    "نص الرسالة كاملة": clean_line
                })

        # --- 4. عرض النتائج المباشرة ---
        st.markdown("---")
        
        df_missing = pd.DataFrame(missing_entries)
        df_all = pd.DataFrame(all_entries)

        total_input = len(all_entries)
        total_missing = len(missing_entries)
        total_found = total_input - total_missing

        c1, c2, c3 = st.columns(3)
        c1.metric("إجمالي الحوالات بالنافذة", total_input)
        c2.metric("حوالات مقيدة وموجودة", total_found)
        c3.metric("🚨 أرقام حوالات غير موجودة في الـ PDF", total_missing)

        st.markdown("### 🚨 قائمة أرقام الحوالات والرسائل غير الموجودة في ملف الـ PDF:")

        if not df_missing.empty:
            st.warning(f"تم العثور على ({total_missing}) حركة مفقودة لم تظهر في ملف ה-PDF:")
            st.dataframe(df_missing, use_container_width=True)

            # تنزيل قائمة المفقودات فقط
            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                df_missing.to_excel(writer, index=False, sheet_name='Missing_Transactions')
            excel_buf.seek(0)

            st.download_button(
                label="📥 تنزيل جدول الحوالات المفقودة فقط (Excel)",
                data=excel_buf,
                file_name=f"Missing_PDF_References_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.success("🎉 جميع أرقام الحوالات والمراجع الموجودة في النافذة مطابقة ومقيدة بالكامل داخل ملف الـ PDF!")

        # عرض الكشف الشامل كخيار ثانوي
        with st.expander("📋 اضغط هنا لرؤية تقرير الفحص الشامل (الموجود وغير الموجود)"):
            st.dataframe(df_all, use_container_width=True)

    else:
        st.error("⚠️ يرجى لصق الرسائل النصية ورفع ملف الـ PDF أولاً.")
