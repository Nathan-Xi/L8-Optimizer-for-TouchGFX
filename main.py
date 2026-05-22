"""
=====================================================================================
L8 Compression & Dithering Optimizer for TouchGFX
=====================================================================================

Company            : Shanghai University
Engineer           : Nathan Xi

Create Date        : 2026-05-16

Description:
    A GUI image preprocessing tool designed for embedded graphics frameworks
    (e.g., STM32C0 TouchGFX). It heavily optimizes standard RGB images into strictly
    compressed 8-bit palette (L8 format) images.

    By employing a proprietary "Pre-quantization High-Frequency Noise Injection"
    algorithm combined with "Floyd-Steinberg Error Diffusion", it mathematically
    eliminates color banding (step artifacts) in smooth gradients. This allows for
    photorealistic UI assets using minimal RAM/Flash footprints (e.g., pseudo true-color
    gradients using only a 64-color palette).

Key Features:
    1. Custom Palette Downsampling: Dynamic control from 2 to 256 colors.
    2. Noise-Driven Dithering: Adjustable noise matrix injection to break color steps.
    3. Non-blocking UI Pipeline: Async multi-threading and debouncing implementation.
    4. Ready-to-Use Export: Outputs compliant 8-bit P-mode PNGs.

Dependencies:
    Python 3.13
    Pillow 12.2.0
    numpy 2.4.5

Revision History:
    v1.0 - 2026-05-16 - Initial Python Implementation. FSD dithering.
    v1.1 - 2026-05-17 - Improved GUI layout with image preview and thread handling.

=====================================================================================
"""
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import numpy as np
import threading


