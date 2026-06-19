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
    从 https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/ 解析开奖数据
    更健壮的匹配：查找包含 7 位数字（期号）和至少 7 个数字（号码）的行
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

    results = []

    # 方法：在页面中查找所有包含 7 位数字的行
    # 匹配模式：7位数字（期号） + 日期（含括号） + 至少7个数字（号码）
    # 使用更灵活的正则
    pattern = r'(\d{7})\s*[|｜]\s*([^|｜]+)\s*[|｜]\s*([\d\s]+)'
    matches = re.findall(pattern, html)
    print(f"🔍 模式1匹配到 {len(matches)} 行")

    for match in matches:
        period = match[0].strip()
        date = match[1].strip()
        numbers_str = match[2].strip()
        # 提取所有数字
        numbers = re.findall(r'\d+', numbers_str)
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
            print(f"⚠️ 跳过 {period}: 号码数量不足 ({len(numbers)})")

    # 如果上面没匹配到，尝试更宽松的匹配（忽略分隔符）
    if not results:
        print("🔄 尝试备用匹配模式...")
        # 匹配期号 + 日期 + 一串数字（至少7个）
        pattern2 = r'(\d{7})\s*[|｜]?\s*([^|｜]+?)\s*[|｜]?\s*((?:\d+\s*){7,})'
        matches2 = re.findall(pattern2, html)
        print(f"🔍 模式2匹配到 {len(matches2)} 行")
        for match in matches2:
            period = match[0].strip()
            date = match[1].strip()
            numbers = re.findall(r'\d+', match[2])
            if len(numbers) >= 7:
                reds = ','.join(numbers[:6])
                blue = numbers[6]
                results.append({
                    '期号': period,
                    '开奖日期': date,
                    '红球': reds,
                    '蓝球': blue
                })

    # 最后，如果还没有数据，直接按行解析
    if not results:
        print("🔄 尝试按行解析...")
        lines = html.split('\n')
        for line in lines:
            # 查找包含 7 位数字的行，且该行后面有多个数字
            if re.search(r'\d{7}', line):
                # 提取所有数字
                all_nums = re.findall(r'\d+', line)
                if len(all_nums) >= 8:  # 7位期号 + 至少7个号码
                    period = all_nums[0]
                    # 尝试提取日期（包含中文括号）
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2}\(.)', line)
                    date = date_match.group(1) if date_match else ''
                    # 号码从第2个数字开始
                    nums = all_nums[1:]
                    if len(nums) >= 7:
                        reds = ','.join(nums[:6])
                        blue = nums[6]
                        results.append({
                            '期号': period,
                            '开奖日期': date,
                            '红球': reds,
                            '蓝球': blue
                        })

    print(f"✅ 总共解析到 {len(results)} 条记录")
    if results:
        print(f"📌 最新期号: {results[0]['期号'] if results else '无'}")
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
            if item['期号'] not in existing:
                continue  # 只检测新增的
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