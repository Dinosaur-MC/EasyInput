#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
万能文本输入器 - Windows
通过 SendInput 直接模拟键盘输入，绕过剪贴板，支持任意 Unicode 字符。
"""

import tkinter as tk
from src.text_input_app import TextInputApp, APP_VERSION

__version__ = APP_VERSION


if __name__ == "__main__":
    root = tk.Tk()
    app = TextInputApp(root)
    root.mainloop()