class UltimateL8ConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("L8 Optimizer")
        self.root.geometry("850x650")
        self.root.resizable(False, False)

        self.export_img_p_mode = None
        self.current_img_path = None

        # 多线程与防抖状态控制
        self.is_processing = False
        self.pending_process = False
        self.debounce_timer = None

        # 兼容不同版本的 Pillow
        self.resample_filter = getattr(Image, 'Resampling', Image).NEAREST

        self.setup_ui()

    def setup_ui(self):
        # 控制面板
        control_frame = tk.Frame(self.root, relief=tk.RIDGE, bd=2)
        control_frame.pack(pady=10, fill=tk.X, padx=20)

        self.btn_load = tk.Button(control_frame, text="打开生图", font=("Arial", 10, "bold"),
                                  command=self.load_image)
        self.btn_load.grid(row=0, column=0, padx=20, pady=10)

        # 文本输入框
        lbl_colors = tk.Label(control_frame, text="最大颜色数 (2-256):")
        lbl_colors.grid(row=0, column=1, padx=5)

        self.color_var = tk.StringVar(value="64")
        self.entry_colors = tk.Entry(control_frame, textvariable=self.color_var, width=6, font=("Arial", 12, "bold"),
                                     justify="center")
        self.entry_colors.grid(row=0, column=2, padx=5)

        self.entry_colors.bind("<KeyRelease>", self.schedule_reprocess)
        self.entry_colors.bind("<FocusOut>", self.schedule_reprocess)

        # 噪声强度滑块
        lbl_noise = tk.Label(control_frame, text="加噪强度 (0-30):")
        lbl_noise.grid(row=0, column=3, padx=(15, 5))
        self.scale_noise = tk.Scale(control_frame, from_=0, to=30, orient=tk.HORIZONTAL, length=150,
                                    command=self.schedule_reprocess)  # 拖动时实时触发防抖
        self.scale_noise.set(10)
        self.scale_noise.grid(row=0, column=4, padx=5)

        # 图像预览区域
        mid_frame = tk.Frame(self.root)
        mid_frame.pack(pady=5)

        left_frame = tk.Frame(mid_frame)
        left_frame.grid(row=0, column=0, padx=20)
        self.canvas_left = tk.Canvas(left_frame, width=350, height=350, bg="#E0E0E0", highlightthickness=1,
                                     highlightbackground="#A0A0A0")
        self.canvas_left.pack()
        self.lbl_left_desc = tk.Label(left_frame, text="常规量化", font=("Arial", 10, "bold"), fg="#03234B")
        self.lbl_left_desc.pack(pady=8)

        right_frame = tk.Frame(mid_frame)
        right_frame.grid(row=0, column=1, padx=20)
        self.canvas_right = tk.Canvas(right_frame, width=350, height=350, bg="#E0E0E0", highlightthickness=1,
                                      highlightbackground="#A0A0A0")
        self.canvas_right.pack()
        self.lbl_right_desc = tk.Label(right_frame, text="加噪+抖动 (平滑)", font=("Arial", 10, "bold"), fg="#03234B")
        self.lbl_right_desc.pack(pady=8)

        # 导出
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(pady=10)
        self.btn_save = tk.Button(bottom_frame, text="导出 (.png)", font=("Arial", 11, "bold"),
                                  state=tk.DISABLED, command=self.save_image)
        self.btn_save.pack()

    def get_valid_colors(self):
        """输入框的安全验证逻辑"""
        try:
            val = int(self.color_var.get())
            if val < 2:
                val = 2
            elif val > 256:
                val = 256
        except ValueError:
            val = 64
        return val

    def load_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if file_path:
            self.current_img_path = file_path
            self.schedule_reprocess()

    def schedule_reprocess(self, *args):
        """防抖 等待 400 毫秒无操作后开始处理"""
        if not self.current_img_path:
            return

        if self.debounce_timer:
            self.root.after_cancel(self.debounce_timer)

        # 设置400毫秒延迟
        self.debounce_timer = self.root.after(400, self.trigger_processing)

    def trigger_processing(self):
        """触发处理逻辑"""
        if self.is_processing:
            # 如果后台正在跑，设置一个标记，等它跑完了再跑一次新的
            self.pending_process = True
        else:
            self.start_processing_thread()

    def start_processing_thread(self):
        """后台处理线程，避免卡死主界面"""
        self.is_processing = True
        self.pending_process = False

        # 禁用保存按钮，并在画布上给出加载提示
        self.btn_save.config(state=tk.DISABLED)
        self.canvas_left.delete("all")
        self.canvas_left.create_text(175, 175, text="Processing...", fill="#E6007E", font=("Arial", 12))
        self.canvas_right.delete("all")
        self.canvas_right.create_text(175, 175, text="Processing...", fill="#E6007E", font=("Arial", 12))

        colors = self.get_valid_colors()
        noise_strength = self.scale_noise.get()

        # 开启守护线程进行密集运算
        thread = threading.Thread(
            target=self._processing_task_bg,
            args=(self.current_img_path, colors, noise_strength)
        )
        thread.daemon = True
        thread.start()

    def _processing_task_bg(self, img_path, colors, noise_strength):
        """后台线程不阻塞UI"""
        try:
            img_rgb = Image.open(img_path).convert('RGB')

            # 1. 常规量化
            l8_normal = img_rgb.quantize(colors=colors, dither=Image.NONE)

            # 2. 注入噪声并抖动量化
            if noise_strength > 0:
                img_arr = np.array(img_rgb, dtype=np.int16)
                noise = np.random.randint(-noise_strength, noise_strength + 1, img_arr.shape)
                img_arr = np.clip(img_arr + noise, 0, 255).astype(np.uint8)
                img_noisy = Image.fromarray(img_arr)
            else:
                img_noisy = img_rgb

            l8_magic = img_noisy.quantize(colors=colors, dither=Image.FLOYDSTEINBERG)

            # 预览缩略图呈现
            preview_normal = l8_normal.convert('RGB')
            preview_normal.thumbnail((350, 350), self.resample_filter)

            preview_magic = l8_magic.convert('RGB')
            preview_magic.thumbnail((350, 350), self.resample_filter)

            # 将结果传回主UI线程更新
            self.root.after(0, self._processing_done_ui,
                            l8_magic, preview_normal, preview_magic, colors, noise_strength, None)

        except Exception as e:
            self.root.after(0, self._processing_done_ui,
                            None, None, None, colors, noise_strength, str(e))

    def _processing_done_ui(self, l8_magic, preview_normal, preview_magic, colors, noise_strength, error_msg):
        """运算结束，更新界面"""
        self.is_processing = False

        if error_msg:
            messagebox.showerror("Processing failed", f"Err: {error_msg}")
        else:
            self.export_img_p_mode = l8_magic
            self.update_canvas(self.canvas_left, preview_normal, "left")
            self.update_canvas(self.canvas_right, preview_magic, "right")

            # 验证后的数值写回输入框，防止用户看到错误输入
            if self.color_var.get() != str(colors):
                self.color_var.set(str(colors))

            self.lbl_left_desc.config(text=f"普通量化 ({colors} 色)")
            self.lbl_right_desc.config(text=f"加噪(强度:{noise_strength}) + 抖动量化 ({colors} 色)")
            self.btn_save.config(state=tk.NORMAL)

        # 如果在计算期间用户改了参数，触发下一次处理
        if self.pending_process:
            self.start_processing_thread()

    def update_canvas(self, canvas, pil_img, side):
        tk_img = ImageTk.PhotoImage(pil_img)
        if side == "left":
            self.tk_img_left = tk_img
        else:
            self.tk_img_right = tk_img
        canvas.delete("all")
        canvas.create_image(175, 175, image=tk_img, anchor=tk.CENTER)

    def save_image(self):
        if not self.export_img_p_mode: return
        colors = self.get_valid_colors()
        save_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG 图像", "*.png")],
            initialfile=f"optimized_l8_{colors}colors.png"
        )
        if save_path:
            try:
                self.export_img_p_mode.save(save_path, format="PNG")
                messagebox.showinfo("Saved", f"\n使用 {colors} 色 CLUT。")
            except Exception as e:
                messagebox.showerror("Err", f"Failed: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = UltimateL8ConverterApp(root)
    root.mainloop()