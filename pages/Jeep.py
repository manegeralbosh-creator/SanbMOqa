import io
import re
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="نظام قيود محافظ جيب وجوالي - أونكس برو", layout="wide"
)
st.title("📱 نظام استخراج قيود محافظ (جيب / جوالي) - أونكس برو")

# --- 1. إعداد الثوابت للحسابات ---
JEEP_ACCOUNT = "1211013"
JEEP_ANALYTICAL = "701"

CASH_SALES_ACCOUNT = "1211003"
CASH_SALES_ANALYTICAL = "3"

st.sidebar.header("⚙️ إعدادات الحسابات المعتمدة")
st.sidebar.info(f"""
**الحساب المدين (صندوق جيب):**
- رقم الحساب: {JEEP_ACCOUNT}
- الحساب التحليلي: {JEEP_ANALYTICAL}

---
**الحساب الدائن المقابل (صندوق المبيعات):**
- رقم الحساب: {CASH_SALES_ACCOUNT}
- الحساب التحليلي: {CASH_SALES_ANALYTICAL}
""")


# --- 2. دالة الفصل الفائقة الدقة للرسائل المجمعة (30+ رسالة) ---
def split_bulk_messages_strict(text):
  # أولاً: المحاولة بالتفكيك حسب الأسطر (وهي الطريقة الأكثر دقة عند النسخ واللصق)
  lines = [line.strip() for line in text.splitlines() if line.strip()]

  all_messages = []
  for line in lines:
    # إزالة الأرقام الترتيبية من بداية السطر إن وجدت مثل "1/" أو "1-"
    clean_line = re.sub(r'^\d+[\/\.-]\s*', '', line).strip()
    if clean_line:
      all_messages.append(clean_line)

  # ثانياً: إذا كان النص كاملاً ملتصقاً بدون أسطر جديدة، يتم الفصل بواسطة التعبير النمطي
  if len(all_messages) <= 1 and len(text) > 100:
    pattern = r'(?=(?:أضيف|اضيف|استلمت|لقد\s*استلمت|تم|إيداع|ايداع|تحويل)\s*[\d\.,]+)'
    parts = re.split(pattern, text)
    all_messages = [p.strip() for p in parts if p.strip()]

  return all_messages


# --- 3. دالة تحليل الرسالة واستخراج التفاصيل ---
def parse_jeep_jawali_message(raw_text):
  # 1. استخراج المبلغ والعملة أولاً للتحقق من أن السطر يحتوي على حركة مالية
  amount_match = re.search(
      r'([\d\.,]+)\s*(ر\.ي|YER|ريال\s*يمني|ر\.س|SAR|ريال\s*سعودي)',
      raw_text,
      re.IGNORECASE,
  )

  if not amount_match:
    amount_match_alt = re.search(
        r'(?:أضيف|اضيف|استلمت|لقد\s*استلمت|مبلغ)\s*([\d\.,]+)', raw_text
    )
    if amount_match_alt:
      amount_val = float(amount_match_alt.group(1).replace(',', ''))
      is_saudi = (
          'سعودي' in raw_text or 'SAR' in raw_text or 'ر.س' in raw_text
      )
      currency_code = '2' if is_saudi else '1'
    else:
      return None  # تجنب السطور التعريفية أو الخالية من المبالغ
  else:
    amount_val = float(amount_match.group(1).replace(',', ''))
    curr_text = amount_match.group(2).replace(' ', '')
    is_saudi = 'سعودي' in curr_text or 'س' in curr_text or 'SAR' in curr_text
    currency_code = '2' if is_saudi else '1'

  # 2. استخراج ما بعد كلمة "من" (المصدر: رقم نقطة / رقم جوال / اسم شخص)
  from_match = re.search(r'من\s*([^:\n\r]+)', raw_text)
  if from_match:
    from_source = from_match.group(1).strip()
    # تنظيف العبارات الزائدة المحيطة بالمصدر
    from_source = re.sub(
        r'\s*(رصيد|رص:|رصيدك|م:|مرجع).*$', '', from_source, flags=re.IGNORECASE
    ).strip()
    from_source = re.sub(r'^بمرجع\s*\d+\s*', '', from_source).strip()
  else:
    from_source = 'محفظة جيب/جوالي'

  reference_no = from_source
  description = f'أضيف مبلغ من {from_source}'

  return {
      'رقم الحساب': JEEP_ACCOUNT,
      'الحساب التحليلي': JEEP_ANALYTICAL,
      'البيان': description,
      'المبلغ': amount_val,
      'العملة': currency_code,
      'رقم المرجع': reference_no,
      'النص الأصلي': raw_text,
  }


# --- 4. واجهة إدخال الرسائل (مخصصة للأعداد الكبيرة) ---
st.subheader('📥 إدخال رسائل جيب / جوالي (يستوعب 30+ رسالة)')

bulk_msg = st.text_area(
    'انسخ والصق كافة الرسائل هنا (كل رسالة في سطر جديد):',
    height=320,  # مساحة واسعة لاستيعاب قائمة كبيرة من الرسائل
    placeholder=(
        'أمثلة:\nأضيف 30000ر.ي مشتريات رص:220611.7ر.ي من 9895218'
        ' م:17891983578541\nاستلمت مبلغ 1500 YER من 773954922 رصيدك هو'
        ' 258113.19\nلقد استلمت 36000 YER كقيمة مشتريات من بمرجع 335950184210'
        ' من فاروق علي مطهر الحميدي'
    ),
)

if 'jeep_parsed_rows' not in st.session_state:
  st.session_state.jeep_parsed_rows = []

