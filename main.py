# -*- coding: utf-8 -*-
import os
import threading
import json
import time
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import platform
from kivy.graphics import Color, Rectangle
from service import MedicalService

# 引入字体
from kivy.core.text import LabelBase

LabelBase.register(name='Roboto', fn_regular='msyh.ttf')

# 字体配置
FONT_L = '32sp'
FONT_M = '28sp'

# 安卓装饰器
if platform == 'android':
    from android.runnable import run_on_ui_thread
    from jnius import autoclass, cast
else:
    def run_on_ui_thread(f):
        return f


class AndroidTTS:
    """
    纯 JNI 实现的安卓 TTS，比 Plyer 更稳健
    """

    def __init__(self):
        self.tts = None
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
                Context = autoclass('android.content.Context')
                # 实例化 TTS
                self.tts = TextToSpeech(PythonActivity.mActivity, None)
                print("[TTS] Initialized natively")
            except Exception as e:
                print(f"[TTS] Init failed: {e}")

    def speak(self, text):
        if self.tts:
            try:
                # flush 模式：打断当前正在说的，立即说新的
                self.tts.speak(str(text), 0, None)  # 0 = QUEUE_FLUSH
            except Exception as e:
                print(f"[TTS] Speak error: {e}")
        else:
            print(f"[TTS-MOCK] {text}")


class NativeUtils:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NativeUtils, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.tts_engine = AndroidTTS()
        if platform == 'android':
            try:
                # 禁用 StrictMode (解决相机 FileUriExposedException)
                StrictMode = autoclass('android.os.StrictMode')
                Builder = autoclass('android.os.StrictMode$VmPolicy$Builder')
                StrictMode.setVmPolicy(Builder().build())
            except:
                pass

    @run_on_ui_thread
    def show_toast(self, text):
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Toast = autoclass('android.widget.Toast')
                String = autoclass('java.lang.String')
                Toast.makeText(PythonActivity.mActivity, String(str(text)), 0).show()
            except:
                pass
        else:
            print(f"[TOAST] {text}")

    def speak(self, text):
        self.tts_engine.speak(text)

    def request_permissions(self):
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.RECORD_AUDIO
            ])

    def get_private_dir(self):
        if platform == 'android':
            try:
                PA = autoclass('org.kivy.android.PythonActivity')
                return PA.mActivity.getExternalFilesDir(None).getAbsolutePath()
            except:
                return "."
        return "."

    def take_photo(self, callback):
        """
        使用动态文件名调用相机
        """
        # 生成唯一文件名，防止冲突
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.jpg"
        filepath = os.path.join(self.get_private_dir(), filename)

        self.cb = callback
        self.target_path = filepath

        if platform == 'android':
            from plyer import camera
            try:
                print(f"[Camera] Requesting photo to: {filepath}")
                camera.take_picture(filename=filepath, on_complete=self._on_camera_return)
            except Exception as e:
                self.show_toast(f"相机启动错误: {e}")
        else:
            # 电脑测试
            with open(filepath, 'w') as f:
                f.write("dummy")
            self._on_camera_return(filepath)

    def _on_camera_return(self, path):
        # 注意：Plyer 返回的 path 可能是个参数，也可能为空，我们要优先信赖自己生成的 target_path
        real_path = self.target_path
        print(f"[Camera] Return. Checking: {real_path}")

        # 延迟检测，给文件系统写入留出 buffer 时间
        Clock.schedule_once(lambda dt: self._check_file(real_path), 1.0)

    def _check_file(self, path):
        if os.path.exists(path) and os.path.getsize(path) > 0:
            print(f"[Camera] Success: {path}")
            if self.cb: self.cb(path)
        else:
            print(f"[Camera] File missing or empty: {path}")
            self.show_toast("未检测到照片，请重试")


class ResultScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.native = NativeUtils()

        root = BoxLayout(orientation='vertical', padding='15dp', spacing='10dp')
        with root.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(size=(2000, 2000))

        root.add_widget(Label(text="诊断结果", font_size=FONT_L, color=(0, 0, 0, 1), bold=True, size_hint_y=0.1))

        scroll = ScrollView(size_hint_y=0.8)
        self.box = BoxLayout(orientation='vertical', spacing='20dp', size_hint_y=None, padding=[0, 20, 0, 20])
        self.box.bind(minimum_height=self.box.setter('height'))

        self.lbl_content = Label(
            text="加载中...", font_size=FONT_M, color=(0, 0, 0, 1), markup=True,
            size_hint_y=None, halign='left', valign='top', text_size=(Window.width - 50, None)
        )
        self.lbl_content.bind(texture_size=self.lbl_content.setter('size'))

        self.box.add_widget(self.lbl_content)
        scroll.add_widget(self.box)
        root.add_widget(scroll)

        btn = Button(text="返回首页", size_hint_y=0.1, background_color=(0.2, 0.2, 0.2, 1), font_size=FONT_L)
        btn.bind(on_release=lambda x: setattr(self.manager, 'current', 'home'))
        root.add_widget(btn)
        self.add_widget(root)

    def update(self, data):
        res = data.get('result', {})
        core = res.get('core_conclusion', '无')
        abn = res.get('abnormal_analysis', '无')
        life = res.get('life_advice', '无')

        text = f"[color=#aa0000][b]核心结论：[/b][/color]\n{core}\n\n"
        text += f"[b]异常分析：[/b]\n{abn}\n\n"
        text += f"[color=#006600][b]生活建议：[/b][/color]\n{life}"

        self.lbl_content.text = text
        self.lbl_content.text_size = (Window.width - 50, None)
        self.lbl_content.texture_update()

        self.native.speak(f"解读完成。{core}")


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.native = NativeUtils()
        self.svc = MedicalService()

        root = BoxLayout(orientation='vertical', padding='20dp', spacing='30dp')
        with root.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(size=(2000, 2000))

        root.add_widget(
            Label(text="智能医疗报告解读", font_size='36sp', color=(0, 0, 0, 1), bold=True, size_hint_y=0.2))
        self.status = Label(text="初始化中...", font_size=FONT_M, color=(0.5, 0.5, 0.5, 1), size_hint_y=0.1)
        root.add_widget(self.status)

        # 按钮容器
        btn_box = BoxLayout(orientation='vertical', spacing='20dp', size_hint_y=0.5)

        btn_cam = Button(text="📷 拍照解读", font_size=FONT_L, background_color=(0.2, 0.2, 0.2, 1))
        btn_cam.bind(on_release=self.action_snap)
        btn_box.add_widget(btn_cam)

        btn_box.add_widget(Button(text="🖼️ 相册选择", font_size=FONT_L, background_color=(0.5, 0.5, 0.5, 1)))
        btn_box.add_widget(Button(text="🕒 历史记录", font_size=FONT_L, background_color=(0.5, 0.5, 0.5, 1)))

        root.add_widget(btn_box)
        root.add_widget(Label(size_hint_y=0.2))
        self.add_widget(root)

        Clock.schedule_once(self.start, 1)

    def start(self, dt):
        self.native.request_permissions()
        if self.svc.config_ready:
            self.status.text = "✅ 云端就绪，请拍照"
            self.native.speak("系统就绪")
        else:
            self.status.text = "⚠️ 密钥错误"

    def action_snap(self, instance):
        self.native.speak("请拍摄报告")
        self.native.take_photo(self.on_photo_ready)

    def on_photo_ready(self, path):
        self.status.text = "🔄 正在分析..."
        self.native.speak("正在分析，请稍候")
        threading.Thread(target=self.run_ai, args=(path,)).start()

    def run_ai(self, path):
        try:
            res = self.svc.process(path)
            Clock.schedule_once(lambda dt: self.done(res), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: self.error(str(e)), 0)

    def done(self, res):
        if res['code'] == 200:
            self.status.text = "完成"
            self.manager.get_screen('result').update(res['data'])
            self.manager.current = 'result'
        else:
            self.error(res['message'])

    def error(self, msg):
        self.status.text = "❌ 失败"
        self.native.show_toast(msg)
        self.native.speak("分析失败")


class MedicalApp(App):
    def build(self):
        Window.clearcolor = (1, 1, 1, 1)
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(ResultScreen(name='result'))
        return sm


if __name__ == '__main__':
    MedicalApp().run()