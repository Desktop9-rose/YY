# -*- coding: utf-8 -*-
import os
import threading
import sqlite3
import json
import configparser
from datetime import datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.lang import Builder
from kivy.clock import Clock, mainthread
from kivy.properties import StringProperty, NumericProperty, ListProperty
from kivy.uix.button import Button
from kivy.animation import Animation
from kivy.core.text import LabelBase

# 引入后端
from backend import AndroidHelper, APIService

# 字体注册 (防止中文乱码)
# 确保 msyh.ttf 在 main.py 同级目录
font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'msyh.ttf')
LabelBase.register(name='Roboto', fn_regular=font_path)

Builder.load_string('''
#:import hex kivy.utils.get_color_from_hex

<CommonButton>:
    background_normal: ''
    background_color: (0,0,0,0)
    canvas.before:
        Color:
            rgba: self.bg_color if self.state == 'normal' else [x*0.8 for x in self.bg_color]
            a: self.opacity_val
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [20,]
    BoxLayout:
        pos: root.pos
        size: root.size
        orientation: 'horizontal'
        padding: 20
        spacing: 20
        Image:
            source: root.icon_source
            size_hint: None, None
            size: '40dp', '40dp'
            pos_hint: {'center_y': 0.5}
        Label:
            text: root.text
            font_size: '22sp'
            bold: True
            color: (1,1,1,1)
            text_size: self.size
            halign: 'left'
            valign: 'middle'

<HomeScreen>:
    canvas.before:
        Color:
            rgba: hex('#F5F5F5')
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        padding: '30dp'
        spacing: '20dp'

        Label:
            text: '智能医疗报告助手'
            font_size: '36sp'
            color: hex('#212121')
            bold: True
            size_hint_y: 0.3

        CommonButton:
            text: '拍照解读'
            # icon_source: 'assets/camera.png' # 如果没有图片，暂时注释
            bg_color: hex('#2E7D32')
            on_release: app.on_camera_click()

        CommonButton:
            text: '相册选择'
            # icon_source: 'assets/gallery.png'
            bg_color: hex('#1565C0')
            on_release: app.pick_image()

        CommonButton:
            text: '历史记录'
            bg_color: hex('#424242')
            on_release: app.root.current = 'history'

        BoxLayout:
            size_hint_y: 0.15
            Button:
                text: '设置 / 密钥状态'
                font_size: '18sp'
                color: hex('#757575')
                background_normal: ''
                background_color: (0,0,0,0)
                on_release: app.root.current = 'settings'

<LoadingScreen>:
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: (0,0,0,0.85)
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            text: "正在分析中..."
            font_size: '28sp'
            color: (1,1,1,1)
        Label:
            text: "上传图片 -> 视觉识别 -> AI 诊断"
            font_size: '16sp'
            color: (0.8, 0.8, 0.8, 1)

<ResultScreen>:
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: hex('#FFFFFF')
            Rectangle:
                pos: self.pos
                size: self.size

        # 标题栏
        BoxLayout:
            size_hint_y: 0.1
            padding: '10dp'
            Label:
                id: res_title
                text: "报告结果"
                color: hex('#000000')
                font_size: '24sp'
                bold: True

        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: '20dp'
                spacing: '15dp'

                Label:
                    text: "核心结论"
                    color: hex('#D32F2F')
                    font_size: '20sp'
                    bold: True
                    size_hint_y: None
                    height: '30dp'
                    text_size: self.width, None
                    halign: 'left'
                Label:
                    id: res_core
                    text: "加载中..."
                    color: hex('#212121')
                    size_hint_y: None
                    height: self.texture_size[1] + 20
                    text_size: self.width, None
                    halign: 'left'

                Label:
                    text: "异常分析"
                    color: hex('#F57C00')
                    font_size: '20sp'
                    bold: True
                    size_hint_y: None
                    height: '30dp'
                    text_size: self.width, None
                    halign: 'left'
                Label:
                    id: res_abnormal
                    text: "..."
                    color: hex('#212121')
                    size_hint_y: None
                    height: self.texture_size[1] + 20
                    text_size: self.width, None
                    halign: 'left'

                Label:
                    text: "生活建议"
                    color: hex('#388E3C')
                    font_size: '20sp'
                    bold: True
                    size_hint_y: None
                    height: '30dp'
                    text_size: self.width, None
                    halign: 'left'
                Label:
                    id: res_advice
                    text: "..."
                    color: hex('#212121')
                    size_hint_y: None
                    height: self.texture_size[1] + 20
                    text_size: self.width, None
                    halign: 'left'

        BoxLayout:
            size_hint_y: 0.1
            padding: '10dp'
            spacing: '10dp'
            Button:
                text: "播报结果"
                background_color: hex('#1976D2')
                on_release: app.speak_result()
            Button:
                text: "返回首页"
                background_color: hex('#757575')
                on_release: app.root.current = 'home'

<SettingsScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: '20dp'
        spacing: '15dp'
        canvas.before:
            Color:
                rgba: hex('#FFFFFF')
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: "API 密钥配置"
            color: hex('#000000')
            font_size: '24sp'
            size_hint_y: None
            height: '50dp'

        Label:
            text: "注意：若已在 GitHub Secrets 配置，此处可留空。手动输入将覆盖默认配置。"
            color: hex('#D32F2F')
            font_size: '14sp'
            text_size: self.width, None
            size_hint_y: None
            height: '40dp'

        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                spacing: '10dp'

                TextInput:
                    id: input_tongyi
                    hint_text: '通义千问 Key (推荐)'
                    multiline: False
                    size_hint_y: None
                    height: '50dp'

                TextInput:
                    id: input_deepseek
                    hint_text: 'DeepSeek Key (可选)'
                    multiline: False
                    size_hint_y: None
                    height: '50dp'

                TextInput:
                    id: input_ali_ak
                    hint_text: '阿里云 AccessKey (备用OCR)'
                    multiline: False
                    size_hint_y: None
                    height: '50dp'
                TextInput:
                    id: input_ali_sk
                    hint_text: '阿里云 SecretKey (备用OCR)'
                    multiline: False
                    password: True
                    size_hint_y: None
                    height: '50dp'

        Button:
            text: "保存配置"
            size_hint_y: None
            height: '60dp'
            background_color: hex('#2E7D32')
            on_release: root.save()

        Button:
            text: "返回"
            size_hint_y: None
            height: '60dp'
            background_color: hex('#757575')
            on_release: app.root.current = 'home'

<HistoryScreen>:
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: hex('#F5F5F5')
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            text: "历史记录功能开发中..."
            color: (0,0,0,1)
        Button:
            text: "返回"
            size_hint_y: 0.1
            on_release: app.root.current = 'home'
''')


