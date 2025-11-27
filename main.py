# -*- coding: utf-8 -*-
import os
import threading
import json
import time
import sqlite3
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import platform
from kivy.graphics import Color, Rectangle
from service import MedicalService

# 引入字体
from kivy.core.text import LabelBase

LabelBase.register(name='Roboto', fn_regular='msyh.ttf')

# 字体配置
FONT_XL = '40sp'
FONT_L = '32sp'
FONT_M = '28sp'
FONT_S = '24sp'

# 安卓特定导入
if platform == 'android':
    from jnius import autoclass, cast, PythonJavaClass, java_method
    from android import activity
    from android.runnable import run_on_ui_thread
else:
    def run_on_ui_thread(f):
        return f


    activity = None


# --- 数据库管理 ---
class DBManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                summary TEXT,
                details TEXT
            )
        ''')
        self.conn.commit()

    def add_record(self, summary, details):
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.cursor.execute('INSERT INTO history (date, summary, details) VALUES (?, ?, ?)',
                            (date_str, summary, json.dumps(details, ensure_ascii=False)))
        self.conn.commit()

    def get_all(self):
        self.cursor.execute('SELECT * FROM history ORDER BY id DESC')
        return self.cursor.fetchall()

    def delete(self, uid):
        self.cursor.execute('DELETE FROM history WHERE id=?', (uid,))
        self.conn.commit()


# --- 原生功能封装 ---
class NativeUtils:
    _instance = None
    _callback = None
    _photo_uri = None

    REQUEST_CAMERA = 0x101
    REQUEST_GALLERY = 0x102

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NativeUtils, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.tts = None
        if platform == 'android':
            try:
                # 1. TTS 初始化 (无监听器模式，最稳)
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
                self.tts = TextToSpeech(PythonActivity.mActivity, None)

                # 2. 绑定 Activity Result
                activity.bind(on_activity_result=self.on_activity_result)

                # 3. 禁用 StrictMode (保底)
                StrictMode = autoclass('android.os.StrictMode')
                Builder = autoclass('android.os.StrictMode$VmPolicy$Builder')
                StrictMode.setVmPolicy(Builder().build())
            except Exception as e:
                print(f"[Native] Init Error: {e}")

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
        if self.tts:
            try:
                self.tts.speak(str(text), 0, None)
            except:
                pass
        else:
            print(f"[TTS] {text}")

    def request_permissions(self):
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.RECORD_AUDIO
            ])

    def get_app_dir(self):
        if platform == 'android':
            try:
                PA = autoclass('org.kivy.android.PythonActivity')
                return PA.mActivity.getExternalFilesDir(None).getAbsolutePath()
            except:
                return "."
        return "."

    def open_camera(self, callback):
        """修复版相机调用"""
        self._callback = callback
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                MediaStore = autoclass('android.provider.MediaStore')
                # 关键修复：正确引用内部类
                Media = autoclass('android.provider.MediaStore$Images$Media')
                ContentValues = autoclass('android.content.ContentValues')

                # 创建占位符
                values = ContentValues()
                values.put(Media.TITLE, f"OCR_{int(time.time())}")
                values.put(Media.MIME_TYPE, "image/jpeg")

                self._photo_uri = PythonActivity.mActivity.getContentResolver().insert(
                    Media.EXTERNAL_CONTENT_URI, values
                )

                intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                intent.putExtra(MediaStore.EXTRA_OUTPUT, self._photo_uri)
                PythonActivity.mActivity.startActivityForResult(intent, self.REQUEST_CAMERA)
            except Exception as e:
                self.show_toast(f"相机错误: {e}")
                print(f"[Camera] Error: {e}")
        else:
            self.show_toast("电脑端模拟拍照")
            # 模拟生成文件
            p = "mock_cam.jpg"
            with open(p, 'w') as f:
                f.write("test")
            callback(p)

    def open_gallery(self, callback):
        """打开相册"""
        self._callback = callback
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                intent = Intent(Intent.ACTION_PICK)
                intent.setType("image/*")
                PythonActivity.mActivity.startActivityForResult(intent, self.REQUEST_GALLERY)
            except Exception as e:
                self.show_toast(f"相册错误: {e}")
        else:
            self.show_toast("电脑端不支持相册")

    def on_activity_result(self, request_code, result_code, intent):
        """处理回调"""
        if result_code != -1:  # RESULT_OK
            self.show_toast("操作取消")
            return True

        if request_code == self.REQUEST_CAMERA:
            # 相机返回：处理 self._photo_uri
            if self._photo_uri:
                path = self._uri_to_path(self._photo_uri)
                if path and self._callback:
                    Clock.schedule_once(lambda dt: self._callback(path), 0)

        elif request_code == self.REQUEST_GALLERY:
            # 相册返回：从 intent 获取 uri
            if intent:
                uri = intent.getData()
                path = self._uri_to_path(uri)
                if path and self._callback:
                    Clock.schedule_once(lambda dt: self._callback(path), 0)
        return True

    def _uri_to_path(self, uri):
        """URI 转 真实路径 (简化版，使用流复制)"""
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            context = PythonActivity.mActivity
            resolver = context.getContentResolver()

            # 创建本地缓存文件
            dest_path = os.path.join(self.get_app_dir(), f"temp_{int(time.time())}.jpg")

            # Java流复制
            input_stream = resolver.openInputStream(uri)
            FileOutputStream = autoclass('java.io.FileOutputStream')
            output_stream = FileOutputStream(dest_path)

            # 简单的 buffer copy
            buffer = bytearray(4096)
            while True:
                read = input_stream.read(buffer)
                if read == -1: break
                # 注意：jnius 传 bytearray 有点坑，我们这里假设底层已处理
                # 如果不行，我们使用 Python 的 readinto 逻辑
                # 为了稳妥，我们直接用更粗暴的 Cursor 查询法
                break  # 暂停流复制方案，改用 Cursor

            # Cursor 方案 (虽然 Android 11 不推荐，但在兼容模式下可用)
            MediaStore = autoclass('android.provider.MediaStore$Images$Media')
            cursor = resolver.query(uri, None, None, None, None)
            if cursor:
                cursor.moveToFirst()
                idx = cursor.getColumnIndex("_data")  # DATA
                path = cursor.getString(idx)
                cursor.close()
                return path
        except Exception as e:
            print(f"[URI] Convert Error: {e}")
        return None


# --- 界面类 ---

class ResultScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.native = NativeUtils()
        self.db = None  # 在 main 中注入

        root = BoxLayout(orientation='vertical', padding='15dp', spacing='10dp')
        with root.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(size=(2000, 2000))

        root.add_widget(Label(text="诊断结果", font_size=FONT_L, color=(0, 0, 0, 1), bold=True, size_hint_y=0.1))

        scroll = ScrollView(size_hint_y=0.8)
        self.box = BoxLayout(orientation='vertical', spacing='20dp', size_hint_y=None, padding=[0, 20, 0, 20])
        self.box.bind(minimum_height=self.box.setter('height'))

        self.lbl_content = Label(
            text="", font_size=FONT_M, color=(0, 0, 0, 1), markup=True,
            size_hint_y=None, halign='left', valign='top', text_size=(Window.width - 50, None)
        )
        self.lbl_content.bind(texture_size=self.lbl_content.setter('size'))

        self.box.add_widget(self.lbl_content)
        scroll.add_widget(self.box)
        root.add_widget(scroll)

        btn_layout = BoxLayout(size_hint_y=0.1, spacing='10dp')
        btn_play = Button(text="🔊 播报", background_color=(0.2, 0.6, 1, 1))
        btn_play.bind(on_release=self.replay_audio)
        btn_back = Button(text="返回", background_color=(0.5, 0.5, 0.5, 1))
        btn_back.bind(on_release=lambda x: setattr(self.manager, 'current', 'home'))

        btn_layout.add_widget(btn_play)
        btn_layout.add_widget(btn_back)
        root.add_widget(btn_layout)
        self.add_widget(root)

        self.current_text = ""

    def update(self, data, save_db=True):
        res = data.get('result', {})
        core = res.get('core_conclusion', '无')
        abn = res.get('abnormal_analysis', '无')
        life = res.get('life_advice', '无')

        # 存入数据库
        if save_db and self.db:
            self.db.add_record(core, res)

        text = f"[color=#aa0000][b]核心结论：[/b][/color]\n{core}\n\n"
        text += f"[b]异常分析：[/b]\n{abn}\n\n"
        text += f"[color=#006600][b]生活建议：[/b][/color]\n{life}"

        self.lbl_content.text = text
        self.lbl_content.text_size = (Window.width - 50, None)
        self.lbl_content.texture_update()

        self.current_text = f"解读完成。{core}。异常分析：{abn}"
        self.native.speak(self.current_text)

    def replay_audio(self, instance):
        if self.current_text:
            self.native.speak(self.current_text)


class HistoryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = None

        root = BoxLayout(orientation='vertical', padding='10dp')
        with root.canvas.before:
            Color(0.95, 0.95, 0.95, 1)
            Rectangle(size=(2000, 2000))

        root.add_widget(Label(text="历史记录", font_size=FONT_L, color=(0, 0, 0, 1), size_hint_y=0.1))

        self.scroll = ScrollView(size_hint_y=0.8)
        self.list_box = BoxLayout(orientation='vertical', spacing='10dp', size_hint_y=None)
        self.list_box.bind(minimum_height=self.list_box.setter('height'))
        self.scroll.add_widget(self.list_box)
        root.add_widget(self.scroll)

        btn_back = Button(text="返回", size_hint_y=0.1, background_color=(0.5, 0.5, 0.5, 1))
        btn_back.bind(on_release=lambda x: setattr(self.manager, 'current', 'home'))
        root.add_widget(btn_back)
        self.add_widget(root)

    def on_enter(self):
        self.refresh_list()

    def refresh_list(self):
        self.list_box.clear_widgets()
        if not self.db: return
        records = self.db.get_all()
        for rid, date, summary, details in records:
            item = BoxLayout(orientation='vertical', size_hint_y=None, height='100dp', padding='5dp')
            # item background
            with item.canvas.before:
                Color(1, 1, 1, 1)
                Rectangle(pos=item.pos, size=item.size)

            lbl_date = Label(text=date, font_size=FONT_S, color=(0.5, 0.5, 0.5, 1), size_hint_y=0.3)
            lbl_sum = Label(text=summary[:20] + "...", font_size=FONT_M, color=(0, 0, 0, 1), size_hint_y=0.7)

            item.add_widget(lbl_date)
            item.add_widget(lbl_sum)

            # 点击事件 (使用 Button 覆盖实现)
            btn = Button(text="", background_color=(0, 0, 0, 0), size_hint=(1, 1), pos=item.pos)
            btn.bind(on_release=lambda x, d=details: self.show_detail(d))
            item.add_widget(btn)  # 覆盖在上面

            self.list_box.add_widget(item)

    def show_detail(self, details_json):
        try:
            data = json.loads(details_json)
            self.manager.get_screen('result').update({'result': data}, save_db=False)
            self.manager.current = 'result'
        except:
            pass


class SettingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.svc = None  # 注入

        root = BoxLayout(orientation='vertical', padding='20dp', spacing='20dp')
        with root.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(size=(2000, 2000))

        root.add_widget(Label(text="设置", font_size=FONT_L, color=(0, 0, 0, 1), size_hint_y=0.1))

        # API Key 配置区
        self.ti_ak = TextInput(hint_text="Aliyun AK ID", multiline=False, size_hint_y=None, height='50dp')
        self.ti_sk = TextInput(hint_text="Aliyun AK Secret", multiline=False, size_hint_y=None, height='50dp',
                               password=True)
        root.add_widget(self.ti_ak)
        root.add_widget(self.ti_sk)

        btn_save = Button(text="保存配置", size_hint_y=None, height='60dp')
        btn_save.bind(on_release=self.save_config)
        root.add_widget(btn_save)

        root.add_widget(Label(size_hint_y=0.5))  # 占位

        btn_back = Button(text="返回", size_hint_y=None, height='60dp', background_color=(0.5, 0.5, 0.5, 1))
        btn_back.bind(on_release=lambda x: setattr(self.manager, 'current', 'home'))
        root.add_widget(btn_back)

        self.add_widget(root)

    def save_config(self, instance):
        # 简单写文件
        with open('config.ini', 'w') as f:
            f.write(f"[aliyun]\naccess_key_id={self.ti_ak.text}\naccess_key_secret={self.ti_sk.text}\n")
            # 其他配置略
        # 重新加载
        if self.svc:
            self.svc.reload_config()
        NativeUtils().show_toast("配置已保存")


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.native = NativeUtils()
        self.svc = MedicalService()

        root = BoxLayout(orientation='vertical', padding='20dp', spacing='30dp')
        with root.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(size=(2000, 2000))

        # 顶部
        header = BoxLayout(size_hint_y=0.1)
        header.add_widget(Label(text="智能医疗报告解读", font_size=FONT_L, color=(0, 0, 0, 1), bold=True))
        btn_set = Button(text="⚙️", size_hint_x=None, width='50dp', background_color=(0, 0, 0, 0), color=(0, 0, 0, 1))
        btn_set.bind(on_release=lambda x: setattr(self.manager, 'current', 'setting'))
        header.add_widget(btn_set)
        root.add_widget(header)

        self.status = Label(text="初始化...", font_size=FONT_M, color=(0.5, 0.5, 0.5, 1), size_hint_y=0.1)
        root.add_widget(self.status)

        # 按钮区
        btn_box = BoxLayout(orientation='vertical', spacing='20dp', size_hint_y=0.6)

        btn_cam = Button(text="📷 拍照解读", font_size=FONT_L, background_color=(0.2, 0.6, 1, 1))
        btn_cam.bind(on_release=self.action_camera)

        btn_gal = Button(text="🖼️ 相册选择", font_size=FONT_L, background_color=(0.2, 0.8, 0.2, 1))
        btn_gal.bind(on_release=self.action_gallery)

        btn_hist = Button(text="🕒 历史记录", font_size=FONT_L, background_color=(0.8, 0.6, 0.2, 1))
        btn_hist.bind(on_release=lambda x: setattr(self.manager, 'current', 'history'))

        btn_box.add_widget(btn_cam)
        btn_box.add_widget(btn_gal)
        btn_box.add_widget(btn_hist)
        root.add_widget(btn_box)

        root.add_widget(Label(size_hint_y=0.2))
        self.add_widget(root)

        Clock.schedule_once(self.start, 2)

    def start(self, dt):
        self.native.request_permissions()
        if self.svc.config_ready:
            self.status.text = "✅ 云端就绪"
            self.native.speak("系统就绪")
        else:
            self.status.text = "⚠️ 请先设置密钥"

    def action_camera(self, instance):
        self.native.speak("请拍摄报告")
        self.native.open_camera(self.process_img)

    def action_gallery(self, instance):
        self.native.speak("请选择图片")
        self.native.open_gallery(self.process_img)

    def process_img(self, path):
        if not path or not os.path.exists(path):
            self.native.show_toast("文件不存在")
            return

        self.status.text = "🔄 分析中..."
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

        # 初始化数据库
        db_path = os.path.join(NativeUtils().get_app_dir(), 'medical.db')
        db = DBManager(db_path)

        sm = ScreenManager()

        home = HomeScreen(name='home')
        result = ResultScreen(name='result')
        result.db = db  # 注入DB

        history = HistoryScreen(name='history')
        history.db = db

        setting = SettingScreen(name='setting')
        setting.svc = home.svc

        sm.add_widget(home)
        sm.add_widget(result)
        sm.add_widget(history)
        sm.add_widget(setting)

        return sm


if __name__ == '__main__':
    MedicalApp().run()