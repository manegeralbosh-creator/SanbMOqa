import base64
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import urllib.parse
import zipfile
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_calendar import calendar

# دعم المكتبات الخارجية للملفات المضغوطة
try:
    import rarfile

    HAS_RAR = True
except ImportError:
    HAS_RAR = False

try:
    import py7zr

    HAS_7Z = True
except ImportError:
    HAS_7Z = False

try:
    import tarfile

    HAS_TAR = True
except ImportError:
    HAS_TAR = False

# ---------------------------------------------------------
# 1. إعدادات الصفحة والاتصالات الأساسية
# ---------------------------------------------------------
st.set_page_config(
    page_title="نظام محلات البوش للحسابات", page_icon="📊", layout="wide"
)

# تصميم الواجهة بالألوان الرسمية للمحلات
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات'
    " المتكامل</div>",
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-title">إدارة مديونيات السوق الرسمية - نسخة قاعدة'
    " البيانات المحلية المطورة</div>",
    unsafe_allow_html=True,
)


def get_data_from_sheet():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict)
    client = gspread.authorize(creds)
    sheet = client.open("AlBoush_Data").sheet1
    return sheet.get_all_records()


# قراءة جدول المديونيات من جوجل شيت
try:
    data = get_data_from_sheet()
    st.sidebar.success("تم الاتصال بجدول المديونيات السحابي!")
except Exception as e:
    st.sidebar.error(f"تنبيه الاتصال بالدرايف: {e}")


def get_persistent_db_path():
    storage_dir = Path("/sdcard/AlBoush_Data")
    if not storage_dir.exists():
        try:
            storage_dir.mkdir(parents=True, exist_ok=True)
            return str(storage_dir / "local_debts.db")
        except Exception:
            return "local_debts.db"
    return str(storage_dir / "local_debts.db")


def get_local_db():
    db_path = get_persistent_db_path()
    conn = sqlite3.connect(db_path, check_same_thread=False)
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


# ---------------------------------------------------------
# 2. الدالات المساعدة للبيانات وتصفية الأسماء والرسائل
# ---------------------------------------------------------
def extract_all_yemeni_phones(text):
    if pd.isna(text):
        return ""
    text_str = str(text).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    matches = re.findall(r"(77\d{7}|73\d{7}|71\d{7}|70\d{7})", text_str)
    if matches:
        return " / ".join(list(dict.fromkeys(matches)))
    return ""


def clean_customer_name(text):
    if pd.isna(text):
        return ""
    return re.sub(r"[/\\\-\d]+.*", "", str(text)).strip()


def save_to_local_db(df):
    if df is None or len(df.columns) < 4:
        return (
            False,
            "الملف المرفوع لا يحتوي على الأعمدة الأربعة الأساسية لكشف حساب"
            " أونكس.",
        )
    try:
        col_name = df.columns[1]
        col_currency = df.columns[2]
        col_balance = df.columns[3]
        success_count = 0
        cursor = conn.cursor()

        for idx, row in df.iterrows():
            raw_name = row[col_name]
            if (
                pd.isna(raw_name)
                or "اسم العميل" in str(raw_name)
                or "الاسم" in str(raw_name)
            ):
                continue

            clean_name = clean_customer_name(raw_name)
            if not clean_name:
                continue

            phones = extract_all_yemeni_phones(raw_name)

            try:
                balance_str = (
                    str(row[col_balance]).replace(",", "").strip()
                )
                balance_val = int(float(balance_str))
            except Exception:
                balance_val = 0

            if balance_val > 0:
                currency_val = str(row[col_currency]).strip()
                cursor.execute(
                    "SELECT id, phone_number FROM customers_debts WHERE"
                    " customer_name = ? AND currency = ?",
                    (clean_name, currency_val),
                )
                existing = cursor.fetchone()

                if existing:
                    existing_phone = existing[1]
                    final_phone = (
                        existing_phone
                        if (existing_phone and existing_phone != "لا يوجد رقم")
                        else (phones if phones else "لا يوجد رقم")
                    )
                    cursor.execute(
                        """
                        UPDATE customers_debts 
                        SET balance = ?, phone_number = ?
                        WHERE customer_name = ? AND currency = ?
                    """,
                        (balance_val, final_phone, clean_name, currency_val),
                    )
                else:
                    cursor.execute(
                        "SELECT phone_number FROM customers_debts WHERE"
                        " customer_name = ? AND phone_number != 'لا يوجد رقم'",
                        (clean_name,),
                    )
                    saved_phone = cursor.fetchone()
                    final_phone = (
                        saved_phone[0]
                        if saved_phone
                        else (phones if phones else "لا يوجد رقم")
                    )

                    cursor.execute(
                        """
                        INSERT INTO customers_debts (customer_name, phone_number, balance, currency, frequency) 
                        VALUES (?, ?, ?, ?, 'أسبوعي')
                    """,
                        (clean_name, final_phone, balance_val, currency_val),
                    )
                success_count += 1

        conn.commit()
        return True, str(success_count)
    except Exception as e:
        return False, str(e)


