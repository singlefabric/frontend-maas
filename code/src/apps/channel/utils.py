import requests
import json
from requests_toolbelt.multipart.encoder import MultipartEncoder

class AIClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

    def chat_completion(self, url, model, messages, stream=True):
        """文本生成"""
        # url = "https://openapi.coreshub.cn/v1/chat/completions"
        data = {
            "model": model,
            "stream": stream,
            "messages": messages
        }
        return self._make_json_request(url, data)

    def text_to_speech(self, url, model, text, voice, output_file=None):
        """文本转语音"""

        # url = "https://openapi.coreshub.cn/v1/audio/speech"
        data = {
            "model": model,
            "input": text,
            "voice": voice
        }
        return self._make_form_request(url, data)

    def speech_to_text(self, url, model, audio_file):
        """语音转文本"""
        # url = "https://openapi.coreshub.cn/v1/audio/transcriptions"
        return self._make_multipart_request(url, audio_file, {"model": model})

    def text_embedding(self, url, model, input_text):
        """文本嵌入"""
        # url = "https://openapi.coreshub.cn/v1/embeddings"
        data = {
            "model": model,
            "input": input_text
        }
        return self._make_json_request(url, data)

    def text_rerank(self, url, model, query, documents, top_n=2):
        """文本重排序"""
        # url = "https://openapi.coreshub.cn/v1/rerank"
        data = {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": top_n
        }
        return self._make_json_request(url, data)

    def _make_json_request(self, url, data, auth=True):
        headers = self.base_headers.copy() if auth else {}
        headers["Content-Type"] = "application/json"
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return True, response.status_code
        except requests.exceptions.RequestException as e:
            return False, response.status_code if hasattr(e.response, 'status_code') else str(e)

    def _make_form_request(self, url, data):
        headers = self.base_headers.copy()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            return True, response.status_code
        except requests.exceptions.RequestException as e:
            return False, response.status_code if hasattr(e.response, 'status_code') else str(e)

    def _make_multipart_request(self, url, file_path, data):
        headers = self.base_headers.copy()
        multipart_data = MultipartEncoder(
            fields={
                'file': (file_path, open(file_path, 'rb'), 'audio/wav'),
                **data
            }
        )
        headers["Content-Type"] = multipart_data.content_type
        try:
            response = requests.post(url, headers=headers, data=multipart_data)
            response.raise_for_status()
            return True, response.status_code
        except requests.exceptions.RequestException as e:
            return False, response.status_code if hasattr(e.response, 'status_code') else str(e)

    def _download_file(self, url, data, output_file):
        headers = self.base_headers.copy()
        headers["Content-Type"] = "application/json"
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            with open(output_file, 'wb') as f:
                f.write(response.content)
            return True, response.status_code
        except requests.exceptions.RequestException as e:
            return False, response.status_code if hasattr(e.response, 'status_code') else str(e)
