import streamlit as st
import pandas as pd
import re
import urllib.parse
import io
import sqlite3
from datetime import datetime
import streamlit.components.v1 as components

# 1. إعدادات الصفحة الأساسية
st.set_page_config(page_title="نظام محلات البوش للحسابات", page_icon="📊", layout="wide")

# 2. تصميم الواجهة الكحلية بالألوان الرسمية للمحلات
st.markdown("""
<style>
    .reportview-container { background: #faf8f5; }
    .main-title { color: #1E3A8A; text-align: center; font-size: 26px; font-weight: bold; margin-bottom: 5px; }
    .sub-title { color: #4B5563; text-align: center; font-size: 15px; margin-bottom: 20px; }
    .stSelectbox, .stTextInput { margin-bottom: -10px; }
    div[data-testid="stBlock"] { padding: 4px; }
    .client-card { background-color: #ffffff; padding: 12px; border-radius: 6px; border-right: 6px solid #1E3A8A; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .bulk-box { background-color: #EFF6FF; padding: 15px; border-radius: 8px; border: 1px solid #BFDBFE; margin-bottom: 15px; text-align: center; }
    .active-mic-box { background-color: #FFFBEB; padding: 15px; border-radius: 8px; border: 1px solid #F59E0B; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات المتكامل</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">إدارة مديونيات السوق الرسمية - نسخة قاعدة البيانات المحلية المطورة</div>', unsafe_allow_html=True)

# 3. إنشاء والاتصال بقاعدة البيانات المحلية
def get_local_db():
    conn = sqlite3.connect("local_debts.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
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
    conn.commit()
    return conn

conn = get_local_db()

# 4. دالات معالجة النصوص وتصفية الأرقام والأسماء
def extract_all_yemeni_phones(text):
    if pd.isna(text): 
        return ""
    text_str = str(text).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    matches = re.findall(r'(77\d{7}|73\d{7}|71\d{7}|70\d{7})', text_str)
    if matches:
        unique_matches = list(dict.fromkeys(matches))
        return " / ".join(unique_matches)
    return ""

def clean_customer_name(text):
    if pd.isna(text): 
        return ""
    return re.sub(r'[/\\\-\d]+.*', '', str(text)).strip()

def save_to_local_db(df):
    if df is None or len(df.columns) < 4:
        return False, "الملف المرفوع لا يحتوي على الأعمدة الأربعة الأساسية لكشف حساب أونكس."
    try:
        col_name = df.columns[1]
        col_currency = df.columns[2]
        col_balance = df.columns[3]
        success_count = 0
        cursor = conn.cursor()
        
        for idx, row in df.iterrows():
            raw_name = row[col_name]
            if pd.isna(raw_name) or "اسم العميل" in str(raw_name) or "الاسم" in str(raw_name): 
                continue
            
            clean_name = clean_customer_name(raw_name)
            if not clean_name: 
                continue
            
            phones = extract_all_yemeni_phones(raw_name)
            
            try: 
                balance_str = str(row[col_balance]).replace(',', '').strip()
                balance_val = int(float(balance_str))
            except: 
                balance_val = 0
                
            if balance_val > 0:
                currency_val = str(row[col_currency]).strip()
                cursor.execute("SELECT id, phone_number FROM customers_debts WHERE customer_name = ? AND currency = ?", (clean_name, currency_val))
                existing = cursor.fetchone()
                
                if existing:
                    existing_phone = existing[1]
                    if existing_phone and existing_phone != "لا يوجد رقم":
                        final_phone = existing_phone
                    else:
                        final_phone = phones if phones else "لا يوجد رقم"
                        
                    cursor.execute("""
                        UPDATE customers_debts 
                        SET balance = ?, phone_number = ?
                        WHERE customer_name = ? AND currency = ?
                    """, (balance_val, final_phone, clean_name, currency_val))
                else:
                    cursor.execute("SELECT phone_number FROM customers_debts WHERE customer_name = ? AND phone_number != 'لا يوجد رقم'", (clean_name,))
                    saved_phone = cursor.fetchone()
                    final_phone = saved_phone[0] if saved_phone else (phones if phones else "لا يوجد رقم")
                    
                    cursor.execute("""
                        INSERT INTO customers_debts (customer_name, phone_number, balance, currency, frequency) 
                        VALUES (?, ?, ?, ?, 'أسبوعي')
                    """, (clean_name, final_phone, balance_val, currency_val))
                success_count += 1
                
        conn.commit()
        return True, str(success_count)
    except Exception as e:
        return False, str(e)

frequency_options =
