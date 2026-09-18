import streamlit as st
import pandas as pd
from PIL import Image
import io

st.title("التقاط جدول وتحويله إلى Excel")

# 1. نافذة التقاط الصورة أو رفعها
image_file = st.camera_input("التقط صورة الجدول") # أو st.file_uploader("رفع صورة")

if image_file is not None:
    # عرض الصورة الملتقطة
    img = Image.open(image_file)
    st.image(img, caption="الصورة الملتقطة", use_column_width=True)
    
    if st.button("معالجة وتحويل إلى Excel"):
        with st.spinner("جاري قراءة البيانات واستخراج الأرقام المكتوبة..."):
            
            # --- هنا يتم استدعاء نموذج الـ OCR / Vision API ---
            # مثال لبيانات مستخرجة محاكاة للجدول:
            data = [
                {"رقم الصنف": "04-VT-0138-AUTEX", "اسم الصنف": "كف ميزانيه فرامل عربيه الماني", "رقم الكود": "2026919100", "التجزئة": "50", "الجملة": "30.1"},
                {"رقم الصنف": "04-0517452610-AUTEX", "اسم الصنف": "كف ميزانيه فرامل عربيه", "رقم الكود": "2026919101", "التجزئة": "45", "الجملة": "36.78"}
            ]
            
            df = pd.DataFrame(data)
            st.dataframe(df) # عرض الجدول في النافذة
            
            # تحويل البيانات إلى ملف Excel لتحميله
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
            
            st.download_button(
                label="تنزيل ملف Excel",
                data=output.getvalue(),
                file_name="extracted_table.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
