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

# 如果不是安卓，提供一些假的接口防止报错
if platform == 'android':
    from jnius import autoclass, cast
    from android import activity
    from android.runnable import run_on_ui_thread
else:
    def run_on_ui_thread(f):
        return f


    activity = None


class NativeUtils:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NativeUtils, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.callback = None
        self.temp_image_path = None

        if platform == 'android':
            try:
                # 1. 绑定 Activity 结果监听
                activity.bind(on_activity_result=self.on_activity_result)

                # 2. 绕过 Android 7.0+ 的 FileURI 限制 (最暴力的修复方案)
                StrictMode = autoclass('android.os.StrictMode')
                Builder = autoclass('android.os.StrictMode$VmPolicy$Builder')
                policy = Builder().build()
                StrictMode.setVmPolicy(policy)
            except Exception as e:
                print(f"Native Init Error: {e}")

    def get_cache_dir(self):
        """获取安卓缓存目录"""
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                return PythonActivity.mActivity.getExternalCacheDir().getAbsolutePath()
            except:
                return "."
        return "."

    def toast(self, text):
        """显示原生 Toast"""
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

    def open_camera(self, callback):
        """调用相机"""
        self.callback = callback
        if platform == 'android':
            try:
                Intent = autoclass('android.content.Intent')
                MediaStore = autoclass('android.provider.MediaStore')
                File = autoclass('java.io.File')
                Uri = autoclass('android.net.Uri')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')

                # 设置拍照存储路径
                filename = f"cam_{int(time.time())}.jpg"
                self.temp_image_path = os.path.join(self.get_cache_dir(), filename)
                photo_file = File(self.temp_image_path)

                # 这里的 Uri.fromFile 在绕过 StrictMode 后可用
                image_uri = Uri.fromFile(photo_file)

                intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                # 关键修复：显式转换为 Parcelable，否则会报错 Invalid instance
                parcelable_uri = cast('android.os.Parcelable', image_uri)
                intent.putExtra(MediaStore.EXTRA_OUTPUT, parcelable_uri)

                PythonActivity.mActivity.startActivityForResult(intent, 0x101)
            except Exception as e:
                self.toast(f"相机启动失败: {str(e)}")
                print(f"Camera Error: {e}")
        else:
            self.toast("电脑端模拟拍照")
            # 模拟回调
            Clock.schedule_once(lambda dt: callback("mock.jpg"), 1)

    def open_gallery(self, callback):
        """调用相册"""
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
        else:
            self.toast("电脑端模拟相册")

    def on_activity_result(self, request_code, result_code, intent):
        """处理回调结果"""
        if result_code != -1:  # RESULT_OK = -1
            return True

        if request_code == 0x101:  # 相机
            if self.temp_image_path and os.path.exists(self.temp_image_path):
                if self.callback:
                    self.callback(self.temp_image_path)
            else:
                self.toast("拍照未保存")

        elif request_code == 0x102:  # 相册
            if intent:
                uri = intent.getData()
                # 启动线程去复制文件，防止阻塞 UI
                threading.Thread(target=self._copy_uri_content, args=(uri,)).start()

        return True

    def _copy_uri_content(self, uri):
        """将相册的 content:// 复制为真实文件"""
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            context = PythonActivity.mActivity
            content_resolver = context.getContentResolver()

            # 打开输入流
            input_stream = content_resolver.openInputStream(uri)

            # 准备输出文件
            filename = f"gallery_{int(time.time())}.jpg"
            dest_path = os.path.join(self.get_cache_dir(), filename)

            # 读取并写入 (Python 读取 Java InputStream 比较麻烦，这里用 byte array)
            # 更简单的方法：使用 FileDescriptor
            pfd = content_resolver.openFileDescriptor(uri, "r")
            fd = pfd.getFd()

            with os.fdopen(fd, 'rb', closefd=False) as src:
                with open(dest_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)

            pfd.close()
            # input_stream.close() # fdopen handles it

            if self.callback:
                # 回调必须在 UI 线程或者由 Kivy Clock 调度
                Clock.schedule_once(lambda dt: self.callback(dest_path), 0)

        except Exception as e:
            print(f"Gallery Copy Error: {e}")
            Clock.schedule_once(lambda dt: self.toast("无法读取图片"), 0)


