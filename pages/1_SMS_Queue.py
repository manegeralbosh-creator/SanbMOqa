import streamlit as st
import pandas as pd
import urllib.parse

st.set_page_config(page_title="طابور فواتير الشريحة", page_icon="📱", layout="wide")

st.title("📱 طابور إرسال الفواتير الشاملة (عبر شريحة SMS)")
st.write("ربط آلي ببيانات الإكسل عبر كود الفاتورة وتجميع الأصناف والرصيد بضغطة زر.")

# 1. قسم رفع الملفات (يقبل جميع صيغ الضغط والإكسل)
st.subheader("📂 رفع ملفات النظام")
col_f1, col_f2 = st.columns(2)

with col_f1:
    excel_file = st.file_uploader("اختر ملف الفواتير (Excel)", type=["xlsx", "xls"])

with col_f2:
    # تم إزالة التقييد بـ zip لتقبل جميع صيغ الملفات المضغوطة (RAR, 7Z, ZIP, TAR...)
    compressed_file = st.file_uploader("اختر ملف المرفقات المضغوط (جميع الصيغ)", type=None)

# 2. معالجة وتجميع بيانات الإكسل بناءً على كود الفاتورة (العمود الأول)
invoices_dict = {}

if excel_file is not None:
    df = pd.read_excel(excel_file)
    
    # التعرف على العمود الأول لكود الفاتورة
    code_col = df.columns[0]
    
    for _, row in df.iterrows():
        inv_code = str(row[code_col]).strip()
        
        if inv_code not in invoices_dict:
            invoices_dict[inv_code] = {
                "code": inv_code,
                "customer": str(row.get("اسم العميل", row.get("العميل", "عميل"))),
                "phone": str(row.get("رقم الهاتف", row.get("الهاتف", ""))),
                "old_balance": row.get("الرصيد السابق", row.get("سابق", 0)),
                "net_amount": row.get("صافي الفاتورة", row.get("الإجمالي", 0)),
                "items": []
            }
        
        item_name = row.get("اسم الصنف", row.get("الصنف", ""))
        qty = row.get("الكمية", "")
        if pd.notna(item_name) and str(item_name).strip() != "":
            item_str = f"{item_name} ({qty})" if pd.notna(qty) and qty != "" else f"{item_name}"
            invoices_dict[inv_code]["items"].append(item_str)

    st.success(f"تم تجميع {len(invoices_dict)} فاتورة مستقلة بنجاح من ملف الإكسل!")

if compressed_file is not None:
    st.info(f"تم رفع الملف المضغوط: `{compressed_file.name}` بنجاح.")

st.divider()

# 3. عرض طابور الإرسال وصياغة الرسالة النصية
if invoices_dict:
    st.subheader("📋 طابور الفواتير الجاهزة للإرسال")
    
    for inv_code, inv in invoices_dict.items():
        with st.container():
            c1, c2, c3 = st.columns([3, 4, 3])
            
            items_text = " ، ".join(inv["items"]) if inv["items"] else "تفاصيل محددة بالنظام"
            
            try:
                total_due = float(inv["net_amount"]) + float(inv["old_balance"])
            except:
                total_due = inv["net_amount"]

            sms_text = (
                f"فواتير: الأخ {inv['customer']}\n"
                f"فاتورة رقم: {inv['code']}\n"
                f"الأصناف: {items_text}\n"
                f"قيمة الفاتورة: {inv['net_amount']}\n"
                f"الرصيد السابق: {inv['old_balance']}\n"
                f"الإجمالي المطلوب: {total_due}\n"
                f"شكراً لتعاملكم معنا."
            )
            
            with c1:
                st.markdown(f"**العميل:** {inv['customer']}")
                st.markdown(f"**رقم الفاتورة:** `{inv['code']}`")
                st.caption(f"📞 {inv['phone']}")
                
            with c2:
                st.text_area("نص الرسالة:", value=sms_text, height=120, key=f"txt_{inv_code}")
                
            with c3:
                encoded_body = urllib.parse.quote(sms_text)
                sms_url = f"sms:{inv['phone']}?body={encoded_body}"
                
                st.link_button("📲 إرسال عبر الشريحة", sms_url, use_container_width=True)
                
            st.divider()
else:
    st.info("💡 قم برفع ملف Excel والأرشيف المضغوط للبدء.")