col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
  if st.button('⚡ تحليل ومعالجة كافة الرسائل', type='primary'):
    if bulk_msg.strip():
      messages = split_bulk_messages_strict(bulk_msg)
      parsed_list = []
      failed_count = 0

      for m in messages:
        res = parse_jeep_jawali_message(m)
        if res:
          parsed_list.append(res)
        else:
          failed_count += 1

      st.session_state.jeep_parsed_rows = parsed_list
      st.success(
          f'✅ تم استخراج ومطابقة {len(parsed_list)} رسالة/حركة بنجاح من إجمالي'
          f' {len(messages)} سطر!'
      )
      if failed_count > 0:
        st.info(
            f'ℹ️ تم استبعاد {failed_count} سطر (سطور فارغة أو لا تحتوي على'
            ' مبالغ مالية).'
        )
    else:
      st.warning('يرجى لصق نص الرسائل أولاً.')

with col_btn2:
  if st.button('🗑️ مسح القائمة'):
    st.session_state.jeep_parsed_rows = []
    st.rerun()

# --- 5. بناء وتصدير قيد اليومية المركب لأونكس برو ---
if st.session_state.jeep_parsed_rows:
  st.markdown('---')
  st.subheader('📊 القيود الناتجة والمجمعة')

  df_debits = pd.DataFrame(st.session_state.jeep_parsed_rows)

  st.write(
      f'### 1️⃣ صفوف الحساب المدين - صندوق جيب ({len(df_debits)} حركة مدخلة):'
  )
  st.dataframe(
      df_debits[[
          'رقم الحساب',
          'الحساب التحليلي',
          'البيان',
          'المبلغ',
          'العملة',
          'رقم المرجع',
      ]],
      use_container_width=True,
  )

  # حساب إجمالي المبالغ لكل عملة
  total_yer = df_debits[df_debits['العملة'] == '1']['المبلغ'].sum()
  total_sar = df_debits[df_debits['العملة'] == '2']['المبلغ'].sum()

  st.write('### 2️⃣ صفوف الحساب الدائن المجمعة (صندوق المبيعات - 1211003):')
  summary_credits = []
  if total_yer > 0:
    summary_credits.append({
        'رقم الحساب': CASH_SALES_ACCOUNT,
        'الحساب التحليلي': CASH_SALES_ANALYTICAL,
        'البيان': 'إجمالي مقبولات محفظة جيب/جوالي (ريال يمني)',
        'المبلغ': total_yer,
        'العملة': '1 (ريال يمني)',
        'النوع': 'دائن',
    })
  if total_sar > 0:
    summary_credits.append({
        'رقم الحساب': CASH_SALES_ACCOUNT,
        'الحساب التحليلي': CASH_SALES_ANALYTICAL,
        'البيان': 'إجمالي مقبولات محفظة جيب/جوالي (ريال سعودي)',
        'المبلغ': total_sar,
        'العملة': '2 (ريال سعودي)',
        'النوع': 'دائن',
    })

  st.dataframe(pd.DataFrame(summary_credits), use_container_width=True)

  # --- بناء هيكلية أونكس برو للتحميل المباشر ---
  onyx_final_rows = []

  # أ) إضافة كافة الصفوف المدينة
  for idx, row in df_debits.iterrows():
    is_foreign = str(row['العملة']) == '2'
    onyx_final_rows.append({
        'رقم الحساب': row['رقم الحساب'],
        'الحساب التحليلي': row['الحساب التحليلي'],
        'البيان': row['البيان'],
        'مدين محلي': 0.0 if is_foreign else row['المبلغ'],
        'مدين أجنبي': row['المبلغ'] if is_foreign else 0.0,
        'دائن محلي': 0.0,
        'دائن أجنبي': 0.0,
        'العملة': row['العملة'],
        'مركز التكلفة': '',
        'المشروع': '',
        'النشاط': '',
    })

  # ب) إضافة القيد الدائن المقابل لليمني
  if total_yer > 0:
    onyx_final_rows.append({
        'رقم الحساب': CASH_SALES_ACCOUNT,
        'الحساب التحليلي': CASH_SALES_ANALYTICAL,
        'البيان': 'إجمالي مقبولات محفظة جيب/جوالي (ريال يمني)',
        'مدين محلي': 0.0,
        'مدين أجنبي': 0.0,
        'دائن محلي': total_yer,
        'دائن أجنبي': 0.0,
        'العملة': '1',
        'مركز التكلفة': '',
        'المشروع': '',
        'النشاط': '',
    })

  # ج) إضافة القيد الدائن المقابل للسعودي
  if total_sar > 0:
    onyx_final_rows.append({
        'رقم الحساب': CASH_SALES_ACCOUNT,
        'الحساب التحليلي': CASH_SALES_ANALYTICAL,
        'البيان': 'إجمالي مقبولات محفظة جيب/جوالي (ريال سعودي)',
        'مدين محلي': 0.0,
        'مدين أجنبي': 0.0,
        'دائن محلي': 0.0,
        'دائن أجنبي': total_sar,
        'العملة': '2',
        'مركز التكلفة': '',
        'المشروع': '',
        'النشاط': '',
    })

  df_onyx_export = pd.DataFrame(onyx_final_rows)

  excel_buffer = io.BytesIO()
  with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
    df_onyx_export.to_excel(writer, index=False, sheet_name='Onyx_Import')
  excel_buffer.seek(0)

  st.markdown('---')
  st.download_button(
      label=(
          '📥 تنزيل ملف الإكسل المباشر لشاشة قيود اليومية (أونكس برو - جيب/جوالي)'
      ),
      data=excel_buffer,
      file_name=(
          'Onyx_Jeep_Jawali_Journal_'
          f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx"
      ),
      mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      type='primary',
  )
