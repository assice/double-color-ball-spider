import os
import csv
import re
import requests
from config_manager import load_config
from prize_checker import check_prize
from wechat_push import send_wechat_message

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, 'data')
CSV_PATH = os.path.join(DATA_DIR, 'ssq_history.csv')
os.makedirs(DATA_DIR, exist_ok=True)


def fetch_from_html():
    """
    从 https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/ 解析所有开奖数据
    正则匹配每一行表格数据，格式：2026069 | 2026-06-18(四) | 12 14 16 17 18 32 8
    返回列表，每条记录包含 期号、开奖日期、红球、蓝球
    """
    url = "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        print("🔄 正在从 HTML 页面获取数据...")
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        html = resp.text
        print(f"📄 页面获取成功，大小: {len(html)} 字节")
    except Exception as e:
        print(f"❌ 获取页面失败: {e}")
        return []

    # 匹配表格行：期号 | 日期 | 号码（空格分隔）
    # 示例：2026069 | 2026-06-18(四) | 12 14 16 17 18 32 8 |
    pattern = r'(\d{7})\s*\|\s*([^|]+)\s*\|\s*([\d\s]+)\s*\|'
    matches = re.findall(pattern, html)

    print(f"🔍 正则匹配到 {len(matches)} 行数据")

    results = []
    for match in matches:
        period = match[0].strip()
        date = match[1].strip()
        numbers = match[2].strip().split()

        if len(numbers) >= 7:
            reds = ','.join(numbers[:6])
            blue = numbers[6]
            results.append({
                '期号': period,
                '开奖日期': date,
                '红球': reds,
                '蓝球': blue
            })
        else:
            print(f"⚠️ 跳过异常行: 期号={period}, 号码数量={len(numbers)}")

    print(f"✅ 从 HTML 解析到 {len(results)} 条记录")
    if results:
        print(f"📌 最新期号: {results[0]['期号']}")
    return results


def ensure_latest():
    """确保 CSV 包含最新数据（从 HTML 解析 + 去重 + 排序）"""
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
        print("📂 CSV 文件不存在，将创建新文件")

    all_data = fetch_from_html()
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

    # 中奖检测
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