class CloudService:
    def __init__(self, config):
        self.ak = config.get('ali_ak', '')
        self.sk = config.get('ali_sk', '')
        self.ds_key = config.get('deepseek_key', '')
        self.ty_key = config.get('tongyi_key', '')

    def run_pipeline(self, image_path):
        """
        1. 阿里云 OCR
        2. DeepSeek 分析
        """
        # 1. OCR
        ocr_text = self._aliyun_ocr(image_path)
        if not ocr_text:
            return {"title": "识别失败", "core_conclusion": "OCR 无法提取文字，请检查网络或密钥。"}

        # 2. AI
        return self._analyze_text(ocr_text)

    def _aliyun_ocr(self, image_path):
        """阿里云全文识别高精版 (手写签名，无SDK依赖)"""
        try:
            with open(image_path, 'rb') as f:
                img_b64 = base64.b64encode(f.read()).decode('utf-8')

            # 构造参数
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            nonce = str(uuid.uuid4())
            params = {
                "Action": "RecognizeAdvanced",
                "Version": "2021-07-07",
                "Format": "JSON",
                "AccessKeyId": self.ak,
                "SignatureMethod": "HMAC-SHA1",
                "SignatureVersion": "1.0",
                "SignatureNonce": nonce,
                "Timestamp": timestamp,
                "NeedRotate": "true",
                "NeedSortPage": "true",
                "OutputCharInfo": "false"
            }

            # 签名逻辑
            sorted_keys = sorted(params.keys())
            query_str = "&".join([f"{self._percent_encode(k)}={self._percent_encode(params[k])}" for k in sorted_keys])
            string_to_sign = "POST&%2F&" + self._percent_encode(query_str)

            key = self.sk + "&"
            signature = base64.b64encode(
                hmac.new(key.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1).digest()).decode('utf-8')

            # 最终请求
            url = "https://ocr-api.cn-hangzhou.aliyuncs.com"
            # Body 必须包含 image 或 url，这里使用 JSON 提交
            # 注意：RecognizeAdvanced API 的签名通常只针对 Query 参数，Body 传输内容不参与签名计算
            # 但为了稳妥，这里使用 Form-Data 提交图片，配合 Query 里的签名

            params["Signature"] = signature

            # 使用 requests 的 files 参数自动处理 multipart/form-data
            # 重新打开文件流
            with open(image_path, 'rb') as f:
                files = {'body': f}
                resp = requests.post(url, params=params, files=files, timeout=15)

            if resp.status_code == 200:
                data = resp.json()
                if 'Data' in data:
                    content_obj = json.loads(data['Data'])
                    return content_obj.get('content', '')

            print(f"OCR Error: {resp.text}")
            return None

        except Exception as e:
            print(f"OCR Exception: {e}")
            return None

    def _percent_encode(self, s):
        res = urllib.parse.quote(str(s), safe='')
        return res.replace('+', '%20').replace('*', '%2A').replace('%7E', '~')

    def _analyze_text(self, text):
        """DeepSeek 文本分析"""
        prompt = f"""
        你是一位专业医生。请分析以下化验单/检查报告的OCR识别文本。
        忽略乱码。
        文本：{text[:3000]}

        请严格按以下 JSON 格式返回，不要包含 ```json 等标记：
        {{
            "title": "报告标题",
            "core_conclusion": "一句话核心结论",
            "abnormal_analysis": "异常指标的详细分析",
            "life_advice": "3条具体生活建议"
        }}
        """
        try:
            url = "https://api.deepseek.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.ds_key}"}
            data = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}  # 强制 JSON
            }

            resp = requests.post(url, json=data, headers=headers, timeout=30)
            res_json = resp.json()

            content = res_json['choices'][0]['message']['content']

            # 清洗 markdown 标记，防止 DeepSeek 有时候不听话
            content = content.replace("```json", "").replace("```", "").strip()

            return json.loads(content)
        except Exception as e:
            print(f"AI Exception: {e}")
            return {
                "title": "解析错误",
                "core_conclusion": "AI 响应解析失败",
                "abnormal_analysis": str(e),
                "life_advice": "请重试"
            }