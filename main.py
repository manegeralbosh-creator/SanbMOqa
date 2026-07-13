import streamlit as st
import pandas as pd
import re
import urllib.parse
import io
import sqlite3
from datetime import datetime

# إعدادات الصفحة بطابع رسمي مريح لشاشات الجوال والكمبيوتر
st.set_page_config(page_title="نظام محلات البوش للحسابات", page_icon="📊", layout="wide")

# تصميم الواجهة بالألوان الرسمية للمحلات (الكحلي والأبيض)
st.markdown("""
    <style>
    .reportview-container { background: #faf8f5; }
    .main-title { color: #1E3A8A; text-align: center; font-size: 26px; font-weight: bold; margin-bottom: 5px; }
    .sub-title { color: #4B5563; text-align: center; font-size: 15px; margin-bottom: 20px; }
    .stSelectbox, .stTextInput { margin-bottom: -10px; }
    div[data-testid="stBlock"] { padding: 4px; }
    .client-card { background-color: #ffffff; padding: 12px; border-radius: 6px; border-right: 6px solid #1E3A8A; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات المتكامل</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">إدارة مديونيات السوق الرسمية - نسخة قاعدة البيانات المحلية المطورة</div>', unsafe_allow_html=True)

# 🛠️ إنشاء والاتصال بقاعدة البيانات المحلية داخل الكمبيوتر
def get_local_db():
    conn = sqlite3.connect("local_debts.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers_debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT UNIQUE,
            phone_number TEXT,
            balance INTEGER,
            currency TEXT,
            frequency TEXT DEFAULT 'أسبوعي',
            last_sent_date TEXT
        )
    """)
    conn.commit()
    return conn

conn = get_local_db()

# دالة مطورة لاستخراج "جميع" أرقام الهواتف اليمنية الموجودة في النص (77, 73, 71, 70) والربط بينها بـ " / "
def extract_all_yemeni_phones(text):
    if pd.isna(text): return ""
    text_str = str(text).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    matches = re.findall(r'(77\d{7}|73\d{7}|71\d{7}|70\d{7})', text_str)
    if matches:
        unique_matches = list(dict.fromkeys(matches))
        return " / ".join(unique_matches)
    return ""

# دالة تنظيف اسم العميل من الرموز والتواريخ المستخرجة من أونكس
def clean_customer_name(text):
    if pd.isna(text): return ""
    return re.sub(r'[/\\\-\d]+.*', '', str(text)).strip()

# دالة تحديث ومزامنة الحسابات في القاعدة المحلية
def save_to_local_db(df):
    if df is None or len(df.columns) < 4:
        return False, "الملف المرفوع لا يحتوي على الأعمدة الأربعة الأساسية لكشف حساب أونكس."
    try:
        col_name, col_currency, col_balance = df.columns[1], df.columns[2], df.columns[3]
        success_count = 0
        cursor = conn.cursor()
        
        for idx, row in df.iterrows():
            raw_name = row[col_name]
            if pd.isna(raw_name) or "اسم العميل" in str(raw_name) or "الاسم" in str(raw_name): continue
            
            clean_name = clean_customer_name(raw_name)
            if not clean_name: continue
            
            phones = extract_all_yemeni_phones(raw_name)
            
            try: 
                balance_str = str(row[col_balance]).replace(',', '').strip()
                balance_val = int(float(balance_str))
            except: balance_val = 0
            
            if balance_val > 0:
                cursor.execute("SELECT id, phone_number FROM customers_debts WHERE customer_name = ?", (clean_name,))
                existing = cursor.fetchone()
                
                if existing:
                    existing_phone = existing[1]
                    final_phone = existing_phone if existing_phone and existing_phone != "لا يوجد رقم" else (phones if phones else "لا يوجد رقم")
                    cursor.execute("""
                        UPDATE customers_debts 
                        SET balance = ?, currency = ?, phone_number = ?
                        WHERE customer_name = ?
                    """, (balance_val, str(row[col_currency]).strip(), final_phone, clean_name))
                else:
                    cursor.execute("""
                        INSERT INTO customers_debts (customer_name, phone_number, balance, currency, frequency) 
                        VALUES (?, ?, ?, ?, 'أسبوعي')
                    """, (clean_name, phones if phones else "لا يوجد رقم", balance_val, str(row[col_currency]).strip()))
                success_count += 1
                
        conn.commit()
        return True, f"✅ تم تحديث ومزامنة {success_count} عميل بنجاح في قاعدة البيانات
