import base64
import io
import os
import re
import urllib.parse
import zipfile
import pandas as pd
import requests
import json
import streamlit as st

# --- ضبط إعدادات الصفحة ---
st.set_page_config(page_title="نظام الفواتير - محلات البوش", page_icon="📲", layout="wide")

st.subheader('📲 نظام مراجعة وإرسال الفواتير عبر الواتساب (محلات البوش)')

# --- إعدادات Meta WhatsApp API في الشريط الجانبي ---
st.sidebar.header("⚙️ إعدادات Meta WhatsApp API")
api_enabled = st.sidebar.checkbox("تفعيل الإرسال الآلي عبر Meta API", value=True)
ACCESS_TOKEN = st.sidebar.text_input("Access Token", type="password", help="أدخل رمز الوصول الخاص بـ Meta")
PHONE_NUMBER_ID = st.sidebar.text_input("Phone Number ID", help="أدخل معرف رقم الهاتف الخاص بـ API")

st.sidebar.markdown("---")

# 1. تهيئة متغيرات الجلسة للبيانات والملفات
if 'completed_invoices' not in st.session_state:
    st.session_state.completed_invoices = set()

if 'skipped_invoices' not in st.session_state:
    st.session_state.skipped_invoices = set()

if 'pdf_store' not in st.session_state:
    st.session_state.pdf_store = {}

# --- دالة الإرسال عبر Meta WhatsApp Cloud API ---
def send_via_meta_api(phone, message_text, pdf_bytes=None, pdf_name="Invoice.pdf"):
    """دالة لإرسال الرسائل النصية وملفات الـ PDF عبر Meta API"""
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        return False, "يرجى إدخال Access Token و Phone Number ID في الشريط الجانبي أولاً."
    
    # تنظيف رقم الهاتف (إزالة + أو 00)
    clean_phone = re.sub(r'\D', '', str(phone))
    if clean_phone.startswith('00'):
        clean_phone = clean_phone[2:]
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    
    # 1. إرسال النص الأساسي
    payload_text = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "text",
        "text": {"preview_url": False, "body": message_text}
    }
    
    res_text = requests.post(url, headers=headers, json=payload_text)
    
    if res_text.status_code != 200:
        return False, f"فشل إرسال النص: {res_text.text}"
    
    # 2. إرسال ملف الـ PDF إذا كان متوفراً (رفع الملف ثم إرساله)
    if pdf_bytes:
        media_url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/media"
        media_headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        files = {
            'file': (pdf_name, pdf_bytes, 'application/pdf'),
            'messaging_product': (None, 'whatsapp')
        }
        
        media_res = requests.post(media_url, headers=media_headers, files=files)
        if media_res.status_code == 200:
            media_id = media_res.json().get('id')
            
            payload_doc = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": clean_phone,
                "type": "document",
                "document": {
                    "id": media_id,
                    "filename": pdf_name,
                    "caption": f"مرفق فاتورة: {pdf_name}"
                }
            }
            requests.post(url, headers=headers, json=payload_doc)
            
    return True, "تم الإرسال بنجاح عبر API!"

# 2. رفع الملفات
st.markdown('#### 📂 1. رفع البيانات والفواتير')

col_ex, col_archive, col_pdf_direct = st.columns([1.2, 1.2, 1.2])

with col_ex:
    excel_file = st.file_uploader(
        '📊 ملف كشف المبيعات (Excel)', type=['xlsx', 'xls'], key='inv_excel'
    )

with col_archive:
    archive_file = st.file_uploader(
        '📦 أرشيف مضغوط (ZIP / RAR / 7Z / TAR)',
        type=['zip', 'rar', '7z', 'tar', 'gz'],
        key='inv_archive',
    )

with col_pdf_direct:
    direct_pdf_files = st.file_uploader(
        '📄 ملفات PDF مباشرة (دفعة واحدة)',
        type=['pdf'],
        accept_multiple_files=True,
        key='inv_direct_pdfs',
    )

# 3. معالجة وتخزين ملفات الـ PDF
if archive_file is not None:
    file_ext = archive_file.name.split('.')[-1].lower()
    try:
        if file_ext == 'zip':
            with zipfile.ZipFile(archive_file, 'r') as z:
                for file_info in z.infolist():
                    if file_info.filename.lower().endswith('.pdf'):
                        filename = os.path.basename(file_info.filename)
                        raw_name = filename.replace('.pdf', '').replace('.PDF', '').strip()
                        clean_num = ''.join(filter(str.isdigit, raw_name))
                        file_bytes = z.read(file_info.filename)
                        st.session_state.pdf_store[raw_name] = file_bytes
                        if clean_num:
                            st.session_state.pdf_store[clean_num] = file_bytes

    except Exception as e:
        st.error(f'❌ حدث خطأ أثناء قراءة الملف المضغوط: {e}')