class CommonButton(Button):
    bg_color = ListProperty([0, 0, 0, 1])
    icon_source = StringProperty('')
    opacity_val = NumericProperty(1)

    def on_state(self, instance, value):
        Animation(opacity_val=0.8 if value == 'down' else 1, duration=0.1).start(self)


class HomeScreen(Screen): pass


class LoadingScreen(Screen): pass


class HistoryScreen(Screen): pass


class ResultScreen(Screen):
    def update_view(self, data):
        self.ids.res_title.text = data.get('title', '未命名报告')
        self.ids.res_core.text = data.get('core_conclusion', '解析失败')
        self.ids.res_abnormal.text = data.get('abnormal_analysis', '无')
        self.ids.res_advice.text = str(data.get('life_advice', '无'))


class SettingsScreen(Screen):
    def on_enter(self):
        app = App.get_running_app()
        self.ids.input_tongyi.text = app.config_data.get('tongyi_key', '')
        self.ids.input_deepseek.text = app.config_data.get('deepseek_key', '')
        self.ids.input_ali_ak.text = app.config_data.get('ali_ak', '')
        self.ids.input_ali_sk.text = app.config_data.get('ali_sk', '')

    def save(self):
        app = App.get_running_app()
        app.save_config(
            self.ids.input_tongyi.text,
            self.ids.input_deepseek.text,
            self.ids.input_ali_ak.text,
            self.ids.input_ali_sk.text
        )
        app.root.current = 'home'


class MedicalApp(App):
    def build(self):
        self.native = AndroidHelper()
        self.api = APIService()
        self.db_path = os.path.join(self.native.get_cache_dir(), 'history.db')

        # 加载配置
        self.load_local_config()

        # 初始化 UI
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(LoadingScreen(name='loading'))
        sm.add_widget(ResultScreen(name='result'))
        sm.add_widget(SettingsScreen(name='settings'))
        sm.add_widget(HistoryScreen(name='history'))

        # 请求权限 (仅第一次有效)
        self.request_permissions()

        return sm

    def request_permissions(self):
        from kivy.utils import platform
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.INTERNET
            ])

    def load_local_config(self):
        self.config_file = os.path.join(self.native.get_cache_dir(), 'app_config.ini')
        self.conf = configparser.ConfigParser()
        self.conf.read(self.config_file)

        if not self.conf.has_section('keys'):
            self.conf.add_section('keys')

        self.config_data = {
            'tongyi_key': self.conf.get('keys', 'tongyi_key', fallback=''),
            'deepseek_key': self.conf.get('keys', 'deepseek_key', fallback=''),
            'ali_ak': self.conf.get('keys', 'ali_ak', fallback=''),
            'ali_sk': self.conf.get('keys', 'ali_sk', fallback='')
        }

        # 更新 API Service (优先使用 GitHub Secrets，其次使用 Config.ini)
        self.api.update_keys(
            self.config_data['ali_ak'],
            self.config_data['ali_sk'],
            self.config_data['deepseek_key'],
            self.config_data['tongyi_key']
        )

    def save_config(self, ty, ds, ak, sk):
        self.conf.set('keys', 'tongyi_key', ty)
        self.conf.set('keys', 'deepseek_key', ds)
        self.conf.set('keys', 'ali_ak', ak)
        self.conf.set('keys', 'ali_sk', sk)
        with open(self.config_file, 'w') as f:
            self.conf.write(f)
        self.load_local_config()
        self.native.toast("配置已保存")

    # --- 业务逻辑 ---

    def on_camera_click(self):
        self.native.speak("请拍摄报告")
        self.native.open_camera(self.on_image_selected)

    def pick_image(self):
        self.native.speak("请选择图片")
        self.native.open_gallery(self.on_image_selected)

    def on_image_selected(self, file_path):
        if not file_path: return
        self.root.current = 'loading'
        # 开启新线程处理，防止 UI 卡死白屏
        threading.Thread(target=self.run_analysis, args=(file_path,)).start()

    def run_analysis(self, path):
        try:
            result = self.api.analyze_image(path)
            self.on_analysis_complete(result)
        except Exception as e:
            print(f"Analysis Error: {e}")
            self.on_analysis_complete({
                "title": "错误",
                "core_conclusion": "发生未知错误",
                "abnormal_analysis": str(e)
            })

    @mainthread
    def on_analysis_complete(self, result):
        """强制回到主线程更新 UI"""
        self.current_result_text = result.get('core_conclusion', '')
        res_screen = self.root.get_screen('result')
        res_screen.update_view(result)
        self.root.current = 'result'
        self.native.speak("解读完成")

    def speak_result(self):
        if hasattr(self, 'current_result_text'):
            self.native.speak(self.current_result_text)


if __name__ == '__main__':
    MedicalApp().run()