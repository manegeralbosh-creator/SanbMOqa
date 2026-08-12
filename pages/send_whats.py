import base64
import io
import os
import re
import urllib.parse
import zipfile
import pandas as pd
import pdfplumber
import streamlit as st

st.subheader('📲 نظام مراجعة وإرسال الفواتير عبر الواتساب')

# 1. تهيئة متغيرات الجلسة للبيانات والملفات (لضمان عدم ضياعها أثناء التنقل)
if 'completed_invoices' not in st.session_state:
    st.session_state.completed_invoices = set()

if 'skipped_invoices' not in st.session_state:
    st.session_state.skipped_invoices = set()

if 'pdf_store' not in st.session_state:
    st.session_state.pdf_store = {}

# 2. رفع الملفات (ملف الإكسل + خيارين لرفع الفواتير)
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

# 3. معالجة وتخزين ملفات الـ PDF في session_state لمنع فقدانها
# أ) معالجة الأرشيف المضغوط
if archive_file is not None:
    file_ext = archive_file.name.split('.')[-1].lower()
    try:
        if file_ext == 'zip':
            with zipfile.ZipFile(archive_file, 'r') as z:
                for file_info in z.infolist():
                    if file_info.filename.lower().endswith('.pdf'):
                        filename = os.path.basename(file_info.filename)
                        raw_name = (
                            filename.replace('.pdf', '').replace('.PDF', '').strip()
                        )
                        clean_num = ''.join(filter(str.isdigit, raw_name))
                        file_bytes = z.read(file_info.filename)
                        st.session_state.pdf_store[raw_name] = file_bytes
                        if clean_num:
                            st.session_state.pdf_store[clean_num] = file_bytes

        elif file_ext == 'rar':
            if 'HAS_RAR' in globals() and HAS_RAR:
                with rarfile.RarFile(archive_file) as r:
                    for file_info in r.infolist():
                        if file_info.filename.lower().endswith('.pdf'):
                            filename = os.path.basename(file_info.filename)
                            raw_name = (
                                filename.replace('.pdf', '').replace('.PDF', '').strip()
                            )
                            clean_num = ''.join(filter(str.isdigit, raw_name))
                            file_bytes = r.read(file_info.filename)
                            st.session_state.pdf_store[raw_name] = file_bytes
                            if clean_num:
                                st.session_state.pdf_store[clean_num] = file_bytes
            else:
                st.warning('⚠️ لقراءة ملفات RAR يرجى تثبيت مكتبة rarfile.')

        elif file_ext == '7z':
            if 'HAS_7Z' in globals() and HAS_7Z:
                with py7zr.SevenZipFile(archive_file, mode='r') as z:
                    all_files = z.readall()
                    for name, bio in all_files.items():
                        if name.lower().endswith('.pdf'):
                            filename = os.path.basename(name)
                            raw_name = (
                                filename.replace('.pdf', '').replace('.PDF', '').strip()
                            )
                            clean_num = ''.join(filter(str.isdigit, raw_name))
                            file_bytes = bio.read()
                            st.session_state.pdf_store[raw_name] = file_bytes
                            if clean_num:
                                st.session_state.pdf_store[clean_num] = file_bytes
            else:
                st.warning('⚠️ لقراءة ملفات 7Z يرجى تثبيت مكتبة py7zr.')

        elif file_ext in ['tar', 'gz']:
            if 'HAS_TAR' in globals() and HAS_TAR:
                with tarfile.open(fileobj=archive_file) as t:
                    for member in t.getmembers():
                        if member.isfile() and member.name.lower().endswith('.pdf'):
                            filename = os.path.basename(member.name)
                            raw_name = (
                                filename.replace('.pdf', '').replace('.PDF', '').strip()
                            )
                            clean_num = ''.join(filter(str.isdigit, raw_name))
                            f = t.extractfile(member)
                            if f:
                                file_bytes = f.read()
                                st.session_state.pdf_store[raw_name] = file_bytes
                                if clean_num:
                                    st.session_state.pdf_store[clean_num] = file_bytes

    except Exception as e:
        st.error(f'❌ حدث خطأ أثناء قراءة الملف المضغوط: {e}')

# ب) معالجة ملفات PDF المرفوعة مباشرة
if direct_pdf_files:
    for f in direct_pdf_files:
        raw_name = (
            os.path.basename(f.name).replace('.pdf', '').replace('.PDF', '').strip()
        )
        clean_num = ''.join(filter(str.isdigit, raw_name))
        file_bytes = f.getvalue()
        st.session_state.pdf_store[raw_name] = file_bytes
        if clean_num:
            st.session_state.pdf_store[clean_num] = file_bytes

