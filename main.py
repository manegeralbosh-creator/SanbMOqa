import os
import requests
import webbrowser
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.core.window import Window

# تهيئة حجم الشاشة لتناسب لوحة مفاتيح الجوال
Window.softinput_mode = "below_target"

# الخط العربي المعتمد لحل مشكلة المربعات تماماً
ARABIC_FONT = "arabic_font.ttf"

def download_font_if_missing():
    """ دالة تضمن تحميل الخط العربي لكي تظهر النصوص العربية بشكل صحيح ومقروء """
    if not os.path.exists(ARABIC_FONT):
        url = "https://github.com/google/fonts/raw/main/ofl/cairo/Cairo%5Bwght%5D.ttf"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                with open(ARABIC_FONT, 'wb') as f:
                    f.write(response.content)
        except Exception as e:
            print(f"Font download error: {e}")

download_font_if_missing()

class BocshUiScreen(BoxLayout):
    def __init__(self, **kwargs):
        super(BocshUiScreen, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 15
        self.spacing = 8

        # --- 1. عنوان التطبيق الرئيسي ---
        self.add_widget(Label(
            text="منظومة بوكش (Bocsh) لإدارة الائتمان", 
            font_name=ARABIC_FONT, font_size=22, size_hint_y=None, height=45
        ))

        # --- 2. تحديد نوع الإرسال (فردي أو فئة كاملة) ---
        self.add_widget(Label(text=":نوع الإرسال المطلوب", font_name=ARABIC_FONT, font_size=15, size_hint_y=None, height=20))
        type_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=45, spacing=10)
        
        self.btn_group = ToggleButton(text='إرسال لفئة (أونكس)', group='send_type', state='down', font_name=ARABIC_FONT, font_size=15)
        self.btn_individual = ToggleButton(text='إرسال لعميل فردي', group='send_type', font_name=ARABIC_FONT, font_size=15)
        
        self.btn_group.bind(on_press=self.toggle_fields)
        self.btn_individual.bind(on_press=self.toggle_fields)
        
        type_layout.add_widget(self.btn_group)
        type_layout.add_widget(self.btn_individual)
        self.add_widget(type_layout)

        # --- 3. مربع الفئة (مربط الفرس المرتبط بأونكس) ---
        self.cat_label = Label(text=":فئة العملاء المستهدفة (مربط الفرس)", font_name=ARABIC_FONT, font_size=15, size_hint_y=None, height=20)
        self.add_widget(self.cat_label)
        self.category_spinner = Spinner(
            text='اختر الفئة من أونكس',
            values=('فئة أ (متأخرات عالية)', 'فئة ب (التزام متوسط)', 'فئة ج (عملاء جدد)'),
            font_name=ARABIC_FONT, size_hint_y=None, height=45
        )
        self.add_widget(self.category_spinner)

        # --- 4. حقل اسم العميل (للإرسال الفردي) ---
        self.name_label = Label(text=":اسم العميل", font_name=ARABIC_FONT, font_size=15, size_hint_y=None, height=20, opacity=0.3)
        self.add_widget(self.name_label)
        self.client_name_input = TextInput(hint_text="أدخل اسم العميل هنا...", font_name=ARABIC_FONT, multiline=False, size_hint_y=None, height=45, disabled=True)
        self.add_widget(self.client_name_input)

        # --- 5. حقل رقم العميل (للإرسال الفردي) ---
        self.phone_label = Label(text=":رقم جوال العميل", font_name=ARABIC_FONT, font_size=15, size_hint_y=None, height=20, opacity=0.3)
        self.add_widget(self.phone_label)
        self.client_phone_input = TextInput(hint_text="مثال: 967770000000", font_name=ARABIC_FONT, multiline=False, size_hint_y=None, height=45, disabled=True)
        self.add_widget(self.client_phone_input)

        # --- 6. أيقونة وخيار التوقيت والجدولة الزمنية ---
        self.add_widget(Label(text="🕒 :توقيت وجدولة الإرسال آلياً", font_name=ARABIC_FONT, font_size=15, size_hint_y=None, height=20))
        self.time_spinner = Spinner(
            text='إرسال فوري الآن',
            values=('إرسال فوري الآن', 'جدولة: كل أسبوع تلقائياً', 'جدولة: نهاية كل شهر'),
            font_name=ARABIC_FONT, size_hint_y=None, height=45
        )
        self.add_widget(self.time_spinner)

        # --- 7. مربع نص الرسالة ---
        self.add_widget(Label(text=":محتوى ونص ومطالبة الرسالة", font_name=ARABIC_FONT, font_size=15, size_hint_y=None, height=20))
        self.msg_input = TextInput(hint_text="اكتب نص الرسالة أو المطالبة المالية الآجلة هنا...", font_name=ARABIC_FONT, multiline=True, size_hint_y=None, height=100)
        self.add_widget(self.msg_input)

        # --- 8. زر التشغيل الفوري ---
        self.send_btn = Button(text="حفظ الإعدادات وبدء التشغيل الدوري", font_name=ARABIC_FONT, background_color=(0, 0.5, 0.2, 1), size_hint_y=None, height=55, font_size=18)
        self.send_btn.bind(on_press=self.execute_sending_logic)
        self.add_widget(self.send_btn)

    def toggle_fields(self, instance):
        if self.btn_individual.state == 'down':
            self.client_name_input.disabled = False
            self.client_phone_input.disabled = False
            self.name_label.opacity = 1.0
            self.phone_label.opacity = 1.0
            self.category_spinner.disabled = True
            self.cat_label.opacity = 0.3
        else:
            self.client_name_input.disabled = True
            self.client_phone_input.disabled = True
            self.name_label.opacity = 0.3
            self.phone_label.opacity = 0.3
            self.category_spinner.disabled = False
            self.cat_label.opacity = 1.0

    def execute_sending_logic(self, instance):
        message = self.msg_input.text
        if not message:
            return

        if self.btn_individual.state == 'down':
            phone = self.client_phone_input.text
            if phone:
                self.open_whatsapp(phone, message)
        else:
            selected_category = self.category_spinner.text
            mock_onyx_data = [
                {"name": "عميل تجريبي 1", "phone": "967770000001", "category": "فئة أ (متأخرات عالية)"},
                {"name": "عميل تجريبي 2", "phone": "967770000002", "category": "فئة أ (متأخرات عالية)"}
            ]
            target_clients = [c for c in mock_onyx_data if c["category"] == selected_category]
            for client in target_clients:
                self.open_whatsapp(client['phone'], message)

    def open_whatsapp(self, phone, message):
        clean_phone = "".join(filter(str.isdigit, phone))
        whatsapp_url = f"https://wa.me/{clean_phone}?text={requests.utils.quote(message)}"
        webbrowser.open(whatsapp_url)

class BocshApp(App):
    def build(self):
        return BocshUiScreen()

if __name__ == '__main__':
    BocshApp().run()
