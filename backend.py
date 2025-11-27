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
from datetime import datetime
from kivy.utils import platform
from kivy.clock import Clock

# 安卓环境预设
if platform == 'android':
    from jnius import autoclass, cast
    from android import activity
    from android.runnable import run_on_ui_thread
else:
    def run_on_ui_thread(f):
        return f


    activity = None


class AndroidHelper:
    """处理相机、相册、Toast、TTS等安卓原生功能"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AndroidHelper, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.callback = None
        self.temp_image_path = None
        self.tts = None

        if platform == 'android':
            try:
                # 监听 Activity 结果
                activity.bind(on_activity_result=self.on_activity_result)

                # 初始化 TTS
                TTS = autoclass('android.speech.tts.TextToSpeech')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                context = PythonActivity.mActivity.getApplicationContext()
                self.tts = TTS(context, None)

                # 绕过 Android 7.0+ 文件权限限制 (FileUriExposedException)
                StrictMode = autoclass('android.os.StrictMode')
                Builder = autoclass('android.os.StrictMode$VmPolicy$Builder')
                policy = Builder().build()
                StrictMode.setVmPolicy(policy)
            except Exception as e:
                print(f"Android Init Error: {e}")

    def get_cache_dir(self):
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                return PythonActivity.mActivity.getExternalCacheDir().getAbsolutePath()
            except:
                return "."
        return "."

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
        else:
            print(f"[TTS] {text}")

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
                # 禁用 StrictMode 后可直接使用 fromFile
                image_uri = Uri.fromFile(photo_file)

                intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                # 关键修复：强制转换为 Parcelable 接口，修复报错
                parcelable_uri = cast('android.os.Parcelable', image_uri)
                intent.putExtra(MediaStore.EXTRA_OUTPUT, parcelable_uri)

                PythonActivity.mActivity.startActivityForResult(intent, 0x101)
            except Exception as e:
                self.toast(f"相机启动失败: {e}")
        else:
            self.toast("电脑端模拟拍照")
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
            except Exception as e:
                self.toast(f"相册启动失败: {e}")

    def on_activity_result(self, request_code, result_code, intent):
        if result_code != -1: return True  # -1 is RESULT_OK

        if request_code == 0x101:  # 相机
            if self.temp_image_path and os.path.exists(self.temp_image_path):
                if self.callback: self.callback(self.temp_image_path)
            else:
                self.toast("未检测到照片")

        elif request_code == 0x102:  # 相册
            if intent:
                uri = intent.getData()
                # 启动线程复制文件，避免阻塞 UI 导致白屏
                threading.Thread(target=self._copy_uri_content, args=(uri,)).start()
        return True

    def _copy_uri_content(self, uri):
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            content_resolver = PythonActivity.mActivity.getContentResolver()

            pfd = content_resolver.openFileDescriptor(uri, "r")
            if not pfd: return
            fd = pfd.getFd()

            filename = f"gallery_{int(time.time())}.jpg"
            dest_path = os.path.join(self.get_cache_dir(), filename)

            with os.fdopen(fd, 'rb', closefd=False) as src:
                with open(dest_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            pfd.close()

            if self.callback:
                # 回调必须通过 Clock 调度回主线程，或者由接收方处理
                Clock.schedule_once(lambda dt: self.callback(dest_path), 0)
        except Exception as e:
            print(f"Copy Error: {e}")
            self.toast("图片读取失败")


class APIService:
    def __init__(self):
        # 优先读取环境变量 (GitHub Secrets)，其次读取配置文件
        self.ak = os.environ.get('ALIYUN_AK_ID', '')
        self.sk = os.environ.get('ALIYUN_AK_SECRET', '')
        self.ds_key = os.environ.get('DEEPSEEK_KEY', '')
        self.ty_key = os.environ.get('TONGYI_KEY', '')

        # 如果环境变量为空，尝试读取本地 config.ini (用于本地调试或手动设置)
        # 这里逻辑在 main.py 中处理加载 config.ini 到内存，然后更新这个 Service

    def update_keys(self, ak, sk, ds, ty):
        if ak: self.ak = ak
        if sk: self.sk = sk
        if ds: self.ds_key = ds
        if ty: self.ty_key = ty

    def analyze_image(self, image_path):
        """
        双模态流水线：
        1. 尝试通义千问 VL (视觉理解)，因其无需独立 OCR，容错率高。
        2. 如果失败，fallback 逻辑可扩展。
        3. 调用 DeepSeek 进行专业医学润色 (如果需要)。
        """
        if not self.ty_key and not self.ak:
            return {"title": "配置缺失", "core_conclusion": "请检查 API 密钥设置 (GitHub Secrets 或 手动输入)"}

        # 步骤 1: 视觉识别 (Tongyi VL) - 你的日志显示这个之前是通的
        ocr_text = self._tongyi_vl_ocr(image_path)
        if not ocr_text:
            return {"title": "识别失败", "core_conclusion": "无法从图片中提取文字，请确保图片清晰。"}

        # 步骤 2: 医学分析 (DeepSeek)
        return self._deepseek_analyze(ocr_text)

    def _tongyi_vl_ocr(self, image_path):
        if not self.ty_key: return None
        try:
            with open(image_path, 'rb') as f:
                img_b64 = base64.b64encode(f.read()).decode('utf-8')

            url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
            headers = {"Authorization": f"Bearer {self.ty_key}", "Content-Type": "application/json"}
            data = {
                "model": "qwen-vl-max",
                "input": {
                    "messages": [
                        {"role": "user", "content": [
                            {"image": f"data:image/jpeg;base64,{img_b64}"},
                            {"text": "请完整的提取这张化验单上的所有文字信息，包含指标名称、数值、单位和箭头符号。"}
                        ]}
                    ]
                }
            }
            resp = requests.post(url, json=data, headers=headers, timeout=35)
            if resp.status_code == 200:
                res = resp.json()
                if 'output' in res and 'choices' in res['output']:
                    return res['output']['choices'][0]['message']['content'][0]['text']
            print(f"VL Error: {resp.text}")
        except Exception as e:
            print(f"VL Exception: {e}")
        return None

    def _deepseek_analyze(self, text):
        if not self.ds_key:
            # 如果没有 DeepSeek Key，直接返回 OCR 结果的简单包装
            return {
                "title": "识别结果 (无AI分析)",
                "core_conclusion": "未配置 DeepSeek Key，仅显示识别内容。",
                "abnormal_analysis": text[:200] + "...",
                "life_advice": "请配置 DeepSeek Key 以获取专业解读。"
            }

        prompt = f"""
        你是一位专业医生。请根据以下化验单文本生成 JSON 报告。
        文本：{text[:3000]}

        请返回纯 JSON 格式，不要包含 Markdown 代码块标记 (如 ```json)。格式如下：
        {{
            "title": "报告类型 (如: 血常规)",
            "core_conclusion": "一句话核心结论",
            "abnormal_analysis": "异常指标分析 (列出具体的异常项及其含义)",
            "life_advice": "3条生活建议"
        }}
        """
        try:
            url = "https://api.deepseek.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.ds_key}"}
            data = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}
            }
            resp = requests.post(url, json=data, headers=headers, timeout=30)
            content = resp.json()['choices'][0]['message']['content']

            # 关键修复：清洗 Markdown 标记，防止 JSON 解析炸裂
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as e:
            print(f"DeepSeek Error: {e}")
            return {
                "title": "分析失败",
                "core_conclusion": "AI 响应解析错误",
                "abnormal_analysis": "请重试或检查网络。",
                "life_advice": ""
            }