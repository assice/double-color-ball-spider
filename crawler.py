import os
import csv
import requests
from config_manager import load_config
from prize_checker import check_prize
from wechat_push import send_wechat_message

# ==================== 配置 ====================
API_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, 'data')
CSV_PATH = os.path.join(DATA_DIR, 'ssq_history.csv')
os.makedirs(DATA_DIR, exist_ok=True)

# ==================== 核心爬取函数 ====================
def fetch_new_data(existing_periods, pages=3, page_size=30):
    """
    从官网获取数据，只返回不在 existing_periods 中的新数据
    :param existing_periods: 已有期号集合
    :param pages: 爬取多少页
    :param page_size: 每页多少条
    :return: 新数据列表，每条为 dict{期号, 开奖日期, 红球, 蓝球}
    """
    new_items = []
    for page in range(1, pages + 1):
        params = {
            'name': 'ssq',
            'pageNo': page,
            'pageSize': page_size,
            'systemType': 'PC'
        }
        try:
            resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data and 'result' in data and isinstance(data['result'], list):
                for item in data['result']:
                    period = item.get('code', '').strip()
                    if period in existing_periods:
                        continue
                    new_items.append({
                        '期号': period,
                        '开奖日期': item.get('date', '').strip(),
                        '红球': item.get('red', '').strip(),
                        '蓝球': item.get('blue', '').strip()
                    })
                # 如果这一页全部已存在，可以提前终止（因为后面更旧的期号更可能已存在）
                # 但为了保险，我们继续请求下一页（最多pages页）
                print(f"第 {page} 页获取 {len(data['result'])} 条，累计新增 {len(new_items)} 条")
            else:
                break
        except Exception as e:
            print(f"爬取第 {page} 页失败: {e}")
            break
    return new_items

def update_csv():
    """
    增量更新CSV文件：
    1. 读取已有期号
    2. 爬取新数据
    3. 追加到CSV
    4. 检测新数据中的中奖情况并推送微信通知
    """
    # 1. 读取已有期号
    existing = set()
    if os.path.isfile(CSV_PATH):
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('期号'):
                    existing.add(row['期号'].strip())
    print(f"已有 {len(existing)} 期记录")

    # 2. 爬取新数据
    new_items = fetch_new_data(existing, pages=3, page_size=30)
    if not new_items:
        print("无新数据需要更新")
        return

    # 3. 追加到CSV
    file_exists = os.path.isfile(CSV_PATH)
    with open(CSV_PATH, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['期号', '开奖日期', '红球', '蓝球'])
        if not file_exists:
            writer.writeheader()
        for item in new_items:
            writer.writerow(item)
    print(f"新增 {len(new_items)} 条数据")

    # 4. 检测中奖并推送微信通知
    # 读取用户当前配置的号码
    cfg = load_config()
    reds_str = cfg.get('reds', '')
    blue_str = cfg.get('blue', '')
    multiplier = int(cfg.get('multiplier', 2))

    my_reds = [r.strip() for r in reds_str.split() if r.strip()]
    my_blue = blue_str.strip()
    my_reds_set = set(my_reds)

    if not my_reds or not my_blue:
        print("⚠️ 未配置自选号码，跳过中奖检测")
        return

    # 检测每条新数据
    prize_messages = []
    for item in new_items:
        prize_level, prize_amount = check_prize(my_reds_set, my_blue, item['红球'], item['蓝球'])
        if prize_level:
            # 根据奖金类型构造显示
            if prize_amount == '浮动':
                amount_display = '浮动奖金'
            elif isinstance(prize_amount, int):
                # 单注奖金，乘以倍数
                total = prize_amount * multiplier
                amount_display = f"{total} 元 (单注 {prize_amount} 元 × {multiplier}倍)"
            else:
                amount_display = str(prize_amount)
            msg = (f"🎉 期号：{item['期号']}\n"
                   f"开奖日期：{item['开奖日期']}\n"
                   f"奖级：{prize_level}\n"
                   f"奖金：{amount_display}")
            prize_messages.append(msg)

    # 发送通知
    if prize_messages:
        title = "🎊 双色球中奖提醒！"
        # 用 <br> 拼接多条消息（PushPlus 支持 HTML）
        content = "<br><br>".join(prize_messages)
        send_wechat_message(title, content)
    else:
        print("本次更新无中奖记录")

def load_all_data():
    """从CSV加载全部数据"""
    data = []
    if not os.path.isfile(CSV_PATH):
        return data
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('期号') and row.get('红球'):
                data.append(row)
    return data

# 独立运行测试
if __name__ == '__main__':
    print("开始更新数据...")
    update_csv()
    print("更新完成")