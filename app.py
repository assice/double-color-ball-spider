import os
from flask import Flask, render_template, request, redirect, url_for
from config_manager import load_config, save_config
from crawler import load_all_data, update_csv
from prize_checker import check_prize

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ssq-secret-key-change-in-production'

# 用于 /update 路由的简单密钥（建议改为从环境变量读取）
UPDATE_SECRET_KEY = os.environ.get('UPDATE_SECRET_KEY', 'your_secret_key_here')

def filter_and_calc(cfg):
    all_data = load_all_data()
    if not all_data:
        return [], {}

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

    filtered.sort(key=lambda x: x['期号'], reverse=True)

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
    return result_list, stats

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
    results, stats = filter_and_calc(cfg)
    all_data = load_all_data()
    latest_period = all_data[0]['期号'] if all_data else ''
    return render_template('index.html',
                           config=cfg,
                           results=results,
                           stats=stats,
                           latest_period=latest_period)

@app.route('/update')
def manual_update():
    key = request.args.get('key', '')
    if key != UPDATE_SECRET_KEY:
        return "Unauthorized: invalid key", 401
    try:
        from crawler import update_csv
        update_csv()
        return "数据更新完成", 200
    except Exception as e:
        return f"更新失败: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # 首次启动时可选执行一次更新（注释掉，避免启动延迟）
    # 数据由外部定时任务触发更新
    print("🚀 Flask 应用启动，数据更新由外部定时服务触发（如 cron-job.org）")
    app.run(host='0.0.0.0', port=port, debug=False)