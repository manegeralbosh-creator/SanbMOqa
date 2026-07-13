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
    .sub-title { color: #4B5563; text-align
