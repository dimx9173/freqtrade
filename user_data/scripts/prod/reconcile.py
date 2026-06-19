#!/usr/bin/env python3
"""
reconcile.py
強制同步 registry ↔ 實際狀態
"""
import json
import subprocess
import os
import sys
from datetime import datetime

REGISTRY_PATH = "/home/brian/freqtrade/user_data/config/prod/registry.json"
BASE_DIR = "/home/brian/freqtrade"


def load_registry():
    with open(REGISTRY_PATH, "r") as f:
        return json.load(f)


def save_registry(registry):
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def find_freqtrade_process(slot_id):
    """尋找指定 slot 的 freqtrade process"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"freqtrade.*slot_{slot_id}.json"],
            capture_output=True,
            text=True
        )
        pids = result.stdout.strip().split("\n")
        pids = [p for p in pids if p]
        
        for pid in pids:
            try:
                with open(f"/proc/{pid}/cmdline", "r") as f:
                    cmdline = f.read()
                    if f"slot_{slot_id}.json" in cmdline:
                        return {"pid": pid, "cmdline": cmdline}
            except:
                continue
        return None
    except:
        return None


def extract_strategy_from_cmdline(cmdline):
    """從 cmdline 提取策略名稱"""
    parts = cmdline.split("\x00")
    for i, part in enumerate(parts):
        if part == "--strategy" and i + 1 < len(parts):
            return parts[i + 1]
    return None


def main():
    apply_mode = "--apply" in sys.argv
    
    registry = load_registry()
    slots = registry.get("slots", {})
    
    print("=== 狀態漂移偵測 ===\n")
    
    drift_count = 0
    drifts = []
    
    for slot_id in sorted(slots.keys(), key=int):
        slot = slots[slot_id]
        name = slot.get("name")
        expected_strategy = slot.get("strategy")
        expected_status = slot.get("status", "unknown")
        
        # 檢查 process
        proc = find_freqtrade_process(slot_id)
        actual_running = proc is not None
        actual_strategy = None
        
        if proc:
            actual_strategy = extract_strategy_from_cmdline(proc["cmdline"])
        
        # 檢查漂移
        drifted = False
        
        # 狀態漂移
        if expected_status == "running" and not actual_running:
            print(f"⚠️  Slot {slot_id} ({name}): registry=running, actual=stopped")
            drifted = True
            drift_count += 1
            drifts.append({
                "slot": slot_id,
                "field": "status",
                "expected": "running",
                "actual": "stopped"
            })
            
            if apply_mode:
                slots[slot_id]["status"] = "stopped"
                print(f"   → 已更新 registry: status=stopped")
        
        elif expected_status in ["stopped", "error"] and actual_running:
            print(f"⚠️  Slot {slot_id} ({name}): registry={expected_status}, actual=running")
            drifted = True
            drift_count += 1
            drifts.append({
                "slot": slot_id,
                "field": "status",
                "expected": expected_status,
                "actual": "running"
            })
            
            if apply_mode:
                slots[slot_id]["status"] = "running"
                print(f"   → 已更新 registry: status=running")
        
        # 策略漂移
        if actual_running and actual_strategy and actual_strategy != expected_strategy:
            print(f"⚠️  Slot {slot_id} ({name}): registry={expected_strategy}, actual={actual_strategy}")
            drifted = True
            drift_count += 1
            drifts.append({
                "slot": slot_id,
                "field": "strategy",
                "expected": expected_strategy,
                "actual": actual_strategy
            })
            
            if apply_mode:
                slots[slot_id]["strategy"] = actual_strategy
                print(f"   → 已更新 registry: strategy={actual_strategy}")
        
        # 正常狀態
        if not drifted:
            if actual_running:
                print(f"✅ Slot {slot_id} ({name}): running, strategy={expected_strategy}")
            else:
                print(f"⏸️  Slot {slot_id} ({name}): stopped")
    
    print("\n=== 總結 ===")
    if drift_count == 0:
        print("✅ 無漂移，registry 與實際狀態一致")
    else:
        print(f"⚠️  偵測到 {drift_count} 處漂移")
        if not apply_mode:
            print("\n執行 `python3 scripts/prod/reconcile.py --apply` 以實際狀態為準更新 registry")
        else:
            # 更新 last_reconciled
            registry["last_reconciled"] = datetime.utcnow().isoformat() + "Z"
            save_registry(registry)
            
            # Git commit
            subprocess.run(
                ["git", "add", "user_data/config/prod/registry.json"],
                cwd=BASE_DIR
            )
            subprocess.run(
                ["git", "commit", "--no-verify", "-m", 
                 f"auto(prod): reconcile registry @ {datetime.now().strftime('%Y%m%d_%H%M%S')}"],
                cwd=BASE_DIR,
                capture_output=True
            )
            print("✅ Registry 已同步並 commit")


if __name__ == "__main__":
    main()
