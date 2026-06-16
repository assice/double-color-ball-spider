import os
import requests

# 从环境变量读取 Token（Render 上配置）
PUSHPLUS_TOKEN = os.environ.get('PUSHPLUS_TOKEN', '')
PUSHPLUS_TOPIC = os.environ.get('PUSHPLUS_TOPIC', '')

def send_wechat_message(title, content):
    """
    通过 PushPlus 发送消息到微信
    :param title: 消息标题
    :param content: 消息内容，支持 HTML 格式
    """
    if not PUSHPLUS_TOKEN:
        print("⚠️ 未配置 PUSHPLUS_TOKEN，无法发送微信通知")
        return

    url = "http://www.pushplus.plus/send"
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "html"
    }
    if PUSHPLUS_TOPIC:
        data["topic"] = PUSHPLUS_TOPIC

    try:
        resp = requests.post(url, json=data, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            if result.get('code') == 200:
                print("✅ 微信通知发送成功")
            else:
                print(f"❌ 微信通知发送失败：{result.get('msg')}")
        else:
            print(f"❌ 微信通知发送失败，HTTP {resp.status_code}")
    except Exception as e:
        print(f"❌ 发送微信通知异常：{e}")

# 测试用
if __name__ == '__main__':
    send_wechat_message("测试消息", "Hello, 这是一条来自 Python 的测试通知！")