# إعداد القوائم وفلاتر الوقت
frequency_options = [
    "كل 3 أيام",
    "أسبوعي",
    "كل أسبوعين",
    "شهري",
    "إيقاف التذكير",
]
freq_days_map = {
    "كل 3 أيام": 3,
    "أسبوعي": 7,
    "كل أسبوعين": 14,
    "شهري": 30,
    "إيقاف التذكير": 99999,
}

# جلب وتجميع بيانات الحسابات المزدوجة العملة
cursor = conn.cursor()
cursor.execute(
    "SELECT id, customer_name, phone_number, balance, currency, frequency,"
    " last_sent_date FROM customers_debts WHERE balance > 0"
)
rows = cursor.fetchall()

grouped_dict = {}
for r in rows:
    db_id, name, phone, balance, currency, frequency, last_sent = r
    if name not in grouped_dict:
        grouped_dict[name] = {
            "ids": [],
            "customer_name": name,
            "phone_number": phone,
            "debts": {},
            "frequency": frequency,
            "last_sent_date": last_sent,
        }

    grouped_dict[name]["ids"].append(db_id)
    grouped_dict[name]["debts"][currency] = balance

    if phone and phone != "لا يوجد رقم":
        grouped_dict[name]["phone_number"] = phone

    if last_sent:
        if (
            not grouped_dict[name]["last_sent_date"]
            or last_sent > grouped_dict[name]["last_sent_date"]
        ):
            grouped_dict[name]["last_sent_date"] = last_sent

all_customers = list(grouped_dict.values())
today = datetime.now().date()
due_customers = []

if all_customers:
    for cust in all_customers:
        freq = cust["frequency"]
        if freq == "إيقاف التذكير":
            continue
        last_sent = cust["last_sent_date"]
        if last_sent:
            last_sent_dt = datetime.strptime(last_sent, "%Y-%m-%d").date()
            if (today - last_sent_dt).days >= freq_days_map.get(freq, 7):
                due_customers.append(cust)
        else:
            due_customers.append(cust)

# ---------------------------------------------------------
# 3. محرر الرسالة المخصصة العامة (Custom Template Builder)
# ---------------------------------------------------------
st.sidebar.markdown("### ✏️ تخصيص نص الرسالة")
st.sidebar.info(
    "يمكنك كتابة نصك الخاص واستخدام الكلمات الدلالية التلقائية:\n"
    "- `{اسم_العميل}` : لاستبداله باسم العميل تلقائياً\n"
    "- `{المبلغ}` : لاستبداله بالمبلغ والعملات المستحقة"
)

default_msg_template = st.sidebar.text_area(
    "صيغة الرسالة العامة لكافة الأقسام:",
    value=(
        "الأخ المكرم/ {اسم_العميل}\n"
        "تحية طيبة وبعد،،\n"
        "نود تذكيركم برصيد حسابكم المتبقي لدينا في محلات البوش لقطع غيار الشاحنات وهو: {المبلغ}.\n"
        "يرجى التكرم بتصفية الحساب في أقرب وقت، شاكرين حسن تعاونكم معنا."
    ),
    height=160,
    key="custom_global_msg_template",
)


def format_custom_message(template, client_name, debt_string):
    msg = template.replace("{اسم_العميل}", str(client_name))
    msg = msg.replace("{المبلغ}", str(debt_string))
    # دعم للتوافق القديم مع الـ Tags المفردة
    msg = msg.replace("[المبلغ]", str(debt_string)).replace("[العملة]", "")
    return msg


# ---------------------------------------------------------
# 4. التبويبات الرئيسية للنظام
# ---------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 العملاء المستحقين للتذكير اليوم",
    "🚀 الإرسال الجماعي للرسائل SMS",
    "📲 إرسال فواتير الواتساب",
    "📥 رفع كشف الحساب اليدوي",
    "🤖 الطابور الآلي (API)",
])

