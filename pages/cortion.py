import re
import tkinter as tk
from tkinter import ttk


def extract_numbers(text):
    # استخراج كافة الأرقام المقبولة كأرقام حوالات (أرقام بطول 3 خانات أو أكثر)
    return set(re.findall(r"\b\d{3,}\b", text))


def process_reconciliation():
    # الحصول على النصوص من المربعين
    acc_text = text_accountant.get("1.0", tk.END)
    alalamiya_text = text_alalamiya.get("1.0", tk.END)

    # استخراج أرقام الحوالات
    acc_ids = extract_numbers(acc_text)
    alalamiya_ids = extract_numbers(alalamiya_text)

    # الحوالات المطابقة (الموجودة في الطرفين)
    matched = acc_ids.intersection(alalamiya_ids)

    # غير المطابقة (الموجودة في أحد الطرفين فقط)
    unmatched_acc = acc_ids - matched
    unmatched_alalamiya = alalamiya_ids - matched

    # مسح النتائج السابقة
    text_result_acc.delete("1.0", tk.END)
    text_result_alalamiya.delete("1.0", tk.END)

    # عرض الحوالات غير المطابقة
    text_result_acc.insert(
        tk.END,
        "\n".join(sorted(unmatched_acc)) if unmatched_acc else "لا يوجد",
    )
    text_result_alalamiya.insert(
        tk.END,
        "\n".join(sorted(unmatched_alalamiya))
        if unmatched_alalamiya
        else "لا يوجد",
    )

    lbl_status.config(
        text=f"تمت المطابقة! عدد الحوالات المتطابقة المخفية: {len(matched)}"
    )


# إنشاء النافذة الرئيسية
root = tk.Tk()
root.title("نظام مطابقة الحوالات")
root.geometry("800x600")

# العنوان الرئيسي
ttk.Label(
    root, text="برنامج مطابقة الحوالات المالية", font=("Arial", 16, "bold")
).pack(pady=10)

# الإدخال (المحاسب والعالمية)
frame_inputs = ttk.Frame(root)
frame_inputs.pack(fill="both", expand=True, padx=10, pady=5)

# نافذة المحاسب
frame_acc = ttk.LabelFrame(frame_inputs, text=" نافذة المحاسب ")
frame_acc.pack(side="left", fill="both", expand=True, padx=5)
text_accountant = tk.Text(frame_acc, width=30, height=12)
text_accountant.pack(fill="both", expand=True, padx=5, pady=5)

# نافذة العالمية
frame_alalamiya = ttk.LabelFrame(frame_inputs, text=" نافذة العالمية ")
frame_alalamiya.pack(side="right", fill="both", expand=True, padx=5)
text_alalamiya = tk.Text(frame_alalamiya, width=30, height=12)
text_alalamiya.pack(fill="both", expand=True, padx=5, pady=5)

# زر المطابقة
btn_match = ttk.Button(
    root, text="إجراء المطابقة", command=process_reconciliation
)
btn_match.pack(pady=10)

lbl_status = ttk.Label(
    root,
    text="ضع أرقام الحوالات واضغط على إجراء المطابقة",
    font=("Arial", 10, "italic"),
)
lbl_status.pack()

# عرض النتائج
frame_results = ttk.LabelFrame(
    root, text=" الحوالات غير المطابقة (الفرق بين النافذتين) "
)
frame_results.pack(fill="both", expand=True, padx=10, pady=10)

# نتائج المحاسب
frame_res_acc = ttk.LabelFrame(frame_results, text=" متبقي المحاسب ")
frame_res_acc.pack(side="left", fill="both", expand=True, padx=5)
text_result_acc = tk.Text(frame_res_acc, width=30, height=8, fg="red")
text_result_acc.pack(fill="both", expand=True, padx=5, pady=5)

# نتائج العالمية
frame_res_alalamiya = ttk.LabelFrame(frame_results, text=" متبقي العالمية ")
frame_res_alalamiya.pack(side="right", fill="both", expand=True, padx=5)
text_result_alalamiya = tk.Text(
    frame_res_alalamiya, width=30, height=8, fg="red"
)
text_result_alalamiya.pack(fill="both", expand=True, padx=5, pady=5)

root.mainloop()
