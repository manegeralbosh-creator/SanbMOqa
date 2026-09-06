import io
import re
import pandas as pd
import streamlit as st
from pypdf import PdfReader

# --- 1. ضبط إعدادات الصفحة ---
st.set_page_config(
    page_title="أداة مطابقة الحوالات مع الـ PDF",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 أداة مطابقة رسائل الحوالات مع تقارير PDF")
st.write("أداة مستقلة للتحقق من تقييد أرقام الحوالات والمراجع في أونكس برو/كشوف الحسابات.")

# --- 2. واجهة المدخلات ---
col_text, col_file = st.columns([1, 1])

with col_text:
    bulk_ref_text = st.text_area(
        "1️⃣ الصق الرسائل/أرقام الحوالات هنا (تستوعب 100+ رسالة):",
        height=300,
        placeholder=(
            "أمثلة:\n"
            "أضيف 30000ر.ي مشتريات رص:220611.7ر.ي من 9895218 م:17891983578541\n"
            "استلمت مبلغ 1500 YER من 773954922 رصيدك هو 258113.19\n"
            "لقد استلمت 36000 YER كقيمة مشتريات من بمرجع 335950184210 من فاروق علي مطهر الحميدي"
        )
    )

with col_file:
    uploaded_pdf = st.file_uploader(
        "2️⃣ ارفع ملف الـ PDF المراد المطابقة معه (كشف حساب / تقرير القيود):",
        type=["pdf"]
    )
    st.info("💡 يقوم النظام بقراءة كافة صفحات الـ PDF والبحث عن أرقام الحوالات، أرقام المراجع، أو أرقام الهواتف والأسماء المذكورة بالرسائل.")

# --- 3. معالجة البيانات والمطابقة ---
if st.button("🔎 بدء عملية المطابقة والتحقق", type="primary", use_container_width=True):
    if bulk_ref_text.strip() and uploaded_pdf is not None:
        
        # أ) قراءة واستخراج النصوص من ملف ה-PDF
        with st.spinner("جاري قراءة واستخراج النصوص من ملف الـ PDF..."):
            pdf_reader = PdfReader(uploaded_pdf)
            pdf_full_text = ""
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted:
                    pdf_full_text += extracted + "\n"

        # ب) تفكيك الرسائل المدخلة (سطر بسطر)
        raw_lines = [line.strip() for line in bulk_ref_text.splitlines() if line.strip()]
        matching_results = []

        # ج) معالجة كل رسالة ومطابقتها مع نص الـ PDF
        for line in raw_lines:
            # تنظيف الترقيم المباشر في بداية السطر مثل (1/ أو 1-)
            clean_line = re.sub(r'^\d+[\/\.-]\s*', '', line).strip()
            
            # استخراج الأرقام التي يتراوح طولها بين 4 إلى 16 رقم (أرقام مرجع / نقطة / جوال)
            ref_numbers = re.findall(r'\b\d{4,16}\b', clean_line)

            # استخراج الاسم القادم بعد كلمة "من"
            name_match = re.search(r'من\s*([^\d:\n\r]+)', clean_line)
            sender_name = name_match.group(1).strip() if name_match else ""
            
            # تنظيف الاسم من العبارات الزائدة
            sender_name = re.sub(r'\s*(رصيد|رص:|رصيدك|م:|مرجع).*$', '', sender_name, flags=re.IGNORECASE).strip()

            found_in_pdf = False
            matched_keyword = ""

            # 1. مطابقة الأرقام أولاً داخل نص ה-PDF
            for num in ref_numbers:
                if num in pdf_full_text:
                    found_in_pdf = True
                    matched_keyword = num
                    break

            # 2. إذا لم يجد الأرقام، يتم البحث باسم الشخص إذا كان موجوداً
            if not found_in_pdf and sender_name and len(sender_name) > 3:
                if sender_name in pdf_full_text:
                    found_in_pdf = True
                    matched_keyword = sender_name

            # تحديد العبارة المرجعية للعرض
            ref_display = ", ".join(ref_numbers) if ref_numbers else (sender_name if sender_name else "غير محدد")

            matching_results.append({
                "الرسالة النصية": clean_line,
                "رقم المرجع / المعرف": ref_display,
                "حالة التقييد": "✅ مقيدة بالملف" if found_in_pdf else "❌ غير مقيدة",
                "القيمة المطابقة بالملف": matched_keyword if found_in_pdf else "-"
            })

        df_results = pd.DataFrame(matching_results)

        # --- 4. عرض النتائج والتقارير ---
        st.markdown("---")
        st.subheader("📊 ملخص نتائج المطابقة")

        total_msg = len(df_results)
        matched_count = len(df_results[df_results["حالة التقييد"] == "✅ مقيدة بالملف"])
        unmatched_count = total_msg - matched_count

        m1, m2, m3 = st.columns(3)
        m1.metric("إجمالي الرسائل المدخلة", total_msg)
        m2.metric("الحوالات المقيدة بالملف", matched_count)
        m3.metric("الحوالات التي لم تقيد بعد", unmatched_count)

        # عرض الحوالات التي لم تقيد أولاً
        st.markdown("### ⚠️ 1. الحوالات والرسائل التي لم تُقيد في ملف الـ PDF:")
        df_unmatched = df_results[df_results["حالة التقييد"] == "❌ غير مقيدة"]

        if not df_unmatched.empty:
            st.dataframe(df_unmatched, use_container_width=True)
        else:
            st.success("🎉 ممتااااز! كافة الحوالات والرسائل مدخلة ومقيدة بالكامل في ملف الـ PDF.")

        st.markdown("### 📋 2. التقرير التفصيلي لكافة الحركات:")
        st.dataframe(df_results, use_container_width=True)

        # إمكانية تنزيل التقرير بصيغة Excel
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
            df_results.to_excel(writer, index=False, sheet_name='Matching_Report')
        excel_buf.seek(0)

        st.download_button(
            label="📥 تنزيل تقرير المطابقة كاملاً (Excel)",
            data=excel_buf,
            file_name=f"PDF_Reconciliation_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )

    else:
        st.error("⚠️ يرجى إدخال الرسائل النصية ورفع ملف الـ PDF أولاً لتشغيل عملية المطابقة.")
