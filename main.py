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

# 引入中文字体
from kivy.core.text import LabelBase

LabelBase.register(name='Roboto', fn_regular='msyh.ttf')

# 字体配置
FONT_L = '32sp'
FONT_M = '28sp'

# 引入安卓线程装饰器
if platform == 'android':
    from android.runnable import run_on_ui_thread
else:
    # 电脑端模拟装饰器
    def run_on_ui_thread(func):
        return func


class NativeUtils:
    """
    安卓原生功能封装 (最终修复版)
    """
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
                # --- 关键修复 1: 禁用 Android 7.0+ 的文件 URI 严格检查 ---
                # 这允许我们将 file:// 路径直接传给相机，彻底解决 FileUriExposedException
                from jnius import autoclass
                StrictMode = autoclass('android.os.StrictMode')
                VmPolicy = autoclass('android.os.StrictMode$VmPolicy')
                Builder = autoclass('android.os.StrictMode$VmPolicy$Builder')
                # 构建一个新的宽松策略
                new_policy = Builder().build()
                StrictMode.setVmPolicy(new_policy)
                print("[Native] StrictMode check disabled successfully.")
            except Exception as e:
                print(f"[Native] StrictMode disable failed: {e}")

            # 初始化 TTS
            try:
                from plyer import tts
                self.tts = tts
            except:
                pass

    @run_on_ui_thread
    def show_toast(self, text):
        """
        关键修复 2: 强制在 UI 线程显示 Toast
        """
        if platform == 'android':
            from jnius import autoclass
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Toast = autoclass('android.widget.Toast')
                String = autoclass('java.lang.String')
                Toast.makeText(PythonActivity.mActivity, String(str(text)), Toast.LENGTH_SHORT).show()
            except Exception as e:
                print(f"[Native] Toast Error: {e}")
        else:
            print(f"[TOAST] {text}")

    def speak(self, text):
        print(f"[SPEAK] {text}")
        if self.tts:
            try:
                self.tts.speak(str(text))
            except:
                pass

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
            from jnius import autoclass
            try:
                PA = autoclass('org.kivy.android.PythonActivity')
                return PA.mActivity.getExternalFilesDir(None).getAbsolutePath()
            except:
                return "."
        return "."

    def take_photo(self, filepath, callback):
        """调用相机"""
        self.cb = callback
        if platform == 'android':
            from plyer import camera
            try:
                # 因为我们禁用了 StrictMode，这里可以直接传文件路径
                camera.take_picture(filename=filepath, on_complete=self._done)
            except Exception as e:
                self.show_toast(f"相机无法启动: {e}")
                print(f"[Native] Camera Error: {e}")
        else:
            self.show_toast("电脑模拟拍照")
            with open(filepath, 'w') as f:
                f.write("test_dummy_image")
            self._done(filepath)

    def _done(self, path):
        print(f"[Native] Photo callback: {path}")
        if self.cb:
            # 回到 Kivy 主线程执行回调
            Clock.schedule_once(lambda dt: self.cb(path), 0)


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
            text="加载中...",
            font_size=FONT_M,
            color=(0, 0, 0, 1),
            markup=True,
            size_hint_y=None,
            halign='left',
            valign='top',
            text_size=(Window.width - 50, None)  # 自动换行
        )
        self.lbl_content.bind(texture_size=self.lbl_content.setter('size'))

        self.box.add_widget(self.lbl_content)
        scroll.add_widget(self.box)
        root.add_widget(scroll)

        btn = Button(text="返回首页", size_hint_y=0.1, background_color=(0.2, 0.2, 0.2, 1), font_size=FONT_L)
        btn.bind(on_release=self.go_back)
        root.add_widget(btn)
        self.add_widget(root)

    def go_back(self, instance):
        self.manager.current = 'home'

    def update(self, data):
        res = data.get('result', {})

        core = res.get('core_conclusion', '无')
        abn = res.get('abnormal_analysis', '无')
        life = res.get('life_advice', '无')

        text = f"[color=#aa0000][b]核心结论：[/b][/color]\n{core}\n\n"
        text += f"[b]异常分析：[/b]\n{abn}\n\n"
        text += f"[color=#006600][b]生活建议：[/b][/color]\n{life}"

        self.lbl_content.text = text
        # 重新计算布局
        self.lbl_content.text_size = (Window.width - 50, None)
        self.lbl_content.texture_update()

        self.native.speak("解读完成。" + core)


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.native = NativeUtils()
        self.svc = MedicalService()

        root = BoxLayout(orientation='vertical', padding='20dp', spacing='30dp')
        with root.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(size=(2000, 2000))

        # 1. 标题
        root.add_widget(
            Label(text="智能医疗报告解读", font_size='36sp', color=(0, 0, 0, 1), bold=True, size_hint_y=0.2))

        # 2. 状态显示
        self.status = Label(text="正在初始化...", font_size=FONT_M, color=(0.5, 0.5, 0.5, 1), size_hint_y=0.1)
        root.add_widget(self.status)

        # 3. 按钮区域
        btn_layout = BoxLayout(orientation='vertical', spacing='20dp', size_hint_y=0.5)

        btn_cam = Button(text="📷 拍照解读", font_size=FONT_L, background_color=(0.2, 0.2, 0.2, 1))
        btn_cam.bind(on_release=self.action_camera)
        btn_layout.add_widget(btn_cam)

        btn_album = Button(text="🖼️ 相册选择", font_size=FONT_L, background_color=(0.5, 0.5, 0.5, 1))
        btn_album.bind(on_release=lambda x: self.native.show_toast("功能开发中"))
        btn_layout.add_widget(btn_album)

        btn_hist = Button(text="🕒 历史记录", font_size=FONT_L, background_color=(0.5, 0.5, 0.5, 1))
        btn_hist.bind(on_release=lambda x: self.native.show_toast("功能开发中"))
        btn_layout.add_widget(btn_hist)

        root.add_widget(btn_layout)
        root.add_widget(Label(size_hint_y=0.2))

        self.add_widget(root)

        Clock.schedule_once(self.start_check, 1)

    def start_check(self, dt):
        self.native.request_permissions()
        if self.svc.config_ready:
            self.status.text = "✅ 云端就绪，请点击拍照"
            self.native.speak("系统就绪，请点击拍照解读")
        else:
            self.status.text = "⚠️ 密钥加载失败"

    def action_camera(self, instance):
        self.native.speak("请拍摄报告")
        # 使用私有目录，安卓 10+ 必须
        p = os.path.join(self.native.get_private_dir(), 'doc_photo.jpg')
        self.native.take_photo(p, self.process)

    def process(self, path):
        # 检查文件是否存在（防止用户打开相机后直接取消）
        if not os.path.exists(path):
            self.native.show_toast("未拍摄照片")
            return

        self.status.text = "🔄 正在上传分析..."
        self.native.speak("正在分析，请稍候")

        # 启动后台线程
        threading.Thread(target=self._run_bg, args=(path,)).start()

    def _run_bg(self, path):
        try:
            res = self.svc.process(path)
            Clock.schedule_once(lambda dt: self._success(res), 0)
        except Exception as e:
            Clock.schedule_once(lambda dt: self._error(str(e)), 0)

    def _success(self, res):
        if res['code'] == 200:
            self.status.text = "分析完成"
            self.manager.get_screen('result').update(res['data'])
            self.manager.current = 'result'
        else:
            self._error(res['message'])

    def _error(self, msg):
        self.status.text = "❌ 失败"
        self.native.show_toast(f"错误: {msg}")
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