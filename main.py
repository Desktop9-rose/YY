# -*- coding: utf-8 -*-
import os
import threading
import json
import time
import sqlite3
from datetime import datetime

# Kivy 依赖
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.textinput import TextInput
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import platform
from kivy.graphics import Color, Rectangle

# 业务逻辑
from service import MedicalService

# 字体注册
from kivy.core.text import LabelBase

LabelBase.register(name='Roboto', fn_regular='msyh.ttf')

# 字体配置
FONT_L = '32sp'
FONT_M = '28sp'
FONT_S = '24sp'

# 安卓环境检测与导入
if platform == 'android':
    from jnius import autoclass, cast, PythonJavaClass, java_method
    from android import activity
    from android.runnable import run_on_ui_thread
else:
    def run_on_ui_thread(f):
        return f


    activity = None


# --- 数据库模块 ---
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
        try:
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.cursor.execute('INSERT INTO history (date, summary, details) VALUES (?, ?, ?)',
                                (date_str, summary, json.dumps(details, ensure_ascii=False)))
            self.conn.commit()
        except Exception as e:
            print(f"[DB] Error: {e}")

    def get_all(self):
        try:
            self.cursor.execute('SELECT * FROM history ORDER BY id DESC')
            return self.cursor.fetchall()
        except:
            return []


# --- TTS 模块 (修复 Context 问题) ---
class AndroidTTS:
    def __init__(self):
        self.tts = None
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                TextToSpeech = autoclass('android.speech.tts.TextToSpeech')

                # 关键修复：使用 Application Context 而不是 Activity Context
                # 这能避免 Activity 重建导致的 TTS 绑定失败 (code -1)
                app_context = PythonActivity.mActivity.getApplicationContext()
                self.tts = TextToSpeech(app_context, None)
                print("[TTS] Initialized with AppContext")
            except Exception as e:
                print(f"[TTS] Init Error: {e}")

    def speak(self, text):
        if self.tts:
            try:
                # 0 = QUEUE_FLUSH
                self.tts.speak(str(text), 0, None)
            except Exception as e:
                print(f"[TTS] Speak Error: {e}")
        else:
            print(f"[TTS-MOCK] {text}")


