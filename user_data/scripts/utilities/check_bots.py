#!/usr/bin/env python3
"""
check_bots.py v2
健康檢查 + 狀態漂移偵測
讀取 registry.json 作為 single source of truth
"""
import subprocess
import requests
import sqlite3
import os
import json
import sys
from datetime import datetime

REGISTRY_PATH = "/home/brian/freqtrade/user_data/config/prod/registry.json"
BASE_DIR = "/home/brian/freqtrade"


def load_registry():
    """載入 registry.json"""
    with open(REGISTRY_PATH, "r") as f:
        return json.load(f)


def check_bot_health(port, timeout=5):
    """檢查 bot 健康狀態"""
    try:
        resp = requests.get(f"http://127.0.0.1:{port}/api/v1/ping", timeout=timeout)
        if resp.status_code == 200:
            return True, "Running"
        else:
            return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


def find_freqtrade_process(port):
    """尋找指定 port 的 freqtrade process"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"freqtrade.*--config.*slot_"],
            capture_output=True,
            text=True
        )
        for pid in result.stdout.strip().split("\n"):
            if not pid:
                continue
            # 檢查 cmdline 是否包含該 port
            try:
                with open(f"/proc/{pid}/cmdline", "r") as f:
                    cmdline = f.read()
                    if f"slot_" in cmdline:
                        # 簡化：回傳 pid 和 cmdline
                        return {"pid": pid, "cmdline": cmdline}
            except:
                continue
        return None
    except:
        return None


def extract_strategy_from_cmdline(cmdline):
    """從 cmdline 提取策略名稱"""
    # 尋找 --strategy 後的值
    parts = cmdline.split("\x00")  # /proc/pid/cmdline 用 null 分隔
    for i, part in enumerate(parts):
        if part == "--strategy" and i + 1 < len(parts):
            return parts[i + 1]
    return None


def detect_drift(registry):
    """偵測 registry 與實際狀態的漂移"""
    drifts = []
    slots = registry.get("slots", {})

    for slot_id, slot in slots.items():
        port = slot.get("port")
        expected_strategy = slot.get("strategy")
        expected_status = slot.get("status", "unknown")

        # 檢查 process 是否存在
        proc = find_freqtrade_process(port)
        actual_running = proc is not None

        # 狀態漂移檢查
        if expected_status == "running" and not actual_running:
            drifts.append({
                "slot": slot_id,
                "type": "status_mismatch",
                "expected": "running",
                "actual": "stopped",
                "message": f"Slot {slot_id}: registry=running, actual=stopped"
            })
        elif expected_status == "stopped" and actual_running:
            drifts.append({
                "slot": slot_id,
                "type": "status_mismatch",
                "expected": "stopped",
                "actual": "running",
                "message": f"Slot {slot_id}: registry=stopped, actual=running"
            })

        # 策略漂移檢查
        if proc and proc.get("cmdline"):
            actual_strategy = extract_strategy_from_cmdline(proc["cmdline"])
            if actual_strategy and actual_strategy != expected_strategy:
                drifts.append({
                    "slot": slot_id,
                    "type": "strategy_mismatch",
                    "expected": expected_strategy,
                    "actual": actual_strategy,
                    "message": f"Slot {slot_id}: registry={expected_strategy}, actual={actual_strategy}"
                })

    return drifts


def get_profit_from_db(db_name):
    """從 SQLite 獲取 P&L 數據"""
    db_path = os.path.join(BASE_DIR, "user_data/sqlite", db_name)
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


def restart_bot(slot_id, slot):
    """重啟 bot"""
    config = f"slot_{slot_id}.json"
    db = slot.get("db")
    log = slot.get("log")
    strategy = slot.get("strategy")

    cmd = (
        f"cd {BASE_DIR} && "
        f"source .venv/bin/activate && "
        f"freqtrade trade "
        f"--config user_data/config/prod/{config} "
        f"--db-url sqlite:///user_data/sqlite/{db} "
        f"--logfile user_data/logs/{log} "
        f"--strategy-path user_data/strategies/prod "
        f"--strategy {strategy}"
    )
    subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    return True


def main():
    registry = load_registry()
    slots = registry.get("slots", {})

    results = []
    profit_lines = []
    drifts = detect_drift(registry)

    # 健康檢查
    for slot_id, slot in sorted(slots.items(), key=lambda x: int(x[0])):
        name = slot.get("name")
        port = slot.get("port")
        db = slot.get("db")

        running, status = check_bot_health(port)

        # 如果 bot 停止且不在 swapping 狀態，嘗試重啟
        if not running and slot.get("status") != "swapping":
            restart_bot(slot_id, slot)
            results.append(f"🔄 Slot {slot_id} ({name}): 未運行 ({status})，已重啟")
        elif running:
            results.append(f"✅ Slot {slot_id} ({name}): 正常運行")
            profit = get_profit_from_db(db)
            if profit:
                profit_lines.append(
                    f"  📊 {name}: 總交易={profit['trade_count']}, "
                    f"已平倉={profit['closed_trades']}, 持倉中={profit['open_trades']}, "
                    f"已平倉損益={profit['profit_abs']:.4f} USDT (avg {profit['profit_pct']:.2f}%)"
                )
            else:
                profit_lines.append(f"  ⚠️ {name}: 無法獲取 P&L 數據")
        else:
            results.append(f"⏸️ Slot {slot_id} ({name}): swapping 狀態，跳過重啟")

    # 漂移報告
    if drifts:
        print("\n⚠️  狀態漂移偵測:")
        for drift in drifts:
            print(f"  - {drift['message']}")
        print("  執行 `bash scripts/prod/reconcile.sh --apply` 同步狀態\n")

    output = "\n".join(results)
    if profit_lines:
        output += "\n\n【P&L 數據】\n" + "\n".join(profit_lines)
    print(output)
    return output


if __name__ == "__main__":
    main()
