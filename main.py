import streamlit as st
import pandas as pd
import re
import urllib.parse

# إعدادات الصفحة
st.set_page_config(page_title="نظام محلات البوش لخدمات الحسابات", page_icon="📊", layout="wide")

# تصميم الواجهة والعناوين
st.markdown("""
    <style>
    .reportview-container { background: #faf8f5; }
    .main-title { color: #1E3A8A; text-align: center; font-size: 32px; font-weight: bold; margin-bottom: 20px; }
    .sub-title { color: #4B5563; text-align: center; font-size: 18px; margin-bottom: 30px; }
    .stSelectbox { margin-bottom: -15px; }
    div[data-testid="stBlock"] { padding: 5px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 نظام محلات البوش لخدمات الحسابات والتذكير الآلي</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">إدارة مديونيات السوق، تحديد الفئات، واستثناء العملاء من الإرسال</div>', unsafe_allow_html=True)

# دالة ذكية لاستخراج رقم الهاتف من اسم العميل (أونكس)
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

# خيارات فئات التكرار المتاحة
frequency_options = ["كل 3 أيام", "أسبوعي", "كل أسبوعين", "شهري", "إيقاف التذكير"]

# تهيئة قاعدة البيانات الاسترشادية مع إضافة حالة الاستثناء الافتراضية (مفعل = True)
if 'accounts_data' not in st.session_state:
    st.session_state.accounts_data = pd.DataFrame([
        {"customer": "مؤسسة النجاح للتجارة", "phone": "770000000", "balance": 150000.0, "currency": "YER", "frequency": "أسبوعي", "active": True},
        {"customer": "شركة شمسان للمرطبات", "phone": "730000000", "balance": 2500.0, "currency": "USD", "frequency": "كل 3 أيام", "active": True}
    ])

tab1, tab2 = st.tabs(["📁 الطريقة الأولى: رفع ملف أونكس وتعديل الخيارات", "⚙️ إعدادات الربط التلقائي (المباشر)"])

with tab1:
    st.subheader("📥 معالجة كشف حساب أونكس ERP")
    uploaded_file = st.file_uploader("قم برفع ملف الإكسل المستخرج من أونكس (Excel / CSV)", type=["xlsx", "xls", "csv"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_onyx = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith('.xls'):
                df_onyx = pd.read_excel(uploaded_file, engine='xlrd')
            else:
                df_onyx = pd.read_excel(uploaded_file, engine='openpyxl')
            
            if len(df_onyx.columns) >= 4:
                # الاعتماد التلقائي على الأعمدة بناءً على هيكلة كشوفات أونكس
                col_name = df_onyx.columns[1]   
                col_currency = df_onyx.columns[2] 
                col_balance = df_onyx.columns[3] # يقرأ العمود المختار تلقائياً
                
                parsed_list = []
                for idx, row in df_onyx.iterrows():
                    raw_name = row[col_name]
                    raw_currency = row[col_currency]
                    raw_balance = row[col_balance]
                    
                    phone = extract_yemeni_phone(raw_name)
                    clean_name = clean_customer_name(raw_name)
                    
                    try:
                        balance_val = float(str(raw_balance).replace(',', ''))
                    except:
                        balance_val = 0.0
                        
                    if balance_val > 0:
                        parsed_list.append({
                            "customer": clean_name if clean_name else raw_name,
                            "phone": phone if phone else "لا يوجد رقم",
                            "balance": balance_val,
                            "currency": str(raw_currency).strip(),
                            "frequency": "أسبوعي",
                            "active": True # افتراضياً العميل نشط عند الرفع لأول مرة
                        })
                
                if parsed_list:
                    st.session_state.accounts_data = pd.DataFrame(parsed_list)
                    st.success(f"✅ تم بنجاح استيراد {len(parsed_list)} عميل من ملف أونكس بنجاح!")
                else:
                    st.warning("⚠️ لم يتم العثور على مبالغ متبقية أكبر من الصفر في العمود المحدد.")
            else:
                st.error("❌ بنية الملف غير مطابقة لتقرير أونكس القياسي.")
        except Exception as e:
            st.error(f"❌ حدث خطأ أثناء قراءة الملف: {str(e)}")

    # عرض جدول التخصيص والاستثناء التفاعلي
    st.write("### 📋 كشف حسابات السوق وتخصيص فئات وإجراءات التذكير:")
    
    if not st.session_state.accounts_data.empty:
        # ترويسة الجدول التفاعلي متضمنة خانة الإجراءات (الاستثناء)
        col_c1, col_c2, col_c3, col_c4, col_c5, col_c6 = st.columns([3, 1.5, 1.5, 1, 1.5, 1.5])
        with col_c1: st.markdown("**العميل**")
        with col_c2: st.markdown("**الهاتف**")
        with col_c3: st.markdown("**المبلغ المتبقي**")
        with col_c4: st.markdown("**العملة**")
        with col_c5: st.markdown("**فئة التكرار ⚙️**")
        with col_c6: st.markdown("**حالة الإرسال 🛠️**")
        st.markdown("---")
        
        # إنشاء مصفوفة لتحديث البيانات بناءً على تفاعل الأزرار والقوائم
        updated_rows = []
        
        for idx, row in st.session_state.accounts_data.iterrows():
            # التأكد من وجود مفتاح النشاط لتجنب الأخطاء عند التحديثات الحية
            is_active = row.get("active", True)
            
            c1, c2, c3, c4, c5, c6 = st.columns([3, 1.5, 1.5, 1, 1.5, 1.5])
            
            # في حال تم استثناء العميل، يظهر النص بلون باهت لتمييزه بصرياً
            with c1: st.write(f"<s>{row['customer']}</s>" if not is_active else row['customer'], unsafe_allow_html=True)
            with c2: st.write(f"<s>{row['phone']}</s>" if not is_active else row['phone'], unsafe_allow_html=True)
            with c3: st.write(f"<s>{row['balance']:,.2f}</s>" if not is_active else f"{row['balance']:,.2f}", unsafe_allow_html=True)
            with c4: st.write(f"<s>{row['currency']}</s>" if not is_active else row['currency'], unsafe_allow_html=True)
            
            with c5:
                current_freq = row.get("frequency", "أسبوعي")
                if current_freq not in frequency_options:
                    current_freq = "أسبوعي"
                
                chosen_freq = st.selectbox(
                    f"فئة {row['customer']}", 
                    frequency_options, 
                    index=frequency_options.index(current_freq),
                    key=f"freq_{idx}",
                    label_visibility="collapsed",
                    disabled=not is_active # تعطيل القائمة المنسدلة للعملاء المستثنين
                )
            
            with c6:
                # زر الاستثناء والتفعيل التفاعلي لكل عميل على حدة
                if is_active:
                    if st.button("🚫 استثناء", key=f"ban_{idx}", use_container_width=True):
                        is_active = False
                        st.rerun()
                else:
                    if st.button("✅ تفعيل", key=f"act_{idx}", use_container_width=True):
                        is_active = True
                        st.rerun()
            
            updated_rows.append({
                "customer": row["customer"],
                "phone": row["phone"],
                "balance": row["balance"],
                "currency": row["currency"],
                "frequency": chosen_freq,
                "active": is_active
            })
            
        # حفظ التحديثات مباشرة في قاعدة بيانات الجلسة الحالية
        st.session_state.accounts_data = pd.DataFrame(updated_rows)
        
        st.markdown("---")
        st.write("### 🚀 إرسال التذكيرات والمتابعة الجاهزة")
        
        # فلترة القائمة المنسدلة النهائية بحيث لا تعرض "العملاء المستثنين" أبداً في أزرار الإرسال
        active_clients_df = st.session_state.accounts_data[st.session_state.accounts_data["active"] == True]
        
        if not active_clients_df.empty:
            client_options = active_clients_df["customer"].tolist()
            selected_client = st.selectbox("اختر العميل المراد مراسلته وتفقد خياراته الحالية:", client_options)
            
            client_row = active_clients_df[active_clients_df["customer"] == selected_client].iloc[0]
            client_phone = client_row["phone"]
            client_amount = client_row["balance"]
            client_curr = client_row["currency"]
            client_freq = client_row["frequency"]
            
            msg = f"تحية طيبة من محلات البوش لقطع غيار الشاحنات.\nنود تذكيركم برصيد حسابكم المتبقي لدينا وهو: {client_amount:,.2f} {client_curr}.\nيرجى التكرم بتصفية الحساب، شاكرين تعاونكم وثقتكم بنا."
            encoded_msg = urllib.parse.quote(msg)
            
            if client_phone and client_phone != "لا يوجد رقم":
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    whatsapp_phone = "967" + client_phone if not client_phone.startswith("967") else client_phone
                    whatsapp_url = f"https://api.whatsapp.com/send?phone={whatsapp_phone}&text={encoded_msg}"
                    st.markdown(f'<a href="{whatsapp_url}" target="_blank"><button style="background-color: #25D366; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; width: 100%;">💬 إرسال عبر واتساب</button></a>', unsafe_allow_html=True)
                
                with col_btn2:
                    sms_url = f"sms:{client_phone}?body={encoded_msg}"
                    st.markdown(f'<a href="{sms_url}"><button style="background-color: #1E3A8A; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; width: 100%;">📱 إرسال SMS مجاني من الشريحة</button></a>', unsafe_allow_html=True)
            else:
                st.warning("⚠️ هذا العميل لا يمتلك رقم هاتف مستخرج من النظام.")
        else:
            st.warning("💡 لقد قمت باستثناء جميع العملاء الحاليين من الإرسال، لا توجد جهات إشعار متاحة حالياً.")
    else:
        st.info("💡 الجدول فارغ حالياً، قم برفع ملف أونكس بالأعلى.")

with tab2:
    st.subheader("🔌 إعدادات الربط الآلي المباشر (API)")
    st.info("🔗 هذا القسم مخصص لربط سيرفر أونكس في المحل مباشرة بالويب لرفع المديونيات تلقائياً.")
