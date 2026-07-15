import streamlit as st
import pandas as pd
import urllib.parse

# إعدادات الصفحة البسيطة والمباشرة
st.set_page_config(
    page_title="نظام محلات البوش لخدمات الحسابات المتكامل",
    page_icon="📊",
    layout="wide"
)

# عنوان النظام الرئيسي تماماً كما كان في البداية
st.markdown("<h1 style='text-align: center; color: #1E3A8A; font-family: Cairo;'>📊 نظام محلات البوش لخدمات الحسابات المتكامل</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #4B5563; font-size: 18px;'>إدارة مديونيات السوق الرسمية - نسخة قاعدة البيانات المحلية المطورة</p>", unsafe_allow_html=True)
st.write("---")

# زر رفع الملف المعتاد في الواجهة الرئيسية
uploaded_file = st.file_uploader("📥 رفع وتحديث كشف الحساب (ملف إكسل)", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        # قراءة البيانات وتنظيفها
        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip()
        
        # التأكد من الأعمدة
        required_cols = ['العميل', 'الهاتف', 'المبلغ', 'العملة']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            st.error(f"⚠️ الملف يفتقد للأعمدة: {', '.join(missing_cols)}")
        else:
            # 🧠 منطق دمج العملتين للعميل في رسالة واحدة
            grouped_debts = {}
            for index, row in df.iterrows():
                phone = str(row['الهاتف']).strip().split('.')[0]
                name = str(row['العميل']).strip()
                amount = float(row['المبلغ'])
                currency = str(row['العملة']).strip()
                
                key = phone if phone and phone != 'nan' else name
                
                if key not in grouped_debts:
                    grouped_debts[key] = {
                        'name': name,
                        'phone': phone,
                        'debts': {}
                    }
                
                # تجميع المبالغ حسب العملة
                if currency in grouped_debts[key]['debts']:
                    grouped_debts[key]['debts'][currency] += amount
                else:
                    grouped_debts[key]['debts'][currency] = amount

            # بناء جدول البيانات المعروضة والرسائل
            processed_rows = []
            for key, info in grouped_debts.items():
                name = info['name']
                phone = info['phone']
                debts = info['debts']
                
                # حساب المبالغ بالتفصيل للجدول
                yemeni_val = debts.get('يمني', 0.0)
                saudi_val = debts.get('سعودي', 0.0)
                
                # صياغة الرسالة المدمجة الذكية
                debt_text_parts = []
                if yemeni_val > 0:
                    debt_text_parts.append(f"{yemeni_val:,.2f} يمني")
                if saudi_val > 0:
                    debt_text_parts.append(f"{saudi_val:,.2f} سعودي")
                
                if debt_text_parts:
                    # دمج العملات بـ "و" في الرسالة
                    combined_debts = " و ".join(debt_text_parts)
                    msg_text = f"عزيزنا العميل {name}، يرجى العلم بأن مديونيتكم المتبقية لمحلات البوش هي: {combined_debts}. شاكرين تعاونكم وسرعة سدادكم."
                    
                    encoded_msg = urllib.parse.quote(msg_text)
                    whatsapp_link = f"https://wa.me/{phone}?text={encoded_msg}" if phone and phone != 'nan' else "#"
                    
                    processed_rows.append({
                        "العميل": name,
                        "الهاتف": phone,
                        "مديونية يمني": yemeni_val,
                        "مديونية سعودي": saudi_val,
                        "نص الرسالة الموحد": msg_text,
                        "رابط واتساب": whatsapp_link
                    })

            # تحويلها لـ DataFrame للعرض المباشر
            final_df = pd.DataFrame(processed_rows)

            # عرض الجدول الرئيسي الفخم والمريح للعين مباشرة
            st.success("✅ تم تحديث كشف الحساب وتجميع المديونيات بنجاح!")
            st.subheader("📋 كشف حساب العملاء الإجمالي")
            st.dataframe(final_df[["العميل", "الهاتف", "مديونية يمني", "مديونية سعودي"]])
            
            st.write("---")
            
            # عرض الرسائل الجاهزة للإرسال في الواجهة الرئيسية مباشرة وبشكل مرتب
            st.subheader("💬 رسائل الإشعارات المدمجة (واتساب)")
            
            # عرض جدول مخصص يحتوي على أزرار إرسال مباشرة لكل عميل بشكل مرتب جداً
            for idx, row in final_df.iterrows():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**👤 {row['العميل']} ({row['الهاتف']})**")
                    st.info(row['نص الرسالة الموحد'])
                with col2:
                    st.write("") # فراغ للترتيب المحاذي
                    st.write("")
                    if row['رابط واتساب'] != "#":
                        st.markdown(f"<a href='{row['رابط واتساب']}' target='_blank' style='display: inline-block; padding: 10px 20px; background-color: #25D366; color: white; text-align: center; text-decoration: none; font-size: 14px; font-weight: bold; border-radius: 8px;'>📲 إرسال واتساب</a>", unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ رقم غير صحيح")
                st.write("---")

    except Exception as e:
        st.error(f"❌ حدث خطأ أثناء قراءة الملف: {str(e)}")
else:
    st.info("💡 الرجاء رفع ملف الإكسل لعرض كشف الحساب والبدء في الإرسال...")
