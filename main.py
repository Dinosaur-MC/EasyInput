#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
万能文本输入器 - Windows 11
通过 SendInput 直接模拟键盘输入，绕过剪贴板，支持任意 Unicode 字符。
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import time
import json
import os
import ctypes
from ctypes import wintypes
from pynput import keyboard
import threading


# ==================== SendInput 实现 ====================
def send_unicode_string(
    text: str,
    is_sending_escape: list[bool],
    char_delay_ms=5,
    esc_before_enter=False,
    clear_line_before_enter=False,
    cancel_check=None,
):
    """
    逐字符发送文本，每个字符后暂停 char_delay_ms 毫秒。
    支持取消检查（cancel_check 返回 True 时终止）。
    优化了特殊键的发送方式，减少卡顿，提高兼容性。
    """
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYDOWN = 0x0
    KEYEVENTF_KEYUP = 0x02
    KEYEVENTF_UNICODE = 0x04

    VK_RETURN = 0x0D
    VK_SHIFT = 0x10
    VK_HOME = 0x24
    VK_DELETE = 0x2E
    VK_ESCAPE = 0x1B

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = (
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        )

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = (
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        )

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = (
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        )

    class INPUT_UNION(ctypes.Union):
        _fields_ = (("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT))

    class INPUT(ctypes.Structure):
        _fields_ = (("type", wintypes.DWORD), ("union", INPUT_UNION))

    SendInput = ctypes.windll.user32.SendInput
    SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    SendInput.restype = wintypes.UINT

    # 封装事件创建
    def create_key_event(vk=0, scan=0, flags=0):
        ki = KEYBDINPUT()
        ki.wVk = vk
        ki.wScan = scan
        ki.dwFlags = flags
        ki.time = 0
        ki.dwExtraInfo = 0
        input_struct = INPUT()
        input_struct.type = INPUT_KEYBOARD
        input_struct.union.ki = ki
        return input_struct

    def send_events(events):
        if not events:
            return
        array_type = INPUT * len(events)
        input_array = array_type(*events)
        sent = SendInput(len(events), input_array, ctypes.sizeof(INPUT))
        if sent != len(events):
            print(f"警告：只发送了 {sent}/{len(events)} 个事件")

    if not text:
        return

    delay = char_delay_ms / 1000.0

    for ch in text:
        if cancel_check and cancel_check():
            print("输入被用户取消")
            return

        if ch == "\n":
            # 可选：Esc 键关闭补全（单独发送，加短延迟）
            if esc_before_enter:
                esc_events = [
                    create_key_event(vk=VK_ESCAPE, flags=KEYEVENTF_KEYDOWN),
                    create_key_event(vk=VK_ESCAPE, flags=KEYEVENTF_KEYUP),
                ]
                is_sending_escape[0] = True
                send_events(esc_events)
                time.sleep(0.01)  # 让系统处理 Esc
                is_sending_escape[0] = False

            # 发送 Enter 键
            enter_events = [
                create_key_event(vk=VK_RETURN, flags=KEYEVENTF_KEYDOWN),
                create_key_event(vk=VK_RETURN, flags=KEYEVENTF_KEYUP),
            ]
            send_events(enter_events)
            time.sleep(delay)

            # 可选：清空当前行 (Shift+Home + Backspace)
            if clear_line_before_enter:
                # 按下 Shift 和 Home
                send_events([create_key_event(vk=VK_SHIFT, flags=KEYEVENTF_KEYDOWN)])
                send_events([create_key_event(vk=VK_HOME, flags=KEYEVENTF_KEYDOWN)])
                # 释放 Home 和 Shift
                send_events([create_key_event(vk=VK_HOME, flags=KEYEVENTF_KEYUP)])
                send_events([create_key_event(vk=VK_SHIFT, flags=KEYEVENTF_KEYUP)])
                time.sleep(delay)
                # Backspace 按下+释放
                back_events = [
                    create_key_event(vk=VK_DELETE, flags=KEYEVENTF_KEYDOWN),
                    create_key_event(vk=VK_DELETE, flags=KEYEVENTF_KEYUP),
                ]
                send_events(back_events)
                time.sleep(delay)
        else:
            # 普通 Unicode 字符
            encoded = ch.encode("utf-16-le")
            char_events = []
            for i in range(0, len(encoded), 2):
                code_unit = int.from_bytes(encoded[i : i + 2], "little")
                char_events.append(
                    create_key_event(scan=code_unit, flags=KEYEVENTF_UNICODE)
                )
                char_events.append(
                    create_key_event(
                        scan=code_unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
                    )
                )
            send_events(char_events)
            time.sleep(delay)


# ==================== 主应用程序 ====================
class TextInputApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("万能文本输入器")
        self.root.geometry("600x540")

        # 配置变量
        self.countdown_seconds = tk.IntVar(value=3)
        self.confirm_before_input = tk.BooleanVar(value=False)
        self.hotkey_modifiers = set()  # 修饰键集合，如 {'ctrl', 'shift'}
        self.hotkey_key = None  # 主键，如 'f8', 'a'
        self.presets = {}  # 预设字典 {名称: 文本}
        self.current_preset_name = tk.StringVar()
        self.input_delay_ms = tk.IntVar(value=20)  # 默认 20ms
        self.esc_before_enter = tk.BooleanVar(value=False)  # 默认关闭
        self.clear_line_before_enter = tk.BooleanVar(value=False)  # 默认关闭

        # 状态变量
        self.is_counting_down = False
        self.cancel_countdown_flag = False
        self.countdown_job = None
        self.current_modifiers = set()  # 当前按下的修饰键（由键盘监听线程维护）
        self.input_thread = None
        self.input_cancel_requested = False
        self.is_sending_escape = [False]

        # 加载配置
        self.config_file = "text_input_config.json"
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
        self.esc_check.pack(side=tk.LEFT, padx=10)

        self.clear_line_check = ttk.Checkbutton(
            options_frame,
            text="换行前清空当前行\n(处理IDE自动缩进)",
            variable=self.clear_line_before_enter,
        )
        self.clear_line_check.pack(side=tk.LEFT, padx=10)

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
                    self.clear_line_before_enter.set(
                        config.get("clear_line_before_enter", False)
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
            "clear_line_before_enter": self.clear_line_before_enter.get(),
        }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
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
        HotkeyDialog(self.root, self)

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
            if key == keyboard.Key.esc and not self.is_sending_escape[0]:
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
        else:
            self.status_var.set("准备输入...")
            self.execute_input()
        # 清理倒计时状态
        self.is_counting_down = False
        self.start_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        if self.countdown_job:
            self.root.after_cancel(self.countdown_job)
            self.countdown_job = None

    def cancel_input(self):
        if self.is_counting_down:
            self.cancel_countdown_flag = True
            self.status_var.set("取消中...")
        if self.input_thread and self.input_thread.is_alive():
            self.request_input_cancel()

    def execute_input(self):
        text = self.text_widget.get("1.0", tk.END).rstrip("\n")
        if not text:
            messagebox.showwarning("警告", "没有要输入的文本")
            self.status_var.set("就绪")
            return
        self.status_var.set("正在输入...")
        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.input_cancel_requested = False
        delay_ms = self.input_delay_ms.get()
        use_esc = self.esc_before_enter.get()
        clear_line = self.clear_line_before_enter.get()

        def input_task():
            try:
                send_unicode_string(
                    text,
                    self.is_sending_escape,
                    char_delay_ms=delay_ms,
                    esc_before_enter=use_esc,
                    clear_line_before_enter=clear_line,
                    cancel_check=lambda: self.input_cancel_requested,
                )
                self.root.after(0, self.input_finished, "输入完成")
            except Exception as e:
                self.root.after(0, self.input_finished, f"输入出错: {e}")

        self.input_thread = threading.Thread(target=input_task, daemon=True)
        self.input_thread.start()

    def request_input_cancel(self):
        """请求取消当前输入（由全局键盘监听调用）"""
        self.input_cancel_requested = True
        self.status_var.set("正在取消输入...")

    def input_finished(self, status):
        self.status_var.set(status)
        self.start_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.input_cancel_requested = False

    # -------------------- 退出清理 --------------------
    def on_closing(self):
        self.save_config()
        if self.listener:
            self.listener.stop()
        self.root.destroy()


# ==================== 热键设置对话框 ====================
class HotkeyDialog:
    def __init__(self, parent: tk.Tk, app: TextInputApp):
        self.parent = parent
        self.app = app
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("设置热键")
        self.dialog.geometry("300x150")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        ttk.Label(self.dialog, text="请按下您希望使用的热键组合...").pack(pady=10)
        self.key_label = ttk.Label(self.dialog, text="", font=("Arial", 12))
        self.key_label.pack(pady=5)

        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=10)
        self.ok_btn = ttk.Button(
            btn_frame, text="确定", command=self.ok, state=tk.DISABLED
        )
        self.ok_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.cancel).pack(
            side=tk.LEFT, padx=5
        )

        # 绑定键盘事件
        self.dialog.bind("<KeyPress>", self.on_key_press)
        self.dialog.bind("<KeyRelease>", self.on_key_release)

        self.pressed_keys = set()
        self.modifiers_recorded = set()
        self.main_key = None
        self.dialog.focus_set()

        # 将窗口居中于父窗口
        self.dialog.update_idletasks()  # 确保窗口大小已计算
        x = (
            parent.winfo_rootx()
            + (parent.winfo_width() // 2)
            - (self.dialog.winfo_width() // 2)
        )
        y = (
            parent.winfo_rooty()
            + (parent.winfo_height() // 2)
            - (self.dialog.winfo_height() // 2)
        )
        self.dialog.geometry(f"+{x}+{y}")

    def on_key_press(self, event: tk.Event):
        keysym = event.keysym
        if keysym in self.pressed_keys:
            return
        self.pressed_keys.add(keysym)

        mod = self.get_modifier(keysym)
        if mod:
            self.modifiers_recorded.add(mod)
        else:
            # 如果是非修饰键，且还没有主键，则记录
            if self.main_key is None:
                self.main_key = self.normalize_key(keysym)
        self.update_display()

    def on_key_release(self, event: tk.Event):
        keysym = event.keysym
        if keysym in self.pressed_keys:
            self.pressed_keys.remove(keysym)

        # 当所有键都释放时，如果有主键，则启用确定按钮
        if not self.pressed_keys and self.main_key is not None:
            self.ok_btn.config(state=tk.NORMAL)
        self.update_display()  # 更新显示（但记录不会改变）

    def get_modifier(self, keysym: str):
        if keysym in ("Control_L", "Control_R", "Control"):
            return "ctrl"
        elif keysym in ("Shift_L", "Shift_R", "Shift"):
            return "shift"
        elif keysym in ("Alt_L", "Alt_R", "Alt"):
            return "alt"
        elif keysym in ("Super_L", "Super_R", "Super", "Win_L", "Win_R"):
            return "cmd"
        else:
            return None

    def normalize_key(self, keysym: str):
        if len(keysym) == 1 and keysym.isalpha():
            return keysym.lower()
        else:
            return keysym.lower()

    def update_display(self):
        parts = list(self.modifiers_recorded)
        if self.main_key:
            parts.append(self.main_key)
        self.key_label.config(text=" + ".join(parts) if parts else "（无）")

    def ok(self):
        self.app.set_hotkey_callback(self.modifiers_recorded.copy(), self.main_key)
        self.dialog.destroy()

    def cancel(self):
        self.dialog.destroy()


# ==================== 启动 ====================
if __name__ == "__main__":
    root = tk.Tk()
    app = TextInputApp(root)
    root.mainloop()
