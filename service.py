# -*- coding: utf-8 -*-
import os
import json
import configparser
import requests
import base64
import uuid
from datetime import datetime


class MedicalService:
    def __init__(self, config_path='config.ini'):
        self.config_ready = False
        self.ak_id = ""
        self.ak_secret = ""
        self.ds_key = ""
        self.ty_key = ""

        # 读取配置，使用绝对路径确保安全
        conf_dir = os.path.dirname(os.path.abspath(__file__))
        full_config_path = os.path.join(conf_dir, config_path)

        if os.path.exists(full_config_path):
            try:
                conf = configparser.ConfigParser()
                conf.read(full_config_path, encoding='utf-8')
                self.ak_id = conf.get('aliyun', 'access_key_id')
                self.ak_secret = conf.get('aliyun', 'access_key_secret')
                self.ds_key = conf.get('llm', 'deepseek_key')
                self.ty_key = conf.get('llm', 'tongyi_key')
                self.config_ready = True
            except Exception as e:
                print(f"[Service] Config Load Error: {e}")

    def process(self, image_path):
        if not self.config_ready:
            return {"code": 4001, "message": "系统配置未加载"}

        # 优先使用通义千问 VL (日志显示 OCR 签名有误，而 VL 成功返回)
        ocr_content = self._ocr_by_tongyi_vl(image_path)

        if not ocr_content:
            return {"code": 5001, "message": "图片识别失败，请检查网络或Key"}

        # AI 智能分析
        final_result = self._analyze_with_ai(ocr_content)

        return {
            "code": 200,
            "data": {
                "items": [],
                "result": final_result
            }
        }

    def _ocr_by_tongyi_vl(self, image_path):
        """
        使用通义千问 VL 模型直接读取图片文字
        """
        try:
            with open(image_path, 'rb') as f:
                img_b64 = base64.b64encode(f.read()).decode('utf-8')

            url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
            headers = {
                "Authorization": f"Bearer {self.ty_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": "qwen-vl-max",
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"image": f"data:image/jpeg;base64,{img_b64}"},
                                {"text": "请把这张化验单里的所有文字完整提取出来，按行显示。"}
                            ]
                        }
                    ]
                }
            }

            resp = requests.post(url, json=data, headers=headers, timeout=30)
            res_json = resp.json()

            if 'output' in res_json and 'choices' in res_json['output']:
                return res_json['output']['choices'][0]['message']['content'][0]['text']
            else:
                print(f"VL Error: {res_json}")
                return None
        except Exception as e:
            print(f"VL Request Error: {e}")
            return None

    def _analyze_with_ai(self, text):
        """纯文本解读"""
        prompt = f"""
        你是一位医生。基于以下化验单文本，生成一份JSON报告。
        【文本】：{text}

        【输出格式 JSON】：
        {{
            "core_conclusion": "一句话核心结论",
            "abnormal_analysis": "异常指标分析",
            "life_advice": "3条生活建议"
        }}
        仅返回JSON，不要包含markdown标记。
        """
        try:
            url = "https://api.deepseek.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.ds_key}"}
            data = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}
            }
            resp = requests.post(url, json=data, headers=headers, timeout=20).json()

            content = resp['choices'][0]['message']['content']

            # --- 关键修复：清洗 Markdown 标记 ---
            if "```" in content:
                content = content.replace("```json", "").replace("```", "").strip()

            return json.loads(content)
        except Exception as e:
            print(f"[Service] AI Error: {e}")
            return {
                "core_conclusion": "报告生成异常",
                "abnormal_analysis": "AI 解析失败，请重试",
                "life_advice": "建议咨询医生"
            }