#!/usr/bin/env python3
import subprocess
import requests
import sqlite3
import os
import time
import sys

BOTS = [
    {"name": "NASOSv4", "port": 13991, "config": "config_1.json", "strategy": "NASOSv4"},
    {"name": "PSV5_Hybrid", "port": 13992, "config": "config_2.json", "strategy": "PSV5_Hybrid"},
    {
        "name": "BB_RPB_TSL_BI",
        "port": 13993,
        "config": "config_3.json",
        "strategy": "BB_RPB_TSL_BI",
    },
    {"name": "NASOSv5_mod3", "port": 13994, "config": "config_4.json", "strategy": "NASOSv5_mod3"},
    {
        "name": "SMAOffsetProtectOptV1",
        "port": 13995,
        "config": "config_5.json",
        "strategy": "SMAOffsetProtectOptV1",
    },
    {
        "name": "ElliotV5_SMA_ninja",
        "port": 13996,
        "config": "config_6.json",
        "strategy": "ElliotV5_SMA_ninja",
    },
]


def check_bot(bot):
    try:
        resp = requests.get(f"http://127.0.0.1:{bot['port']}/api/v1/ping", timeout=5)
        if resp.status_code == 200:
            return True, "Running"
        else:
            return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


def get_profit_from_db(bot):
    sqlite_dir = "/home/brian/freqtrade/user_data/sqlite"
    db_map = {
        13991: "tradesv3_1.sqlite",
        13992: "tradesv3_uat.sqlite",
        13993: "tradesv3_93.sqlite",
        13994: "tradesv3_4.sqlite",
        13995: "tradesv3_5.sqlite",
        13996: "tradesv3_6.sqlite",
    }
    db_file = db_map.get(bot["port"], f"tradesv3_{str(bot['port'])[-2:]}.sqlite")
    db_path = os.path.join(sqlite_dir, db_file)
    if not os.path.exists(db_path):
        return None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trades")
        total_trades = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM trades WHERE is_open = 0")
        closed_trades = cursor.fetchone()[0]
        cursor.execute(
            "SELECT SUM(close_profit_abs), SUM(close_profit) FROM trades WHERE is_open = 0"
        )
        result = cursor.fetchone()
        profit_abs = result[0] or 0
        profit_pct = result[1] or 0
        cursor.execute("SELECT COUNT(*) FROM trades WHERE is_open = 1")
        open_trades = cursor.fetchone()[0]
        conn.close()
        return {
            "trade_count": total_trades,
            "closed_trades": closed_trades,
            "open_trades": open_trades,
            "profit_abs": profit_abs,
            "profit_pct": profit_pct * 100,
        }
    except Exception:
        return None


def restart_bot(bot):
    port_suffix = str(bot["port"])[-2:]
    cmd = f"cd /home/brian/freqtrade && zsh user_data/scripts/utilities/monitor_run.sh 'freqtrade trade --config user_data/config/{bot['config']} --db-url sqlite:///user_data/sqlite/tradesv3_{port_suffix}.sqlite --logfile user_data/logs/freqtrade_{bot['name']}.log --strategy-path user_data/strategies/prod --strategy {bot['strategy']}'"
    subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def main():
    results = []
    profit_lines = []
    for bot in BOTS:
        running, status = check_bot(bot)
        if not running:
            restart_bot(bot)
            results.append(f"🔄 {bot['name']}: 未運行 ({status})，已重啟")
        else:
            results.append(f"✅ {bot['name']}: 正常運行")
            profit = get_profit_from_db(bot)
            if profit:
                profit_lines.append(
                    f"  📊 {bot['name']}: 總交易={profit['trade_count']}, 已平倉={profit['closed_trades']}, 持倉中={profit['open_trades']}, "
                    f"已平倉損益={profit['profit_abs']:.4f} USDT (avg {profit['profit_pct']:.2f}%)"
                )
            else:
                profit_lines.append(f"  ⚠️ {bot['name']}: 無法獲取 P&L 數據")

    output = "\n".join(results)
    if profit_lines:
        output += "\n\n【P&L 數據】\n" + "\n".join(profit_lines)
    print(output)
    return output


if __name__ == "__main__":
    main()
