import streamlit as st
import pandas as pd
import re
import urllib.parse
import urllib.request
import os
from fpdf import FPDF

# إعدادات الصفحة الأساسية
st.set_page_config(page_title="نظام محلات البوش لخدمات الحسابات", page_icon="📊", layout="wide")

# تصميم الواجهة والعناوين
st.markdown("""
    <style>
    .reportview-container { background: #faf8f5; }
    .main-title { color: #1E3A8A; text-align: center; font-size: 32px; font-weight: bold; margin-bottom: 20px; }
    .sub-title { color: #4B5563; text-align: center; font-size: 18px; margin-bottom: 30px; }
    .stSelectbox, .stTextInput { margin-bottom: -15px; }
    div[data-testid="stBlock"] { padding: 5px; }
    .client-card { background-color: #ffffff; padding: 12px; border-radius: 8px; border-right: 5px solid #1E3A8A; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .copy-btn { background-color: #F59E0B; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 14px; cursor: pointer; font-weight: bold; width: 100%; display: block; text-align: center; text-decoration: none; line-height: 20px; }
    .metric-box { background-color: #EFF6FF; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 1px 2px rgba(0,0,0,0.05); border: 1px solid #BFDBFE; }
    </style>
    
    <script>
    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(function() {
            alert("📋 تم نسخ اسم العميل: (" + text + ")\\n\\nيمكنك الآن الانتقال لجهات اتصال جوالك ولصق الاسم في البحث.");
        }, function(err) {
            alert("فشل النسخ التلقائي، يرجى تحديد الاسم ونسخه يدوياً.");
        });
    }
    </script>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات والتذكير الآلي</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">إدارة مديونيات السوق، الإحصائيات الذكية، وتوليد كشوفات PDF فورية</div>', unsafe_allow_html=True)

# دالة لتحميل خط عربي يدعم الـ Unicode تلقائياً لمنع خطأ الترميز
@st.cache_resource
def download_arabic_font():
    font_path = "Amiri-Regular.ttf"
    if not os.path.exists(font_path):
        # تحميل خط أميري العربي من خوادم جوجل للخطوط بشكل آمن
        url = "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf"
        try:
            urllib.request.urlretrieve(url, font_path)
        except:
            pass
    return font_path

# تشغيل دالة تجهيز الخط
font_file = download_arabic_font()

# دالة ذكية لاستخراج رقم الهاتف من اسم العميل وتجنب الأصفار الزائدة بالبداية
def extract_yemeni_phone(text):
    if pd.isna(text):
        return ""
    text_str = str(text)
    text_str = text_str.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    match = re.search(r'(77\d{7}|73\d{7}|71\d{7}|70\d{7})', text_str)
    if match:
        return match.group(1)
    return ""

# دالة لتنظيف اسم العميل من الأرقام والرموز الزائدة
def clean_customer_name(text):
    if pd.isna(text):
        return ""
    text_str = str(text)
    text_clean = re.sub(r'[/\\\-\d]+.*', '', text_str)
    return text_clean.strip()

# دالة آمنة ومحدثة لتوليد ملف PDF يدعم الأسماء العربية بدون خطأ الترميز
def generate_pdf(customer_name, balance, currency):
    pdf = FPDF()
    pdf.add_page()
    
    # التحقق من وجود ملف الخط وتفعيله لدعم الـ Unicode
    if os.path.exists("Amiri-Regular.ttf"):
        pdf.add_font("Amiri", "", "Amiri-Regular.ttf")
        pdf.set_font("Amiri", size=16)
    else:
        pdf.set_font("Helvetica", size=14)
        
    # عنوان الكشف
    pdf.cell(200, 10, txt="Al-Boush Trading Establishment", ln=True, align='C')
    pdf.cell(200, 10, txt="Statement of Account / Debt Reminder", ln=True, align='C')
    pdf.ln(10)
    
    # تفاصيل الحساب (تصفية النص لمنع الأخطاء)
    safe_name = str(customer_name).encode('utf-8', 'ignore').decode('utf-8')
    pdf.cell(200, 10, txt=f"Customer Name: {safe_name}", ln=True, align='L')
    pdf.cell(200, 10, txt=f"Outstanding Balance: {balance:,} {currency}", ln=True, align='L')
    pdf.ln(10)
    
    # ملاحظة تذكيرية
    notice = "Kindly review and settle the above outstanding balance at your earliest convenience. Thank you for your cooperation."
    pdf.multi_cell(0, 10, txt=notice)
    
    return pdf.output(dest='S')

# خيارات فئات التكرار المتاحة
frequency_options = ["كل 3 أيام", "أسبوعي", "كل أسبوعين", "شهري", "إيقاف التذكير"]

# تهيئة البيانات الأساسية في جلسة العمل
if 'raw_accounts' not in st.session_state:
    st.session_state.raw_accounts = []

if 'freq_dict' not in st.session_state:
    st.session_state.freq_dict = {}

if 'custom_phones' not in st.session_state:
    st.session_state.custom_phones = {}

tab1, tab2 = st.tabs(["📁 رفع ملف أونكس وإرسال التذكيرات", "⚙️ إعدادات الربط التلقائي (المباشر)"])

with tab1:
    st.subheader("📥 معالجة كشف حساب أونكس ERP")
    uploaded_file = st.file_uploader("قم برفع ملف الإكسل المستخرج من أونكس (Excel / CSV)", type=["xlsx", "xls", "csv"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_onyx = pd.read_csv(uploaded_file)
            else:
                df_onyx = pd.read_excel(uploaded_file, list(pd.read_excel(uploaded_file, sheet_name=None).keys())[0])
            
            if len(df_onyx.columns) >= 4:
                col_name = df_onyx.columns[1]   
                col_currency = df_onyx.columns[2] 
                col_balance = df_onyx.columns[3]
                
                parsed_list = []
                for idx, row in df_onyx.iterrows():
                    raw_name = row[col_name]
                    raw_currency = row[col_currency]
                    raw_balance = row[col_balance]
                    
                    if pd.isna(raw_name) or "اسم العميل" in str(raw_name):
                        continue
                        
                    phone = extract_yemeni_phone(raw_name)
                    clean_name = clean_customer_name(raw_name)
                    
                    try:
                        balance_val = int(float(str(raw_balance).replace(',', '')))
                    except:
                        balance_val = 0
                        
                    if balance_val > 0:
                        cust_id = f"customer_row_{idx}"
                        parsed_list.append({
                            "id": cust_id,
                            "customer": clean_name if clean_name else raw_name,
                            "phone": phone if phone else "لا يوجد رقم",
                            "balance": balance_val,
                            "currency": str(raw_currency).strip()
                        })
                
                if parsed_list:
                    st.session_state.raw_accounts = parsed_list
                    st.success(f"✅ تم بنجاح استيراد {len(parsed_list)} عميل من ملف أونكس!")
                else:
                    st.warning("⚠️ لم يتم العثور على مبالغ متبقية أكبر من الصفر.")
            else:
                st.error("❌ بنية الملف غير مطابقة لتقرير أونكس القياسي.")
        except Exception as e:
            st.error(f"❌ حدث خطأ أثناء معالجة الملف، يرجى التأكد من حفظ الملف بصيغة صالحة.")

    # 📊 قسم لوحة التحكم والإحصائيات الذكية (Dashboard)
    if st.session_state.raw_accounts:
        st.write("### 📊 لوحة ملخص مديونيات السوق الحالية:")
        
        df_stats = pd.DataFrame(st.session_state.raw_accounts)
        currency_groups = df_stats.groupby('currency')['balance'].sum().to_dict()
        total_customers = len(df_stats)
        
        stat_cols = st.columns(len(currency_groups) + 1)
        with stat_cols[0]:
            st.markdown(f'<div class="metric-box"><span style="color:#4B5563; font-weight:bold;">👥 إجمالي العملاء</span><br><span style="font-size:24px; font-weight:bold; color:#1E3A8A;">{total_customers} عميل</span></div>', unsafe_allow_html=True)
        
        col_idx = 1
        for curr, total_amt in currency_groups.items():
            with stat_cols[col_idx]:
                st.markdown(f'<div class="metric-box"><span style="color:#4B5563; font-weight:bold;">💰 إجمالي ديون ({curr})</span><br><span style="font-size:24px; font-weight:bold; color:#B91C1C;">{total_amt:,}</span></div>', unsafe_allow_html=True)
            col_idx += 1
            
        st.markdown("<br>", unsafe_allow_html=True)

    st.write("### 📋 كشف مديونيات السوق وإرسال التذكيرات الفوري:")
    
    if st.session_state.raw_accounts:
        for item in st.session_state.raw_accounts:
            current_phone = st.session_state.custom_phones.get(item["id"], item["phone"])
            
            phone_to_send = str(current_phone).strip()
            if phone_to_send.startswith('0') and len(phone_to_send) > 1:
                phone_to_send = phone_to_send.lstrip('0')
            
            msg = f"تحية طيبة من محلات البوش لقطع غيار الشاحنات.\nنود تذكيركم برصيد حسابكم المتبقي لدينا وهو: {item['balance']:,} {item['currency']}.\nيرجى التكرم بتصفية الحساب، شاكرين تعاونكم وثقتكم بنا."
            encoded_msg = urllib.parse.quote(msg)
            
            st.markdown(f"""
            <div class="client-card">
                <span style="font-size:18px; font-weight:bold; color:#1E3A8A;">👤 {item['customer']}</span> | 
                <span style="color:#4B5563;">📱 الهاتف الحالي: {current_phone}</span> | 
                <span style="font-size:16px; font-weight:bold; color:#B91C1C;">💰 المتبقي: {item['balance']:,} {item['currency']}</span>
            </div>
            """, unsafe_allow_html=True)
            
            col_one, col_two, col_three, col_four, col_five, col_six = st.columns([1, 1.2, 1, 1, 1, 1])
            
            with col_one:
                current_freq = st.session_state.freq_dict.get(item["id"], "أسبوعي")
                chosen_freq = st.selectbox(
                    f"freq_select_{item['id']}", 
                    frequency_options, 
                    index=frequency_options.index(current_freq) if current_freq in frequency_options else 1,
                    key=f"time_{item['id']}",
                    label_visibility="collapsed"
                )
                st.session_state.freq_dict[item["id"]] = chosen_freq
                
            with col_two:
                input_placeholder = "رقم الجوال الجديد"
                new_phone_input = st.text_input(
                    f"phone_input_{item['id']}", 
                    value="" if current_phone == "لا يوجد رقم" else current_phone,
                    placeholder=input_placeholder,
                    key=f"input_{item['id']}",
                    label_visibility="collapsed"
                )
                if new_phone_input.strip() != "" and new_phone_input.strip() != "لا يوجد رقم":
                    st.session_state.custom_phones[item["id"]] = new_phone_input.strip()
                    current_phone = new_phone_input.strip()
                    phone_to_send = current_phone.lstrip('0')
            
            with col_three:
                customer_escaped = item['customer'].replace("'", "\\'")
                st.markdown(f'<button class="copy-btn" onclick="copyToClipboard(\'{customer_escaped}\')">📋 نسخ الاسم</button>', unsafe_allow_html=True)
            
            with col_four:
                # توليد الملف الآمن
                try:
                    pdf_data = generate_pdf(item['customer'], item['balance'], item['currency'])
                    st.download_button(
                        label="📄 كشف PDF",
                        data=pdf_data,
                        file_name=f"كشف_حساب_{item['customer']}.pdf",
                        mime="application/pdf",
                        key=f"pdf_{item['id']}",
                        use_container_width=True
                    )
                except:
                    st.button("⚠️ خطأ كشف", key=f"pdf_err_{item['id']}", disabled=True, use_container_width=True)
                
            with col_five:
                if phone_to_send and phone_to_send != "لا يوجد رقم":
                    whatsapp_phone = "967" + phone_to_send if not phone_to_send.startswith("967") else phone_to_send
                    whatsapp_url = f"https://api.whatsapp.com/send?phone={whatsapp_phone}&text={encoded_msg}"
                    st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background-color: #25D366; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 14px; cursor: pointer; font-weight: bold; width: 100%;">💬 واتساب</button></a>', unsafe_allow_html=True)
                else:
                    st.button("🚫 رقم", key=f"wa_err_{item['id']}", disabled=True, use_container_width=True)
                    
            with col_six:
                if phone_to_send and phone_to_send != "لا يوجد رقم":
                    sms_url = f"sms:{phone_to_send}?body={encoded_msg}"
                    st.markdown(f'<a href="{sms_url}"><button style="background-color: #1E3A8A; color: white; border: none; padding: 6px 12px; border-radius: 4px; font-size: 14px; cursor: pointer; font-weight: bold; width: 100%;">📱 SMS</button></a>', unsafe_allow_html=True)
                else:
                    st.button("🚫 ناقص", key=f"sms_err_{item['id']}", disabled=True, use_container_width=True)
            
            st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)
    else:
        st.info("💡 الجدول فارغ حالياً، قم برفع ملف أونكس بالأعلى لعرض لوحة الإحصائيات وبيانات العملاء.")

with tab2:
    st.subheader("🔌 إعدادات الربط الآلي المباشر (API)")
    st.info("🔗 هذا القسم مخصص لربط سيرفر أونكس في المحل مباشرة بالويب لرفع المديونيات تلقائياً.")
