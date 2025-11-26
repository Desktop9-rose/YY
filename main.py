# -*- coding: utf-8 -*-
import os
import threading
import json
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

from kivy.core.text import LabelBase

LabelBase.register(name='Roboto', fn_regular='msyh.ttf')

FONT_L = '32sp'
FONT_M = '28sp'


class NativeUtils:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NativeUtils, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.tts = None
        if platform == 'android':
            try:
                from plyer import tts
                self.tts = tts
            except:
                pass

    def show_toast(self, text):
        if platform == 'android':
            from jnius import autoclass
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Toast = autoclass('android.widget.Toast')
                String = autoclass('java.lang.String')
                Toast.makeText(PythonActivity.mActivity, String(text), Toast.LENGTH_SHORT).show()
            except:
                pass
        else:
            print(f"[TOAST] {text}")

    def speak(self, text):
        print(f"[SPEAK] {text}")
        if self.tts:
            try:
                self.tts.speak(text)
            except:
                pass

    def get_private_dir(self):
        if platform == 'android':
            from jnius import autoclass
            try:
                PA = autoclass('org.kivy.android.PythonActivity')
                return PA.mActivity.getExternalFilesDir(None).getAbsolutePath()
            except:
                return "."
        return "."

    def take_photo(self, filepath, callback):
        self.cb = callback
        if platform == 'android':
            from plyer import camera
            try:
                camera.take_picture(filename=filepath, on_complete=self._done)
            except Exception as e:
                self.show_toast(f"相机错误: {e}")
        else:
            self.show_toast("电脑模拟拍照")
            with open(filepath, 'w') as f:
                f.write("test")
            self._done(filepath)

    def _done(self, path):
        if self.cb: self.cb(path)


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
        self.box = BoxLayout(orientation='vertical', spacing='20dp', size_hint_y=None)
        self.box.bind(minimum_height=self.box.setter('height'))

        self.lbl_content = Label(text="", font_size=FONT_M, color=(0, 0, 0, 1), markup=True, size_hint_y=None,
                                 halign='left', valign='top')
        self.lbl_content.bind(texture_size=self.lbl_content.setter('size'))

        self.box.add_widget(self.lbl_content)
        scroll.add_widget(self.box)
        root.add_widget(scroll)

        btn = Button(text="返回", size_hint_y=0.1, background_color=(0.2, 0.2, 0.2, 1))
        btn.bind(on_release=lambda x: setattr(self.manager, 'current', 'home'))
        root.add_widget(btn)
        self.add_widget(root)

    def update(self, data):
        res = data.get('result', {})
        text = f"[color=#aa0000][b]核心结论：[/b][/color]\n{res.get('core_conclusion', '')}\n\n"
        text += f"[b]异常分析：[/b]\n{res.get('abnormal_analysis', '')}\n\n"
        text += f"[color=#006600][b]生活建议：[/b][/color]\n{res.get('life_advice', '')}"
        self.lbl_content.text = text
        self.native.speak(res.get('core_conclusion', ''))


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
            Label(text="智能医疗报告解读", font_size='40sp', color=(0, 0, 0, 1), bold=True, size_hint_y=0.3))
        self.status = Label(text="请拍照", font_size=FONT_M, color=(0.5, 0.5, 0.5, 1), size_hint_y=0.1)
        root.add_widget(self.status)

        btn = Button(text="📷 拍照解读", font_size=FONT_L, background_color=(0.2, 0.2, 0.2, 1), size_hint_y=0.2)
        btn.bind(on_release=self.snap)
        root.add_widget(btn)
        root.add_widget(Label(size_hint_y=0.4))
        self.add_widget(root)

        Clock.schedule_once(lambda dt: self.check(), 1)

    def check(self):
        if self.svc.config_ready:
            self.status.text = "✅ 云端就绪"
            self.native.speak("系统就绪")
        else:
            self.status.text = "⚠️ 配置缺失"

    def snap(self, instance):
        p = os.path.join(self.native.get_private_dir(), 'doc.jpg')
        self.native.take_photo(p, self.process)

    def process(self, path):
        if not os.path.exists(path): return
        self.status.text = "🔄 分析中..."
        self.native.speak("正在分析")
        threading.Thread(target=self._run, args=(path,)).start()

    def _run(self, path):
        res = self.svc.process(path)
        Clock.schedule_once(lambda dt: self._done(res), 0)

    def _done(self, res):
        if res['code'] == 200:
            self.status.text = "完成"
            self.manager.get_screen('result').update(res['data'])
            self.manager.current = 'result'
        else:
            self.status.text = f"错误: {res['message']}"
            self.native.speak("失败")


class MedicalApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(ResultScreen(name='result'))
        return sm


if __name__ == '__main__':
    MedicalApp().run()