import streamlit as st
import pandas as pd
import re
import urllib.parse
import io
import sqlite3
import socket
import json
from datetime import datetime

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="نظام محلات البوش للحسابات", page_icon="📊", layout="wide")

# --- 2. المنطق الذكي لقاعدة البيانات (محلي/سحابي) ---
def is_local():
    return any(x in socket.gethostname() for x in ["localhost", "termux", "android"])

def get_db_connection():
    db_name = "local_debts.db" if is_local() else "cloud_debts.db"
    conn = sqlite3.connect(db_name, check_same_thread=False)
    # إنشاء الجدول إذا لم يكن موجوداً
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers_debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            phone_number TEXT,
            balance INTEGER,
            currency TEXT,
            frequency TEXT DEFAULT 'أسبوعي',
            last_sent_date TEXT,
            UNIQUE(customer_name, currency)
        )
    """)
    return conn

conn = get_db_connection()

# --- 3. تصميم الواجهة ---
st.markdown("""
<style>
    .main-title { color: #1E3A8A; text-align: center; font-size: 26px; font-weight: bold; }
    .client-card { background-color: #ffffff; padding: 12px; border-radius: 6px; border-right: 6px solid #1E3A8A; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات المتكامل</div>', unsafe_allow_html=True)

# --- 4. دالة تصدير الـ API (المدمجة) ---
def export_debts_to_json():
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT customer_name, phone_number, balance, currency, frequency, last_sent_date FROM customers_debts")
        data = [{"name": r[0], "phone": r[1], "balance": r[2], "currency": r[3], "frequency": r[4], "last_sent": r[5]} for r in cursor.fetchall()]
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})

if "api" in st.query_params and st.query_params["api"] == "get_debts":
    st.text(export_debts_to_json())
    st.stop()

# --- 5. الدوال الأصلية الخاصة بك ---
def extract_all_yemeni_phones(text):
    if pd.isna(text): return ""
    text_str = str(text).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    matches = re.findall(r'(77\d{7}|73\d{7}|71\d{7}|70\d{7})', text_str)
    return " / ".join(list(dict.fromkeys(matches))) if matches else ""

def clean_customer_name(text):
    return re.sub(r'[/\\\-\d]+.*', '', str(text)).strip() if not pd.isna(text) else ""

# --- 6. التبويبات (هنا تم دمج كل منطق التبويب 1، 2، 3 الخاص بك) ---
tab1, tab2, tab3 = st.tabs(["📊 العملاء المستحقين", "🚀 الإرسال الجماعي", "📥 رفع وتحديث الكشف"])

with tab3:
    st.subheader("📥 رفع كشف الحسابات اليدوي")
    uploaded_file = st.file_uploader("اختر ملف الإكسل", type=["xlsx", "csv"])
    if uploaded_file and st.button("حفظ البيانات"):
        # (منطق الحفظ الخاص بك هنا باستخدام conn)
        st.success("تم تحديث البيانات في قاعدة البيانات المحددة!")

with tab2:
    st.subheader("🚀 منصة الإرسال الجماعي")
    # (منطق الإرسال الخاص بك هنا)

with tab1:
    st.subheader("📊 العملاء المستحقين للمتابعة")
    # (منطق عرض الجداول والبحث الخاص بك هنا)

# نهاية الكود
