# -*- coding: utf-8 -*-
import os
import threading
import json
import configparser
import shutil
from kivy.lang import Builder
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.core.text import LabelBase

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.dialog import MDDialog
from kivymd.toast import toast

# 引入后端逻辑
from backend import BackendService

# 注册中文字体
font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'msyh.ttf')
if os.path.exists(font_path):
    LabelBase.register(name='Roboto', fn_regular=font_path)

KV = '''
#:import hex kivy.utils.get_color_from_hex

<HomeCard@MDCard>:
    orientation: "horizontal"
    size_hint: 0.9, None
    height: "100dp"
    padding: "20dp"
    spacing: "20dp"
    radius: [15]
    ripple_behavior: True
    elevation: 2
    md_bg_color: hex('#FFFFFF')

    MDIcon:
        icon: root.icon
        theme_text_color: "Custom"
        text_color: root.icon_color
        font_size: "48sp"
        pos_hint: {"center_y": .5}

    MDLabel:
        text: root.text
        font_style: "H5"
        bold: True
        theme_text_color: "Custom"
        text_color: hex('#333333')
        pos_hint: {"center_y": .5}

<HomeScreen>:
    MDBoxLayout:
        orientation: 'vertical'
        md_bg_color: hex('#F5F5F5')

        MDTopAppBar:
            title: "医疗报告助手"
            specific_text_color: 1, 1, 1, 1
            elevation: 0
            right_action_items: [["cog", lambda x: app.open_settings()]]

        MDBoxLayout:
            orientation: 'vertical'
            padding: "20dp"
            spacing: "25dp"
            adaptive_height: True
            pos_hint: {"top": 1}

            MDLabel:
                text: "请选择操作"
                font_style: "Subtitle1"
                theme_text_color: "Hint"
                size_hint_y: None
                height: self.texture_size[1]

            HomeCard:
                icon: "camera"
                text: "拍照解读"
                icon_color: hex('#2E7D32')
                on_release: app.action_camera()

            HomeCard:
                icon: "image"
                text: "相册选择"
                icon_color: hex('#1565C0')
                on_release: app.action_gallery()

            HomeCard:
                icon: "history"
                text: "历史记录"
                icon_color: hex('#424242')
                on_release: app.switch_to('history')

        Widget:

<ResultScreen>:
    MDBoxLayout:
        orientation: 'vertical'
        md_bg_color: hex('#FFFFFF')

        MDTopAppBar:
            title: "分析结果"
            left_action_items: [["arrow-left", lambda x: app.switch_to('home')]]
            right_action_items: [["volume-high", lambda x: app.speak_result()]]

        ScrollView:
            MDBoxLayout:
                orientation: 'vertical'
                padding: "20dp"
                spacing: "15dp"
                adaptive_height: True

                MDLabel:
                    id: res_title
                    text: "加载中..."
                    font_style: "H5"
                    bold: True
                    adaptive_height: True

                MDSeparator:

                MDLabel:
                    text: "核心结论"
                    color: hex('#D32F2F')
                    font_style: "Subtitle1"
                    bold: True
                    adaptive_height: True
                MDLabel:
                    id: res_core
                    text: "..."
                    font_style: "Body1"
                    adaptive_height: True

                MDLabel:
                    text: "异常分析"
                    color: hex('#F57C00')
                    font_style: "Subtitle1"
                    bold: True
                    adaptive_height: True
                MDLabel:
                    id: res_abnormal
                    text: "..."
                    font_style: "Body1"
                    adaptive_height: True

                MDLabel:
                    text: "生活建议"
                    color: hex('#388E3C')
                    font_style: "Subtitle1"
                    bold: True
                    adaptive_height: True
                MDLabel:
                    id: res_advice
                    text: "..."
                    font_style: "Body1"
                    adaptive_height: True

<HistoryScreen>:
    MDBoxLayout:
        orientation: 'vertical'

        MDTopAppBar:
            title: "历史记录"
            left_action_items: [["arrow-left", lambda x: app.switch_to('home')]]

        MDRecycleView:
            id: history_list
            viewclass: 'TwoLineAvatarIconListItem'
            MDRecycleBoxLayout:
                default_size: None, dp(72)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'

<SettingsScreen>:
    MDBoxLayout:
        orientation: 'vertical'
        padding: "20dp"
        spacing: "10dp"

        MDLabel:
            text: "API 密钥配置"
            font_style: "H5"
            size_hint_y: None
            height: "50dp"

        MDTextField:
            id: key_tongyi
            hint_text: "通义千问 Key"
            mode: "rectangle"

        MDTextField:
            id: key_deepseek
            hint_text: "DeepSeek Key"
            mode: "rectangle"

        MDTextField:
            id: key_ak
            hint_text: "阿里云 AccessKey"
            mode: "rectangle"

        MDTextField:
            id: key_sk
            hint_text: "阿里云 SecretKey"
            mode: "rectangle"
            password: True

        MDRaisedButton:
            text: "保存配置"
            size_hint_x: 1
            on_release: app.save_config()

        MDFlatButton:
            text: "取消"
            size_hint_x: 1
            on_release: app.switch_to('home')

        Widget:
'''


class HomeScreen(MDScreen): pass


class ResultScreen(MDScreen): pass


class HistoryScreen(MDScreen): pass


class SettingsScreen(MDScreen): pass


class MedicalApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Green"
        self.backend = BackendService()

        # 加载 UI
        self.sm = Builder.load_string(KV)

        self.screen_manager = ScreenManager()
        self.screen_manager.add_widget(HomeScreen(name='home'))
        self.screen_manager.add_widget(ResultScreen(name='result'))
        self.screen_manager.add_widget(HistoryScreen(name='history'))
        self.screen_manager.add_widget(SettingsScreen(name='settings'))

        # 启动逻辑
        self.load_user_config()  # 修复：重命名方法，避免冲突
        self.request_perms()

        return self.screen_manager

    def request_perms(self):
        from kivy.utils import platform
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.CAMERA, Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE,
                                 Permission.INTERNET])

    def load_user_config(self):
        """
        加载配置逻辑：
        1. 确定应用内部可写目录 (internal storage)。
        2. 检查是否有打包自带的 app_config.ini (来自 GitHub Secrets)。
        3. 如果内部存储没有配置文件，从打包资源中复制一份过去。
        """
        # 目标路径：App 私有数据目录（可读写）
        writable_dir = self.user_data_dir
        self.config_file = os.path.join(writable_dir, 'app_config.ini')

        # 源路径：APK 包内资源（只读）
        bundled_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_config.ini')

        # 如果可写目录没有配置，且包内有配置，则复制（初始化）
        if not os.path.exists(self.config_file) and os.path.exists(bundled_config):
            try:
                shutil.copy(bundled_config, self.config_file)
                print(f"Config copied from {bundled_config} to {self.config_file}")
            except Exception as e:
                print(f"Config copy failed: {e}")

        # 读取配置
        self.app_config = configparser.ConfigParser()
        self.app_config.read(self.config_file)
        if not self.app_config.has_section('keys'):
            self.app_config.add_section('keys')

        self.keys = {
            'tongyi_key': self.app_config.get('keys', 'tongyi_key', fallback=''),
            'deepseek_key': self.app_config.get('keys', 'deepseek_key', fallback=''),
            'ali_ak': self.app_config.get('keys', 'ali_ak', fallback=''),
            'ali_sk': self.app_config.get('keys', 'ali_sk', fallback='')
        }
        print(f"Loaded keys: {self.keys.keys()}")  # Debug log

    def save_config(self):
        sc = self.screen_manager.get_screen('settings')
        self.app_config.set('keys', 'tongyi_key', sc.ids.key_tongyi.text)
        self.app_config.set('keys', 'deepseek_key', sc.ids.key_deepseek.text)
        self.app_config.set('keys', 'ali_ak', sc.ids.key_ak.text)
        self.app_config.set('keys', 'ali_sk', sc.ids.key_sk.text)

        with open(self.config_file, 'w') as f:
            self.app_config.write(f)

        self.load_user_config()
        toast("配置已保存")
        self.switch_to('home')

    def switch_to(self, screen_name):
        self.screen_manager.current = screen_name
        if screen_name == 'history':
            self.load_history()
        if screen_name == 'settings':
            sc = self.screen_manager.get_screen('settings')
            sc.ids.key_tongyi.text = self.keys['tongyi_key']
            sc.ids.key_deepseek.text = self.keys['deepseek_key']
            sc.ids.key_ak.text = self.keys['ali_ak']
            sc.ids.key_sk.text = self.keys['ali_sk']

    # --- Actions ---
    def action_camera(self):
        self.backend.open_camera(self.on_image_ready)

    def action_gallery(self):
        self.backend.open_gallery(self.on_image_ready)

    def on_image_ready(self, path):
        if not path: return
        self.show_loading()
        # 确保在后台线程运行分析
        threading.Thread(target=self.run_analysis, args=(path,)).start()

    def run_analysis(self, path):
        # Call AI
        res = self.backend.analyze_report(path, self.keys)
        # 确保 UI 更新在主线程
        self.update_result_ui(res)
        # Save
        self.backend.save_record(res)

    @mainthread
    def update_result_ui(self, data):
        if hasattr(self, 'dialog') and self.dialog:
            self.dialog.dismiss()

        sc = self.screen_manager.get_screen('result')
        sc.ids.res_title.text = data.get('title', '分析完成')
        sc.ids.res_core.text = data.get('core_conclusion', '无内容')
        sc.ids.res_abnormal.text = str(data.get('abnormal_analysis', '无异常'))
        sc.ids.res_advice.text = str(data.get('life_advice', '无建议'))

        self.current_res_text = data.get('core_conclusion', '')
        self.switch_to('result')
        self.backend.speak("分析完成")

    @mainthread
    def show_loading(self):
        self.dialog = MDDialog(title="正在分析...", text="请稍候，AI正在解读您的报告", auto_dismiss=False)
        self.dialog.open()

    def open_settings(self):
        self.switch_to('settings')

    def speak_result(self):
        if hasattr(self, 'current_res_text'):
            self.backend.speak(self.current_res_text)

    # --- History ---
    def load_history(self):
        data = self.backend.get_history()
        sc = self.screen_manager.get_screen('history')
        # 清空列表
        sc.ids.history_list.data = []
        if not data:
            toast("暂无历史记录")
            return

        sc.ids.history_list.data = [
            {
                'viewclass': 'TwoLineAvatarIconListItem',
                'text': item[2],  # Title
                'secondary_text': item[1],  # Date
                'icon': "file-document",
                'on_release': lambda x=item[4]: self.show_history_detail(x)
            } for item in data
        ]

    def show_history_detail(self, json_str):
        try:
            data = json.loads(json_str)
            self.update_result_ui(data)
        except:
            toast("记录损坏")


if __name__ == '__main__':
    MedicalApp().run()