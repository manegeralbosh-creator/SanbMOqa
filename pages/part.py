import urllib.parse
import pandas as pd
import requests
import streamlit as st

# إعدادات الصفحة
st.set_page_config(
    page_title="كتالوج الشاحنات - البحث في المواقع والكتالوجات",
    layout="wide",
    page_icon="🚛",
)

st.title("🚛 تطبيق البحث الذكي في كتالوجات ومواقع قطع غيار الشاحنات")
st.caption(
    "ابحث في قاعدة بياناتك المحلية أو ابحث مباشرة في الكتالوجات والمواقع العالمية (Volvo, Actros, Scania...)"
)

# 1. قاعدة البيانات المحلية السريعة
local_data = [
    {
        "اسم القطعة": "فلتر زيت",
        "النوع": "Volvo",
        "الموديل": "FH16",
        "رقم الوكالة (OEM)": "21707133",
        "الشركات البديلة": "Hengst: H300W01 | Mann: W 11102/34",
        "صورة القطعة": "https://via.placeholder.com/200x150.png?text=21707133",
    },
    {
        "اسم القطعة": "فلتر زيت",
        "النوع": "Mercedes Actros",
        "الموديل": "MP4",
        "رقم الوكالة (OEM)": "A4711800209",
        "الشركات البديلة": "Hengst: E500H D129 | Mann: HU 12 001 x",
        "صورة القطعة": "https://via.placeholder.com/200x150.png?text=A4711800209",
    },
]
df_local = pd.DataFrame(local_data)

# 2. حقل البحث
query = st.text_input(
    "🔎 أدخل رقم القطعة OEM، رقم بديل (Hengst/Mann)، أو اسم القطعة:",
    placeholder="مثال: 21707133 أو A4711800209 أو فلتر زيت...",
)

col_brand, col_model = st.columns(2)
with col_brand:
    brand = st.selectbox(
        "اختر الماركة (اختر الكل للبحث الشامل):",
        ["الكل", "Volvo", "Mercedes Actros", "Iveco", "MAN", "Scania", "DAF"],
    )
with col_model:
    model = st.text_input("الموديل (اختياري):", placeholder="مثال: FH12, MP4...")

st.divider()

# tab1: البحث المحلي | tab2: البحث في الكتالوجات والمواقع العالمية
tab1, tab2 = st.tabs(
    ["📦 الكتالوج المحلي", "🌐 البحث في الكتالوجات والمواقع العالمية"]
)

with tab1:
    if query:
        q = query.strip().lower()
        results = df_local[
            df_local["رقم الوكالة (OEM)"].str.lower().str.contains(q)
            | df_local["الشركات البديلة"].str.lower().str.contains(q)
            | df_local["اسم القطعة"].str.lower().str.contains(q)
        ]
        if not results.empty:
            for _, row in results.iterrows():
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.subheader(f"{row['اسم القطعة']} - {row['النوع']}")
                    st.write(f"**رقم الوكالة:** `{row['رقم الوكالة (OEM)']}`")
                    st.write(f"**البدائل:** {row['الشركات البديلة']}")
                with c2:
                    st.image(row["صورة القطعة"])
        else:
            st.info("لم يتم العثور على القطعة في الكتالوج المحلي. انتقل لتبويب (البحث في المواقع العالمية).")
    else:
        st.dataframe(df_local, use_container_width=True)

with tab2:
    st.subheader("🔗 البحث المباشر في أضخم Kتالوجات ومواقع شاحنات العالم")

    search_term = query if query else f"{brand if brand != 'الكل' else ''} {model}"

    if search_term.strip():
        encoded_query = urllib.parse.quote(search_term)

        st.markdown(f"### 🎯 روابط البحث السريع للقطعة/الرقم: `{search_term}`")

        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("#### 🚚 كتالوجات قطع الشاحنات")
            # موقع FinditParts لشاحنات الفولفو والأكتروس
            st.link_button(
                "🌐 FinditParts (أمريكا والبدائل)",
                f"https://www.finditparts.com/search?utf8=%E2%9C%93&key={encoded_query}",
            )
            # موقع 7zap الكتالوجات الأصلية بالـ VIN والـ OEM
            st.link_button(
                "📐 7zap Truck OEM Catalogs",
                f"https://7zap.com/en/catalog/truck/?search={encoded_query}",
            )

        with c2:
            st.markdown("#### 🇩🇪 مواقع البدائل والأرقام الأوروبية")
            # AutoDoc أوروبا للقطع والبدائل
            st.link_button(
                "🛠️ AutoDoc Truck Parts",
                f"https://www.autodoc.co.uk/search?keyword={encoded_query}",
            )
            # Knorr-Bremse / Wabco
            st.link_button(
                "🔍 Google Images (صور ورسومات القطعة)",
                f"https://www.google.com/search?tbm=isch&q={encoded_query}+truck+part+OEM",
            )

        with c3:
            st.markdown("#### 🏭 كتالوجات الفلاتر والبدائل العالمية")
            # Kتالوج Hengst
            st.link_button(
                "🟡 Hengst Filter Catalog",
                f"https://www.hengst.com/en/online-catalog/search/?q={encoded_query}",
            )
            # Kتالوج Mann Filter
            st.link_button(
                "🟢 Mann Filter Catalog",
                f"https://www.mann-filter.com/en-official/catalog/search.html?query={encoded_query}",
            )

        st.success(
            "اضغط على أي زر أعلاه وسيفتح لك صفحة البحث المباشرة برقم القطعة في الكتالوج المطلوب بدون الحاجة لإعادة الكتابة!"
        )
    else:
        st.warning("⚠️ يرجى كتابة رقم القطعة أو اسمها في صندوق البحث أعلاه لتفعيل روابط الكتالوجات والمواقع.")
