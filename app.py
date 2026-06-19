import os
import sys
from io import StringIO
from flask import Flask, render_template, request, redirect, url_for
from config_manager import load_config, save_config
from crawler import load_all_data, ensure_latest
from prize_checker import check_prize

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ssq-secret-key-change-in-production'

UPDATE_SECRET_KEY = os.environ.get('UPDATE_SECRET_KEY', 'your_secret_key_here')

def filter_and_calc(cfg):
    ensure_latest()
    all_data = load_all_data()
    if not all_data:
        return [], {}, None

    # 按期号降序排序（确保最新在前）
    all_data.sort(key=lambda x: int(x['期号']), reverse=True)
    latest = all_data[0] if all_data else None

    # 应用筛选条件
    start_period = cfg.get('start_period', '').strip()
    end_period = cfg.get('end_period', '').strip()
    start_date = cfg.get('start_date', '').strip()
    end_date = cfg.get('end_date', '').strip()

    filtered = all_data
    if start_period:
        filtered = [d for d in filtered if d['期号'] >= start_period]
    if end_period:
        filtered = [d for d in filtered if d['期号'] <= end_period]
    if start_date:
        filtered = [d for d in filtered if d['开奖日期'] >= start_date]
    if end_date:
        filtered = [d for d in filtered if d['开奖日期'] <= end_date]

    filtered.sort(key=lambda x: int(x['期号']), reverse=True)

    # 中奖检测
    reds_str = cfg.get('reds', '')
    blue_str = cfg.get('blue', '')
    multiplier = int(cfg.get('multiplier', 2))
    my_reds = [r.strip() for r in reds_str.split() if r.strip()]
    my_blue = blue_str.strip()
    my_reds_set = set(my_reds)

    result_list = []
    prize_stats = {}
    total_prize = 0

    for row in filtered:
        prize_level, prize_amount = check_prize(my_reds_set, my_blue, row['红球'], row['蓝球'])
        row_data = {
            '期号': row['期号'],
            '开奖日期': row['开奖日期'],
            '红球': row['红球'],
            '蓝球': row['蓝球'],
            '奖级': prize_level,
            '奖金': prize_amount
        }
        result_list.append(row_data)

        if prize_level:
            prize_stats[prize_level] = prize_stats.get(prize_level, 0) + 1
            if isinstance(prize_amount, int):
                total_prize += prize_amount * multiplier

    stats = {
        'prize_counts': prize_stats,
        'total_prize': total_prize,
        'multiplier': multiplier,
        'my_numbers': f"{' '.join(my_reds)} + {my_blue}"
    }
    return result_list, stats, latest

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        cfg = {
            'reds': request.form.get('reds', ''),
            'blue': request.form.get('blue', ''),
            'multiplier': request.form.get('multiplier', 2),
            'start_period': request.form.get('start_period', ''),
            'end_period': request.form.get('end_period', ''),
            'start_date': request.form.get('start_date', ''),
            'end_date': request.form.get('end_date', '')
        }
        save_config(cfg)
        return redirect(url_for('index'))

    cfg = load_config()
    results, stats, latest = filter_and_calc(cfg)
    all_data = load_all_data()
    # 修复：使用 max 按数字排序获取最新期号，而不是依赖顺序
    if all_data:
        latest_period = max(all_data, key=lambda x: int(x['期号']))['期号']
    else:
        latest_period = ''
    return render_template('index.html',
                           config=cfg,
                           results=results,
                           stats=stats,
                           latest=latest,
                           latest_period=latest_period)

@app.route('/update')
def manual_update():
    key = request.args.get('key', '')
    if key != UPDATE_SECRET_KEY:
        return "Unauthorized: invalid key", 401

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        result = ensure_latest()
        sys.stdout = old_stdout
        if result:
            return "✅ 数据更新完成，已添加最新期", 200
        else:
            return "✅ 数据更新完成，无新增记录", 200
    except Exception as e:
        sys.stdout = old_stdout
        return f"❌ 更新失败: {str(e)}", 500

@app.route('/rebuild')
def rebuild():
    """强制重建数据：删除旧CSV，重新从API获取并写入"""
    key = request.args.get('key', '')
    if key != UPDATE_SECRET_KEY:
        return "Unauthorized: invalid key", 401
    try:
        import csv
        from crawler import fetch_from_api, CSV_PATH
        if os.path.isfile(CSV_PATH):
            os.remove(CSV_PATH)
            print("🗑️ 已删除旧 CSV")
        all_data = fetch_from_api()
        if not all_data:
            return "❌ 获取数据失败，请稍后重试", 500
        all_data.sort(key=lambda x: int(x['期号']), reverse=True)
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['期号', '开奖日期', '红球', '蓝球'])
            writer.writeheader()
            writer.writerows(all_data)
        return f"✅ 重建完成，共写入 {len(all_data)} 条记录，最新期号：{all_data[0]['期号']}", 200
    except Exception as e:
        return f"❌ 重建失败: {str(e)}", 500

@app.route('/debug')
def debug():
    from crawler import load_all_data, CSV_PATH
    import os
    if not os.path.isfile(CSV_PATH):
        return "CSV 文件不存在"
    data = load_all_data()
    if not data:
        return "CSV 为空"
    latest = max(data, key=lambda x: int(x['期号']))
    return f"✅ 最新期号：{latest['期号']}，总数：{len(data)} 条"

@app.route('/test_push')
def test_push():
    from wechat_push import send_wechat_message
    token = os.environ.get('PUSHPLUS_TOKEN', '')
    if not token:
        return "❌ 错误：PUSHPLUS_TOKEN 未设置", 500
    try:
        send_wechat_message("🧪 测试消息", "如果你收到此消息，说明推送配置成功！")
        return "✅ 测试消息已发送，请查看微信", 200
    except Exception as e:
        return f"❌ 发送失败: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🚀 Flask 应用启动")
    token = os.environ.get('PUSHPLUS_TOKEN', '')
    if token:
        print(f"✅ PUSHPLUS_TOKEN 已设置")
    else:
        print("⚠️ 警告：PUSHPLUS_TOKEN 未设置")
    app.run(host='0.0.0.0', port=port, debug=False)