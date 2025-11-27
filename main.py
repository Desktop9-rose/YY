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
from kivy.core.window import Window
from kivy.clock import Clock, mainthread
from kivy.properties import StringProperty, NumericProperty, ListProperty
from kivy.uix.button import Button
from kivy.animation import Animation
from kivy.core.text import LabelBase

# 引入后端逻辑
from backend import NativeUtils, CloudService

# 注册中文字体 (必须在 KV 加载前)
# 假设 msyh.ttf 在 main.py 同级目录
font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'msyh.ttf')
LabelBase.register(name='Roboto', fn_regular=font_path)  # 替换默认字体防止方块

# Load UI
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
            font_size: '20sp'
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
            text: '医疗报告助手'
            font_size: '32sp'
            color: hex('#212121')
            bold: True
            size_hint_y: 0.3

        CommonButton:
            text: '拍照解读'
            # icon_source: 'assets/camera.png' 
            bg_color: hex('#2E7D32')
            on_release: app.on_camera_click()

        CommonButton:
            text: '相册选择'
            # icon_source: 'assets/gallery.png'
            bg_color: hex('#1565C0')
            on_release: app.pick_image()

        CommonButton:
            text: '历史记录'
            # icon_source: 'assets/history.png'
            bg_color: hex('#424242')
            on_release: app.root.current = 'history'

        BoxLayout:
            size_hint_y: 0.15
            Button:
                text: '设置 API 密钥'
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
                rgba: (0,0,0,0.8)
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            text: "正在智能分析中..."
            font_size: '24sp'
        Label:
            id: loading_detail
            text: "上传图片 -> OCR识别 -> AI推理"
            font_size: '16sp'
            color: (0.8, 0.8, 0.8, 1)

<ResultScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: '10dp'
        canvas.before:
            Color:
                rgba: hex('#FFFFFF')
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            id: res_title
            text: "报告标题"
            size_hint_y: 0.1
            color: hex('#000000')
            font_size: '24sp'
            bold: True

        ScrollView:
            BoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                padding: '10dp'
                spacing: '20dp'

                Label:
                    text: "[b]核心结论[/b]"
                    markup: True
                    color: hex('#D32F2F')
                    size_hint_y: None
                    height: '30dp'
                    text_size: self.width, None
                    halign: 'left'
                Label:
                    id: res_core
                    text: "..."
                    color: hex('#212121')
                    size_hint_y: None
                    height: self.texture_size[1]
                    text_size: self.width, None
                    halign: 'left'

                Label:
                    text: "[b]异常指标分析[/b]"
                    markup: True
                    color: hex('#F57C00')
                    size_hint_y: None
                    height: '30dp'
                    text_size: self.width, None
                    halign: 'left'
                Label:
                    id: res_abnormal
                    text: "..."
                    color: hex('#212121')
                    size_hint_y: None
                    height: self.texture_size[1]
                    text_size: self.width, None
                    halign: 'left'

                Label:
                    text: "[b]生活建议[/b]"
                    markup: True
                    color: hex('#388E3C')
                    size_hint_y: None
                    height: '30dp'
                    text_size: self.width, None
                    halign: 'left'
                Label:
                    id: res_advice
                    text: "..."
                    color: hex('#212121')
                    size_hint_y: None
                    height: self.texture_size[1]
                    text_size: self.width, None
                    halign: 'left'

        Button:
            text: "返回首页"
            size_hint_y: 0.1
            background_color: hex('#757575')
            on_release: app.root.current = 'home'

<SettingsScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: '20dp'
        spacing: '10dp'
        canvas.before:
            Color:
                rgba: hex('#FFFFFF')
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: "配置密钥"
            color: hex('#000000')
            font_size: '24sp'
            size_hint_y: 0.1

        TextInput:
            id: input_ali_ak
            hint_text: '阿里云 AccessKey ID'
            multiline: False
            size_hint_y: None
            height: '50dp'
        TextInput:
            id: input_ali_sk
            hint_text: '阿里云 AccessKey Secret'
            multiline: False
            password: True
            size_hint_y: None
            height: '50dp'
        TextInput:
            id: input_deepseek
            hint_text: 'DeepSeek API Key'
            multiline: False
            password: True
            size_hint_y: None
            height: '50dp'

        Button:
            text: "保存并返回"
            size_hint_y: None
            height: '60dp'
            on_release: root.save()

        Widget: 
            size_hint_y: 0.5

