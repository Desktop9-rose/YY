# -*- coding: utf-8 -*-
import os
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import platform
from kivy.graphics import Color, Rectangle

# 设置全局字体大小基准 (适配老年人)
FONT_BASE = '28sp'
FONT_TITLE = '36sp'
FONT_BTN = '32sp'

# 颜色配置 (高对比度)
COLOR_BG = (1, 1, 1, 1)  # 白底
COLOR_TEXT = (0, 0, 0, 1)  # 黑字
COLOR_BTN_BG = (0.2, 0.2, 0.2, 1)  # 深灰按钮
COLOR_BTN_TEXT = (1, 1, 1, 1)  # 白字


class NativeUtils:
    """安卓原生功能封装类 (单例模式)"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NativeUtils, cls).__new__(cls)
            cls._instance._init_native()
        return cls._instance

    def _init_native(self):
        self.tts = None
        self.Android = None
        if platform == 'android':
            from jnius import autoclass
            self.PythonActivity = autoclass('org.kivy.android.PythonActivity')
            self.CurrentActivity = self.PythonActivity.mActivity
            self.Context = autoclass('android.content.Context')
            self.Toast = autoclass('android.widget.Toast')
            self.String = autoclass('java.lang.String')

            # 初始化 TTS (简易版，直接调用 Intent 或 尝试 Jnius)
            # 为了第一阶段稳定性，我们先用 plyer (buildozer中已包含)
            try:
                from plyer import tts
                self.tts = tts
            except Exception as e:
                print(f"TTS Init Error: {e}")

    def show_toast(self, text):
        """显示原生 Toast 提示"""
        if platform == 'android':
            try:
                # 必须在 UI 线程运行
                msg = self.String(text)
                toast = self.Toast.makeText(self.CurrentActivity, msg, self.Toast.LENGTH_SHORT)
                toast.show()
            except Exception as e:
                print(f"Toast Error: {e}")
        else:
            print(f"[TOAST]: {text}")

    def speak(self, text):
        """语音播报"""
        if self.tts:
            try:
                self.tts.speak(text)
            except Exception as e:
                print(f"Speak Error: {e}")
        else:
            print(f"[SPEAKING]: {text}")

    def request_permissions(self):
        """动态申请权限 (Android 6.0+)"""
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.RECORD_AUDIO
            ])


class ElderlyButton(Button):
    """自定义老年人按钮：大尺寸、高对比度"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_size = FONT_BTN
        self.bold = True
        self.background_normal = ''
        self.background_color = COLOR_BTN_BG
        self.color = COLOR_BTN_TEXT
        self.size_hint_y = None
        self.height = '80dp'  # 保证大点击区域


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.native = NativeUtils()

        # 根布局
        root = BoxLayout(orientation='vertical', padding='20dp', spacing='20dp')

        # 绘制白色背景
        with root.canvas.before:
            Color(*COLOR_BG)
            self.rect = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._update_rect, pos=self._update_rect)

        # 1. 顶部标题
        lbl_title = Label(
            text="智能医疗报告解读",
            font_size=FONT_TITLE,
            color=COLOR_TEXT,
            bold=True,
            size_hint_y=0.2
        )
        root.add_widget(lbl_title)

        # 2. 核心功能区
        btn_camera = ElderlyButton(text="📷 拍照解读")
        btn_camera.bind(on_release=self.action_camera)

        btn_gallery = ElderlyButton(text="🖼️ 相册选择")
        btn_gallery.bind(on_release=self.action_gallery)

        btn_history = ElderlyButton(text="🕒 历史记录")
        btn_history.bind(on_release=self.action_history)

        root.add_widget(btn_camera)
        root.add_widget(btn_gallery)
        root.add_widget(btn_history)

        # 占位符填充底部
        root.add_widget(Label(size_hint_y=0.3))

        self.add_widget(root)

        # 启动时自动申请权限
        Clock.schedule_once(lambda dt: self.native.request_permissions(), 1)
        # 启动时播放欢迎语
        Clock.schedule_once(lambda dt: self.native.speak("欢迎使用智能医疗解读助手"), 2)

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def action_camera(self, instance):
        self.native.speak("正在打开相机，请稍候")
        self.native.show_toast("相机功能将在第二阶段接入")
        # 这里预留了调用原生相机的接口位置

    def action_gallery(self, instance):
        self.native.speak("正在打开相册")
        self.native.show_toast("相册功能将在第二阶段接入")

    def action_history(self, instance):
        self.native.speak("查看历史记录")
        # 切换屏幕逻辑示例
        # self.manager.current = 'history'


class MedicalApp(App):
    def build(self):
        # 强制设置全屏白色背景
        Window.clearcolor = (1, 1, 1, 1)

        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        return sm


if __name__ == '__main__':
    # 支持中文显示 (需在同目录下放入中文字体文件，如 simsun.ttf)
    # 如果没有字体，为了防止乱码，可以用 DroidSansFallback
    from kivy.core.text import LabelBase

    # 假设你的 fonts 目录下有字体，如果没有，Kivy默认字体不支持中文
    # 这里为了测试不报错，请确保项目根目录有 msyh.ttf 或类似中文字体
    LabelBase.register(name='Roboto', fn_regular='msyh.ttf')

    MedicalApp().run()