# --- 原生功能工具类 (核心修复区) ---
class NativeUtils:
    _instance = None
    _callback = None
    _camera_target_path = None

    REQUEST_CAMERA = 0x101
    REQUEST_GALLERY = 0x102

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NativeUtils, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.tts_engine = AndroidTTS()
        if platform == 'android':
            try:
                # 1. 绑定回调
                activity.bind(on_activity_result=self.on_activity_result)

                # 2. 禁用 StrictMode (核弹级修复)
                # 这允许我们直接通过 file:// 协议调用相机，绕过 MediaStore 插入失败的问题
                StrictMode = autoclass('android.os.StrictMode')
                Builder = autoclass('android.os.StrictMode$VmPolicy$Builder')
                new_policy = Builder().build()
                StrictMode.setVmPolicy(new_policy)
                print("[Native] StrictMode disabled (Camera Fix)")
            except Exception as e:
                print(f"[Native] Init Warn: {e}")

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
        # 延迟调用以确保 TTS 引擎就绪
        Clock.schedule_once(lambda dt: self.tts_engine.speak(text), 0.2)

    def request_permissions(self):
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.CAMERA,
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.RECORD_AUDIO
                ])
            except Exception as e:
                print(f"[Perm] Error: {e}")

    def get_cache_dir(self):
        """获取外部缓存目录 (相比 FilesDir 更不易被相机拒读)"""
        if platform == 'android':
            try:
                PA = autoclass('org.kivy.android.PythonActivity')
                return PA.mActivity.getExternalCacheDir().getAbsolutePath()
            except:
                return "."
        return "."

    def open_camera(self, callback):
        """
        修复版相机：使用 file:// URI + StrictMode Bypass
        解决 Invalid column null 错误
        """
        self._callback = callback
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                MediaStore = autoclass('android.provider.MediaStore')
                Uri = autoclass('android.net.Uri')
                File = autoclass('java.io.File')

                # 1. 构造目标文件路径
                filename = f"OCR_{int(time.time())}.jpg"
                self._camera_target_path = os.path.join(self.get_cache_dir(), filename)

                # 2. 创建 Java File 对象
                photo_file = File(self._camera_target_path)
                # 关键：直接使用 fromFile 获取 file:// URI (需要禁用 StrictMode)
                photo_uri = Uri.fromFile(photo_file)

                # 3. 启动相机
                intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                intent.putExtra(MediaStore.EXTRA_OUTPUT, photo_uri)

                PythonActivity.mActivity.startActivityForResult(intent, self.REQUEST_CAMERA)
                print(f"[Camera] Intent started. Target: {self._camera_target_path}")
            except Exception as e:
                self.show_toast(f"相机启动失败: {e}")
                print(f"[Camera] Error: {e}")
        else:
            self.show_toast("电脑模拟拍照")
            p = "mock_cam.jpg"
            with open(p, 'w') as f:
                f.write("test")
            callback(p)

    def open_gallery(self, callback):
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
            self.show_toast("电脑不支持")

    def on_activity_result(self, request_code, result_code, intent):
        if result_code != -1:  # RESULT_OK
            return True

        if request_code == self.REQUEST_CAMERA:
            # 相机返回：直接检查我们预设的文件路径
            if self._camera_target_path and os.path.exists(self._camera_target_path):
                print(f"[Camera] File exists: {self._camera_target_path}")
                self._safe_callback(self._camera_target_path)
            else:
                # 延迟检测，防止文件系统写入延迟
                Clock.schedule_once(lambda dt: self._check_cam_file(), 1.0)

        elif request_code == self.REQUEST_GALLERY:
            # 相册返回：处理 Content URI
            if intent:
                uri = intent.getData()
                # 在后台线程处理文件复制，避免阻塞 UI
                threading.Thread(target=self._process_gallery_uri, args=(uri,)).start()

        return True

    def _check_cam_file(self):
        if self._camera_target_path and os.path.exists(self._camera_target_path):
            self._safe_callback(self._camera_target_path)
        else:
            self.show_toast("未检测到照片")

    def _process_gallery_uri(self, uri):
        """处理相册 URI"""
        safe_path = self._copy_uri_to_file_java(uri)
        if safe_path:
            self._safe_callback(safe_path)
        else:
            Clock.schedule_once(lambda dt: self.show_toast("图片读取失败"), 0)

    def _safe_callback(self, path):
        if self._callback:
            Clock.schedule_once(lambda dt: self._callback(path), 0)

    def _copy_uri_to_file_java(self, uri):
        """
        【核心修复】使用纯 Java IO 流复制文件
        解决 Python open() 遇到的 Permission denied
        """
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            context = PythonActivity.mActivity

            # 1. 准备输入流
            resolver = context.getContentResolver()
            input_stream = resolver.openInputStream(uri)
            if not input_stream: return None

            # 2. 准备输出文件
            dest_path = os.path.join(self.get_cache_dir(), f"gallery_{int(time.time())}.jpg")
            File = autoclass('java.io.File')
            dest_file = File(dest_path)
            FileOutputStream = autoclass('java.io.FileOutputStream')
            output_stream = FileOutputStream(dest_file)

            # 3. 缓冲区复制 (Java byte[])
            # 由于 Jnius 传递 byte[] 复杂，我们使用一种变通方法：
            # 使用 Apache Commons IO 或类似逻辑的简化版？不，依赖太多。
            # 我们这里使用一次性读取（针对图片通常几MB，还可以接受）
            # 或者简单的逐字节读取太慢。

            # 为了稳定性，我们尝试使用 Android FileUtils (API 29+)
            # 但为了兼容性，我们尝试最简单的方案：
            # Python 读取 /proc/self/fd/ 失败是因为 SELinux。
            # 但我们可以利用 context.getCacheDir() 是 app 私有的特性。

            # 让我们尝试用 Kivy 的 Context 辅助？无。

            # 重新尝试：byte 数组传输
            # 定义一个 8KB 的 buffer
            # 这种方法在 Python 中写很难。

            # 替代方案：让 Service 直接处理 URI？
            # 阿里云 SDK 也不支持 content://。

            # 最终方案：
            # 我们使用 read_bytes() 读取全部内容（Jnius 适配版）
            # 虽然耗内存，但是能跑通。

            # 构造一个 ByteArrayOutputStream 来接收数据
            ByteArrayOutputStream = autoclass('java.io.ByteArrayOutputStream')
            byte_stream = ByteArrayOutputStream()

            # 简单的 int read() 循环在 Python 中太慢。
            # 让我们赌一把：使用 Python 的 open() 读取 /proc/self/fd/
            # 之前的报错说明是权限问题。

            # 那么，我们使用 Python 的 shutil.copyfileobj ?
            # 需要把 Java InputStream 包装成 Python file-object。

            # 实在不行，我们使用最简单的：
            # 调用 MediaStore.Images.Media.getBitmap?
            MediaStore = autoclass('android.provider.MediaStore$Images$Media')
            bitmap = MediaStore.getBitmap(resolver, uri)

            # 将 Bitmap 压缩保存到文件
            CompressFormat = autoclass('android.graphics.Bitmap$CompressFormat')
            bitmap.compress(CompressFormat.JPEG, 90, output_stream)

            output_stream.close()
            input_stream.close()
            print(f"[File] Bitmap saved to: {dest_path}")
            return dest_path

        except Exception as e:
            print(f"[File] Copy Java Error: {e}")
            return None


