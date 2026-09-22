import re
import pandas as pd
import streamlit as st


def extract_numbers(text):
    # استخراج كافة أرقام الحوالات (3 أرقام أو أكثر)
    if not text:
        return set()
    return set(re.findall(r"\b\d{3,}\b", text))


st.set_page_config(page_title="مطابقة الحوالات", layout="wide")

st.title("📊 برنامج مطابقة الحوالات المالية")
st.write("قم بوضع أرقام الحوالات في النافذتين للمطابقة وإخفاء المتشابهات.")

# إنشاء عمودين للنوافذ
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏢 نافذة المحاسب")
    acc_input = st.text_area(
        "ضع حوالات المحاسب هنا:", height=200, key="accountant"
    )

with col2:
    st.subheader("🌐 نافذة العالمية")
    alalamiya_input = st.text_area(
        "ضع حوالات العالمية هنا:", height=200, key="alalamiya"
    )

# زر المطابقة
if st.button("⚡ إجراء المطابقة", type="primary"):
    acc_ids = extract_numbers(acc_input)
    alalamiya_ids = extract_numbers(alalamiya_input)

    # الحوالات المتطابقة
    matched = acc_ids.intersection(alalamiya_ids)

    # غير المطابقة
    unmatched_acc = sorted(list(acc_ids - matched))
    unmatched_alalamiya = sorted(list(alalamiya_ids - matched))

    st.success(
        f"تمت المطابقة بنجاح! تم إخفاء **{len(matched)}** حوالة متطابقة."
    )

    st.divider()
    st.subheader("⚠️ الحوالات غير المطابقة (الفرق بين النافذتين)")

    res_col1, res_col2 = st.columns(2)

    with res_col1:
        st.warning(f"متبقي المحاسب ({len(unmatched_acc)})")
        if unmatched_acc:
            st.write(unmatched_acc)
        else:
            st.info("لا توجد فروقات في نافذة المحاسب")

    with res_col2:
        st.warning(f"متبقي العالمية ({len(unmatched_alalamiya)})")
        if unmatched_alalamiya:
            st.write(unmatched_alalamiya)
        else:
            st.info("لا توجد فروقات في نافذة العالمية")
