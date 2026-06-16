# crawler.py
# ... 其他导入 ...
from wechat_push import send_wechat_message
import os
import csv
import requests

API_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, 'data')
CSV_PATH = os.path.join(DATA_DIR, 'ssq_history.csv')
os.makedirs(DATA_DIR, exist_ok=True)

def fetch_new_data(existing_periods, pages=3, page_size=30):
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
            if data and 'result' in data:
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
            else:
                break
        except Exception as e:
            print(f"爬取第 {page} 页失败: {e}")
            break
    return new_items

def update_csv():
    existing = set()
    if os.path.isfile(CSV_PATH):
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('期号'):
                    existing.add(row['期号'].strip())
    new_items = fetch_new_data(existing)
    if new_items:
        file_exists = os.path.isfile(CSV_PATH)
        with open(CSV_PATH, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['期号', '开奖日期', '红球', '蓝球'])
            if not file_exists:
                writer.writeheader()
            for item in new_items:
                writer.writerow(item)
        print(f"新增 {len(new_items)} 条数据")
    else:
        print("无新数据")

def load_all_data():
    data = []
    if not os.path.isfile(CSV_PATH):
        return data
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('期号') and row.get('红球'):
                data.append(row)
    return data
