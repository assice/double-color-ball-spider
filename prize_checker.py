def check_prize(my_reds_set, my_blue, draw_reds_str, draw_blue_str):
    if not draw_reds_str or not draw_blue_str:
        return None, None

    draw_reds = set(draw_reds_str.split(','))
    draw_blue = draw_blue_str.strip()

    hit_reds = len(my_reds_set & draw_reds)
    hit_blue = 1 if my_blue == draw_blue else 0

    if hit_reds == 6 and hit_blue == 1:
        return '一等奖', '浮动'
    elif hit_reds == 6 and hit_blue == 0:
        return '二等奖', '浮动'
    elif hit_reds == 5 and hit_blue == 1:
        return '三等奖', 3000
    elif (hit_reds == 5 and hit_blue == 0) or (hit_reds == 4 and hit_blue == 1):
        return '四等奖', 200
    elif (hit_reds == 4 and hit_blue == 0) or (hit_reds == 3 and hit_blue == 1):
        return '五等奖', 10
    elif hit_blue == 1:
        return '六等奖', 5
    elif hit_reds == 3 and hit_blue == 0:
        return '福运奖', 5
    else:
        return None, None