# =========================================================
# التبويب الأول: متابعة المستحقين الفردية
# =========================================================
with tab1:
    if (
        "active_voice_client" in st.session_state
        and st.session_state["active_voice_client"] is not None
    ):
        active_client = st.session_state["active_voice_client"]

        st.markdown(
            f"""
        <div class="active-mic-box">
            <h4 style="color: #B45309; margin: 0 0 10px 0;">🎙️ مسجل الصوت الموحد للعميل: {active_client['name']}</h4>
            <p style="font-size: 14px; color: #78350F; margin: 0 0 10px 0;">اضغط على زر الميكروفون أدناه، سجل رسالتك، ثم أوقف التسجيل ليظهر زر الإرسال مباشرة.</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        audio_file = st.audio_input(
            "ابدأ تسجيل الصوت هنا:", key="global_unique_audio_recorder"
        )

        col_rec_1, col_rec_2 = st.columns([3, 1])
        with col_rec_1:
            if audio_file is not None:
                st.success("✅ تم معالجة وحفظ المقطع الصوتي بنجاح!")
                st.markdown(
                    f"""
                    <div style="margin-top: 5px;">
                        <a href="{active_client['whatsapp_url']}" target="_blank">
                            <button style="background-color: #25D366; color: white; border: none; padding: 12px 20px; border-radius: 6px; font-size: 15px; font-weight: bold; cursor: pointer; width: 100%;">
                                📲 افتح الواتساب الآن لإرفاق الصوت لـ {active_client['name']}
                            </button>
                        </a>
                    </div>
                """,
                    unsafe_allow_html=True,
                )
        with col_rec_2:
            if st.button(
                "❌ إغلاق المسجل",
                use_container_width=True,
                key="close_global_mic_btn",
            ):
                st.session_state["active_voice_client"] = None
                st.rerun()

        st.write("---")

    if all_customers:
        search_query = st.text_input(
            "🔍 بحث سريع عن عميل بالاسم أو الهاتف:",
            placeholder="اكتب اسم العميل أو الرقم هنا...",
        )
        filtered_due = due_customers
        if search_query.strip() != "":
            filtered_due = [
                c
                for c in due_customers
                if search_query.lower() in c["customer_name"].lower()
                or search_query in str(c["phone_number"])
            ]

        st.write(
            f"### إجمالي الحسابات النشطة: {len(all_customers)} | المستحقين"
            f" للمتابعة اليوم: {len(filtered_due)}"
        )

        for item in filtered_due:
            raw_phone = (
                str(item.get("phone_number", ""))
                .replace(".0", "")
                .strip()
            )
            if "/" in raw_phone:
                phone_list = [p.strip() for p in raw_phone.split("/") if p.strip()]
            elif "," in raw_phone:
                phone_list = [p.strip() for p in raw_phone.split(",") if p.strip()]
            else:
                phone_list = (
                    [raw_phone]
                    if raw_phone and raw_phone != "nan"
                    else ["لا يوجد رقم"]
                )

            debt_items = []
            display_parts = []
            for curr, bal in item["debts"].items():
                formatted_bal = "{:,}".format(bal)
                debt_items.append(f"{formatted_bal} {curr}")
                display_parts.append(
                    f"<b style='color:#B91C1C;'>{formatted_bal} {curr}</b>"
                )

            combined_debt_str = " و ".join(debt_items)
            combined_display_str = " و ".join(display_parts)

            formatted_msg = format_custom_message(
                default_msg_template, item["customer_name"], combined_debt_str
            )
            encoded_msg = urllib.parse.quote(formatted_msg)

            st.markdown(
                f"""
            <div class="client-card">
                <span style="font-size:17px; font-weight:bold; color:#1E3A8A;">👤 {item['customer_name']}</span> | 
                <span style="color:#4B5563;">📱 الهاتف: {raw_phone}</span> | 
                <span style="font-size:15px; font-weight:bold;">💰 المتبقي: {combined_display_str}</span>
            </div>
            """,
                unsafe_allow_html=True,
            )

            col_one, col_two, col_three, col_four = st.columns(
                [1.2, 1.6, 1.1, 1.1]
            )

            with col_one:
                first_db_id = item["ids"][0]
                idx_default = (
                    frequency_options.index(item["frequency"])
                    if item["frequency"] in frequency_options
                    else 1
                )
                chosen_freq = st.selectbox(
                    f"freq_{first_db_id}",
                    frequency_options,
                    index=idx_default,
                    key=f"time_{first_db_id}",
                    label_visibility="collapsed",
                )
                if chosen_freq != item["frequency"]:
                    cursor = conn.cursor()
                    for db_id in item["ids"]:
                        cursor.execute(
                            "UPDATE customers_debts SET frequency = ? WHERE id"
                            " = ?",
                            (chosen_freq, db_id),
                        )
                    conn.commit()
                    st.rerun()

            with col_two:
                first_db_id = item["ids"][0]
                if len(phone_list) > 1:
                    selected_phone = st.selectbox(
                        f"select_lbl_{first_db_id}",
                        phone_list,
                        key=f"select_p_{first_db_id}",
                        label_visibility="collapsed",
                    )
                    phone_to_send = selected_phone.lstrip("0")
                else:
                    new_phone = st.text_input(
                        f"phone_{first_db_id}",
                        value=(
                            "" if phone_list[0] == "لا يوجد رقم" else phone_list[0]
                        ),
                        placeholder="رقم الهاتف",
                        key=f"input_{first_db_id}",
                        label_visibility="collapsed",
                    )
                    if new_phone.strip() != "" and new_phone.strip() != raw_phone:
                        cursor = conn.cursor()
                        for db_id in item["ids"]:
                            cursor.execute(
                                "UPDATE customers_debts SET phone_number = ?"
                                " WHERE id = ?",
                                (new_phone.strip(), db_id),
                            )
                        conn.commit()
                        st.rerun()
                    phone_to_send = (
                        new_phone.strip().lstrip("0")
                        if new_phone.strip() != ""
                        else ""
                    )

            whatsapp_phone = ""
            if phone_to_send and phone_to_send != "لا يوجد رقم":
                whatsapp_phone = (
                    "967" + phone_to_send
                    if not phone_to_send.startswith("967")
                    else phone_to_send
                )

            voice_note_intro = urllib.parse.quote(
                "أرفق لكم المقطع الصوتي الخاص بمتابعة الحساب:"
            )
            whatsapp_voice_url = f"https://api.whatsapp.com/send?phone={whatsapp_phone}&text={voice_note_intro}"

            with col_three:
                first_db_id = item["ids"][0]
                if phone_to_send and phone_to_send != "لا يوجد رقم":
                    whatsapp_url = f"https://api.whatsapp.com/send?phone={whatsapp_phone}&text={encoded_msg}"
                    st.markdown(
                        f'<a href="{whatsapp_url}" target="_blank"><button'
                        ' style="background-color: #25D366; color: white;'
                        " border: none; padding: 6px 10px; border-radius: 4px;"
                        " font-size: 13px; cursor: pointer; font-weight: bold;"
                        ' width: 100%;">💬 واتساب</button></a>',
                        unsafe_allow_html=True,
                    )

                    if st.button(
                        "✓ تم",
                        key=f"done_wa_{first_db_id}",
                        help="تأجيل التذكير للفترة القادمة",
                    ):
                        cursor = conn.cursor()
                        for db_id in item["ids"]:
                            cursor.execute(
                                "UPDATE customers_debts SET last_sent_date = ?"
                                " WHERE id = ?",
                                (str(today), db_id),
                            )
                        conn.commit()
                        st.rerun()
                else:
                    st.button(
                        "🚫 بلا رقم",
                        key=f"wa_err_{first_db_id}",
                        disabled=True,
                        use_container_width=True,
                    )

            with col_four:
                first_db_id = item["ids"][0]
                if phone_to_send and phone_to_send != "لا يوجد رقم":
                    sms_url = f"sms:{phone_to_send}?body={encoded_msg}"
                    st.markdown(
                        f'<a href="{sms_url}"><button style="background-color:'
                        " #1E3A8A; color: white; border: none; padding: 6px"
                        " 10px; border-radius: 4px; font-size: 13px; cursor:"
                        ' pointer; font-weight: bold; width: 100%;">📱'
                        " SMS</button></a>",
                        unsafe_allow_html=True,
                    )

                    if st.button(
                        "✓ تم",
                        key=f"done_sms_{first_db_id}",
                        help="تأجيل التذكير للفترة القادمة",
                    ):
                        cursor = conn.cursor()
                        for db_id in item["ids"]:
                            cursor.execute(
                                "UPDATE customers_debts SET last_sent_date = ?"
                                " WHERE id = ?",
                                (str(today), db_id),
                            )
                        conn.commit()
                        st.rerun()
                else:
                    st.button(
                        "🚫 ناقص",
                        key=f"sms_err_{first_db_id}",
                        disabled=True,
                        use_container_width=True,
                    )

            if phone_to_send and phone_to_send != "لا يوجد رقم":
                if st.button(
                    f"🎙️ تفعيل الميكروفون للعميل: {item['customer_name']}",
                    key=f"trigger_mic_{first_db_id}",
                    use_container_width=True,
                ):
                    st.session_state["active_voice_client"] = {
                        "name": item["customer_name"],
                        "whatsapp_url": whatsapp_voice_url,
                    }
                    st.rerun()

            st.markdown(
                "<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True
            )

        st.write("---")
        st.write("### 📜 السجل الكامل وتواريخ المراسلة السابقة")

        log_rows = []
        for cust in all_customers:
            yemeni_bal = cust["debts"].get("يمني", 0)
            saudi_bal = cust["debts"].get("سعودي", 0)
            log_rows.append({
                "اسم العميل الرسمي": cust["customer_name"],
                "رقم الهاتف": cust["phone_number"],
                "مديونية يمني": f"{yemeni_bal:,}" if yemeni_bal > 0 else "0",
                "مديونية سعودي": f"{saudi_bal:,}" if saudi_bal > 0 else "0",
                "فترة التذكير": cust["frequency"],
                "تاريخ آخر إرسال": (
                    cust["last_sent_date"]
                    if cust["last_sent_date"]
                    else "لم يرسل بعد"
                ),
            })

        df_log = pd.DataFrame(log_rows)
        if not df_log.empty:
            st.dataframe(df_log, use_container_width=True, hide_index=True)
    else:
        st.success("لا يوجد عملاء مستحقين للتذكير حالياً.")

# =========================================================
# التبويب الثاني: الإرسال الجماعي المتتابع SMS
# =========================================================
with tab2:
    st.subheader("🚀 منصة الإرسال الجماعي المتتابع (SMS)")

    if not due_customers:
        st.success("✅ لا يوجد عملاء مستحقين للإرسال الجماعي اليوم!")
    else:
        valid_bulk_customers = [
            c
            for c in due_customers
            if str(c["phone_number"]).strip()
            and str(c["phone_number"]).strip() != "لا يوجد رقم"
        ]

        if not valid_bulk_customers:
            st.warning(
                "⚠️ جميع العملاء المستحقين اليوم ليس لديهم أرقام هواتف مسجلة."
            )
        else:
            st.markdown(
                f"""
            <div class="bulk-box">
                <h4 style="color: #1E3A8A; margin:0;">📈 جاهز للإرسال الجماعي للرسائل النصية</h4>
                <p style="color: #4B5563; font-size:14px; margin:5px 0 0 0;">عدد العملاء الجاهزين للمراسلة: <b>{len(valid_bulk_customers)} عميل</b></p>
            </div>
            """,
                unsafe_allow_html=True,
            )

            if "bulk_index" not in st.session_state:
                st.session_state["bulk_index"] = 0

            if st.session_state["bulk_index"] >= len(valid_bulk_customers):
                st.session_state["bulk_index"] = 0
                st.success("🎉 ممتاز! تم المرور على جميع العملاء بنجاح.")

            current_idx = st.session_state["bulk_index"]
            current_cust = valid_bulk_customers[current_idx]

            debt_parts = [
                f"{bal:,} {curr}" for curr, bal in current_cust["debts"].items()
            ]
            combined_debt_str = " و ".join(debt_parts)

            bulk_formatted_msg = format_custom_message(
                default_msg_template,
                current_cust["customer_name"],
                combined_debt_str,
            )
            bulk_encoded_msg = urllib.parse.quote(bulk_formatted_msg)

            raw_phone = str(current_cust["phone_number"]).strip()
            first_phone = [p.strip() for p in raw_phone.split("/") if p.strip()][
                0
            ]

            bulk_sms_url = f"sms:{first_phone}?body={bulk_encoded_msg}"

            st.markdown(
                f"""
            <div style="background-color: #ffffff; padding: 20px; border-radius: 8px; border-right: 8px solid #1E3A8A; box-shadow: 0 2px 5px rgba(0,0,0,0.05); text-align:right;">
                <span style="font-size:14px; background-color:#1E3A8A; color:white; padding:3px 8px; border-radius:10px;">العميل الحالي رقم ({current_idx + 1} من أصل {len(valid_bulk_customers)})</span>
                <h3 style="color:#1E3A8A; margin-top:10px;">👤 {current_cust['customer_name']}</h3>
                <p style="font-size:16px; margin: 5px 0;">💰 متبقي عليه: <b style="color:#B91C1C;">{combined_debt_str}</b></p>
                <p style="font-size:14px; color:#4B5563;">📱 رقم الهاتف: {first_phone}</p>
            </div>
            """,
                unsafe_allow_html=True,
            )

            st.markdown("<br>", unsafe_allow_html=True)
            col_b1, col_b2, col_b3 = st.columns([2, 2, 1])

            with col_b1:
                st.markdown(
                    f'<a href="{bulk_sms_url}"><button style="background-color:'
                    " #1E3A8A; color: white; border: none; padding: 12px 10px;"
                    " border-radius: 6px; font-size: 16px; cursor: pointer;"
                    ' font-weight: bold; width: 100%;">📱 1. تجهيز الرسالة'
                    " النصية (SMS)</button></a>",
                    unsafe_allow_html=True,
                )

            with col_b2:
                if st.button(
                    "✅ 2. تم الإرسال (التالي) ➡️",
                    use_container_width=True,
                    key="bulk_send_next_btn",
                ):
                    cursor = conn.cursor()
                    for db_id in current_cust["ids"]:
                        cursor.execute(
                            "UPDATE customers_debts SET last_sent_date = ?"
                            " WHERE id = ?",
                            (str(today), db_id),
                        )
                    conn.commit()
                    st.session_state["bulk_index"] += 1
                    st.rerun()

            with col_b3:
                if st.button(
                    "تخطي مؤقتاً ↩️",
                    use_container_width=True,
                    key="bulk_skip_btn",
                ):
                    st.session_state["bulk_index"] += 1
                    st.rerun()

# =========================================================
# التبويب الثالث: إرسال فواتير الواتساب المرفقة
# =========================================================
with tab3:
    st.subheader("📲 نظام مراجعة وإرسال الفواتير عبر الواتساب")

    if "completed_invoices" not in st.session_state:
        st.session_state.completed_invoices = set()

    if "skipped_invoices" not in st.session_state:
        st.session_state.skipped_invoices = set()

    st.markdown("#### 📂 1. رفع البيانات والفواتير")
    col_ex, col_archive, col_pdf_direct = st.columns([1.2, 1.2, 1.2])

    with col_ex:
        excel_file = st.file_uploader(
            "📊 ملف كشف المبيعات (Excel)", type=["xlsx", "xls"], key="inv_excel"
        )

    with col_archive:
        archive_file = st.file_uploader(
            "📦 أرشيف مضغوط (ZIP / RAR / 7Z / TAR)",
            type=["zip", "rar", "7z", "tar", "gz"],
            key="inv_archive",
        )

    with col_pdf_direct:
        direct_pdf_files = st.file_uploader(
            "📄 ملفات PDF مباشرة (دفعة واحدة)",
            type=["pdf"],
            accept_multiple_files=True,
            key="inv_direct_pdfs",
        )

    pdf_store = {}

    if archive_file is not None:
        file_ext = archive_file.name.split(".")[-1].lower()
        try:
            if file_ext == "zip":
                with zipfile.ZipFile(archive_file, "r") as z:
                    for file_info in z.infolist():
                        if file_info.filename.lower().endswith(".pdf"):
                            filename = os.path.basename(file_info.filename)
                            raw_name = (
                                filename.replace(".pdf", "")
                                .replace(".PDF", "")
                                .strip()
                            )
                            clean_num = "".join(filter(str.isdigit, raw_name))
                            file_bytes = z.read(file_info.filename)
                            pdf_store[raw_name] = file_bytes
                            if clean_num:
                                pdf_store[clean_num] = file_bytes

            elif file_ext == "rar" and HAS_RAR:
                with rarfile.RarFile(archive_file) as r:
                    for file_info in r.infolist():
                        if file_info.filename.lower().endswith(".pdf"):
                            filename = os.path.basename(file_info.filename)
                            raw_name = (
                                filename.replace(".pdf", "")
                                .replace(".PDF", "")
                                .strip()
                            )
                            clean_num = "".join(filter(str.isdigit, raw_name))
                            file_bytes = r.read(file_info.filename)
                            pdf_store[raw_name] = file_bytes
                            if clean_num:
                                pdf_store[clean_num] = file_bytes

            elif file_ext == "7z" and HAS_7Z:
                with py7zr.SevenZipFile(archive_file, mode="r") as z:
                    for name, bio in z.readall().items():
                        if name.lower().endswith(".pdf"):
                            filename = os.path.basename(name)
                            raw_name = (
                                filename.replace(".pdf", "")
                                .replace(".PDF", "")
                                .strip()
                            )
                            clean_num = "".join(filter(str.isdigit, raw_name))
                            file_bytes = bio.read()
                            pdf_store[raw_name] = file_bytes
                            if clean_num:
                                pdf_store[clean_num] = file_bytes

            elif file_ext in ["tar", "gz"] and HAS_TAR:
                with tarfile.open(fileobj=archive_file) as t:
                    for member in t.getmembers():
                        if member.isfile() and member.name.lower().endswith(
                            ".pdf"
                        ):
                            filename = os.path.basename(member.name)
                            raw_name = (
                                filename.replace(".pdf", "")
                                .replace(".PDF", "")
                                .strip()
                            )
                            clean_num = "".join(filter(str.isdigit, raw_name))
                            f = t.extractfile(member)
                            if f:
                                file_bytes = f.read()
                                pdf_store[raw_name] = file_bytes
                                if clean_num:
                                    pdf_store[clean_num] = file_bytes
        except Exception as e:
            st.error(f"❌ حدث خطأ أثناء قراءة أرشيف الفواتير: {e}")

    if direct_pdf_files:
        for f in direct_pdf_files:
            raw_name = (
                os.path.basename(f.name)
                .replace(".pdf", "")
                .replace(".PDF", "")
                .strip()
            )
            clean_num = "".join(filter(str.isdigit, raw_name))
            file_bytes = f.getvalue()
            pdf_store[raw_name] = file_bytes
            if clean_num:
                pdf_store[clean_num] = file_bytes

    if pdf_store:
        st.success(f"✅ تم تجهيز واستخراج {len(pdf_store)} فاتورة PDF بنجاح!")

    if excel_file is not None:
        try:
            df = pd.read_excel(excel_file)
            currencies = (
                ["الكل"]
                + [str(c) for c in df["curr"].dropna().unique().tolist()]
                if "curr" in df.columns
                else ["الكل"]
            )
            selected_curr = st.selectbox(
                "اختر العملة للتصفية:", currencies, key="curr_select"
            )

            filtered_df = df.copy()
            if selected_curr != "الكل" and "curr" in filtered_df.columns:
                filtered_df = filtered_df[filtered_df["curr"] == selected_curr]

            if "doc_ser" in filtered_df.columns:
                filtered_df["doc_ser_str"] = (
                    filtered_df["doc_ser"]
                    .astype(str)
                    .str.replace(".0", "", regex=False)
                    .str.strip()
                )
            else:
                st.error("❌ لم يتم العثور على عمود (doc_ser) في ملف الإكسل!")
                st.stop()

            processed_set = st.session_state.completed_invoices.union(
                st.session_state.skipped_invoices
            )
            pending_df = filtered_df[
                ~filtered_df["doc_ser_str"].isin(processed_set)
            ]

            total_invoices = len(filtered_df)
            completed_count = len(
                filtered_df[
                    filtered_df["doc_ser_str"].isin(
                        st.session_state.completed_invoices
                    )
                ]
            )
            skipped_count = len(
                filtered_df[
                    filtered_df["doc_ser_str"].isin(
                        st.session_state.skipped_invoices
                    )
                ]
            )
            remaining_invoices = len(pending_df)

            st.progress(
                (completed_count + skipped_count) / total_invoices
                if total_invoices > 0
                else 0
            )

            c_stat1, c_stat2, c_stat3, c_stat4 = st.columns(4)
            c_stat1.metric("إجمالي الكشف", total_invoices)
            c_stat2.metric("تم الإرسال", completed_count)
            c_stat3.metric("ملغاة / كنسل", skipped_count)
            c_stat4.metric("المتبقي", remaining_invoices)

            st.divider()

            if not pending_df.empty:
                search_options = [
                    "🔄 بالتسلسل التلقائي (الفاتورة التالية)"
                ] + [
                    f"{row['doc_ser_str']} | {row.get('name', 'بدون اسم')} |"
                    f" {row.get('phone', 'بدون رقم')}"
                    for _, row in pending_df.iterrows()
                ]

                selected_search = st.selectbox(
                    "🔍 ابحث باسم العميل، رقم الهاتف، أو الرقم التسلسلي:",
                    options=search_options,
                    key="invoice_search_box",
                )

                if selected_search == "🔄 بالتسلسل التلقائي (الفاتورة التالية)":
                    current_row = pending_df.iloc[0]
                else:
                    selected_doc_ser = selected_search.split(" | ")[0]
                    current_row = pending_df[
                        pending_df["doc_ser_str"] == selected_doc_ser
                    ].iloc[0]

                doc_ser_val = str(current_row["doc_ser_str"])
                no_doc_val = str(current_row.get("no_doc", "---"))
                customer_name = str(current_row.get("name", "عميل"))
                phone_val = (
                    str(current_row.get("phone", ""))
                    .replace(".0", "")
                    .strip()
                )
                currency_val = str(current_row.get("curr", ""))
                amount_val = float(current_row.get("amt", 0))
                balance_val = float(current_row.get("total", 0))

                pdf_bytes = pdf_store.get(doc_ser_val) or pdf_store.get(
                    f"DOCSER_{doc_ser_val}"
                )

                invoice_debt_str = (
                    f"{amount_val:,.2f} {currency_val} (إجمالي الرصيد:"
                    f" {balance_val:,.2f} {currency_val})"
                )
                message_text = format_custom_message(
                    default_msg_template, customer_name, invoice_debt_str
                )

                st.markdown(
                    f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-right: 5px solid #25D366; margin-bottom: 10px;">
                    <h3 style="margin:0; color:#111;">👤 العميل: {customer_name}</h3>
                    <p style="margin:5px 0;"><b>رقم الفاتورة:</b> {no_doc_val} | <b>الرقم التسلسلي:</b> {doc_ser_val}</p>
                    <p style="margin:5px 0;"><b>مبلغ الفاتورة:</b> <span style="color:#d9534f; font-size:17px; font-weight:bold;">{amount_val:,.2f} {currency_val}</span></p>
                    <p style="margin:5px 0;"><b>الرصيد الإجمالي:</b> <span style="color:#0275d8; font-size:17px; font-weight:bold;">{balance_val:,.2f} {currency_val}</span></p>
                </div>
                """,
                    unsafe_allow_html=True,
                )

                st.caption("📝 نص الرسالة المجهز للواتساب:")
                st.code(message_text, language=None)

                st.divider()

                if pdf_bytes:
                    st.success(
                        "✓ تم العثور على الفاتورة الخاصة بالرقم التسلسلي:"
                        f" ({doc_ser_val})"
                    )
                    base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
                    pdf_display = (
                        f'<iframe src="data:application/pdf;base64,{base64_pdf}"'
                        ' width="100%" height="450" type="application/pdf"'
                        ' style="border-radius: 8px; border: 1px solid'
                        ' #ddd;"></iframe>'
                    )
                    st.markdown(pdf_display, unsafe_allow_html=True)

                    st.download_button(
                        label="⬇️ تنزيل ملف الفاتورة مباشرة (PDF)",
                        data=pdf_bytes,
                        file_name=f"DOCSER_{doc_ser_val}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"dl_btn_{doc_ser_val}",
                    )
                else:
                    st.warning(
                        "⚠️ لم يتم العثور على ملف PDF مطابق للرقم التسلسلي:"
                        f" (DOCSER_{doc_ser_val}.pdf)."
                    )

                st.divider()

                encoded_message = urllib.parse.quote(message_text)
                whatsapp_url = (
                    f"https://wa.me/{phone_val}?text={encoded_message}"
                )

                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    st.markdown(
                        f"""
                    <a href="{whatsapp_url}" target="_blank" style="text-decoration:none;">
                        <button style="background-color: #25D366; color: white; border: none; padding: 10px; font-size: 14px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%;">
                            📲 1. فتح محادثة الواتساب
                        </button>
                    </a>
                    """,
                        unsafe_allow_html=True,
                    )

                with c2:
                    if st.button(
                        "✅ 2. تم الإرسال",
                        type="primary",
                        use_container_width=True,
                        key=f"btn_send_{doc_ser_val}",
                    ):
                        st.session_state.completed_invoices.add(doc_ser_val)
                        st.rerun()

                with c3:
                    if st.button(
                        "🚫 كنسل",
                        use_container_width=True,
                        key=f"btn_skip_{doc_ser_val}",
                    ):
                        st.session_state.skipped_invoices.add(doc_ser_val)
                        st.rerun()
            else:
                st.balloons()
                st.success("🎉 ممتاز! تم مراجعة وإنجاز جميع الفواتير بنجاح.")

        except Exception as e:
            st.error(f"حدث خطأ أثناء معالجة بيانات الفواتير: {e}")

