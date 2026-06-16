<<<<<<< HEAD
import os
import requests

# 从环境变量读取 Token（Render 上配置）
PUSHPLUS_TOKEN = os.environ.get('PUSHPLUS_TOKEN', '')  # 如果没有设置，留空
PUSHPLUS_TOPIC = os.environ.get('PUSHPLUS_TOPIC', '')  # 群组编码，可选

def send_wechat_message(title, content):
    if not PUSHPLUS_TOKEN:
        print("⚠️ 未配置 PUSHPLUS_TOKEN，无法发送微信通知")
        return
    url = "http://www.pushplus.plus/send"
=======
# wechat_push.py
import requests

# --- 配置区域 ---
# 在这里填写你在 PushPlus 官网获取的 Token
PUSHPLUS_TOKEN = ""
# 如果你想推送到群组，在这里填写群组编码，否则留空
PUSHPLUS_TOPIC = "" 

def send_wechat_message(title, content):
    """
    通过 PushPlus 发送消息到微信
    :param title: 消息标题
    :param content: 消息内容，支持 HTML 格式
    """
    url = "http://www.pushplus.plus/send" # 发送接口地址[reference:12]
    
>>>>>>> 15c5fb7fa8a7221c213d18dbd72f22a56059cef6
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
<<<<<<< HEAD
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
=======
        "template": "html" # 使用 HTML 模板，让内容排版更好看[reference:13]
    }
    
    # 如果配置了群组编码，则添加到请求中
    if PUSHPLUS_TOPIC:
        data["topic"] = PUSHPLUS_TOPIC

    try:
        response = requests.post(url, json=data) # 使用 JSON 格式发送[reference:14]
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 200:
                print("✅ 微信通知发送成功！")
            else:
                print(f"❌ 微信通知发送失败：{result.get('msg')}")
        else:
            print(f"❌ 微信通知发送失败，HTTP状态码：{response.status_code}")
    except Exception as e:
        print(f"❌ 发送微信通知时发生错误：{e}")

# 一个小示例，用于测试
if __name__ == '__main__':
    send_wechat_message("测试消息", "Hello, 这是一条来自 Python 的测试通知！")
>>>>>>> 15c5fb7fa8a7221c213d18dbd72f22a56059cef6
