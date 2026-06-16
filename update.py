#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
独立更新脚本，供 Render Cron Job 调用
功能：从官网获取最新数据，检测中奖并推送微信通知
"""

from crawler import update_csv

if __name__ == '__main__':
    print("⏰ Cron Job 开始执行...")
    update_csv()
    print("✅ Cron Job 执行完毕")