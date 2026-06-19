import os
import sys
from io import StringIO
from flask import Flask, render_template, request, redirect, url_for, jsonify
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

    all_data.sort(key=lambda x: int(x['期号']), reverse=True)
    latest = all_data[0] if all_data else None

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
    """
    强制更新数据（合并去重，不删除已有数据）
    """
    key = request.args.get('key', '')
    if key != UPDATE_SECRET_KEY:
        return "Unauthorized: invalid key", 401

    try:
        result = ensure_latest()
        if result:
            return "✅ 数据已合并更新，最新期已添加", 200
        else:
            return "✅ 数据已是最新，无新增记录", 200
    except Exception as e:
        return f"❌ 更新失败: {str(e)}", 500


@app.route('/debug')
def debug():
    from crawler import load_all_data, CSV_PATH
    import os
    if not os.path.isfile(CSV_PATH):
        return "CSV 文件不存在，请先访问 /rebuild 更新数据"
    data = load_all_data()
    if not data:
        return "CSV 为空"
    latest = max(data, key=lambda x: int(x['期号']))
    return f"✅ 最新期号：{latest['期号']}，总数：{len(data)} 条"


@app.route('/check', methods=['POST'])
def check_period():
    """
    手动输入期号和号码，分析是否中奖
    """
    period = request.form.get('period', '').strip()
    reds_input = request.form.get('reds', '').strip()
    blue_input = request.form.get('blue', '').strip()

    if not period or not reds_input or not blue_input:
        return jsonify({'status': 'error', 'message': '请完整填写期号、红球和蓝球'})

    reds_list = [r.strip() for r in reds_input.split(',') if r.strip()]
    if len(reds_list) != 6:
        return jsonify({'status': 'error', 'message': '红球必须为6个号码，用逗号分隔'})

    all_data = load_all_data()
    target = None
    for row in all_data:
        if row['期号'] == period:
            target = row
            break

    if not target:
        return jsonify({'status': 'error', 'message': f'未找到期号 {period} 的数据，请先更新数据'})

    cfg = load_config()
    multiplier = int(cfg.get('multiplier', 2))
    my_reds_set = set(reds_list)
    my_blue = blue_input

    prize_level, prize_amount = check_prize(my_reds_set, my_blue, target['红球'], target['蓝球'])

    if prize_level:
        if prize_amount == '浮动':
            amount_display = '浮动奖金'
        elif isinstance(prize_amount, int):
            total = prize_amount * multiplier
            amount_display = f"{total} 元 (单注 {prize_amount} 元 × {multiplier}倍)"
        else:
            amount_display = str(prize_amount)
        result = {
            'status': 'win',
            'level': prize_level,
            'amount': amount_display,
            'period': period,
            'date': target['开奖日期'],
            'actual_reds': target['红球'],
            'actual_blue': target['蓝球']
        }
    else:
        result = {
            'status': 'no_win',
            'level': '未中奖',
            'amount': '0',
            'period': period,
            'date': target['开奖日期'],
            'actual_reds': target['红球'],
            'actual_blue': target['蓝球']
        }

    return jsonify(result)


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
