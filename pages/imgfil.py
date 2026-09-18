import streamlit as st
import pandas as pd
import json
import io
from PIL import Image
from google import genai
from google.genai import types

# إعداد واجهة الصفحة
st.set_page_config(page_title="تحويل صور الجداول إلى Excel", layout="wide")

st.title("📊 محول صور الجداول إلى Excel (مجاني عبر Google Gemini)")
st.write("التقط صورة للجدول (سواء كان مطبوعاً أو بخط اليد) وسيتم التعرف عليه واستخراج البيانات إلى ملف Excel بكل دقة.")

# الشريط الجانبي لإدخال المفتاح
st.sidebar.header("⚙️ الإعدادات")
gemini_api_key = st.sidebar.text_input("أدخل مفتاح Gemini API Key المجاني:", type="password")

st.sidebar.markdown("""
---
💡 **كيف تحصل على المفتاح المجاني؟**
1. ادخل إلى [Google AI Studio](https://aistudio.google.com/app/apikey).
2. اضغط على **Create API key**.
3. انسخ المفتاح وانصقه هنا.
""")

if not gemini_api_key:
    st.warning("⚠️ يرجى إدخال مفتاح Google Gemini API في الشريط الجانبي لتفعيل الخدمة مجاناً.")

# اختيار مصدر الصورة
source_option = st.radio("اختر طريقة إدخال الصورة:", ["استخدام الكاميرا 📷", "رفع صورة من الجهاز 📁"])

image_bytes = None

if source_option == "استخدام الكاميرا 📷":
    camera_file = st.camera_input("التقط صورة الجدول")
    if camera_file:
        image_bytes = camera_file.getvalue()
else:
    uploaded_file = st.file_uploader("قم برفع صورة الجدول (PNG, JPG, JPEG)", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        image_bytes = uploaded_file.getvalue()


# دالة إرسال الصورة إلى Gemini واستخراج الجداول
def extract_table_with_gemini(img_bytes, api_key):
    client = genai.Client(api_key=api_key)
    
    prompt = """
    أنت خبير في التعرف الضوئي على الحروف (OCR) ومعالجة المستندات والأسعار وقطع الغيار.
    قم بتحليل صورة الجدول المرفقة واستخراج جميع البيانات المطبوعة والمكتوبة بخط اليد بدقة متناهية.
    
    تعليمات هامة:
    1. استخرج كامل الصفوف والأعمدة الموجودة بالورقة (رقم الصنف، اسم الصنف، رقم الكود، التجزئة، الجملة، إلخ).
    2. حافظ على عناوين الأعمدة كما هي باللغة العربية أو الإنجليزية.
    3. أرجع النتيجة حصراً بصيغة JSON Array بدون أي مقدمات أو شرح أو علامات markdown غير صالحة.
    
    تنسيق الـ JSON المطلوب:
    [
        {"رقم الصنف": "...", "اسم الصنف": "...", "رقم الكود": "...", "التجزئة": "...", "الجملة": "..."},
        ...
    ]
    """
    
    # اسم النموذج المحدث
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            prompt,
            types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg')
        ]
    )
    
    return response.text


# معالجة الصورة عند الضغط على الزر
if image_bytes and gemini_api_key:
    st.image(image_bytes, caption="الصورة المختارة", width=450)
    
    if st.button("🚀 استخراج البيانات وتحويل لـ Excel", type="primary"):
        with st.spinner("جاري قراءة البيانات المطبوعة والخط اليدوي بواسطة الذكاء الاصطناعي..."):
            try:
                raw_response = extract_table_with_gemini(image_bytes, gemini_api_key)
                
                # تنظيف الاستجابة لضمان الحصول على JSON نقي
                cleaned_response = raw_response.strip()
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.startswith("```"):
                    cleaned_response = cleaned_response[3:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()
                
                parsed_data = json.loads(cleaned_response)
                
                # معالجة تفاصيل JSON
                if isinstance(parsed_data, dict):
                    first_key = list(parsed_data.keys())[0]
                    rows = parsed_data[first_key]
                else:
                    rows = parsed_data
                
                # إنشاء dataframe
                df = pd.DataFrame(rows)
                
                st.success("تم استخراج البيانات بنجاح! 🎉")
                st.subheader("📋 عرض الجدول المستخرج:")
                st.dataframe(df, use_container_width=True)
                
                # تحويل الجدول إلى ملف Excel للتنزيل
                excel_io = io.BytesIO()
                with pd.ExcelWriter(excel_io, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='البيانات المستخرجة')
                
                st.download_button(
                    label="📥 تحميل ملف Excel (.xlsx)",
                    data=excel_io.getvalue(),
                    file_name="extracted_table.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
            except Exception as e:
                st.error(f"حدث خطأ أثناء معالجة الصورة: {str(e)}")
