#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT))
from lib.campaign_manager import CampaignManager

TRACKER_FILE = "module-data/action-tracker.json"
WARN_THRESHOLD = 35


def _get_campaign_dir():
    cm = CampaignManager()
    path = cm.get_active_campaign_dir()
    return str(path) if path else None


def _load_tracker(campaign_dir):
    path = Path(campaign_dir) / TRACKER_FILE
    if path.exists():
        return json.loads(path.read_text())
    return {"accounted": [], "pending": []}


def _save_tracker(campaign_dir, data):
    path = Path(campaign_dir) / TRACKER_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def log_action(action_type, detail, tool=None):
    campaign_dir = _get_campaign_dir()
    if not campaign_dir:
        return

    data = _load_tracker(campaign_dir)
    entry = {
        "type": action_type,
        "detail": detail,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }
    if tool:
        entry["tool"] = tool

    data["pending"].append(entry)
    _save_tracker(campaign_dir, data)

    pending_count = len(data["pending"])
    if pending_count >= WARN_THRESHOLD:
        actions_summary = []
        for a in data["pending"][-5:]:
            actions_summary.append(f"  {a['type']}: {a['detail']}")
        recent = "\n".join(actions_summary)
        print(f"\n⏰ ACTION TRACKER: {pending_count} действий без учёта времени!")
        print(f"Последние:")
        print(recent)
        print(f"Оцени сколько прошло → bash tools/dm-time.sh \"<время>\" \"<дата>\" --elapsed N --resolve-actions\n")


def resolve_actions(elapsed_hours, time_label=None):
    campaign_dir = _get_campaign_dir()
    if not campaign_dir:
        return

    data = _load_tracker(campaign_dir)
    if not data["pending"]:
        return

    resolved = {
        "actions": data["pending"],
        "elapsed": elapsed_hours,
        "resolved_at": time_label or datetime.now().strftime("%Y-%m-%d %H:%M"),
        "action_count": len(data["pending"]),
    }
    data["accounted"].append(resolved)
    data["pending"] = []
    _save_tracker(campaign_dir, data)

    print(f"✅ ACTION TRACKER: {resolved['action_count']} действий учтено ({elapsed_hours}ч)")


def show_status():
    campaign_dir = _get_campaign_dir()
    if not campaign_dir:
        print("No active campaign")
        return

    data = _load_tracker(campaign_dir)
    pending = len(data["pending"])
    total_accounted = sum(b["action_count"] for b in data["accounted"])

    print(f"📊 Action Tracker: {pending} pending | {total_accounted} accounted ({len(data['accounted'])} batches)")
    if data["pending"]:
        print("Pending:")
        for a in data["pending"]:
            print(f"  [{a['type']}] {a['detail']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: action_tracker.py <log|resolve|status> [args]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "log":
        if len(sys.argv) < 4:
            print("Usage: action_tracker.py log <type> <detail> [tool]")
            sys.exit(1)
        tool = sys.argv[4] if len(sys.argv) > 4 else None
        log_action(sys.argv[2], sys.argv[3], tool)

    elif cmd == "resolve":
        elapsed = float(sys.argv[2]) if len(sys.argv) > 2 else 0
        label = sys.argv[3] if len(sys.argv) > 3 else None
        resolve_actions(elapsed, label)

    elif cmd == "status":
        show_status()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
