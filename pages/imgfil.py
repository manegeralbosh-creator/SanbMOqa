import streamlit as st
import pandas as pd
import json
import io
import base64
from openai import OpenAI

# إعداد واجهة الصفحة
st.set_page_config(page_title="تحويل المستندات إلى Excel", layout="wide")

st.title("📊 محول صور الجداول إلى Excel")
st.write("التقط صورة للجدول (مطبوع أو بخط اليد) وسيتم التعرف عليه واستخراج البيانات إلى ملف Excel.")

# الشريط الجانبي لإدخال المفتاح
st.sidebar.header("الإعدادات")
api_key = st.sidebar.text_input("أدخل مفتاح OpenAI API Key:", type="password")

if not api_key:
    st.warning("⚠️ يرجى إدخال مفتاح OpenAI API في الشريط الجانبي لتفعيل الخدمة.")

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

# دالة إرسال الصورة للذكاء الاصطناعي واستخراج البيانات
def extract_table_from_image(img_bytes, key):
    client = OpenAI(api_key=key)
    base64_image = base64.b64encode(img_bytes).decode('utf-8')
    
    prompt = """
    قم بتحليل صورة الجدول المرفقة واستخراج كافة البيانات الموجودة بها بدقة عالية.
    تنبيه: الجدول يحتوي على نصوص مطابقة وأرقام/ملاحظات بخط اليد.
    
    أرجع النتيجة بصيغة JSON حصراً على شكل قائمة من الكائنات (List of Objects)، حيث يمثل كل كائن صفاً في الجدول وترتبط المفاتيح بأسماء الأعمدة باللغة العربية كالتالي:
    [
      {"رقم الصنف": "...", "اسم الصنف": "...", "رقم الكود": "...", "التجزئة": "...", "الجملة": "..."},
      ...
    ]
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ],
        max_tokens=3000
    )
    
    return response.choices[0].message.content

# تنفيذ المعالجة وتوليد Excel
if image_bytes and api_key:
    st.image(image_bytes, caption="الصورة المختارة", width=400)
    
    if st.button("🚀 استخراج البيانات وتحويل لـ Excel", type="primary"):
        with st.spinner("جاري تحليل الجدول والخط اليدوي..."):
            try:
                raw_response = extract_table_from_image(image_bytes, api_key)
                
                # تنظيف استجابة النظام للحصول على JSON صالح
                cleaned_response = raw_response.strip().replace("```json", "").replace("```", "")
                parsed_data = json.loads(cleaned_response)
                
                # التعامل مع هيكلية البيانات المرجعة
                if isinstance(parsed_data, dict):
                    first_key = list(parsed_data.keys())[0]
                    rows = parsed_data[first_key]
                else:
                    rows = parsed_data
                
                # إنشاء جدول البيانات
                df = pd.DataFrame(rows)
                
                st.success("تم استخراج البيانات بنجاح! 🎉")
                st.subheader("عرض البيانات المستخرجة:")
                st.dataframe(df, use_container_width=True)
                
                # تحويل الجدول إلى ملف Excel للتنزيل
                excel_io = io.BytesIO()
                with pd.ExcelWriter(excel_io, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='البيانات')
                
                st.download_button(
                    label="📥 تحميل ملف Excel (.xlsx)",
                    data=excel_io.getvalue(),
                    file_name="extracted_table.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
            except Exception as e:
                st.error(f"حدث خطأ أثناء استخراج البيانات: {str(e)}")