if direct_pdf_files:
    for f in direct_pdf_files:
        raw_name = os.path.basename(f.name).replace('.pdf', '').replace('.PDF', '').strip()
        clean_num = ''.join(filter(str.isdigit, raw_name))
        file_bytes = f.getvalue()
        st.session_state.pdf_store[raw_name] = file_bytes
        if clean_num:
            st.session_state.pdf_store[clean_num] = file_bytes

if st.session_state.pdf_store:
    st.success(f'✅ الذاكرة تحتوي حالياً على {len(st.session_state.pdf_store)} فاتورة PDF جاهزة للإرسال!')

if excel_file is not None:
    try:
        df = pd.read_excel(excel_file)

        # التصفية حسب العملة
        if 'curr' in df.columns:
            currencies = ['الكل'] + [str(c) for c in df['curr'].dropna().unique().tolist()]
        else:
            currencies = ['الكل']

        selected_curr = st.selectbox('اختر العملة للتصفية:', currencies, key='curr_select')

        filtered_df = df.copy()
        if selected_curr != 'الكل' and 'curr' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['curr'] == selected_curr]

        if 'doc_ser' in filtered_df.columns:
            filtered_df['doc_ser_str'] = (
                filtered_df['doc_ser']
                .astype(str)
                .str.replace('.0', '', regex=False)
                .str.strip()
            )
        else:
            st.error('❌ لم يتم العثور على عمود (doc_ser) في ملف الإكسل!')
            st.stop()

        processed_set = st.session_state.completed_invoices.union(st.session_state.skipped_invoices)
        pending_df = filtered_df[~filtered_df['doc_ser_str'].isin(processed_set)]

        total_invoices = len(filtered_df)
        completed_count = len(filtered_df[filtered_df['doc_ser_str'].isin(st.session_state.completed_invoices)])
        skipped_count = len(filtered_df[filtered_df['doc_ser_str'].isin(st.session_state.skipped_invoices)])
        remaining_invoices = len(pending_df)

        st.progress((completed_count + skipped_count) / total_invoices if total_invoices > 0 else 0)

        # شريط الإحصائيات
        st.markdown(f"""
        <div style="display: flex; justify-content: space-around; align-items: center; background-color: #f8f9fa; padding: 8px 5px; border-radius: 8px; border: 1px solid #e9ecef; margin: 8px 0; text-align: center;">
            <div style="flex: 1; border-left: 1px solid #dee2e6;">
                <span style="font-size: 11px; color: #6c757d; display: block;">إجمالي الكشف</span>
                <strong style="font-size: 15px; color: #212529;">{total_invoices}</strong>
            </div>
            <div style="flex: 1; border-left: 1px solid #dee2e6;">
                <span style="font-size: 11px; color: #28a745; display: block;">تم الإرسال</span>
                <strong style="font-size: 15px; color: #28a745;">{completed_count}</strong>
            </div>
            <div style="flex: 1; border-left: 1px solid #dee2e6;">
                <span style="font-size: 11px; color: #dc3545; display: block;">ملغاة / كنسل</span>
                <strong style="font-size: 15px; color: #dc3545;">{skipped_count}</strong>
            </div>
            <div style="flex: 1;">
                <span style="font-size: 11px; color: #007bff; display: block;">المتبقي</span>
                <strong style="font-size: 15px; color: #007bff;">{remaining_invoices}</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        if not pending_df.empty:
            search_options = ['🔄 بالتسلسل التلقائي (الفاتورة التالية)'] + [
                f"{row['doc_ser_str']} | {row.get('name', 'بدون اسم')} | {row.get('phone', 'بدون رقم')}"
                for _, row in pending_df.iterrows()
            ]

            selected_search = st.selectbox('🔍 ابحث باسم العميل، رقم الهاتف، أو الرقم التسلسلي:', options=search_options, key='invoice_search_box')

            if selected_search == '🔄 بالتسلسل التلقائي (الفاتورة التالية)':
                current_row = pending_df.iloc[0]
            else:
                selected_doc_ser = selected_search.split(' | ')[0]
                current_row = pending_df[pending_df['doc_ser_str'] == selected_doc_ser].iloc[0]

            doc_ser_val = str(current_row['doc_ser_str'])
            no_doc_val = str(current_row.get('no_doc', '---'))
            customer_name = str(current_row.get('name', 'عميل'))
            phone_val = str(current_row.get('phone', '')).replace('.0', '').strip()
            currency_val = str(current_row.get('curr', ''))
            amount_val = float(current_row.get('amt', 0))
            balance_val = float(current_row.get('total', 0))
            description_val = str(current_row.get('decs', '---')).strip()

            pdf_bytes = st.session_state.pdf_store.get(doc_ser_val) or st.session_state.pdf_store.get(f'DOCSER_{doc_ser_val}')

            message_text = (
                f'البوش للتجارة - المركز الرئيسي جدر\n'
                f'الأخ: {customer_name}\n'
                f'البيان: {description_val}\n'
                f'مبلغ الفاتورة: {amount_val:,.2f} {currency_val}\n'
                f'الرصيد الإجمالي: {balance_val:,.2f} {currency_val}\n'
            )

            st.markdown(
                f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-right: 5px solid #25D366; margin-bottom: 10px;">
                    <h3 style="margin:0; color:#111;">👤 العميل: {customer_name}</h3>
                    <p style="margin:5px 0;"><b>رقم الفاتورة:</b> {no_doc_val} | <b>الرقم التسلسلي:</b> {doc_ser_val}</p>
                    <p style="margin:5px 0;"><b>البيان:</b> {description_val}</p>
                    <p style="margin:5px 0;"><b>مبلغ الفاتورة:</b> <span style="color:#d9534f; font-size:17px; font-weight:bold;">{amount_val:,.2f} {currency_val}</span></p>
                    <p style="margin:5px 0;"><b>الرصيد الإجمالي:</b> <span style="color:#0275d8; font-size:17px; font-weight:bold;">{balance_val:,.2f} {currency_val}</span></p>
                </div>
            """,
                unsafe_allow_html=True,
            )

            st.caption('📝 نص الرسالة المجهز للواتساب:')
            st.code(message_text, language=None)

            st.divider()

            # خيارات الفاتورة المرفقة
            if pdf_bytes:
                st.success(f'✓ تم العثور على الفاتورة الخاصّة بالرقم التسلسلي: ({doc_ser_val})')
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')

                st.download_button(
                    label=f'⬇️ تنزيل ملف الفاتورة مباشرة (PDF)',
                    data=pdf_bytes,
                    file_name=f'DOCSER_{doc_ser_val}.pdf',
                    mime='application/pdf',
                    use_container_width=True,
                    key=f'dl_btn_{doc_ser_val}',
                )

            st.divider()

            # أزرار الإرسال والتحكم المحدثة
            encoded_message = urllib.parse.quote(message_text)
            whatsapp_url = f'https://wa.me/{phone_val}?text={encoded_message}'

            col_api, col_manual, col_skip = st.columns([2.5, 2, 1])

            with col_api:
                # زر الإرسال التلقائي عبر Meta API
                if st.button('🚀 إرسال تلقائي عبر Meta API', type='primary', use_container_width=True, key=f'btn_api_{doc_ser_val}'):
                    with st.spinner("جاري الإرسال عبر API..."):
                        pdf_filename = f'DOCSER_{doc_ser_val}.pdf' if pdf_bytes else None
                        success, resp_msg = send_via_meta_api(phone_val, message_text, pdf_bytes, pdf_filename)
                        
                        if success:
                            st.success("✅ تم الإرسال بنجاح عبر الـ API!")
                            st.session_state.completed_invoices.add(doc_ser_val)
                            st.rerun()
                        else:
                            st.error(f"❌ {resp_msg}")

            with col_manual:
                # زر الفتح اليدوي في تطبيق واتساب
                st.markdown(
                    f"""
                    <a href="{whatsapp_url}" target="_blank" style="text-decoration:none;">
                        <button style="background-color: #25D366; color: white; border: none; padding: 9px; font-size: 14px; font-weight: bold; border-radius: 8px; cursor: pointer; width: 100%;">
                            📲 فتح المحادثة يدوياً
                        </button>
                    </a>
                """,
                    unsafe_allow_html=True,
                )

            with col_skip:
                if st.button('🚫 كنسل', use_container_width=True, key=f'btn_skip_{doc_ser_val}'):
                    st.session_state.skipped_invoices.add(doc_ser_val)
                    st.rerun()

        else:
            st.balloons()
            st.success('🎉 ممتاز! تم مراجعة وإنجاز جميع الفواتير بنجاح.')

    except Exception as e:
        st.error(f'حدث خطأ أثناء معالجة البيانات: {e}')
