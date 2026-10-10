import requests
import time
import subprocess

import base64
import os
from typing import Optional, Union


def image_to_base64(path):
    # 调试：输出当前工作目录和文件路径
    # print(f"[DEBUG] Current working directory: {os.getcwd()}")
    # print(f"[DEBUG] Trying to open: {path}")
    # print(f"[DEBUG] File exists: {os.path.exists(path)}")
    
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def get_windows_ip():
    # Get default gateway, which is typically the Windows host IP
    result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if line.startswith('default'):
            return line.split()[2]
    return None

class OllamaLib:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.win_ip = get_windows_ip()

    def llm_call(self, sys_prompt: str, usr_prompt: str):
        url = f"http://{self.win_ip}:11434/v1/chat/completions"

        headers = {
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": usr_prompt}
            ]
        }

        response = requests.post(url, json=data, headers=headers)
        # print(response.json())

        return response.json() 
    

    def image_llm_call(self, image_path: str, sys_prompt: str, usr_prompt: str):
        image_b64 = image_to_base64(image_path)

        url = f"http://{self.win_ip}:11434/api/chat"

        headers = {
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": sys_prompt
                },
                {
                    "role": "user",
                    "content": usr_prompt,
                    "images": [image_b64]
                }
            ],
            "stream": False
        }

        response = requests.post(url, json=payload, headers=headers)
        # print(response.json())

        return response.json()


def ollama_llm(
    sys_prompt: str,
    usr_prompt: str,
    think: bool = True,
    keep_alive: Optional[Union[int, str]] = None,
):
    win_ip = get_windows_ip()

    url = f"http://{win_ip}:11434/api/chat"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "model": "qwen3-vl:8b",
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": usr_prompt}
        ],
        "think": think,
        "stream": False
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    response = requests.post(url, json=payload, headers=headers)
    # print(response.json())

    return response.json()  # Return the JSON response for further processing if needed


def ollama_multi_modal_llm(
    image_path: str,
    sys_prompt: str,
    usr_prompt: str,
    keep_alive: Optional[Union[int, str]] = None,
):
    win_ip = get_windows_ip()

    # print(image_path)
    image_b64 = image_to_base64(image_path)
    # print(" Image converted to base64, length:", len(image_b64))

    url = f"http://{win_ip}:11434/api/chat"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        # "model": "ministral-3:14b",
        # "model": "qwen2.5vl:72b",   # or qwen2.5-vl:7b / 
        "model": "qwen3-vl:8b",
        "messages": [
            {
                "role": "system",
                "content": sys_prompt
            },
            {
                "role": "user",
                "content": usr_prompt,
                "images": [image_b64]
            }
        ],
        "stream": False
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    # print(win_ip, image_path)
    response = requests.post(url, json=payload, headers=headers)
    # print(response)
    # print(f"LLM response: {response}")
    # print(response.json())
    # 输出结果
    # print(response.json()["response"])

    return response.json()  # Return the JSON response for further processing if needed