<HistoryScreen>:
    BoxLayout:
        orientation: 'vertical'
        Label:
            text: "暂未实现历史记录详情查看"
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
        if value == 'down':
            anim = Animation(opacity_val=0.8, duration=0.1)
        else:
            anim = Animation(opacity_val=1, duration=0.1)
        anim.start(self)


class HomeScreen(Screen):
    pass


class LoadingScreen(Screen):
    pass


class ResultScreen(Screen):
    def update_view(self, data):
        self.ids.res_title.text = data.get('title', '无标题')
        self.ids.res_core.text = data.get('core_conclusion', '无')
        self.ids.res_abnormal.text = data.get('abnormal_analysis', '无')
        self.ids.res_advice.text = str(data.get('life_advice', '无'))


class SettingsScreen(Screen):
    def on_enter(self):
        # 回显配置
        app = App.get_running_app()
        self.ids.input_ali_ak.text = app.config_data.get('ali_ak', '')
        self.ids.input_ali_sk.text = app.config_data.get('ali_sk', '')
        self.ids.input_deepseek.text = app.config_data.get('deepseek_key', '')

    def save(self):
        app = App.get_running_app()
        app.save_config(
            self.ids.input_ali_ak.text,
            self.ids.input_ali_sk.text,
            self.ids.input_deepseek.text
        )
        app.root.current = 'home'


class HistoryScreen(Screen):
    pass


class MedicalApp(App):
    def build(self):
        self.native = NativeUtils()
        self.db_path = os.path.join(self.native.get_cache_dir(), 'history.db')
        self._init_db()
        self.load_config()

        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(LoadingScreen(name='loading'))
        sm.add_widget(ResultScreen(name='result'))
        sm.add_widget(SettingsScreen(name='settings'))
        sm.add_widget(HistoryScreen(name='history'))

        # 请求权限 (仅安卓)
        self.request_android_permissions()

        return sm

    def request_android_permissions(self):
        from kivy.utils import platform
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.INTERNET
            ])

    def _init_db(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, json_data TEXT)")
        self.conn.commit()

    def load_config(self):
        # 简单使用 ini 存储
        self.config_file = os.path.join(self.native.get_cache_dir(), 'app_config.ini')
        self.conf = configparser.ConfigParser()
        self.conf.read(self.config_file)
        if not self.conf.has_section('keys'):
            self.conf.add_section('keys')

        self.config_data = {
            'ali_ak': self.conf.get('keys', 'ali_ak', fallback=''),
            'ali_sk': self.conf.get('keys', 'ali_sk', fallback=''),
            'deepseek_key': self.conf.get('keys', 'deepseek_key', fallback=''),
            'tongyi_key': ''
        }

    def save_config(self, ak, sk, ds):
        self.conf.set('keys', 'ali_ak', ak)
        self.conf.set('keys', 'ali_sk', sk)
        self.conf.set('keys', 'deepseek_key', ds)
        with open(self.config_file, 'w') as f:
            self.conf.write(f)
        self.load_config()
        self.native.toast("配置已保存")

    # --- 业务逻辑 ---

    def on_camera_click(self):
        self.native.open_camera(self.on_image_selected)

    def pick_image(self):
        self.native.open_gallery(self.on_image_selected)

    def on_image_selected(self, file_path):
        if not file_path:
            return
        # 切换到加载页
        self.root.current = 'loading'
        # 启动线程分析
        threading.Thread(target=self.run_analysis, args=(file_path,)).start()

    def run_analysis(self, path):
        # 1. 初始化云服务
        svc = CloudService(self.config_data)

        # 2. 执行流水线
        result = svc.run_pipeline(path)

        # 3. 完成后回调 UI
        self.on_analysis_complete(result)

    @mainthread
    def on_analysis_complete(self, result):
        """必须在主线程更新 UI"""
        # 保存历史
        try:
            self.conn.execute("INSERT INTO history (json_data) VALUES (?)", (json.dumps(result),))
            self.conn.commit()
        except Exception as e:
            print(f"DB Save Error: {e}")

        # 更新结果页
        res_screen = self.root.get_screen('result')
        res_screen.update_view(result)

        # 跳转
        self.root.current = 'result'


if __name__ == '__main__':
    MedicalApp().run()