import requests
import time
import subprocess

import base64


def image_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def get_windows_ip():
    # Get default gateway, which is typically the Windows host IP
    result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if line.startswith('default'):
            return line.split()[2]
    return None




def call_ollama(model_name, messages, tools=None):
    windows_ip = get_windows_ip()
    # print(windows_ip)
    url = f"http://{windows_ip}:11434/v1/chat/completions"


    response = requests.post(
        url,
        json={
            "model": model_name,
            "messages": messages,
            "tools": tools,
            "temperature": 0
        }
    )
    return response.json()["choices"][0]["message"]["content"]