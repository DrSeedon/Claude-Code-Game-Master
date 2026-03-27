#!/usr/bin/env python3
"""
CORE time management — game clock, calendar, elapsed calculation.
Stores precise_time (HH:MM) and game_date in campaign-overview.json.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from campaign_manager import CampaignManager
from json_ops import JsonOperations
from colors import tag_error


class TimeManager:

    def __init__(self, world_state_dir: str = "world-state"):
        self.campaign_mgr = CampaignManager(world_state_dir)
        self.campaign_dir = self.campaign_mgr.get_active_campaign_dir()
        if self.campaign_dir is None:
            raise RuntimeError("No active campaign.")
        self.json_ops = JsonOperations(str(self.campaign_dir))
        self._cal_config = None
        self._overview = None

    def _load_overview(self) -> dict:
        if self._overview is None:
            self._overview = self.json_ops.load_json("campaign-overview.json")
        return self._overview

    def _save_overview(self, data: dict) -> bool:
        self._overview = data
        return self.json_ops.save_json("campaign-overview.json", data)

    def _cal(self) -> dict:
        if self._cal_config is None:
            try:
                from lib.calendar import load_config
                self._cal_config = load_config(self.campaign_dir)
            except Exception:
                self._cal_config = {}
        return self._cal_config

    def _ensure_precise_time(self, data: dict) -> str:
        if "precise_time" in data:
            return data["precise_time"]
        module_time = self._read_module_time()
        if module_time:
            data["precise_time"] = module_time
            return module_time
        tod = data.get("time_of_day", "08:00")
        if ":" in tod:
            data["precise_time"] = tod
            return tod
        data["precise_time"] = "08:00"
        return "08:00"

    def _ensure_game_date(self, data: dict) -> dict:
        if "game_date" in data and isinstance(data["game_date"], dict):
            return data["game_date"]
        module_date = self._read_module_date()
        if module_date:
            data["game_date"] = module_date
            return module_date
        date_str = data.get("current_date", "")
        if date_str:
            try:
                from lib.calendar import parse_date
                gd = parse_date(date_str, self._cal())
                data["game_date"] = gd
                return gd
            except (ValueError, KeyError):
                pass
        return {}

    def _read_module_time(self) -> str:
        try:
            md_path = Path(self.campaign_dir) / "module-data" / "custom-stats.json"
            if md_path.exists():
                md = json.loads(md_path.read_text(encoding="utf-8"))
                return md.get("precise_time", "")
        except Exception:
            pass
        return ""

    def _read_module_date(self) -> dict:
        try:
            md_path = Path(self.campaign_dir) / "module-data" / "custom-stats.json"
            if md_path.exists():
                md = json.loads(md_path.read_text(encoding="utf-8"))
                gd = md.get("game_date")
                if isinstance(gd, dict):
                    return gd
        except Exception:
            pass
        return {}

    def get_time(self) -> dict:
        data = self._load_overview()
        return {
            "time_of_day": data.get("time_of_day", "Unknown"),
            "current_date": data.get("current_date", "Unknown"),
            "precise_time": self._ensure_precise_time(data),
            "game_date": self._ensure_game_date(data),
        }

    def advance(self, elapsed_hours: float, sleeping: bool = False) -> dict:
        data = self._load_overview()
        clock = self._ensure_precise_time(data)
        game_date = self._ensure_game_date(data)
        cal = self._cal()

        old_clock = clock

        if game_date and cal.get("months"):
            from lib.calendar import advance_hours, format_date, weekday
            new_date, new_clock = advance_hours(game_date, clock, elapsed_hours, cal)
            data["game_date"] = new_date
            data["precise_time"] = new_clock
            data["current_date"] = format_date(new_date, cal)
            data["time_of_day"] = new_clock
        else:
            h, m = map(int, clock.split(":"))
            total_min = h * 60 + m + int(elapsed_hours * 60)
            new_h = (total_min // 60) % 24
            new_m = total_min % 60
            new_clock = f"{new_h:02d}:{new_m:02d}"
            data["precise_time"] = new_clock
            data["time_of_day"] = new_clock

        self._sync_to_module(data)
        self._save_overview(data)
        self._print_time(data, elapsed_hours)

        return {
            "elapsed_hours": elapsed_hours,
            "old_clock": old_clock,
            "new_clock": data["precise_time"],
            "sleeping": sleeping,
        }

    def set_time(self, target_hhmm: str) -> dict:
        data = self._load_overview()
        clock = self._ensure_precise_time(data)

        old_h, old_m = map(int, clock.split(":"))
        new_h, new_m = map(int, target_hhmm.split(":"))

        old_total = old_h * 60 + old_m
        new_total = new_h * 60 + new_m
        diff_min = new_total - old_total
        if diff_min < 0:
            diff_min += 24 * 60
        elapsed_hours = diff_min / 60.0

        return self.advance(elapsed_hours)

    def update_time(self, time_of_day: str, date: str) -> bool:
        data = self._load_overview()
        data["time_of_day"] = time_of_day
        data["current_date"] = date
        if ":" in time_of_day:
            data["precise_time"] = time_of_day
        return self._save_overview(data)

    def _sync_to_module(self, data: dict):
        try:
            md_path = Path(self.campaign_dir) / "module-data" / "custom-stats.json"
            if md_path.exists():
                md = json.loads(md_path.read_text(encoding="utf-8"))
                md["precise_time"] = data.get("precise_time", "08:00")
                if "game_date" in data:
                    md["game_date"] = data["game_date"]
                md_path.write_text(json.dumps(md, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _print_time(self, data: dict, elapsed_hours: float = 0):
        C = "\033[36m"
        DM = "\033[2m"
        Y = "\033[33m"
        RS = "\033[0m"

        clock = data.get("precise_time", "??:??")
        game_date = data.get("game_date")
        cal = self._cal()

        date_display = data.get("current_date", "")
        if game_date and cal.get("months"):
            try:
                from lib.calendar import format_date, weekday
                date_display = format_date(game_date, cal)
                wd = weekday(game_date, cal)
                if wd:
                    date_display = f"{Y}{wd}{RS}, {date_display}"
            except Exception:
                pass

        elapsed_str = f" {DM}(+{elapsed_hours:g}h){RS}" if elapsed_hours > 0 else ""
        print(f"\n⏰ {C}{clock}{RS}, {date_display}{elapsed_str}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CORE time management")
    subparsers = parser.add_subparsers(dest="action")

    adv = subparsers.add_parser("advance")
    adv.add_argument("--elapsed", type=float, required=True)
    adv.add_argument("--sleeping", action="store_true")

    st = subparsers.add_parser("set-time")
    st.add_argument("--to", required=True, dest="target")

    upd = subparsers.add_parser("update")
    upd.add_argument("time_of_day")
    upd.add_argument("date")

    gt = subparsers.add_parser("get")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        mgr = TimeManager()

        if args.action == "advance":
            result = mgr.advance(args.elapsed, args.sleeping)
            print(f"ELAPSED_HOURS={result['elapsed_hours']:.6f}")
            if args.sleeping:
                print("SLEEPING=1")

        elif args.action == "set-time":
            result = mgr.set_time(args.target)
            print(f"ELAPSED_HOURS={result['elapsed_hours']:.6f}")

        elif args.action == "update":
            if not mgr.update_time(args.time_of_day, args.date):
                sys.exit(1)

        elif args.action == "get":
            t = mgr.get_time()
            print(f"⏰ {t['precise_time']}, {t['current_date']}")

    except RuntimeError as e:
        print(tag_error(str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
