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
from service import MedicalService  # 引入刚才创建的 service.py

# 引入中文字体 (必须确保 msyh.ttf 存在)
from kivy.core.text import LabelBase

LabelBase.register(name='Roboto', fn_regular='msyh.ttf')

# 字体常量
FONT_L = '32sp'
FONT_M = '28sp'
FONT_S = '24sp'


class NativeUtils:
    """安卓原生功能封装"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NativeUtils, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.tts = None
        if platform == 'android':
            from jnius import autoclass
            self.PythonActivity = autoclass('org.kivy.android.PythonActivity')
            self.CurrentActivity = self.PythonActivity.mActivity
            self.Context = autoclass('android.content.Context')
            self.Toast = autoclass('android.widget.Toast')
            self.String = autoclass('java.lang.String')

            # 初始化 TTS (使用 plyer，简单稳定)
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
            print(f"[TOAST] {text}")

    def speak(self, text):
        print(f"[SPEAK] {text}")
        if self.tts:
            try:
                self.tts.speak(text)
            except:
                pass

    def get_private_dir(self):
        """获取安卓私有目录 (解决 Android 10+ 权限问题)"""
        if platform == 'android':
            try:
                # 调用 Java: getExternalFilesDir(null)
                return self.CurrentActivity.getExternalFilesDir(None).getAbsolutePath()
            except:
                return "."
        return "."

    def take_photo(self, filepath, callback):
        """调用相机"""
        self.photo_callback = callback
        if platform == 'android':
            from plyer import camera
            try:
                # 关键：plyer.camera 在安卓上需要完整路径
                camera.take_picture(filename=filepath, on_complete=self._on_plyer_complete)
            except Exception as e:
                self.show_toast(f"相机错误: {e}")
        else:
            self.show_toast("电脑端模拟拍照")
            # 模拟创建一张空图片，防止 service 报错
            with open(filepath, 'w') as f:
                f.write("dummy")
            self._on_plyer_complete(filepath)

    def _on_plyer_complete(self, path):
        if self.photo_callback:
            self.photo_callback(path)


class ResultScreen(Screen):
    """结果展示页"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.native = NativeUtils()

        # 白底布局
        root = BoxLayout(orientation='vertical', padding='15dp', spacing='10dp')
        with root.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(size=(2000, 2000))

        # 标题
        root.add_widget(Label(text="会诊结论", font_size=FONT_L, color=(0, 0, 0, 1), bold=True, size_hint_y=0.1))

        # 滚动区域
        scroll = ScrollView(size_hint_y=0.8)
        self.box_content = BoxLayout(orientation='vertical', spacing='20dp', size_hint_y=None)
        self.box_content.bind(minimum_height=self.box_content.setter('height'))

        # 1. 核心结论 (红字)
        self.lbl_core = Label(text="", font_size=FONT_L, color=(0.8, 0, 0, 1), markup=True, size_hint_y=None,
                              halign='left', valign='top')
        self.lbl_core.bind(texture_size=self.lbl_core.setter('size'))
        self.box_content.add_widget(self.lbl_core)

        # 2. 异常分析 (黑字)
        self.lbl_abnormal = Label(text="", font_size=FONT_M, color=(0, 0, 0, 1), markup=True, size_hint_y=None,
                                  halign='left')
        self.lbl_abnormal.bind(texture_size=self.lbl_abnormal.setter('size'))
        self.box_content.add_widget(self.lbl_abnormal)

        # 3. 生活建议 (黑字)
        self.lbl_advice = Label(text="", font_size=FONT_M, color=(0, 0.5, 0, 1), markup=True, size_hint_y=None,
                                halign='left')
        self.lbl_advice.bind(texture_size=self.lbl_advice.setter('size'))
        self.box_content.add_widget(self.lbl_advice)

        scroll.add_widget(self.box_content)
        root.add_widget(scroll)

        # 返回按钮
        btn_back = Button(text="返回首页", size_hint_y=0.1, background_color=(0.2, 0.2, 0.2, 1), font_size=FONT_M)
        btn_back.bind(on_release=self.go_back)
        root.add_widget(btn_back)

        self.add_widget(root)

    def update_report(self, data):
        """渲染报告"""
        res = data.get('result', {})

        core = res.get('core_conclusion', '暂无结论')
        abn = res.get('abnormal_analysis', '无')
        adv = res.get('life_advice', '无')

        self.lbl_core.text = f"[b]核心结论：[/b]\n{core}"
        self.lbl_abnormal.text = f"[b]异常分析：[/b]\n{abn}"
        self.lbl_advice.text = f"[b]生活建议：[/b]\n{adv}"

        # 强制刷新布局
        self.lbl_core.texture_update()

        # 语音播报核心结论
        self.native.speak(f"解读完成。{core}")

    def go_back(self, instance):
        self.manager.current = 'home'


class HomeScreen(Screen):
    """首页"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.native = NativeUtils()
        self.service = MedicalService()

        # 布局
        root = BoxLayout(orientation='vertical', padding='20dp', spacing='30dp')
        with root.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(size=(2000, 2000))

        # 标题
        root.add_widget(
            Label(text="智能医疗报告解读", font_size=FONT_L, color=(0, 0, 0, 1), bold=True, size_hint_y=0.2))

        # 状态显示
        self.lbl_status = Label(text="点击下方按钮拍照", font_size=FONT_M, color=(0.5, 0.5, 0.5, 1), size_hint_y=0.1)
        root.add_widget(self.lbl_status)

        # 拍照按钮
        btn_cam = Button(text="📷 拍照解读", font_size=FONT_L, background_color=(0.2, 0.2, 0.2, 1), size_hint_y=0.2)
        btn_cam.bind(on_release=self.action_camera)
        root.add_widget(btn_cam)

        # 占位
        root.add_widget(Label(size_hint_y=0.5))
        self.add_widget(root)

        # 启动自检
        Clock.schedule_once(self.check_config, 1)

    def check_config(self, dt):
        if self.service.config_ready:
            self.lbl_status.text = "✅ 云端已连接，请拍照"
            self.native.speak("欢迎使用，请点击拍照按钮")
        else:
            self.lbl_status.text = "⚠️ 密钥配置失败"

    def action_camera(self, instance):
        self.native.speak("请拍摄清晰的报告")
        # 获取安全的私有路径
        private_dir = self.native.get_private_dir()
        file_path = os.path.join(private_dir, "temp_report.jpg")

        self.native.take_photo(file_path, self.on_photo_taken)

    def on_photo_taken(self, path):
        if not os.path.exists(path):
            self.lbl_status.text = "❌ 拍照取消或失败"
            return

        self.lbl_status.text = "🔄 正在上传并分析..."
        self.native.speak("正在分析，请稍候")

        # 启动线程处理
        threading.Thread(target=self.do_process, args=(path,)).start()

    def do_process(self, path):
        # 后台调用 Service
        result = self.service.process(path)
        # 回到主线程更新 UI
        Clock.schedule_once(lambda dt: self.on_success(result), 0)

    def on_success(self, result):
        if result['code'] == 200:
            self.lbl_status.text = "解读成功"
            # 跳转
            screen = self.manager.get_screen('result')
            screen.update_report(result['data'])
            self.manager.current = 'result'
        else:
            self.lbl_status.text = f"出错：{result['message']}"
            self.native.speak("解读失败，请重试")


class MedicalApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(ResultScreen(name='result'))
        return sm


if __name__ == '__main__':
    MedicalApp().run()