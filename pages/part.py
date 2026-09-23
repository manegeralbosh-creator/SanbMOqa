import pandas as pd
import streamlit as st

# إعدادات الصفحة
st.set_page_config(page_title="كتالوج قطع غيار الشاحنات", layout="wide")

# 1. قاعدة البيانات (يمكنك مستقبلاً قراءتها من ملف Excel مباشرة)
# يمكنك إضافة أي عدد من القطع داخل هذه القائمة
parts_database = [
    {
        "اسم القطعة": "فلتر زيت",
        "النوع": "Volvo",
        "الموديل": "FH16",
        "رقم الوكالة (OEM)": "21707133",
        "الأرقام البديلة": [
            "Hengst: H300W01",
            "Mann: W 11102/34",
            "Donaldson: P550425",
        ],
        "صورة القطعة": "https://via.placeholder.com/300x200.png?text=Volvo+Oil+Filter",
    },
    {
        "اسم القطعة": "فلتر زيت",
        "النوع": "Mercedes Actros",
        "الموديل": "MP4",
        "رقم الوكالة (OEM)": "A4711800209",
        "الأرقام البديلة": [
            "Hengst: E500H D129",
            "Mann: HU 12 001 x",
            "Knecht: OX 823D",
        ],
        "صورة القطعة": "https://via.placeholder.com/300x200.png?text=Actros+Oil+Filter",
    },
    {
        "اسم القطعة": "فلتر جفاف (Air Dryer)",
        "النوع": "Volvo",
        "الموديل": "FH12",
        "رقم الوكالة (OEM)": "20558781",
        "الأرقام البديلة": ["Wabco: 4324102227", "Hengst: T250W"],
        "صورة القطعة": "https://via.placeholder.com/300x200.png?text=Air+Dryer+Filter",
    },
    {
        "اسم القطعة": "فلتر ديزل",
        "النوع": "Iveco",
        "الموديل": "Stralis",
        "رقم الوكالة (OEM)": "504033400",
        "الأرقام البديلة": ["Mann: WK 940/20 x", "Bosch: F026402008"],
        "صورة القطعة": "https://via.placeholder.com/300x200.png?text=Iveco+Fuel+Filter",
    },
]

# تحويل البيانات إلى DataFrame لتسهيل البحث
df = pd.DataFrame(parts_database)

st.title("🚛 نظام البحث عن أرقام قطع غيار الشاحنات")
st.write("اختر اسم القطعة والنوع والموديل لعرض رقم الوكالة والبدائل المتاحة.")

st.divider()

# 2. واجهة خيارات البحث
col1, col2, col3 = st.columns(3)

with col1:
    # قائمة أسماء القطع المتاحة
    available_parts = sorted(list(df["اسم القطعة"].unique()))
    selected_part = st.selectbox("🔧 اسم القطعة:", available_parts)

with col2:
    # تصفية الأنواع المتاحة بناءً على القطعة المختارة
    available_brands = sorted(
        list(df[df["اسم القطعة"] == selected_part]["النوع"].unique())
    )
    selected_brand = st.selectbox("🚛 النوع (الشركة المصنعة):", available_brands)

with col3:
    # تصفية الموديلات المتاحة بناءً على القطعة والنوع
    available_models = sorted(
        list(
            df[
                (df["اسم القطعة"] == selected_part)
                & (df["النوع"] == selected_brand)
            ]["الموديل"].unique()
        )
    )
    selected_model = st.selectbox("📅 الموديل:", available_models)

# 3. زر البحث وعرض النتائج
if st.button("🔍 بحث عن القطعة", type="primary"):
    # البحث في البيانات
    result = df[
        (df["اسم القطعة"] == selected_part)
        & (df["النوع"] == selected_brand)
        & (df["الموديل"] == selected_model)
    ]

    if not result.empty:
        item = result.iloc[0]

        st.success("تم العثور على تفاصيل القطعة!")
        st.divider()

        res_col1, res_col2 = st.columns([2, 1])

        with res_col1:
            st.subheader(f"📌 {item['اسم القطعة']} - {item['النوع']}")

            # عرض رقم الوكالة
            st.markdown(f"**رقم الوكالة الأصلي (OEM):**")
            st.code(item["رقم الوكالة (OEM)"], language="text")

            # عرض الأرقام البديلة
            st.markdown(f"**الأرقام البديلة (Cross Reference):**")
            for alt in item["الأرقام البديلة"]:
                st.write(f"• {alt}")

        with res_col2:
            st.subheader("🖼️ صورة القطعة")
            # عرض صورة القطعة من الرابط
            st.image(item["صورة القطعة"], use_column_width=True)
    else:
        st.error("لم يتم العثور على نتائج تطابق هذه الخيارات.")
