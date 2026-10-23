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


# =========================================================
# Ollama 多服务配置（双 GPU / 双端口）
#   - VLM  (olmocr2)         -> 11434 / GPU-9cf7...  (Windows 开机自启的默认端口)
#   - 文本 (qwen2.5:7b)      -> 11435 / GPU-99ac...  (由本脚本按需拉起)
# 绑定 0.0.0.0，使 WSL 侧可通过网关 IP 访问。
# =========================================================
OLLAMA_EXE = r"C:\Users\hubo\AppData\Local\Programs\Ollama\ollama.exe"

VLM_PORT = 11434
VLM_GPU_UUID = "GPU-9cf732f2-cba8-43ba-aad8-837fea7ed344"

LLM_PORT = 11435
LLM_GPU_UUID = "GPU-99ac530d-4a7f-f493-8166-7148920ab855"


def _service_up(port, timeout=2.0):
    """探测指定端口的 Ollama 是否已响应。"""
    win_ip = get_windows_ip()
    try:
        r = requests.get(f"http://{win_ip}:{port}/api/version", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _start_service(port, gpu_uuid):
    """在 Windows 侧通过 powershell 后台拉起一个绑定指定 GPU/端口的 ollama serve。"""
    ps_cmd = (
        f"$env:CUDA_VISIBLE_DEVICES='{gpu_uuid}'; "
        f"$env:OLLAMA_HOST='0.0.0.0:{port}'; "
        f"$env:OLLAMA_MAX_LOADED_MODELS='1'; "
        f"Start-Process -FilePath '{OLLAMA_EXE}' -ArgumentList 'serve' -WindowStyle Hidden"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", ps_cmd],
        capture_output=True, text=True,
    )


def _wait_ready(port, timeout=40.0):
    """轮询等待服务就绪。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _service_up(port):
            return True
        time.sleep(1.0)
    return False


def ensure_ollama_services():
    """确保 VLM(11434) 与 文本(11435) 两个 Ollama 服务都在线。
    已在线则跳过；未在线则按对应 GPU/端口自动拉起并等待就绪。
    返回 {port: status} 便于调用方记录日志。"""
    status = {}
    for port, gpu in ((VLM_PORT, VLM_GPU_UUID), (LLM_PORT, LLM_GPU_UUID)):
        if _service_up(port):
            status[port] = "already-running"
            continue
        print(f"[ollama] port {port} down, starting on GPU {gpu[:12]}...", flush=True)
        try:
            _start_service(port, gpu)
            status[port] = "started" if _wait_ready(port) else "failed"
        except Exception as e:
            status[port] = f"error: {e}"
        print(f"[ollama] port {port}: {status[port]}", flush=True)
    return status

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


def _normalize_generate_response(data):
    """将 /api/generate 的返回 ({"response": ...}) 补一个 message.content 字段，
    以兼容下游读取 response["message"]["content"] 的调用方。"""
    if isinstance(data, dict) and "message" not in data:
        data["message"] = {"role": "assistant", "content": data.get("response", "")}
    return data


def ollama_llm(
    sys_prompt: str,
    usr_prompt: str,
    think: bool = True,
    keep_alive: Optional[Union[int, str]] = None,
):
    """文本分类 LLM：使用 qwen2.5:7b-instruct，/api/chat (messages) 形式。"""
    win_ip = get_windows_ip()

    url = f"http://{win_ip}:{LLM_PORT}/api/chat"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "model": "qwen2.5:7b-instruct",
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": usr_prompt}
        ],
        "stream": False,
        # keep_alive 默认 -1：模型常驻显存不卸载
        "keep_alive": -1 if keep_alive is None else keep_alive
    }

    response = requests.post(url, json=payload, headers=headers)
    # print(response.json())

    return response.json()  # /api/chat 原生返回 {"message": {"content": ...}}


def ollama_multi_modal_llm(
    image_path: str,
    sys_prompt: str,
    usr_prompt: str,
    keep_alive: Optional[Union[int, str]] = None,
):
    """olmocr2 官方 API：使用 /api/generate，图片走 images 字段。
    外部仍分别传入 sys_prompt / usr_prompt，内部拼接为单个 prompt。"""
    win_ip = get_windows_ip()

    image_b64 = image_to_base64(image_path)

    url = f"http://{win_ip}:{VLM_PORT}/api/generate"

    headers = {
        "Content-Type": "application/json"
    }

    prompt = f"{sys_prompt}\n\n{usr_prompt}" if sys_prompt else usr_prompt

    payload = {
        "model": "olmocr2",
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "options": {"num_ctx": 16384},
        # keep_alive 默认 -1：模型常驻显存不卸载
        "keep_alive": -1 if keep_alive is None else keep_alive
    }

    response = requests.post(url, json=payload, headers=headers)

    return _normalize_generate_response(response.json())


# =========================================================
# 以下为原基于 /api/chat (messages) 的实现，保留备份（qwen 后端风格）
# =========================================================
def ollama_llm_qwen_backup(
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
        # "model": "qwen3-vl:8b",
        "model": "olmocr2",
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


def ollama_multi_modal_llm_qwen_backup(
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
        # "model": "qwen3-vl:8b",
        "model": "olmocr2",
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