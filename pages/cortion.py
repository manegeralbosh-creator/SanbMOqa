import io
import re
import pandas as pd
import streamlit as st
from pypdf import PdfReader

# --- 1. إعدادات الصفحة ---
st.set_page_config(
    page_title="كاشف أرقام الحوالات المفقودة بالـ PDF",
    page_icon="🚨",
    layout="wide"
)

st.title("🚨 كاشف أرقام الحوالات غير المقيدة في ملف الـ PDF")
st.write("استخراج دقيق لأرقام الحوالات بناءً على محددات الكلمات (برقم / رقم / رقم حوالتك) ومطابقتها مع الـ PDF.")

# --- 2. مدخلات البيانات ---
col_text, col_file = st.columns([1, 1])

with col_text:
    bulk_ref_text = st.text_area(
        "1️⃣ الصق الرسائل هنا (تستوعب 100+ رسالة):",
        height=280,
        placeholder=(
            "أمثلة للأنماط المدعومة:\n"
            "1. تم إيداع 50000 ريال برقم 88412 من أحمد علي\n"
            "2. استلمت مبلغ 1500 YER رقم 773954922 رصيدك هو 258113\n"
            "3. تحويل مبلغ 36000 YER 335950184210 رقم حوالتك من فاروق"
        )
    )

with col_file:
    uploaded_pdf = st.file_uploader(
        "2️⃣ ارفع ملف الـ PDF للمطابقة (كشف الحساب / تقرير الحركات):",
        type=["pdf"]
    )

# --- 3. دالة استخراج رقم الحوالة حسب الشروط المقررة ---
def extract_transfer_number(text):
    # الشرك 1: رقم يسبق عبارة "رقم حوالتك" (مثال: 335950184210 رقم حوالتك)
    match_before = re.search(r'(\d+)\s*رقم\s*حوالتك', text)
    if match_before:
        return match_before.group(1).strip()

    # الشرط 2: رقم يأتي بعد كلمة "برقم" أو "رقم" أو "الرقم" مباشرة
    match_after = re.search(r'(?:برقم|رقم|الرقم)\s*:?\s*(\d+)', text)
    if match_after:
        return match_after.group(1).strip()

    return None

# --- 4. المعالجة والبحث ---
if st.button("🔍 بدء فحص ومطابقة أرقام الحوالات", type="primary", use_container_width=True):
    if bulk_ref_text.strip() and uploaded_pdf is not None:
        
        # أ) استخراج كافة النصوص من صفحات ملف الـ PDF
        with st.spinner("جاري استخراج وقراءة نصوص ملف الـ PDF..."):
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
            # تنظيف الترقيم المباشر ببدء السطر مثل (1/ أو 1-)
            clean_line = re.sub(r'^\d+[\/\.-]\s*', '', line).strip()
            
            # استخراج رقم الحوالة
            ref_number = extract_transfer_number(clean_line)

            if ref_number:
                # المطابقة مع نص ملف الـ PDF
                found_in_pdf = ref_number in pdf_full_text

                entry_data = {
                    "رقم الحوالة المستخرج": ref_number,
                    "نص الرسالة كاملة": clean_line,
                    "الحالة": "✅ موجود بالملف" if found_in_pdf else "❌ غير موجود بالملف"
                }

                all_entries.append(entry_data)

                # إضافة إلى قائمة المفقودات إذا لم يُعثر عليه في الـ PDF
                if not found_in_pdf:
                    missing_entries.append({
                        "رقم الحوالة المفقود": ref_number,
                        "نص الرسالة كاملة": clean_line
                    })
            else:
                # في حال لم ينطبق أي شرط لاستخراج الرقم
                all_entries.append({
                    "رقم الحوالة المستخرج": "⚠️ لم يُعثر على رقم مطابق للشروط",
                    "نص الرسالة كاملة": clean_line,
                    "الحالة": "❌ تعذر الاستخراج"
                })

        # --- 5. عرض جدول الحوالات المفقودة والنتائج ---
        st.markdown("---")
        
        df_missing = pd.DataFrame(missing_entries)
        df_all = pd.DataFrame(all_entries)

        total_input = len(all_entries)
        total_missing = len(missing_entries)
        total_found = total_input - total_missing - len(df_all[df_all["الحالة"] == "❌ تعذر الاستخراج"])

        c1, c2, c3 = st.columns(3)
        c1.metric("إجمالي الرسائل المدخلة", total_input)
        c2.metric("حوالات موجودة ومقيدة بالـ PDF", total_found)
        c3.metric("🚨 أرقام حوالات غير موجودة بالـ PDF", total_missing)

        st.markdown("### 🚨 جدول أرقام الحوالات غير الموجودة في ملف الـ PDF:")

        if not df_missing.empty:
            st.warning(f"تم العثور على ({total_missing}) رقم حوالة غير موجود في ملف الـ PDF:")
            st.dataframe(df_missing, use_container_width=True)

            # تنزيل ملف الإكسل للحوالات المفقودة
            excel_buf = io.BytesIO()
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                df_missing.to_excel(writer, index=False, sheet_name='Missing_Transfer_Numbers')
            excel_buf.seek(0)

            st.download_button(
                label="📥 تنزيل جدول أرقام الحوالات المفقودة فقط (Excel)",
                data=excel_buf,
                file_name=f"Missing_Transfers_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.success("🎉 جميع أرقام الحوالات المستخرجة مطابقة وموجودة بالكامل داخل ملف الـ PDF!")

        # عرض الكشف الكلي كخيار ثانوي للمراجعة
        with st.expander("📋 اضغط هنا لاستعراض تقرير المطابقة لكافة الحركات"):
            st.dataframe(df_all, use_container_width=True)

    else:
        st.error("⚠️ يرجى لصق الرسائل النصية ورفع ملف الـ PDF أولاً للبدء.")