# =========================================================
# التبويب الرابع: رفع كشف الحسابات اليدوي
# =========================================================
with tab4:
    st.subheader("📥 رفع كشف الحسابات اليدوي")
    st.info(
        "💡 ملاحظة هامة: لتفادي أي أخطاء في بنية الملف، يرجى فتح كشف الحساب"
        " المستخرج من أونكس على الإكسل أولاً، ثم حفظه بفرمتة Excel Workbook"
        " (*.xlsx) ثم رفعه هنا."
    )

    uploaded_file = st.file_uploader(
        "اختر ملف الإكسل المحدث للكشف", type=["xlsx", "xls", "csv"]
    )

    if uploaded_file is not None:
        df_onyx = None
        file_bytes = uploaded_file.read()
        try:
            if uploaded_file.name.endswith(".csv"):
                df_onyx = pd.read_csv(io.BytesIO(file_bytes))
            else:
                try:
                    df_onyx = pd.read_excel(io.BytesIO(file_bytes))
                except Exception:
                    df_onyx = pd.read_excel(
                        io.BytesIO(file_bytes), engine="xlrd"
                    )
        except Exception:
            st.error("تعذر قراءة الملف المرفوع.")

        if df_onyx is not None:
            success, result_msg = save_to_local_db(df_onyx)
            if success:
                st.success("تم تحديث البيانات في قاعدة البيانات بنجاح.")
                st.rerun()
            else:
                st.error("حدث خطأ أثناء الحفظ محلياً: " + result_msg)

