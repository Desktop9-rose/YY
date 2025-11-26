# -*- coding: utf-8 -*-
import os
import json
import configparser
import requests
from concurrent.futures import ThreadPoolExecutor

# 阿里云 SDK (Buildozer 会自动打包这些库)
from alibabacloud_ocr_api20210707.client import Client as OcrClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_ocr_api20210707 import models as ocr_models
from alibabacloud_tea_util import models as util_models


class MedicalService:
    def __init__(self, config_path='config.ini'):
        self.config_ready = False
        self.ak_id = ""
        self.ak_secret = ""
        self.endpoint = "ocr-api.cn-hangzhou.aliyuncs.com"
        self.ds_key = ""
        self.ty_key = ""

        # 尝试读取配置
        if os.path.exists(config_path):
            try:
                conf = configparser.ConfigParser()
                conf.read(config_path, encoding='utf-8')
                self.ak_id = conf.get('aliyun', 'access_key_id')
                self.ak_secret = conf.get('aliyun', 'access_key_secret')
                # 兼容 secrets 注入时可能的 endpoint 配置，或者写死
                if conf.has_option('aliyun', 'endpoint'):
                    self.endpoint = conf.get('aliyun', 'endpoint')

                self.ds_key = conf.get('llm', 'deepseek_key')
                self.ty_key = conf.get('llm', 'tongyi_key')
                self.config_ready = True
            except Exception as e:
                print(f"[Service] Config Error: {e}")

    def process(self, image_path):
        """主入口：传入图片路径，返回最终 JSON"""
        if not self.config_ready:
            return {"code": 4001, "message": "系统配置未加载，请检查网络或重启"}

        # 1. OCR 识别
        ocr_text = self._ocr(image_path)
        if not ocr_text:
            return {"code": 5001, "message": "OCR识别失败，请确保图片清晰"}

        # 2. 数据清洗 (利用通义千问将文本转 JSON)
        clean_data = self._clean_data(ocr_text)
        if not clean_data:
            return {"code": 5002, "message": "未能识别出有效指标，请重拍"}

        # 3. 双模型解读 + 4. 合成 (简化流程，提高速度)
        # 直接让合成模块读取 clean_data
        final_result = self._synthesize_direct(clean_data)

        return {
            "code": 200,
            "data": {
                "items": clean_data,
                "result": final_result
            }
        }

    def _ocr(self, path):
        try:
            config = open_api_models.Config(
                access_key_id=self.ak_id,
                access_key_secret=self.ak_secret
            )
            config.endpoint = self.endpoint
            config.read_timeout = 15000  # 15秒超时
            client = OcrClient(config)

            with open(path, 'rb') as f:
                req = ocr_models.RecognizeAdvancedRequest(
                    body=f,
                    need_rotate=True,
                    need_sort_page=True,
                    output_char_info=False
                )
                runtime = util_models.RuntimeOptions()
                resp = client.recognize_advanced_with_options(req, runtime)

                if resp.body.data:
                    data = json.loads(resp.body.data)
                    return data.get('content', '')
                return None
        except Exception as e:
            print(f"[Service] OCR Exception: {e}")
            return None

    def _clean_data(self, text):
        """调用通义千问清洗数据"""
        prompt = f"""
        任务：将OCR识别的化验单文本转换为标准JSON数组。
        规则：
        1. 提取核心字段：item_name(项目名), result_value(数值), unit(单位), abnormal_flag(异常箭头)。
        2. 自动修复OCR错误（如将 '白 细 胞' 合并为 '白细胞'）。
        3. 仅输出JSON数组，不要Markdown标记。

        【文本】：{text}
        """
        res = self._chat_tongyi(prompt)
        try:
            # 简单清洗 markdown
            clean = res.replace('```json', '').replace('```', '').strip()
            # 截取 [ ... ]
            s = clean.find('[')
            e = clean.rfind(']')
            if s != -1 and e != -1:
                return json.loads(clean[s:e + 1])
            return json.loads(clean)  # 尝试直接解析
        except:
            return []

    def _synthesize_direct(self, data_json):
        """直接调用大模型生成最终会诊意见"""
        data_str = json.dumps(data_json, ensure_ascii=False)
        prompt = f"""
        你是一名经验丰富的全科医生。请根据这份化验单数据，出具一份通俗易懂的会诊报告。

        【化验单数据】：{data_str}

        【输出要求】：
        请严格直接输出以下 JSON 格式（不要废话）：
        {{
            "core_conclusion": "此处写一句话的核心结论（例如：您的血常规大致正常，无需担心）。",
            "abnormal_analysis": "此处解释异常项（例如：白细胞偏高可能提示轻微炎症），若无异常则写无。",
            "life_advice": "此处写3条简短的生活建议，用分号分隔。"
        }}
        """
        # 优先尝试 DeepSeek (分析能力强)，如果失败降级到 Tongyi
        res_ds = self._chat_deepseek(prompt)
        if res_ds: return res_ds

        res_ty = self._chat_tongyi(prompt)
        try:
            clean = res_ty.replace('```json', '').replace('```', '').strip()
            return json.loads(clean)
        except:
            return {
                "core_conclusion": "解读生成异常",
                "abnormal_analysis": "AI 响应格式错误",
                "life_advice": "请咨询线下医生"
            }

    def _chat_deepseek(self, prompt):
        try:
            url = "https://api.deepseek.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.ds_key}"}
            data = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}  # 强制 JSON
            }
            resp = requests.post(url, json=data, headers=headers, timeout=20).json()
            return json.loads(resp['choices'][0]['message']['content'])
        except Exception as e:
            print(f"[Service] DeepSeek Fail: {e}")
            return None

    def _chat_tongyi(self, prompt):
        try:
            url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
            headers = {"Authorization": f"Bearer {self.ty_key}"}
            data = {
                "model": "qwen-turbo",
                "input": {"messages": [{"role": "user", "content": prompt}]},
                "parameters": {"result_format": "message"}
            }
            resp = requests.post(url, json=data, headers=headers, timeout=20).json()
            return resp['output']['choices'][0]['message']['content']
        except Exception as e:
            print(f"[Service] Tongyi Fail: {e}")
            return ""