# إشعار بوجود ملفات جارية بالذاكرة
if st.session_state.pdf_store:
    st.success(f'✅ الذاكرة تحتوي حالياً على {len(st.session_state.pdf_store)} فاتورة PDF جاهزة للإرسال!')

if excel_file is not None:
    try:
        df = pd.read_excel(excel_file)

        # التصفية حسب العملة
        if 'curr' in df.columns:
            currencies = ['الكل'] + [
                str(c) for c in df['curr'].dropna().unique().tolist()
            ]
        else:
            currencies = ['الكل']

        selected_curr = st.selectbox(
            'اختر العملة للتصفية:', currencies, key='curr_select'
        )

        filtered_df = df.copy()
        if selected_curr != 'الكل' and 'curr' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['curr'] == selected_curr]

        # التأكد من وجود عمود الرقم التسلسلي
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

        # استبعاد الفواتير المعالجة سابقاً
        processed_set = st.session_state.completed_invoices.union(
            st.session_state.skipped_invoices
        )
        pending_df = filtered_df[
            ~filtered_df['doc_ser_str'].isin(processed_set)
        ]

        # الإحصائيات والشريط المتقدم
        total_invoices = len(filtered_df)
        completed_count = len(
            filtered_df[
                filtered_df['doc_ser_str'].isin(
                    st.session_state.completed_invoices
                )
            ]
        )
        skipped_count = len(
            filtered_df[
                filtered_df['doc_ser_str'].isin(st.session_state.skipped_invoices)
            ]
        )
        remaining_invoices = len(pending_df)

        st.progress(
            (completed_count + skipped_count) / total_invoices
            if total_invoices > 0
            else 0
        )

        # 📊 شريط الإحصائيات المصغر والأنيق أفقياً
        st.markdown(f"""
        <div style="
            display: flex; 
            justify-content: space-around; 
            align-items: center; 
            background-color: #f8f9fa; 
            padding: 8px 5px; 
            border-radius: 8px; 
            border: 1px solid #e9ecef;
            margin: 8px 0;
            text-align: center;
        ">
            <div style="flex: 1; border-left: 1px solid #dee2e6;">
                <span style="font-size: 11px; color: #6c757d; display: block; margin-bottom: -2px;">إجمالي الكشف</span>
                <strong style="font-size: 15px; color: #212529;">{total_invoices}</strong>
            </div>
            <div style="flex: 1; border-left: 1px solid #dee2e6;">
                <span style="font-size: 11px; color: #28a745; display: block; margin-bottom: -2px;">تم الإرسال</span>
                <strong style="font-size: 15px; color: #28a745;">{completed_count}</strong>
            </div>
            <div style="flex: 1; border-left: 1px solid #dee2e6;">
                <span style="font-size: 11px; color: #dc3545; display: block; margin-bottom: -2px;">ملغاة / كنسل</span>
                <strong style="font-size: 15px; color: #dc3545;">{skipped_count}</strong>
            </div>
            <div style="flex: 1;">
                <span style="font-size: 11px; color: #007bff; display: block; margin-bottom: -2px;">المتبقي</span>
                <strong style="font-size: 15px; color: #007bff;">{remaining_invoices}</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 📊 زر تنزيل التقرير
        if 'generate_excel_report' in globals():
            excel_data = generate_excel_report(
                filtered_df,
                st.session_state.completed_invoices,
                st.session_state.skipped_invoices,
            )
            st.download_button(
                label='📊 تنزيل تقرير حالة الفواتير الحالي (Excel)',
                data=excel_data,
                file_name='تقرير_حالة_الفواتير.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                use_container_width=True,
                key='download_report_btn',
            )

        st.divider()

        if not pending_df.empty:
            # 🔎 4. شريط البحث والتنقل السريع
            search_options = ['🔄 بالتسلسل التلقائي (الفاتورة التالية)'] + [
                f"{row['doc_ser_str']} | {row.get('name', 'بدون اسم')} | {row.get('phone', 'بدون رقم')}"
                for _, row in pending_df.iterrows()
            ]

            selected_search = st.selectbox(
                '🔍 ابحث باسم العميل، رقم الهاتف، أو الرقم التسلسلي:',
                options=search_options,
                key='invoice_search_box',
            )

            if selected_search == '🔄 بالتسلسل التلقائي (الفاتورة التالية)':
                current_row = pending_df.iloc[0]
            else:
                selected_doc_ser = selected_search.split(' | ')[0]
                current_row = pending_df[
                    pending_df['doc_ser_str'] == selected_doc_ser
                ].iloc[0]

            # استخراج بيانات الفاتورة المحددة
            doc_ser_val = str(current_row['doc_ser_str'])
            no_doc_val = str(current_row.get('no_doc', '---'))
            customer_name = str(current_row.get('name', 'عميل'))
            phone_val = str(current_row.get('phone', '')).replace('.0', '').strip()
            currency_val = str(current_row.get('curr', ''))
            amount_val = float(current_row.get('amt', 0))
            balance_val = float(current_row.get('total', 0))

            # البحث عن ملف الـ PDF المطابق للعميل من session_state
            pdf_bytes = st.session_state.pdf_store.get(doc_ser_val) or st.session_state.pdf_store.get(
                f'DOCSER_{doc_ser_val}'
            )

            # نص الرسالة للواتساب
            message_text = (
                f'البوش للتجارة - المركز الرئيسي جدر\n'
                f'الأخ: {customer_name}\n'
                f'مبلغ الفاتورة: {amount_val:,.2f} {currency_val}\n'
                f'الرصيد الإجمالي: {balance_val:,.2f} {currency_val}\n'
            )

            # بطاقة بيانات العميل
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

            st.caption('📝 نص الرسالة المجهز للواتساب:')
            st.code(message_text, language=None)

            st.divider()

            # 5. خيارات الفاتورة المرفقة
            st.markdown('### 📄 خيارات الفاتورة المرفقة:')
            if pdf_bytes:
                st.success(
                    f'✓ تم العثور على الفاتورة الخاصّة بالرقم التسلسلي:'
                    f' ({doc_ser_val})'
                )

                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')

                # زر "مشاركة الفاتورة" لنظام الأندرويد
                share_html = f"""
                <script>
                async function sharePDF_{doc_ser_val}() {{
                    const base64Data = '{base64_pdf}';
                    const fileName = 'DOCSER_{doc_ser_val}.pdf';
                    
                    const res = await fetch(`data:application/pdf;base64,${{base64Data}}`);
                    const blob = await res.blob();
                    const file = new File([blob], fileName, {{ type: 'application/pdf' }});
                    
                    if (navigator.canShare && navigator.canShare({{ files: [file] }})) {{
                        try {{
                            await navigator.share({{
                                files: [file],
                                title: 'فاتورة {customer_name}',
                                text: 'مرفق فاتورة العميل: {customer_name}'
                            }});
                        }} catch (err) {{
                            console.log('تم إلغاء المشاركة أو حدث خطأ:', err);
                        }}
                    }} else {{
                        alert('خاصية المشاركة المباشرة غير مدعومة في هذا المتصفح. يمكنك استخدام زر التنزيل أدناه لمشاركة الفاتورة.');
                    }}
                }}
                </script>

                <button onclick="sharePDF_{doc_ser_val}()" style="
                    background-color: #0275d8;
                    color: white;
                    border: none;
                    padding: 12px;
                    font-size: 15px;
                    font-weight: bold;
                    border-radius: 8px;
                    cursor: pointer;
                    width: 100%;
                    margin-bottom: 8px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 8px;">
                    📲 مشاركة الفاتورة عبر الأندرويد (WhatsApp / Telegram / Apps)
                </button>
                """
                st.components.v1.html(share_html, height=65)

                # زر تنزيل الفاتورة
                st.download_button(
                    label=f'⬇️ تنزيل ملف الفاتورة مباشرة (PDF)',
                    data=pdf_bytes,
                    file_name=f'DOCSER_{doc_ser_val}.pdf',
                    mime='application/pdf',
                    use_container_width=True,
                    key=f'dl_btn_{doc_ser_val}',
                )
            else:
                st.warning(
                    f'⚠️ لم يتم العثور على ملف PDF مطبق للرقم التسلسلي: (DOCSER_{doc_ser_val}.pdf).'
                )

            st.divider()

            # أزرار الإرسال والتحكم
            encoded_message = urllib.parse.quote(message_text)
            whatsapp_url = f'https://wa.me/{phone_val}?text={encoded_message}'

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
                    '✅ 2. تم الإرسال',
                    type='primary',
                    use_container_width=True,
                    key=f'btn_send_{doc_ser_val}',
                ):
                    st.session_state.completed_invoices.add(doc_ser_val)
                    st.rerun()

            with c3:
                if st.button(
                    '🚫 كنسل',
                    use_container_width=True,
                    key=f'btn_skip_{doc_ser_val}',
                ):
                    st.session_state.skipped_invoices.add(doc_ser_val)
                    st.rerun()

        else:
            st.balloons()
            st.success('🎉 ممتاز! تم مراجعة وإنجاز جميع الفواتير بنجاح.')

    except Exception as e:
        st.error(f'حدث خطأ أثناء معالجة البيانات: {e}')