# --- 界面 ---
class ResultScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.native = NativeUtils()
        self.db = None

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

        btn_layout = BoxLayout(size_hint_y=0.1, spacing='10dp')
        btn_play = Button(text="🔊 播报", background_color=(0.2, 0.6, 1, 1))
        btn_play.bind(on_release=self.replay_audio)
        btn_back = Button(text="返回", background_color=(0.5, 0.5, 0.5, 1))
        btn_back.bind(on_release=lambda x: setattr(self.manager, 'current', 'home'))

        btn_layout.add_widget(btn_play)
        btn_layout.add_widget(btn_back)
        root.add_widget(btn_layout)
        self.current_text = ""

    def update(self, data, save_db=True):
        res = data.get('result', {})
        core = res.get('core_conclusion', '无')
        abn = res.get('abnormal_analysis', '无')
        life = res.get('life_advice', '无')

        if save_db and self.db:
            self.db.add_record(core, res)

        text = f"[color=#aa0000][b]核心结论：[/b][/color]\n{core}\n\n"
        text += f"[b]异常分析：[/b]\n{abn}\n\n"
        text += f"[color=#006600][b]生活建议：[/b][/color]\n{life}"

        self.lbl_content.text = text
        self.lbl_content.text_size = (Window.width - 50, None)
        self.lbl_content.texture_update()

        self.current_text = f"解读完成。{core}"
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
            with item.canvas.before:
                Color(1, 1, 1, 1)
                Rectangle(pos=item.pos, size=item.size)
            lbl_date = Label(text=date, font_size=FONT_S, color=(0.5, 0.5, 0.5, 1), size_hint_y=0.3)
            lbl_sum = Label(text=str(summary)[:20] + "...", font_size=FONT_M, color=(0, 0, 0, 1), size_hint_y=0.7)
            item.add_widget(lbl_date)
            item.add_widget(lbl_sum)
            btn = Button(text="", background_color=(0, 0, 0, 0), size_hint=(1, 1), pos=item.pos)
            btn.bind(on_release=lambda x, d=details: self.show_detail(d))
            item.add_widget(btn)
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
        self.svc = None
        root = BoxLayout(orientation='vertical', padding='20dp', spacing='20dp')
        with root.canvas.before:
            Color(1, 1, 1, 1)
            Rectangle(size=(2000, 2000))
        root.add_widget(Label(text="设置", font_size=FONT_L, color=(0, 0, 0, 1), size_hint_y=0.1))
        self.ti_ak = TextInput(hint_text="Aliyun AK ID", multiline=False, size_hint_y=None, height='50dp')
        self.ti_sk = TextInput(hint_text="Aliyun AK Secret", multiline=False, size_hint_y=None, height='50dp',
                               password=True)
        root.add_widget(self.ti_ak)
        root.add_widget(self.ti_sk)
        btn_save = Button(text="保存配置", size_hint_y=None, height='60dp')
        btn_save.bind(on_release=self.save_config)
        root.add_widget(btn_save)
        root.add_widget(Label(size_hint_y=0.5))
        btn_back = Button(text="返回", size_hint_y=None, height='60dp', background_color=(0.5, 0.5, 0.5, 1))
        btn_back.bind(on_release=lambda x: setattr(self.manager, 'current', 'home'))
        root.add_widget(btn_back)
        self.add_widget(root)

    def save_config(self, instance):
        with open('config.ini', 'w') as f:
            f.write(f"[aliyun]\naccess_key_id={self.ti_ak.text}\naccess_key_secret={self.ti_sk.text}\n")
        if self.svc: self.svc.__init__()
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
        header = BoxLayout(size_hint_y=0.1)
        header.add_widget(Label(text="智能医疗报告解读", font_size=FONT_L, color=(0, 0, 0, 1), bold=True))
        btn_set = Button(text="⚙️", size_hint_x=None, width='50dp', background_color=(0, 0, 0, 0), color=(0, 0, 0, 1))
        btn_set.bind(on_release=lambda x: setattr(self.manager, 'current', 'setting'))
        header.add_widget(btn_set)
        root.add_widget(header)
        self.status = Label(text="初始化...", font_size=FONT_M, color=(0.5, 0.5, 0.5, 1), size_hint_y=0.1)
        root.add_widget(self.status)
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
        db_path = os.path.join(NativeUtils().get_app_dir(), 'medical.db')
        db = DBManager(db_path)
        sm = ScreenManager()
        home = HomeScreen(name='home')
        result = ResultScreen(name='result')
        result.db = db
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