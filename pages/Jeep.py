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


# --- 2. دالة الفصل الذكي للرسائل النصية ---
def split_bulk_messages(text):
  pattern = (
      r'(?=(?:أضيف|اضيف|استلمت|لقد\s*استلمت|تم|إيداع|ايداع|تحويل)\s*[\d\.,]+)'
  )
  parts = re.split(pattern, text)
  messages = [p.strip() for p in parts if p.strip()]
  return messages if messages else [text.strip()]


# --- 3. دالة تحليل رسائل جيب وجوالي بالتنسيق الجديد ---
def parse_jeep_jawali_message(raw_text):
  # 1. استخراج ما بعد كلمة "من" (المصدر: رقم نقطة / رقم جوال / اسم شخص)
  from_match = re.search(r'من\s*([^:\n\r]+)', raw_text)
  if from_match:
    from_source = from_match.group(1).strip()
    # تنظيف ما بعد المصدر في حال وجود كلمات ثانوية مثل "رصيد" أو "مرجع"
    from_source = re.sub(
        r'\s*(رصيد|رص:|رصيدك|م:|مرجع).*$', '', from_source, flags=re.IGNORECASE
    ).strip()
    # إزالة كلمة "بمرجع..." إذا جاءت ملاصقة
    from_source = re.sub(r'^بمرجع\s*\d+\s*', '', from_source).strip()
  else:
    from_source = "محفظة جيب/جوالي"

  # رقم المرجع ينزل برقم النقطة أو الجوال أو الاسم القادم بعد كلمة "من"
  reference_no = from_source

  # 2. استخراج المبلغ والعملة
  # البحث عن أنماط العملات (ر.ي / YER / ريال يمني / ر.س / SAR / ريال سعودي)
  amount_match = re.search(
      r'([\d\.,]+)\s*(ر\.ي|YER|ريال\s*يمني|ر\.س|SAR|ريال\s*سعودي)',
      raw_text,
      re.IGNORECASE,
  )

  if not amount_match:
    # محاولة استخراج الرقم المباشر بعد مفاتيح الإيداع
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
      return None
  else:
    amount_val = float(amount_match.group(1).replace(',', ''))
    curr_text = amount_match.group(2).replace(' ', '')
    is_saudi = 'سعودي' in curr_text or 'س' in curr_text or 'SAR' in curr_text
    currency_code = '2' if is_saudi else '1'

  # 3. صياغة البيان بأسلوب: أضيف مبلغ من [ما جاء بعد كلمة من]
  description = f'أضيف مبلغ من {from_source}'

  return {
      'رقم الحساب': JEEP_ACCOUNT,
      'الحساب التحليلي': JEEP_ANALYTICAL,
      'البيان': description,
      'المبلغ': amount_val,
      'العملة': currency_code,
      'رقم المرجع': reference_no,
  }


# --- 4. واجهة إدخال الرسائل ---
st.subheader('📥 إدخال رسائل جيب / جوالي')

bulk_msg = st.text_area(
    'انسخ والصق نص الرسالة أو مجموعة الرسائل هنا:',
    height=180,
    placeholder=(
        'أمثلة:\n1/ أضيف 30000ر.ي مشتريات رص:220611.7ر.ي من 9895218'
        ' م:17891983578541\n2/ استلمت مبلغ 1500 YER من 773954922 رصيدك هو'
        ' 258113.19\n3/ لقد استلمت 36000 YER كقيمة مشتريات من بمرجع 335950184210'
        ' من فاروق علي مطهر الحميدي'
    ),
)

if 'jeep_parsed_rows' not in st.session_state:
  st.session_state.jeep_parsed_rows = []

col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
  if st.button('⚡ تحليل ومعالجة القيود', type='primary'):
    if bulk_msg.strip():
      messages = split_bulk_messages(bulk_msg)
      parsed_list = []
      for m in messages:
        res = parse_jeep_jawali_message(m)
        if res:
          parsed_list.append(res)
      st.session_state.jeep_parsed_rows = parsed_list
      st.success(f'تم تحليل {len(parsed_list)} حركات بنجاح!')
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

  st.write('### 1️⃣ صفوف الحساب المدين (صندوق جيب - 1211013):')
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
        'البيان': 'إجمالي المقبولات محفظة جيب/جوالي (ريال يمني)',
        'المبلغ': total_yer,
        'العملة': '1 (ريال يمني)',
        'النوع': 'دائن',
    })
  if total_sar > 0:
    summary_credits.append({
        'رقم الحساب': CASH_SALES_ACCOUNT,
        'الحساب التحليلي': CASH_SALES_ANALYTICAL,
        'البيان': 'إجمالي المقبولات محفظة جيب/جوالي (ريال سعودي)',
        'المبلغ': total_sar,
        'العملة': '2 (ريال سعودي)',
        'النوع': 'دائن',
    })

  st.dataframe(pd.DataFrame(summary_credits), use_container_width=True)

  # --- بناء هيكلية جدول أونكس برو المطابقة للاستيراد المباشر ---
  onyx_final_rows = []

  # أ) إضافة كافة الصفوف المدينة (صندوق جيب 1211013 / تحليلي 701)
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

  # ب) إضافة القيد الدائن المقابل لليمني (صندوق المبيعات 1211003 / تحليلي 3)
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

  # ج) إضافة القيد الدائن المقابل للسعودي (صندوق المبيعات 1211003 / تحليلي 3)
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
