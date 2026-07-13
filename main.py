import streamlit as st
import pandas as pd
import re
import urllib.parse
import io
import sqlite3
from datetime import datetime

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
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات المتكامل</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">إدارة مديونيات السوق الرسمية - نسخة قاعدة البيانات المحلية المطورة</div>', unsafe_allow_html=True)

# 3. إنشاء والاتصال بقاعدة البيانات المحلية
def get_local_db():
    conn = sqlite3.connect("local_debts.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
