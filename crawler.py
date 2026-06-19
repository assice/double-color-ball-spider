import os
import csv
import re
import requests
from bs4 import BeautifulSoup
from config_manager import load_config
from prize_checker import check_prize
from wechat_push import send_wechat_message

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, 'data')
CSV_PATH = os.path.join(DATA_DIR, 'ssq_history.csv')
os.makedirs(DATA_DIR, exist_ok=True)

# 硬编码的最新几期（作为最后保底）
FALLBACK_DATA = [
    {'期号': '2026069', '开奖日期': '2026-06-18(四)', '红球': '12,14,16,17,18,32', '蓝球': '08'},
    {'期号': '2026068', '开奖日期': '2026-06-16(二)', '红球': '03,05,16,18,29,32', '蓝球': '04'},
    {'期号': '2026067', '开奖日期': '2026-06-14(日)', '红球': '04,19,27,29,30,32', '蓝球': '13'},
]


def fetch_from_third_party():
    """
    使用第三方 API 获取最新双色球数据
    可配置环境变量 THIRD_PARTY_API_URL 和 API_KEY
    """
    api_url = os.environ.get('THIRD_PARTY_API_URL', '')
    api_key = os.environ.get('THIRD_PARTY_API_KEY', '')
    if not api_url:
        return None
    try:
        params = {'key': api_key} if api_key else {}
        resp = requests.get(api_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # 假设返回格式为 { "code": 200, "data": { "expect": "2026069", "number": "12 14 16 17 18 32 08" } }
        if data.get('code') == 200 and 'data' in data:
            item = data['data']
            numbers = item.get('number', '').split()
            if len(numbers) >= 7:
                return [{
                    '期号': item.get('expect', ''),
                    '开奖日期': item.get('opendate', ''),
                    '红球': ','.join(numbers[:6]),
                    '蓝球': numbers[6]
                }]
        return None
    except Exception as e:
        print(f"⚠️ 第三方 API 请求失败: {e}")
        return None


def fetch_from_html():
    """
    从官网 HTML 解析数据（可能被 403，但保留）
    """
    url = "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        html = resp.text
    except Exception as e:
        print(f"❌ 官网页面获取失败: {e}")
        return None

    soup = BeautifulSoup(html, 'html.parser')
    results = []
    rows = soup.find_all('tr')
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 3:
            continue
        period_text = cells[0].get_text(strip=True)
        period_match = re.search(r'(\d{7})', period_text)
        if not period_match:
            continue
        period = period_match.group(1)
        date = cells[1].get_text(strip=True)
        numbers_text = cells[2].get_text(strip=True)
        numbers = re.findall(r'\d+', numbers_text)
        if len(numbers) >= 7:
            results.append({
                '期号': period,
                '开奖日期': date,
                '红球': ','.join(numbers[:6]),
                '蓝球': numbers[6]
            })
    return results if results else None


def fetch_all_data():
    """
    获取数据：优先第三方 API，其次官网 HTML，最后硬编码后备
    """
    # 1. 尝试第三方 API
    data = fetch_from_third_party()
    if data:
        print(f"✅ 使用第三方 API 获取到 {len(data)} 条记录")
        return data

    # 2. 尝试官网 HTML
    data = fetch_from_html()
    if data:
        print(f"✅ 从官网 HTML 解析到 {len(data)} 条记录")
        return data

    # 3. 使用硬编码后备
    print("⚠️ 所有数据源失败，使用硬编码后备数据")
    return FALLBACK_DATA


def ensure_latest():
    """确保 CSV 包含最新数据"""
    print("🔍 开始检查最新数据...")

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
        print("📂 CSV 不存在，将创建新文件")

    all_data = fetch_all_data()
    if not all_data:
        print("❌ 未能获取任何数据")
        return False

    new_count = 0
    for item in all_data:
        if item['期号'] not in existing:
            existing[item['期号']] = item
            new_count += 1

    if new_count == 0:
        print("ℹ️ 无新数据需要更新")
        return False

    sorted_data = sorted(existing.values(), key=lambda x: int(x['期号']), reverse=True)

    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['期号', '开奖日期', '红球', '蓝球'])
        writer.writeheader()
        writer.writerows(sorted_data)

    print(f"✅ 已更新 CSV，新增 {new_count} 条，总计 {len(sorted_data)} 条，最新期号：{sorted_data[0]['期号']}")

    # 中奖检测（检测所有新增）
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
