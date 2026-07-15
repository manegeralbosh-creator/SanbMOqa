import streamlit as st
import pandas as pd
import urllib.parse

# إعدادات الصفحة العامة للتطبيق
st.set_page_config(
    page_title="نظام محلات البوش للحسابات",
    page_icon="📊",
    layout="centered"
)

# تصميم وتنسيق الواجهة باللون الكحلي والأزرق المناسب لهوية محلات البوش
st.markdown("""
    <style>
    .main-title {
        color: #1E3A8A;
        text-align: center;
        font-family: 'Cairo', sans-serif;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .sub-title {
        color: #4B5563;
        text-align: center;
        font-family: 'Cairo', sans-serif;
        font-size: 16px;
        margin-bottom: 25px;
    }
    .stButton>button {
        background-color: #1E3A8A;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #2563EB;
        color: white;
    }
    </style>
""", unsafe_index=True)

st.write('<h1 class="main-title">📊 نظام محلات البوش لخدمات الحسابات المتكامل</h1>', unsafe_allow_html=True)
st.write('<p class="sub-title">إدارة مديونيات السوق الرسمية - معالجة الحسابات وإرسال الإشعارات المدمجة</p>', unsafe_allow_html=True)

# تقسيم الشاشة إلى تبويبات (Tabs) لتنظيم العرض
tab1, tab2 = st.tabs(["📥 رفع وتحديث كشف الحساب", "🚀 الإرسال الجماعي والتفاصيل"])

with tab1:
    st.subheader("📁 رفع ملف مديونيات العملاء")
    uploaded_file = st.file_uploader("اختر ملف الإكسل الخاص بالمديونيات (xlsx, xls)", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        # قراءة ملف الإكسل
        df = pd.read_excel(uploaded_file)
        
        # تنظيف أسماء الأعمدة لحمايتها من الفراغات الزائدة
        df.columns = df.columns.str.strip()
        
        # التأكد من وجود الأعمدة الأساسية في الملف المعالج
        required_cols = ['العميل', 'الهاتف', 'المبلغ', 'العملة']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"⚠️ الملف المرفوع يفتقد للأعمدة التالية: {', '.join(missing_cols)}")
            st.info("تأكد من مطابقة أسماء الأعمدة في ملف الإكسل لـ: (العميل - الهاتف - المبلغ - العملة)")
        else:
            # 🧠 منطق تجميع المديونيات للعميل ذي العملتين
            grouped_debts = {}
            
            for index, row in df.iterrows():
                # قراءة البيانات مع تحويل رقم الهاتف لنص لتفادي المشاكل
                phone = str(row['الهاتف']).strip().split('.')[0] 
                name = str(row['العميل']).strip()
                amount = float(row['المبلغ'])
                currency = str(row['العملة']).strip()
                
                # استخدام رقم الهاتف كمفتاح للتجميع (أو الاسم إذا كان الهاتف غير متوفر)
                key = phone if phone and phone != 'nan' else name
                
                if key not in grouped_debts:
                    grouped_debts[key] = {
                        'name': name,
                        'phone': phone,
                        'debts': {}
                    }
                
                # إضافة المبلغ للعملة المحددة للعميل
                if currency in grouped_debts[key]['debts']:
                    grouped_debts[key]['debts'][currency] += amount
                else:
                    grouped_debts[key]['debts'][currency] = amount

            # إنشاء قائمة لتخزين البيانات المدمجة تمهيداً لعرضها
            processed_data = []
            
            for key, info in grouped_debts.items():
                name = info['name']
                phone = info['phone']
                debts = info['debts']
                
                # صياغة تفاصيل المديونية للرسالة
                debt_details = []
                # تفصيل الحسابات للعرض في الجدول
                yemeni_amount = debts.get('يمني', 0.0)
                saudi_amount = debts.get('سعودي', 0.0)
                
                if yemeni_amount > 0:
                    debt_details.append(f"*{yemeni_amount:,.2f} يمني*")
                if saudi_amount > 0:
                    debt_details.append(f"*{saudi_amount:,.2f} سعودي*")
                
                # إذا كانت هناك مديونيات فعلية، صغ الرسالة المدمجة
                if debt_details:
                    # ربط المديونيات بـ "و" في حال وجود العملتين معاً
                    debts_text = " و ".join(debt_details)
                    
                    # صياغة الرسالة النهائية الموحدة والمثالية للإرسال
                    msg_text = f"عزيزنا العميل {name}، يرجى العلم بأن مديونيتكم المتبقية لمحلات البوش هي: {debts_text}. شاكرين تعاونكم وسرعة سدادكم."
                    
                    # تجهيز رابط واتساب مباشر لتسهيل الإرسال اليدوي بنقرة زر
                    encoded_msg = urllib.parse.quote(msg_text)
                    whatsapp_link = f"https://wa.me/{phone}?text={encoded_msg}" if phone and phone != 'nan' else "#"
                    
                    processed_data.append({
                        "العميل": name,
                        "الهاتف": phone,
                        "مديونية يمني": yemeni_amount,
                        "مديونية سعودي": saudi_amount,
                        "نص الرسالة الموحد": msg_text,
                        "رابط واتساب": whatsapp_link
                    })
            
            # تحويل البيانات المعالجة إلى DataFrame للعرض
            final_df = pd.DataFrame(processed_data)
            
            with tab1:
                st.success("✅ تم معالجة وتجميع الحسابات بنجاح!")
                # عرض كشف الحسابات الإجمالي للعملاء
                st.subheader("📋 ملخص الحسابات المدمجة")
                st.dataframe(final_df[["العميل", "الهاتف", "مديونية يمني", "مديونية سعودي"]])

            with tab2:
                st.subheader("💬 قائمة الرسائل الجاهزة للإرسال")
                st.caption("اضغط على زر 'إرسال عبر واتساب' لفتح المحادثة بالنص المدمج تلقائياً")
                
                # عرض كروت إرسال مخصصة لكل عميل بوضوح وسلاسة
                for idx, row in final_df.iterrows():
                    with st.container():
                        st.markdown(f"### 👤 {row['العميل']} ({row['الهاتف']})")
                        st.info(row['نص الرسالة الموحد'])
                        
                        if row['رابط واتساب'] != "#":
                            st.markdown(f"[📲 إرسال رسالة واتساب مدمجة]({row['رابط واتساب']})", unsafe_allow_html=True)
                        else:
                            st.warning("⚠️ لا يتوفر رقم هاتف صحيح للارسال المباشر")
                        st.write("---")
                        
    except Exception as e:
        st.error(f"❌ حدث خطأ أثناء معالجة الملف: {str(e)}")
else:
    with tab1:
        st.info("💡 بانتظار رفع كشف الإكسل للبدء في دمج وتجهيز الرسائل...")
