import os
os.environ['TK_SILENCE_DEPRECATION'] = '1'

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import sys

class CaptchaLabeler:
    def __init__(self, root):
        self.root = root
        self.root.title("Công cụ gán nhãn Captcha")

        # Cấu hình cửa sổ
        self.root.geometry("500x400")
        self.root.configure(bg='white')  # Đặt màu nền

        print(f"Đường dẫn hiện tại: {os.getcwd()}")

        self.captcha_dir = "training_captchas"

        if os.path.exists(self.captcha_dir):
            print(f"Tìm thấy thư mục: {self.captcha_dir}")
            self.images = [f for f in os.listdir(self.captcha_dir) if f.endswith('.png')]
            print(f"Số lượng ảnh PNG: {len(self.images)}")
            if self.images:
                print(f"Ảnh đầu tiên: {self.images[0]}")
        else:
            print(f"Không tìm thấy thư mục: {self.captcha_dir}")
            messagebox.showerror("Lỗi", f"Không tìm thấy thư mục {self.captcha_dir}")
            return

        self.current_index = 0
        self.create_widgets()
        self.load_first_image()

    def create_widgets(self):
        # Frame chính
        main_frame = ttk.Frame(self.root)
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)

        # Label hiển thị tiến độ
        self.progress_label = ttk.Label(main_frame,
            text=f"Ảnh {self.current_index + 1}/{len(self.images)}")
        self.progress_label.pack(pady=5)

        # Frame cho ảnh
        self.image_frame = ttk.Frame(main_frame, borderwidth=2, relief='solid')
        self.image_frame.pack(pady=10)

        # Label hiển thị ảnh
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(padx=10, pady=10)

        # Frame cho input
        input_frame = ttk.LabelFrame(main_frame, text="Nhập text trong ảnh")
        input_frame.pack(fill='x', pady=10)

        # Entry để nhập text
        self.text_var = tk.StringVar()
        self.entry = ttk.Entry(input_frame, textvariable=self.text_var, width=40)
        self.entry.pack(padx=10, pady=5)

        # Frame cho buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        # Buttons
        self.submit_btn = ttk.Button(button_frame, text="Lưu (Enter)",
                                   command=self.save_label)
        self.submit_btn.pack(side='left', padx=5)

        self.skip_btn = ttk.Button(button_frame, text="Bỏ qua",
                                 command=self.next_image)
        self.skip_btn.pack(side='left', padx=5)

        # Bind Enter key
        self.entry.bind('<Return>', lambda e: self.save_label())

    def load_first_image(self):
        try:
            if self.images:
                image_path = os.path.join(self.captcha_dir, self.images[self.current_index])
                print(f"Đang tải ảnh: {image_path}")

                # Tải và xử lý ảnh
                image = Image.open(image_path)
                # Resize ảnh nếu cần
                # image = image.resize((300, 100), Image.Resampling.LANCZOS)

                # Chuyển đổi và hiển thị
                photo = ImageTk.PhotoImage(image)
                self.image_label.configure(image=photo)
                self.image_label.image = photo

                # Cập nhật label tiến độ
                self.progress_label.configure(
                    text=f"Ảnh {self.current_index + 1}/{len(self.images)}")

                print("Đã tải ảnh thành công")

                # Focus vào ô input
                self.entry.focus_set()
            else:
                print("Không có ảnh để tải")
        except Exception as e:
            print(f"Lỗi khi tải ảnh: {e}")
            messagebox.showerror("Lỗi", f"Không thể tải ảnh: {str(e)}")

    def next_image(self):
        self.current_index += 1
        if self.current_index < len(self.images):
            self.load_first_image()
        else:
            messagebox.showinfo("Hoàn thành", "Đã xử lý tất cả ảnh!")
            self.root.quit()

    def save_label(self):
        label = self.text_var.get().strip()
        if label:
            with open(os.path.join(self.captcha_dir, "labels.txt"), "a") as f:
                f.write(f"{self.images[self.current_index]}\t{label}\n")
            self.text_var.set("")  # Clear input
            self.next_image()

if __name__ == "__main__":
    print("=== Bắt đầu chương trình ===")
    root = tk.Tk()
    app = CaptchaLabeler(root)
    print("=== Đã khởi tạo giao diện ===")
    root.mainloop()