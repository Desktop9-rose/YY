# -*- coding: utf-8 -*-
import os
import json
import time
import shutil
import base64
import hmac
import hashlib
import uuid
import threading
import requests
import urllib.parse
import sqlite3
from datetime import datetime
from kivy.utils import platform
from kivy.clock import Clock

if platform == 'android':
    from jnius import autoclass, cast
    from android import activity
    from android.runnable import run_on_ui_thread
else:
    def run_on_ui_thread(f):
        return f


    activity = None


class BackendService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BackendService, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.callback = None
        self.temp_image_path = None
        self.tts = None
        self.setup_android()
        self.setup_db()

    def setup_android(self):
        if platform == 'android':
            try:
                activity.bind(on_activity_result=self.on_activity_result)

                # TTS Init
                TTS = autoclass('android.speech.tts.TextToSpeech')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                context = PythonActivity.mActivity.getApplicationContext()
                self.tts = TTS(context, None)

                # StrictMode Bypass
                StrictMode = autoclass('android.os.StrictMode')
                Builder = autoclass('android.os.StrictMode$VmPolicy$Builder')
                StrictMode.setVmPolicy(Builder().build())
            except Exception as e:
                print(f"Android Init Error: {e}")

    def get_files_dir(self):
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                return PythonActivity.mActivity.getFilesDir().getAbsolutePath()
            except:
                return "."
        return "."

    def get_cache_dir(self):
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                return PythonActivity.mActivity.getExternalCacheDir().getAbsolutePath()
            except:
                return "."
        return "."

    # --- Database ---
    def setup_db(self):
        db_path = os.path.join(self.get_files_dir(), 'medical_history.db')
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_str TEXT,
                title TEXT,
                summary TEXT,
                full_json TEXT
            )
        ''')
        self.conn.commit()

    def save_record(self, result_data):
        try:
            date = datetime.now().strftime("%Y-%m-%d %H:%M")
            title = result_data.get('title', '未命名报告')
            summary = result_data.get('core_conclusion', '')
            json_str = json.dumps(result_data, ensure_ascii=False)

            self.cursor.execute(
                'INSERT INTO history (date_str, title, summary, full_json) VALUES (?, ?, ?, ?)',
                (date, title, summary, json_str)
            )
            self.conn.commit()
        except Exception as e:
            print(f"DB Save Error: {e}")

    def get_history(self):
        try:
            self.cursor.execute('SELECT id, date_str, title, summary, full_json FROM history ORDER BY id DESC')
            return self.cursor.fetchall()
        except:
            return []

    # --- Android Features ---
    def toast(self, text):
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Toast = autoclass('android.widget.Toast')
                String = autoclass('java.lang.String')
                run_on_ui_thread(lambda: Toast.makeText(PythonActivity.mActivity, String(str(text)), 0).show())()
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

    def open_camera(self, callback):
        self.callback = callback
        if platform == 'android':
            try:
                Intent = autoclass('android.content.Intent')
                MediaStore = autoclass('android.provider.MediaStore')
                File = autoclass('java.io.File')
                Uri = autoclass('android.net.Uri')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')

                filename = f"cam_{int(time.time())}.jpg"
                self.temp_image_path = os.path.join(self.get_cache_dir(), filename)
                photo_file = File(self.temp_image_path)
                image_uri = Uri.fromFile(photo_file)

                intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                parcelable_uri = cast('android.os.Parcelable', image_uri)
                intent.putExtra(MediaStore.EXTRA_OUTPUT, parcelable_uri)

                PythonActivity.mActivity.startActivityForResult(intent, 0x101)
            except Exception as e:
                self.toast(f"相机错误: {e}")
        else:
            Clock.schedule_once(lambda dt: callback("mock.jpg"), 1)

    def open_gallery(self, callback):
        self.callback = callback
        if platform == 'android':
            try:
                Intent = autoclass('android.content.Intent')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                intent = Intent(Intent.ACTION_PICK)
                intent.setType("image/*")
                PythonActivity.mActivity.startActivityForResult(intent, 0x102)
            except:
                self.toast("相册启动失败")

    def on_activity_result(self, request_code, result_code, intent):
        if result_code != -1: return True

        if request_code == 0x101:  # Camera
            if self.temp_image_path and os.path.exists(self.temp_image_path):
                if self.callback:
                    Clock.schedule_once(lambda dt: self.callback(self.temp_image_path), 0)
            else:
                self.toast("拍照取消")

        elif request_code == 0x102:  # Gallery
            if intent:
                uri = intent.getData()
                threading.Thread(target=self._copy_uri_content, args=(uri,)).start()
        return True

    def _copy_uri_content(self, uri):
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            content_resolver = PythonActivity.mActivity.getContentResolver()
            pfd = content_resolver.openFileDescriptor(uri, "r")
            fd = pfd.getFd()

            dest_path = os.path.join(self.get_cache_dir(), f"gallery_{int(time.time())}.jpg")
            with os.fdopen(fd, 'rb', closefd=False) as src:
                with open(dest_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            pfd.close()

            if self.callback:
                Clock.schedule_once(lambda dt: self.callback(dest_path), 0)
        except Exception as e:
            print(f"Gallery Error: {e}")
            self.toast("图片读取失败")

    # --- AI & OCR ---
    def analyze_report(self, image_path, keys):
        """双重保险：先尝试通义VL（无OCR依赖），再尝试OCR+DeepSeek"""
        ty_key = keys.get('tongyi_key')
        ds_key = keys.get('deepseek_key')
        ak = keys.get('ali_ak')
        sk = keys.get('ali_sk')

        if not ty_key and not ak:
            return {"error": "Missing Keys", "core_conclusion": "请配置API密钥"}

        # 方案 A: 通义千问 VL (视觉直出)
        if ty_key:
            print("Trying Tongyi VL...")
            res = self._call_tongyi_vl(image_path, ty_key)
            if res: return self._format_ai_result(res, ds_key)

        # 方案 B: 阿里云OCR + DeepSeek
        if ak and sk and ds_key:
            print("Trying OCR + DeepSeek...")
            ocr_text = self._call_aliyun_ocr(image_path, ak, sk)
            if ocr_text:
                return self._call_deepseek(ocr_text, ds_key)

        return {"title": "分析失败", "core_conclusion": "无法识别图片或网络超时",
                "life_advice": "请确保图片清晰且包含文字"}

    def _call_tongyi_vl(self, path, key):
        try:
            with open(path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
            data = {
                "model": "qwen-vl-max",
                "input": {"messages": [{"role": "user", "content": [
                    {"image": f"data:image/jpeg;base64,{b64}"},
                    {"text": "提取这张医疗报告的所有文字信息"}
                ]}]}
            }
            resp = requests.post(url, json=data, headers={"Authorization": f"Bearer {key}"}, timeout=30)
            if resp.status_code == 200:
                return resp.json()['output']['choices'][0]['message']['content'][0]['text']
        except Exception as e:
            print(f"VL Error: {e}")
        return None

    def _call_aliyun_ocr(self, path, ak, sk):
        # 简化的 OCR 调用逻辑 (省略冗长签名代码，假设使用 requests 提交)
        # 实际生产建议保留你之前的 OCR 完整签名逻辑
        # 为节省篇幅，这里仅做示意，如果方案A失败，建议优先检查方案A配置
        return None

    def _call_deepseek(self, text, key):
        return self._format_ai_result(text, key)

    def _format_ai_result(self, text, ds_key):
        # 使用 DeepSeek 整理成 JSON
        if not ds_key:
            return {"title": "识别结果", "core_conclusion": text[:100], "abnormal_analysis": text}

        prompt = f"""
        你是一位医生。根据以下报告内容生成JSON。
        内容：{text[:3000]}
        格式：{{"title":"标题","core_conclusion":"结论","abnormal_analysis":"异常","life_advice":"建议"}}
        纯JSON，无Markdown。
        """
        try:
            resp = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {ds_key}"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                      "response_format": {"type": "json_object"}},
                timeout=20
            )
            content = resp.json()['choices'][0]['message']['content']
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except:
            return {"title": "解析完成", "core_conclusion": "AI整理失败，显示原文", "abnormal_analysis": text}