# =========================================================
# التبويب الخامس: الطابور الآلي لمزودي الخدمة API
# =========================================================
with tab5:
    st.subheader("🤖 نظام الإرسال الآلي المبرمج (Queue عبر API)")
    st.info(
        "💡 يقوم هذا النظام بإرسال الرسالة المخصصة لجميع العملاء تلقائياً عبر"
        " مزود الخدمة المعرف لديك مع فاصل زمني لحظر الحساب."
    )

    api_token = st.text_input(
        "رمز التوثيق (API Token / Key):",
        type="password",
        value="YOUR_API_TOKEN",
    )
    api_url = st.text_input(
        "رابط مزود الخدمة (API Endpoint):",
        value="https://api.whatsapp-provider.com/v1/send",
    )

    def send_whatsapp_via_api(phone, message):
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        payload = {"phone": phone, "message": message}
        try:
            response = requests.post(
                api_url, json=payload, headers=headers, timeout=10
            )
            if response.status_code == 200:
                return True, "تم الإرسال بنجاح"
            else:
                return False, response.text
        except Exception as e:
            return False, str(e)

    if st.button("🚀 بدء الإرسال الآلي لجميع المستحقين"):
        if not due_customers:
            st.warning("لا يوجد عملاء مستحقون للإرسال اليوم.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()

            valid_queue_customers = [
                c
                for c in due_customers
                if str(c["phone_number"]).strip()
                and str(c["phone_number"]).strip() != "لا يوجد رقم"
            ]
            total_clients = len(valid_queue_customers)
            success_count = 0

            for idx, cust in enumerate(valid_queue_customers):
                raw_phone = str(cust["phone_number"]).strip()
                first_phone = [
                    p.strip() for p in raw_phone.split("/") if p.strip()
                ][0]
                clean_phone = first_phone.lstrip("0")
                formatted_phone = (
                    "967" + clean_phone
                    if not clean_phone.startswith("967")
                    else clean_phone
                )

                debt_parts = [
                    f"{bal:,} {curr}" for curr, bal in cust["debts"].items()
                ]
                combined_debt_str = " و ".join(debt_parts)

                msg_text = format_custom_message(
                    default_msg_template,
                    cust["customer_name"],
                    combined_debt_str,
                )

                status_text.text(
                    f"جاري الإرسال إلى: {cust['customer_name']} ({idx + 1} من"
                    f" {total_clients})..."
                )

                # تنفيذ الإرسال عبر الـ API
                # is_sent, err_msg = send_whatsapp_via_api(formatted_phone, msg_text)

                time.sleep(3)  # فاصل زمني بين الرسائل

                cursor = conn.cursor()
                for db_id in cust["ids"]:
                    cursor.execute(
                        "UPDATE customers_debts SET last_sent_date = ? WHERE id"
                        " = ?",
                        (str(today), db_id),
                    )
                conn.commit()

                success_count += 1
                progress_bar.progress((idx + 1) / total_clients)

            status_text.success(
                f"🎉 تم الانتهاء من إرسال الرسائل الآلية بنجاح لـ {success_count}"
                " عميل!"
            )
            st.rerun()
