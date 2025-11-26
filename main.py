# -*- coding: utf-8 -*-
import os
import configparser
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import platform
from kivy.graphics import Color, Rectangle

# 引入中文字体支持
from kivy.core.text import LabelBase

# 请确保 msyh.ttf 在项目根目录
LabelBase.register(name='Roboto', fn_regular='msyh.ttf')

# 字体与颜色配置
FONT_BASE = '28sp'
FONT_TITLE = '36sp'
FONT_BTN = '32sp'
COLOR_BG = (1, 1, 1, 1)
COLOR_TEXT = (0, 0, 0, 1)
COLOR_BTN_BG = (0.2, 0.2, 0.2, 1)
COLOR_BTN_TEXT = (1, 1, 1, 1)


class NativeUtils:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NativeUtils, cls).__new__(cls)
            cls._instance._init_native()
        return cls._instance

    def _init_native(self):
        self.tts = None
        if platform == 'android':
            from jnius import autoclass
            self.PythonActivity = autoclass('org.kivy.android.PythonActivity')
            self.CurrentActivity = self.PythonActivity.mActivity
            self.Context = autoclass('android.content.Context')
            self.Toast = autoclass('android.widget.Toast')
            self.String = autoclass('java.lang.String')
            try:
                from plyer import tts
                self.tts = tts
            except:
                pass

    def show_toast(self, text):
        if platform == 'android':
            try:
                msg = self.String(text)
                toast = self.Toast.makeText(self.CurrentActivity, msg, self.Toast.LENGTH_SHORT)
                toast.show()
            except:
                pass
        else:
            print(f"[TOAST]: {text}")

    def speak(self, text):
        if self.tts:
            try:
                self.tts.speak(text)
            except:
                pass
        else:
            print(f"[SPEAKING]: {text}")

    def request_permissions(self):
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.RECORD_AUDIO
            ])


class ElderlyButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_size = FONT_BTN
        self.bold = True
        self.background_normal = ''
        self.background_color = COLOR_BTN_BG
        self.color = COLOR_BTN_TEXT
        self.size_hint_y = None
        self.height = '80dp'


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.native = NativeUtils()
        root = BoxLayout(orientation='vertical', padding='20dp', spacing='20dp')
        with root.canvas.before:
            Color(*COLOR_BG)
            self.rect = Rectangle(size=root.size, pos=root.pos)
        root.bind(size=self._update_rect, pos=self._update_rect)

        root.add_widget(
            Label(text="智能医疗报告解读", font_size=FONT_TITLE, color=COLOR_TEXT, bold=True, size_hint_y=0.2))

        # 按钮区
        btn_cam = ElderlyButton(text="📷 拍照解读")
        btn_cam.bind(on_release=self.check_config_and_camera)  # 绑定新事件
        root.add_widget(btn_cam)

        root.add_widget(ElderlyButton(text="🖼️ 相册选择"))
        root.add_widget(ElderlyButton(text="🕒 历史记录"))

        # 底部状态栏 (用于显示配置是否成功)
        self.lbl_status = Label(text="正在检查配置...", font_size='20sp', color=(0.5, 0.5, 0.5, 1), size_hint_y=0.1)
        root.add_widget(self.lbl_status)

        root.add_widget(Label(size_hint_y=0.2))
        self.add_widget(root)

        Clock.schedule_once(lambda dt: self.native.request_permissions(), 1)
        # 启动时检查 config.ini 是否存在
        Clock.schedule_once(self.load_config_status, 2)

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def load_config_status(self, dt):
        """检查 config.ini 是否被 GitHub Actions 成功注入"""
        if os.path.exists('config.ini'):
            try:
                conf = configparser.ConfigParser()
                conf.read('config.ini')
                ak = conf.get('aliyun', 'access_key_id', fallback='Not Found')
                if ak != 'Not Found' and len(ak) > 5:
                    self.lbl_status.text = "✅ 云端连接配置成功"
                    self.native.speak("系统初始化完成")
                else:
                    self.lbl_status.text = "❌ 配置文件为空"
            except Exception as e:
                self.lbl_status.text = f"配置读取错误: {str(e)}"
        else:
            self.lbl_status.text = "⚠️ 未找到配置文件 (本地测试模式)"

    def check_config_and_camera(self, instance):
        self.native.speak("正在启动相机")
        self.native.show_toast("相机模块加载中...")


class MedicalApp(App):
    def build(self):
        Window.clearcolor = (1, 1, 1, 1)
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        return sm


if __name__ == '__main__':
    MedicalApp().run()