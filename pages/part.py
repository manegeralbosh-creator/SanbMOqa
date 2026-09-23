import pandas as pd
import streamlit as st

# إعدادات الصفحة
st.set_page_config(
    page_title="كتالوج قطع غيار الشاحنات الذكي",
    layout="wide",
    page_icon="🚛",
)

# 1. قاعدة بيانات نموذجية لكتالوج واقعي (يمكن استبدالها بملف Excel بأسطر محدودة)
# في التطبيق الحقيقي سنقوم بـ: df = pd.read_excel('truck_parts_catalog.xlsx')
data = [
    {
        "اسم القطعة": "فلتر زيت",
        "النوع": "Volvo",
        "الموديل": "FH16 / FH12",
        "رقم الوكالة (OEM)": "21707133",
        "الشركات البديلة (Cross Reference)": "Hengst: H300W01 | Mann: W 11102/34 | Donaldson: P550425",
        "صورة القطعة": "https://via.placeholder.com/250x180.png?text=Volvo+21707133",
    },
    {
        "اسم القطعة": "فلتر زيت",
        "النوع": "Mercedes Actros",
        "الموديل": "MP4 / Euro 6",
        "رقم الوكالة (OEM)": "A4711800209",
        "الشركات البديلة (Cross Reference)": "Hengst: E500H D129 | Mann: HU 12 001 x | Knecht: OX 823D",
        "صورة القطعة": "https://via.placeholder.com/250x180.png?text=Actros+A4711800209",
    },
    {
        "اسم القطعة": "فلتر جفاف (Air Dryer)",
        "النوع": "Volvo",
        "الموديل": "FH12 / FM",
        "رقم الوكالة (OEM)": "20558781",
        "الشركات البديلة (Cross Reference)": "Wabco: 4324102227 | Hengst: T250W | Knorr: II19483",
        "صورة القطعة": "https://via.placeholder.com/250x180.png?text=Volvo+20558781",
    },
    {
        "اسم القطعة": "فلتر ديزل",
        "النوع": "Iveco",
        "الموديل": "Stralis / Trakker",
        "رقم الوكالة (OEM)": "504033400",
        "الشركات البديلة (Cross Reference)": "Mann: WK 940/20 x | Bosch: F026402008",
        "صورة القطعة": "https://via.placeholder.com/250x180.png?text=Iveco+504033400",
    },
    {
        "اسم القطعة": "طقم كلتش (Clutch Kit)",
        "النوع": "Mercedes Actros",
        "الموديل": "MP2 / MP3",
        "رقم الوكالة (OEM)": "A0222506801",
        "الشركات البديلة (Cross Reference)": "Sachs: 3400700343 | Valeo: 827250",
        "صورة القطعة": "https://via.placeholder.com/250x180.png?text=Actros+Clutch",
    },
]

df = pd.DataFrame(data)

# عنوان التطبيق
st.title("🚛 كتالوج واستعلام قطع غيار الشاحنات (OEM & البدائل)")
st.caption(
    "ابحث برقم القطعة، أرقام البدائل (Hengst, Mann)، اسم القطعة، أو النوع والموديل."
)

st.divider()

# 🔍 2. شريط البحث السريع والذكي (Search Bar)
search_query = st.text_input(
    "🔎 **شريط البحث الشامل:** (أدخل رقم الوكالة OEM، رقم بديل مثل Hengst/Mann، أو اسم القطعة)",
    placeholder="مثال: 21707133 أو H300W01 أو فلتر زيت أو Actros...",
)

st.markdown("### أو تصفية البحث عبر الاختيارات:")

# 3. القوائم المنسدلة للفلترة المتقدمة
col1, col2, col3 = st.columns(3)

with col1:
    part_filter = st.selectbox(
        "اسم القطعة:", ["الكل"] + sorted(list(df["اسم القطعة"].unique()))
    )
with col2:
    brand_filter = st.selectbox(
        "النوع (الشركة):", ["الكل"] + sorted(list(df["النوع"].unique()))
    )
with col3:
    # تصفية الموديلات بحسب النوع
    if brand_filter != "الكل":
        filtered_models = df[df["النوع"] == brand_filter]["الموديل"].unique()
    else:
        filtered_models = df["الموديل"].unique()
    model_filter = st.selectbox(
        "الموديل:", ["الكل"] + sorted(list(filtered_models))
    )

# 4. فلترة البيانات بناءً على البحث النصي والاختيارات
results_df = df.copy()

# الفلترة بالشريط النصي للبحث
if search_query:
    q = search_query.strip().lower()
    results_df = results_df[
        results_df["اسم القطعة"].str.lower().str.contains(q)
        | results_df["النوع"].str.lower().str.contains(q)
        | results_df["الموديل"].str.lower().str.contains(q)
        | results_df["رقم الوكالة (OEM)"].str.lower().str.contains(q)
        | results_df["الشركات البديلة (Cross Reference)"]
        .str.lower()
        .str.contains(q)
    ]

# الفلترة بالقوائم المنسدلة
if part_filter != "الكل":
    results_df = results_df[results_df["اسم القطعة"] == part_filter]
if brand_filter != "الكل":
    results_df = results_df[results_df["النوع"] == brand_filter]
if model_filter != "الكل":
    results_df = results_df[results_df["الموديل"] == model_filter]

st.divider()

# 5. عرض النتائج
st.subheader(f"📋 نتائج البحث ({len(results_df)} قطعة)")

if not results_df.empty:
    for idx, row in results_df.iterrows():
        with st.container():
            c1, c2 = st.columns([2, 1])

            with c1:
                st.markdown(f"### ⚙️ {row['اسم القطعة']} - {row['النوع']}")
                st.write(f"**الموديل المتوافق:** {row['الموديل']}")
                st.markdown(
                    f"**رقم الوكالة الأصلي (OEM):** `{row['رقم الوكالة (OEM)']}`"
                )

                st.markdown("**الأرقام البديلة (Cross Reference):**")
                # تنسيق البدائل لعرضها بشكل واضح
                alternatives = row["الشركات البديلة (Cross Reference)"].split(
                    "|"
                )
                for alt in alternatives:
                    st.info(f"🔹 {alt.strip()}")

            with c2:
                st.image(
                    row["صورة القطعة"],
                    caption=f"{row['اسم القطعة']} - {row['رقم الوكالة (OEM)']}",
                    use_column_width=True,
                )

            st.divider()
else:
    st.warning("⚠️ لم يتم العثور على أية قطعة تطابق شروط البحث الحالية.")
