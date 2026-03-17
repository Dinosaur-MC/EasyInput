import os
import threading
import json

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from pynput import keyboard
from .hotkey_dialog import HotkeyDialog
from .input_method import InputMethod, VK_ESCAPE

APP_VERSION = "0.1.0"


# ==================== 主应用程序 ====================
class TextInputApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"万能文本输入器 v{APP_VERSION}")
        self.root.geometry("600x540")

        # 配置变量
        self.countdown_seconds = tk.IntVar(value=3)
        self.confirm_before_input = tk.BooleanVar(value=False)
        self.hotkey_modifiers = set()  # 修饰键集合，如 {'ctrl', 'shift'}
        self.hotkey_key = None  # 主键，如 'f8', 'a'
        self.presets = {}  # 预设字典 {名称: 文本}
        self.current_preset_name = tk.StringVar()
        self.input_delay_ms = tk.IntVar(value=20)  # 默认 20ms
        self.esc_before_enter = tk.BooleanVar(value=False)
        self.clear_line_after_enter = tk.BooleanVar(value=False)
        self.skip_leading_whitespace = tk.BooleanVar(value=False)

        # 状态变量
        self.is_counting_down = False
        self.cancel_countdown_flag = False
        self.countdown_job = None
        self.current_modifiers = set()  # 当前按下的修饰键（由键盘监听线程维护）
        self.input_thread: threading.Thread | None = None

        # 输入方法
        self.input = InputMethod(tracing_keys={VK_ESCAPE})

        # 加载配置
        self.config_file = "config.json"
        self.load_config()

        # 创建界面
        self.create_widgets()

        # 启动全局键盘监听
        self.listener = None
        self.start_keyboard_listener()

        # 窗口关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    # -------------------- GUI 构建 --------------------
    def create_widgets(self):
        # 预设管理框架
        preset_frame = ttk.LabelFrame(self.root, text="预设管理", padding=5)
        preset_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(preset_frame, text="预设:").grid(row=0, column=0, sticky=tk.W)
        self.preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.current_preset_name,
            values=list(self.presets.keys()),
        )
        self.preset_combo.grid(row=0, column=1, padx=5, sticky=tk.W + tk.E)
        self.preset_combo.bind("<<ComboboxSelected>>", self.on_preset_selected)

        ttk.Button(preset_frame, text="添加预设", command=self.add_preset).grid(
            row=0, column=2, padx=5
        )
        ttk.Button(preset_frame, text="删除预设", command=self.delete_preset).grid(
            row=0, column=3, padx=5
        )
        ttk.Button(preset_frame, text="更新预设", command=self.update_preset).grid(
            row=0, column=4, padx=5
        )
        preset_frame.columnconfigure(1, weight=1)

        # 文本输入区
        text_frame = ttk.LabelFrame(self.root, text="输入文本", padding=5)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.text_widget = tk.Text(text_frame, wrap=tk.WORD, height=10)
        self.text_widget.pack(fill=tk.BOTH, expand=True)

        # 默认选中第一个预设
        first = next(iter(self.presets))
        self.current_preset_name.set(first)
        # 将第一个预设的文本填入文本框
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert("1.0", self.presets[first])

        # 热键设置框架
        hotkey_frame = ttk.LabelFrame(self.root, text="热键设置", padding=5)
        hotkey_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(hotkey_frame, text="当前热键:").grid(row=0, column=0, sticky=tk.W)
        self.hotkey_display = ttk.Entry(hotkey_frame, width=20, state="readonly")
        self.hotkey_display.grid(row=0, column=1, padx=5)
        ttk.Button(hotkey_frame, text="设置热键", command=self.set_hotkey).grid(
            row=0, column=2, padx=5
        )

        ttk.Button(hotkey_frame, text="清除热键", command=self.clear_hotkey).grid(
            row=0, column=3, padx=5
        )

        # 输入速度滑块
        def on_slide(val: str):
            # val 是字符串形式的浮点数
            int_val = int(round(float(val)))
            self.input_delay_ms.set(int_val)

        speed_frame = ttk.LabelFrame(self.root, text="输入速度设置", padding=5)
        speed_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(speed_frame, text="字符间延迟(ms):").pack(side=tk.LEFT)
        self.speed_scale = ttk.Scale(
            speed_frame,
            from_=0,
            to=60,
            orient=tk.HORIZONTAL,
            variable=self.input_delay_ms,
            command=on_slide,
            length=180,
        )
        self.speed_scale.pack(side=tk.LEFT, padx=5)
        ttk.Label(speed_frame, textvariable=self.input_delay_ms).pack(side=tk.LEFT)
        ttk.Label(speed_frame, text="(较大值更稳定)").pack(side=tk.LEFT, padx=10)

        # 延时和选项框架
        options_frame = ttk.LabelFrame(self.root, text="输入设置", padding=5)
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(options_frame, text="输入延时(秒):").pack(side=tk.LEFT)
        self.delay_spin = ttk.Spinbox(
            options_frame, from_=0, to=10, textvariable=self.countdown_seconds, width=5
        )
        self.delay_spin.pack(side=tk.LEFT, padx=10)

        self.esc_check = ttk.Checkbutton(
            options_frame,
            text="换行前发送Esc\n(取消IDE自动补全)",
            variable=self.esc_before_enter,
        )
        self.esc_check.pack(side=tk.LEFT, padx=8)

        self.clear_line_check = ttk.Checkbutton(
            options_frame,
            text="换行前清空当前行\n(处理IDE自动缩进)",
            variable=self.clear_line_after_enter,
        )
        self.clear_line_check.pack(side=tk.LEFT, padx=8)

        self.skip_leading_whitespace_check = ttk.Checkbutton(
            options_frame,
            text="跳过每行前导空白\n(处理IDE自动缩进)",
            variable=self.skip_leading_whitespace,
        )
        self.skip_leading_whitespace_check.pack(side=tk.LEFT, padx=8)

        # 控制按钮框架
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        self.start_button = ttk.Button(
            control_frame, text="立即输入", command=self.start_input_sequence
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.cancel_button = ttk.Button(
            control_frame, text="取消输入", command=self.cancel_input, state=tk.DISABLED
        )
        self.cancel_button.pack(side=tk.LEFT, padx=5)

        self.confirm_check = ttk.Checkbutton(
            control_frame, text="输入前确认", variable=self.confirm_before_input
        )
        self.confirm_check.pack(side=tk.LEFT, padx=20)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)

        # 初始化热键显示
        self.update_hotkey_display()

    # -------------------- 配置管理 --------------------
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config: dict = json.load(f)
                    self.presets = config.get("presets", {})
                    hotkey_mods = config.get("hotkey_modifiers", [])
                    self.hotkey_modifiers = set(hotkey_mods)
                    self.hotkey_key = config.get("hotkey_key")
                    self.countdown_seconds.set(config.get("delay", 3))
                    self.confirm_before_input.set(config.get("confirm", False))
                    self.input_delay_ms.set(config.get("char_delay", 20))
                    self.esc_before_enter.set(config.get("esc_before_enter", False))
                    self.clear_line_after_enter.set(
                        config.get("clear_line_after_enter", False)
                    )
                    self.skip_leading_whitespace.set(
                        config.get("skip_leading_whitespace", False)
                    )
            except Exception:
                pass
        # 确保 presets 非空，并设置默认选中
        if not self.presets:
            self.presets = {"示例": "请输入要输入的文本"}

    def save_config(self):
        config = {
            "presets": self.presets,
            "hotkey_modifiers": list(self.hotkey_modifiers),
            "hotkey_key": self.hotkey_key,
            "delay": self.countdown_seconds.get(),
            "confirm": self.confirm_before_input.get(),
            "char_delay": self.input_delay_ms.get(),
            "esc_before_enter": self.esc_before_enter.get(),
            "clear_line_after_enter": self.clear_line_after_enter.get(),
            "skip_leading_whitespace": self.skip_leading_whitespace.get(),
        }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    # -------------------- 预设操作 --------------------
    def on_preset_selected(self, event=None):
        name = self.current_preset_name.get()
        if name in self.presets:
            self.text_widget.delete("1.0", tk.END)
            self.text_widget.insert("1.0", self.presets[name])

    def add_preset(self):
        name = simpledialog.askstring("添加预设", "请输入预设名称:", parent=self.root)
        if name:
            if name in self.presets:
                if not messagebox.askyesno("确认", f"预设 '{name}' 已存在，是否覆盖？"):
                    return
            text = self.text_widget.get("1.0", tk.END).rstrip("\n")
            self.presets[name] = text
            self.update_preset_combo()
            self.current_preset_name.set(name)  # 立即选中新预设
            self.save_config()

    def delete_preset(self):
        name = self.current_preset_name.get()
        if name and name in self.presets:
            if messagebox.askyesno("确认", f"确定删除预设 '{name}' 吗？"):
                del self.presets[name]
                self.update_preset_combo()
                if self.presets:
                    # 有剩余预设，选中第一个
                    first = next(iter(self.presets))
                    self.current_preset_name.set(first)
                    self.text_widget.delete("1.0", tk.END)
                    self.text_widget.insert("1.0", self.presets[first])
                else:
                    # 没有预设了，清空
                    self.current_preset_name.set("")
                    self.text_widget.delete("1.0", tk.END)
                self.save_config()

    def update_preset(self):
        name = self.current_preset_name.get()
        if name and name in self.presets:
            text = self.text_widget.get("1.0", tk.END).rstrip("\n")
            self.presets[name] = text
            self.save_config()
            messagebox.showinfo("提示", "预设已更新")

    def update_preset_combo(self):
        self.preset_combo["values"] = list(self.presets.keys())

    # -------------------- 热键设置 --------------------
    def update_hotkey_display(self):
        if self.hotkey_key:
            mods = "+".join(sorted(self.hotkey_modifiers))
            hotkey_str = f"{mods}+{self.hotkey_key}" if mods else self.hotkey_key
        else:
            hotkey_str = "未设置"
        self.hotkey_display.config(state="normal")
        self.hotkey_display.delete(0, tk.END)
        self.hotkey_display.insert(0, hotkey_str)
        self.hotkey_display.config(state="readonly")

    def set_hotkey(self):
        """打开热键设置对话框"""
        HotkeyDialog(self.root, self.set_hotkey_callback)

    def set_hotkey_callback(self, modifiers, key):
        """从对话框接收新热键"""
        self.hotkey_modifiers = modifiers
        self.hotkey_key = key
        self.update_hotkey_display()
        self.save_config()

    def clear_hotkey(self):
        self.hotkey_modifiers = set()
        self.hotkey_key = None
        self.update_hotkey_display()
        self.save_config()

    # -------------------- 全局键盘监听 --------------------
    def start_keyboard_listener(self):
        def on_press(key: keyboard.Key | keyboard.KeyCode):
            # 更新当前修饰键集合
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self.current_modifiers.add("ctrl")
            elif key in (
                keyboard.Key.shift,
                keyboard.Key.shift_l,
                keyboard.Key.shift_r,
            ):
                self.current_modifiers.add("shift")
            elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
                self.current_modifiers.add("alt")
            elif key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                self.current_modifiers.add("cmd")
            else:
                # 检查是否匹配用户定义的热键
                if self.hotkey_key:
                    key_str = self.key_to_str(key)
                    if (
                        key_str == self.hotkey_key
                        and self.current_modifiers == self.hotkey_modifiers
                    ):
                        self.root.after(0, self.start_input_sequence)  # 在主线程中执行

            # 紧急停止：ESC 取消倒计时
            if key == keyboard.Key.esc:
                self.root.after(0, self.cancel_input)

        def on_release(key: keyboard.Key | keyboard.KeyCode):
            # 从当前修饰键集合中移除释放的修饰键
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self.current_modifiers.discard("ctrl")
            elif key in (
                keyboard.Key.shift,
                keyboard.Key.shift_l,
                keyboard.Key.shift_r,
            ):
                self.current_modifiers.discard("shift")
            elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
                self.current_modifiers.discard("alt")
            elif key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                self.current_modifiers.discard("cmd")

        self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.listener.daemon = True
        self.listener.start()

    def key_to_str(self, key: keyboard.Key | keyboard.KeyCode):
        """将 pynput 的 Key 对象转换为字符串，与热键存储格式一致"""
        if isinstance(key, keyboard.KeyCode):
            if key.char is None:
                return None
            return key.char.lower()  # 字母统一小写
        else:
            return key.name.lower()  # 功能键如 'f8' 也转为小写

    # -------------------- 输入控制 --------------------
    def start_input_sequence(self):
        if self.is_counting_down:
            # 如果正在倒计时，重新开始
            self.cancel_input()
            # 稍后重新开始，但需要避免递归
            self.root.after(100, self._start_countdown)
        else:
            self._start_countdown()

    def _start_countdown(self):
        # 如果开启了确认对话框，则询问用户
        if self.confirm_before_input.get():
            result = messagebox.askyesno(
                "确认输入",
                "准备输入文本，请确保目标窗口已获得焦点。\n是否开始倒计时？",
                parent=self.root,
            )
            if not result:
                return
        self.is_counting_down = True
        self.cancel_countdown_flag = False
        self.countdown_remaining = self.countdown_seconds.get()
        self.update_countdown()
        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.status_var.set(f"倒计时 {self.countdown_remaining} 秒，按 ESC 取消")

    def update_countdown(self):
        if self.cancel_countdown_flag:
            self.countdown_finished(cancelled=True)
            return
        if self.countdown_remaining > 0:
            self.status_var.set(f"倒计时 {self.countdown_remaining} 秒，按 ESC 取消")
            self.countdown_remaining -= 1
            self.countdown_job = self.root.after(1000, self.update_countdown)
        else:
            self.countdown_finished()

    def countdown_finished(self, cancelled=False):
        if cancelled:
            self.status_var.set("已取消")
            self.start_button.config(state=tk.NORMAL)
            self.cancel_button.config(state=tk.DISABLED)
        else:
            self.status_var.set("准备输入...")
            self.execute_input()
        # 清理倒计时状态
        self.is_counting_down = False
        if self.countdown_job:
            self.root.after_cancel(self.countdown_job)
            self.countdown_job = None

    def cancel_input(self):
        if self.is_counting_down:
            self.cancel_countdown_flag = True
            self.status_var.set("取消中...")
        if (
            self.input_thread
            and self.input_thread.is_alive()
            and not self.input.is_sending(VK_ESCAPE)
        ):
            self.input.cancel_input()

    def execute_input(self):
        text = self.text_widget.get("1.0", tk.END).rstrip("\n")
        if not text:
            messagebox.showwarning("警告", "没有要输入的文本")
            self.status_var.set("就绪")
            return
        self.status_var.set("正在输入...")
        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        delay_ms = self.input_delay_ms.get()
        use_esc = self.clear_line_after_enter.get()
        clear_line = self.clear_line_after_enter.get()
        skip_leading_whitespace = self.skip_leading_whitespace.get()

        def input_task():
            try:
                self.input.send_string(
                    text,
                    delay_ms,
                    esc_before_enter=use_esc,
                    clear_line_after_enter=clear_line,
                    skip_leading_whitespace=skip_leading_whitespace,
                )
                self.root.after(
                    0,
                    self.input_finished,
                    "输入完成" if not self.input.is_canceled() else "输入被取消",
                )
            except Exception as e:
                self.root.after(0, self.input_finished, f"输入出错: {e}")

        self.input_thread = threading.Thread(target=input_task, daemon=True)
        self.input_thread.start()

    def input_finished(self, status):
        self.status_var.set(status)
        self.start_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)

    # -------------------- 退出清理 --------------------
    def on_closing(self):
        self.save_config()
        if self.listener:
            self.listener.stop()
        self.root.destroy()
