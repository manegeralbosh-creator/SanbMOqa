import re
import pandas as pd
import streamlit as st


def extract_alalamiya_ids(text):
    """استخراج أرقام الحوالات من نافذة العالمية بناءً على القواعد والكلمات المفتاحية."""
    if not text:
        return set()

    found_ids = set()

    # تقسيم النص إلى أسطر لمعالجة كل سطر بشكل مستقل
    lines = text.splitlines()
    for line in lines:
        if "حواله من" in line or "حوالة من" in line:
            # 1. حالة وجود رقم/رقم بعد النص (مثل: حواله من : فلان 100/200) -> يتم أخذ الرقم الثاني
            slash_match = re.search(
                r"(?:حواله|حوالة)\s+من\s*:?.*?\b\d+\s*/\s*(\d+)\b", line
            )
            if slash_match:
                found_ids.add(slash_match.group(1))
                continue

            # 2. حالة رقم عادي يأتي بعد النص (مثل: حواله من : فلان 123456)
            normal_match = re.search(
                r"(?:حواله|حوالة)\s+من\s*:?.*?\b(\d{3,})\b", line
            )
            if normal_match:
                found_ids.add(normal_match.group(1))

    return found_ids


def extract_accountant_ids(text):
    """استخراج أرقام الحوالات من نافذة المحاسب بناءً على القواعد والكلمات المفتاحية."""
    if not text:
        return set()

    found_ids = set()

    lines = text.splitlines()
    for line in lines:
        # 1. حالة حوالة الأكوع: الرقم يأتي وقبله الرقم وبعده كلمة "رقم" (مثال: 12345 رقم ...)
        before_match = re.search(r"\b(\d{3,})\b\s*رقم", line)
        if before_match:
            found_ids.add(before_match.group(1))
            continue

        # 2. الحالة العامة: رقم الحوالة يأتي بعد كلمة "رقم" (مثال: رقم 12345 أو رقم: 12345)
        after_match = re.search(r"رقم\s*:?\s*\b(\d{3,})\b", line)
        if after_match:
            found_ids.add(after_match.group(1))

    return found_ids


# إعدادات الصفحة
st.set_page_config(page_title="مطابقة الحوالات الذكي", layout="wide")

st.title("📊 نظام مطابقة الحوالات الذكي")
st.write("استخراج تلقائي لأرقام الحوالات بناءً على الكلمات المفتاحية المحددة.")

# النوافذ
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏢 نافذة المحاسب")
    acc_input = st.text_area(
        "ضع نص حوالات المحاسب هنا:",
        height=220,
        key="accountant",
        placeholder="مثال:\nرقم 554123\n554124 رقم حوالة الأكوع",
    )

with col2:
    st.subheader("🌐 نافذة العالمية")
    alalamiya_input = st.text_area(
        "ضع نص حوالات العالمية هنا:",
        height=220,
        key="alalamiya",
        placeholder="مثال:\nحواله من : محمد علي 700123\nحواله من : أحمد 100/700124",
    )

# إجراء المطابقة
if st.button("⚡ إجراء المطابقة والتصفية", type="primary"):
    acc_ids = extract_accountant_ids(acc_input)
    alalamiya_ids = extract_alalamiya_ids(alalamiya_input)

    # الحوالات المطابقة
    matched = acc_ids.intersection(alalamiya_ids)

    # غير المطابقة
    unmatched_acc = sorted(list(acc_ids - matched))
    unmatched_alalamiya = sorted(list(alalamiya_ids - matched))

    st.success(
        f"تمت العملية! عدد الحوالات المتطابقة والمخفية: **{len(matched)}**"
    )

    st.divider()
    st.subheader("⚠️ الحوالات غير المطابقة (الفرق بين النافذتين)")

    res_col1, res_col2 = st.columns(2)

    with res_col1:
        st.warning(f"متبقي المحاسب ({len(unmatched_acc)})")
        if unmatched_acc:
            for item in unmatched_acc:
                st.code(item, language="text")
        else:
            st.info("لا توجد فروقات في نافذة المحاسب")

    with res_col2:
        st.warning(f"متبقي العالمية ({len(unmatched_alalamiya)})")
        if unmatched_alalamiya:
            for item in unmatched_alalamiya:
                st.code(item, language="text")
        else:
            st.info("لا توجد فروقات في نافذة العالمية")
