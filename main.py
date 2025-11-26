# -*- coding: utf-8 -*-
import os
import threading
import json
import time
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


class NativeUtils:
    """
    安卓原生功能封装 (修复版)
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NativeUtils, cls).__new__(cls)
            cls._init(cls._instance)
        return cls._instance

    def _init(self):
        self.tts = None
        if platform == 'android':
            try:
                # 尝试初始化 TTS
                from plyer import tts
                self.tts = tts
            except Exception as e:
                print(f"[Native] TTS Init Error: {e}")

    def show_toast(self, text):
        """显示原生 Toast"""
        print(f"[TOAST] {text}")  # Logcat 留底
        if platform == 'android':
            from jnius import autoclass
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Toast = autoclass('android.widget.Toast')
                String = autoclass('java.lang.String')
                # 必须在 UI 线程执行，这里通过 run_on_ui_thread 装饰器或者简单调用
                # 简单调用通常可行
                Toast.makeText(PythonActivity.mActivity, String(text), Toast.LENGTH_SHORT).show()
            except Exception as e:
                print(f"[Native] Toast Error: {e}")

    def speak(self, text):
        """语音播报"""
        print(f"[SPEAK] {text}")
        if self.tts:
            try:
                self.tts.speak(text)
            except Exception as e:
                print(f"[Native] TTS Error: {e}")

    def request_permissions(self):
        """
        关键：动态申请权限
        """
        print("[Native] Requesting Permissions...")
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.RECORD_AUDIO
            ])

    def get_private_dir(self):
        """获取私有目录"""
        if platform == 'android':
            from jnius import autoclass
            try:
                PA = autoclass('org.kivy.android.PythonActivity')
                return PA.mActivity.getExternalFilesDir(None).getAbsolutePath()
            except:
                return "."
        return "."

    def take_photo(self, filepath, callback):
        """调用相机"""
        print(f"[Native] Taking photo to: {filepath}")
        self.cb = callback
        if platform == 'android':
            from plyer import camera
            try:
                camera.take_picture(filename=filepath, on_complete=self._done)
            except Exception as e:
                self.show_toast(f"相机启动失败: {e}")
                print(f"[Native] Camera Error: {e}")
        else:
            self.show_toast("电脑模拟拍照")
            # 模拟文件生成
            with open(filepath, 'w') as f:
                f.write("test")
            self._done(filepath)

    def _done(self, path):
        print(f"[Native] Photo taken: {path}")
        if self.cb:
            # 确保回调在主线程执行（Kivy 并不强制，但为了安全）
            Clock.schedule_once(lambda dt: self.cb(path), 0)


# --- UI 部分 ---

class ResultScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.native = NativeUtils()

        root = BoxLayout(orientation='vertical', padding='15dp', spacing='10dp')
        with root.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(size=(2000, 2000))

        # 标题
        root.add_widget(Label(text="诊断结果", font_size=FONT_L, color=(0, 0, 0, 1), bold=True, size_hint_y=0.1))

        # 滚动内容
        scroll = ScrollView(size_hint_y=0.8)
        self.box = BoxLayout(orientation='vertical', spacing='20dp', size_hint_y=None, padding=[0, 20, 0, 20])
        self.box.bind(minimum_height=self.box.setter('height'))

        self.lbl_content = Label(
            text="正在加载...",
            font_size=FONT_M,
            color=(0, 0, 0, 1),
            markup=True,
            size_hint_y=None,
            halign='left',
            valign='top',
            text_size=(Window.width - 50, None)  # 关键：设置 text_size 才能自动换行
        )
        self.lbl_content.bind(texture_size=self.lbl_content.setter('size'))

        self.box.add_widget(self.lbl_content)
        scroll.add_widget(self.box)
        root.add_widget(scroll)

        # 返回按钮
        btn = Button(text="返回首页", size_hint_y=0.1, background_color=(0.2, 0.2, 0.2, 1), font_size=FONT_L)
        btn.bind(on_release=self.go_back)
        root.add_widget(btn)
        self.add_widget(root)

    def go_back(self, instance):
        self.manager.current = 'home'

    def update(self, data):
        print(f"[UI] Updating result: {data}")
        res = data.get('result', {})

        # 构造富文本
        text = f"[color=#aa0000][b]核心结论：[/b][/color]\n{res.get('core_conclusion', '无')}\n\n"
        text += f"[b]异常分析：[/b]\n{res.get('abnormal_analysis', '无')}\n\n"
        text += f"[color=#006600][b]生活建议：[/b][/color]\n{res.get('life_advice', '无')}"

        self.lbl_content.text = text
        self.lbl_content.text_size = (Window.width - 50, None)  # 重新计算换行宽度

        self.native.speak("解读完成。" + res.get('core_conclusion', ''))


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.native = NativeUtils()
        self.svc = MedicalService()

        # 垂直布局，大间距
        root = BoxLayout(orientation='vertical', padding='20dp', spacing='30dp')
        with root.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(size=(2000, 2000))

        # 1. 标题
        root.add_widget(
            Label(text="智能医疗报告解读", font_size='36sp', color=(0, 0, 0, 1), bold=True, size_hint_y=0.2))

        # 2. 状态栏
        self.status = Label(text="正在初始化...", font_size=FONT_M, color=(0.5, 0.5, 0.5, 1), size_hint_y=0.1)
        root.add_widget(self.status)

        # 3. 按钮区 (使用 BoxLayout 包装以确保居中)
        btn_layout = BoxLayout(orientation='vertical', spacing='20dp', size_hint_y=0.5)

        btn_cam = Button(text="📷 拍照解读", font_size=FONT_L, background_color=(0.2, 0.2, 0.2, 1))
        btn_cam.bind(on_release=self.snap)
        btn_layout.add_widget(btn_cam)

        btn_album = Button(text="🖼️ 相册选择", font_size=FONT_L, background_color=(0.5, 0.5, 0.5, 1))
        btn_album.bind(on_release=lambda x: self.native.show_toast("相册功能开发中"))
        btn_layout.add_widget(btn_album)

        btn_hist = Button(text="🕒 历史记录", font_size=FONT_L, background_color=(0.5, 0.5, 0.5, 1))
        btn_hist.bind(on_release=lambda x: self.native.show_toast("历史记录开发中"))
        btn_layout.add_widget(btn_hist)

        root.add_widget(btn_layout)

        # 4. 底部占位
        root.add_widget(Label(size_hint_y=0.2))

        self.add_widget(root)

        # 延迟启动自检和权限申请
        Clock.schedule_once(self.start_app, 1)

    def start_app(self, dt):
        print("[App] Starting...")
        # 1. 申请权限
        self.native.request_permissions()
        # 2. 检查配置
        self.check_config()

    def check_config(self):
        if self.svc.config_ready:
            self.status.text = "✅ 云端就绪，请点击拍照"
            self.native.speak("欢迎使用，请点击拍照解读")
        else:
            self.status.text = "⚠️ 密钥配置失败"
            self.native.show_toast("配置文件加载失败")

    def snap(self, instance):
        print("[App] Snap button clicked")
        p = os.path.join(self.native.get_private_dir(), 'doc_photo.jpg')
        self.native.take_photo(p, self.process_photo)

    def process_photo(self, path):
        if not os.path.exists(path):
            self.native.show_toast("未检测到照片")
            return

        self.status.text = "🔄 正在上传分析..."
        self.native.speak("正在分析，请稍候")

        # 启动后台线程
        threading.Thread(target=self._run_backend, args=(path,)).start()

    def _run_backend(self, path):
        print(f"[App] Processing: {path}")
        try:
            res = self.svc.process(path)
            print(f"[App] Result: {res}")
            Clock.schedule_once(lambda dt: self._on_success(res), 0)
        except Exception as e:
            print(f"[App] Error: {e}")
            Clock.schedule_once(lambda dt: self._on_error(str(e)), 0)

    def _on_success(self, res):
        if res['code'] == 200:
            self.status.text = "分析完成"
            self.manager.get_screen('result').update(res['data'])
            self.manager.current = 'result'
        else:
            self._on_error(res['message'])

    def _on_error(self, msg):
        self.status.text = "❌ 失败"
        self.native.show_toast(f"出错: {msg}")
        self.native.speak("分析失败，请重试")


class MedicalApp(App):
    def build(self):
        # 强制全屏白底
        Window.clearcolor = (1, 1, 1, 1)

        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(ResultScreen(name='result'))
        return sm


if __name__ == '__main__':
    MedicalApp().run()