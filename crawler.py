import os
import csv
import requests
from config_manager import load_config
from prize_checker import check_prize
from wechat_push import send_wechat_message

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, 'data')
CSV_PATH = os.path.join(DATA_DIR, 'ssq_history.csv')
os.makedirs(DATA_DIR, exist_ok=True)

def fetch_from_api():
    """
    使用官方 API 获取双色球历史数据
    关键：必须包含 issueCount 参数，否则只返回缓存旧数据
    """
    url = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
    params = {
        "name": "ssq",
        "issueCount": 100,      # 必须！否则只返回旧数据
        "pageNo": 1,
        "pageSize": 100,
        "systemType": "PC"
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.cwl.gov.cn/',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    try:
        print("🔄 正在从 API 获取数据...")
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get('state') == 0 and 'result' in data:
            results = []
            for item in data['result']:
                # 兼容字段名：date 或 openTime
                date = item.get('date') or item.get('openTime', '')
                results.append({
                    '期号': str(item.get('code', '')).strip(),
                    '开奖日期': str(date).strip(),
                    '红球': str(item.get('red', '')).strip(),
                    '蓝球': str(item.get('blue', '')).strip()
                })
            print(f"✅ API 获取到 {len(results)} 条记录")
            return results
        else:
            print(f"⚠️ API 返回异常: {data.get('message', '未知错误')}")
            return []
    except Exception as e:
        print(f"❌ API 请求失败: {e}")
        return []

def ensure_latest():
    """确保 CSV 包含最新数据（去重 + 排序）"""
    print("🔍 开始检查最新数据...")
    
    # 读取已有数据（兼容旧表头）
    existing = {}
    if os.path.isfile(CSV_PATH):
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('期号'):
                    existing[row['期号'].strip()] = {
                        '期号': row['期号'].strip(),
                        '开奖日期': row.get('开奖日期', '').strip(),
                        '红球': row.get('红球', '').strip(),
                        '蓝球': row.get('蓝球', '').strip()
                    }
        print(f"📂 已有 {len(existing)} 期记录")
    else:
        print("📂 CSV 文件不存在，将创建新文件")

    # 从 API 获取数据
    all_data = fetch_from_api()
    if not all_data:
        print("❌ 未能获取任何数据")
        return False

    # 合并数据（去重）
    new_count = 0
    for item in all_data:
        if item['期号'] not in existing:
            existing[item['期号']] = item
            new_count += 1

    if new_count == 0:
        print("ℹ️ 无新数据需要更新")
        return False

    # 按期号降序排序（最新在前）
    sorted_data = sorted(existing.values(), key=lambda x: int(x['期号']), reverse=True)

    # 重新写入 CSV（只写 4 列，覆盖旧文件，消除表头污染）
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['期号', '开奖日期', '红球', '蓝球'])
        writer.writeheader()
        writer.writerows(sorted_data)

    print(f"✅ 已更新 CSV，新增 {new_count} 条，总计 {len(sorted_data)} 条，最新期号：{sorted_data[0]['期号']}")

    # 中奖检测（只检测新增的）
    cfg = load_config()
    reds_str = cfg.get('reds', '')
    blue_str = cfg.get('blue', '')
    multiplier = int(cfg.get('multiplier', 2))

    my_reds = [r.strip() for r in reds_str.split() if r.strip()]
    my_blue = blue_str.strip()
    my_reds_set = set(my_reds)

    if my_reds and my_blue:
        prize_messages = []
        for item in all_data:
            if item['期号'] in existing:
                prize_level, prize_amount = check_prize(my_reds_set, my_blue, item['红球'], item['蓝球'])
                if prize_level:
                    if prize_amount == '浮动':
                        amount_display = '浮动奖金'
                    elif isinstance(prize_amount, int):
                        total = prize_amount * multiplier
                        amount_display = f"{total} 元 (单注 {prize_amount} 元 × {multiplier}倍)"
                    else:
                        amount_display = str(prize_amount)
                    msg = (f"🎉 期号：{item['期号']}\n"
                           f"开奖日期：{item['开奖日期']}\n"
                           f"奖级：{prize_level}\n"
                           f"奖金：{amount_display}")
                    prize_messages.append(msg)

        if prize_messages:
            title = "🎊 双色球中奖提醒！"
            content = "<br><br>".join(prize_messages)
            send_wechat_message(title, content)
            print(f"✅ 已发送 {len(prize_messages)} 条中奖通知")

    return True

def update_csv():
    return ensure_latest()

def load_all_data():
    data = []
    if not os.path.isfile(CSV_PATH):
        return data
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('期号') and row.get('红球'):
                data.append({
                    '期号': row['期号'].strip(),
                    '开奖日期': row.get('开奖日期', '').strip(),
                    '红球': row.get('红球', '').strip(),
                    '蓝球': row.get('蓝球', '').strip()
                })
    return data

if __name__ == '__main__':
    print("🚀 开始更新数据...")
    ensure_latest()
    print("✅ 更新完成")