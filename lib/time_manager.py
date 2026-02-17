#!/usr/bin/env python3
"""Time management module for DM tools."""

import sys
from pathlib import Path
from lib.campaign_manager import CampaignManager
from lib.json_ops import JsonOperations


class TimeManager:
    """Manage campaign time state."""

    def __init__(self, world_state_dir: str = "world-state", require_active_campaign: bool = True):
        if not require_active_campaign and world_state_dir != "world-state":
            # Direct campaign directory (for testing)
            self.campaign_dir = Path(world_state_dir)
            self.json_ops = JsonOperations(str(self.campaign_dir))
            self.campaign_mgr = None
        else:
            # Normal flow: require active campaign
            self.campaign_mgr = CampaignManager(world_state_dir)
            self.campaign_dir = self.campaign_mgr.get_active_campaign_dir()

            if self.campaign_dir is None:
                raise RuntimeError("No active campaign. Run /new-game or /import first.")

            self.json_ops = JsonOperations(str(self.campaign_dir))

    def update_time(self, time_of_day: str, date: str, elapsed_hours: float = 0, precise_time: str = None) -> bool:
        """
        Update campaign time and check timed consequences.

        Args:
            time_of_day: Descriptive time (e.g., "Evening", "Dawn")
            date: Campaign date string
            elapsed_hours: Hours that passed (for timed consequences)
            precise_time: Exact time in HH:MM format (auto-calculates elapsed)

        Returns:
            bool: Success status
        """
        data = self.json_ops.load_json("campaign-overview.json")

        if precise_time:
            old_precise_time = data.get('precise_time')
            if old_precise_time:
                from datetime import datetime
                try:
                    old_dt = datetime.strptime(old_precise_time, "%H:%M")
                    new_dt = datetime.strptime(precise_time, "%H:%M")
                    elapsed_seconds = (new_dt - old_dt).total_seconds()

                    if elapsed_seconds < 0:
                        elapsed_seconds += 24 * 3600

                    elapsed_hours = elapsed_seconds / 3600
                    print(f"[AUTO] Calculated elapsed time: {elapsed_hours:.2f}h ({old_precise_time} → {precise_time})")
                except ValueError:
                    print(f"[WARNING] Invalid time format, using manual elapsed")

        data['time_of_day'] = time_of_day
        data['current_date'] = date
        if precise_time:
            data['precise_time'] = precise_time

        consequences_triggered = []
        if elapsed_hours > 0:
            consequences_triggered = self._check_time_consequences(elapsed_hours)

        if not self.json_ops.save_json("campaign-overview.json", data):
            print(f"[ERROR] Failed to update time")
            return False

        self._print_time_report(time_of_day, date, precise_time, elapsed_hours, consequences_triggered)

        return True

    def add_time_hours(self, hours: float) -> bool:
        """
        Add hours to current time (helper method for testing).

        Args:
            hours: Hours to add

        Returns:
            bool: Success status
        """
        data = self.json_ops.load_json("campaign-overview.json")
        current_time = data.get('precise_time', '12:00')
        current_date = data.get('current_date', 'Day 1')

        # Parse current time
        from datetime import datetime, timedelta
        try:
            dt = datetime.strptime(current_time, "%H:%M")
            dt += timedelta(hours=hours)
            new_time = dt.strftime("%H:%M")

            # Determine time_of_day from hour
            hour = dt.hour
            if 5 <= hour < 12:
                time_of_day = "Morning"
            elif 12 <= hour < 17:
                time_of_day = "Day"
            elif 17 <= hour < 21:
                time_of_day = "Evening"
            else:
                time_of_day = "Night"

            return self.update_time(time_of_day, current_date, elapsed_hours=int(hours), precise_time=new_time)
        except Exception as e:
            print(f"[ERROR] Failed to add time: {e}")
            return False

    def get_time(self) -> dict:
        """Get current campaign time."""
        data = self.json_ops.load_json("campaign-overview.json")
        return {
            'time_of_day': data.get('time_of_day', 'Unknown'),
            'current_date': data.get('current_date', 'Unknown'),
            'precise_time': data.get('precise_time')
        }

    def _check_time_consequences(self, elapsed_hours: int) -> list:
        """Check and trigger time-based consequences"""
        data = self.json_ops.load_json("consequences.json")

        active = data.get('active', [])
        triggered = []
        remaining = []

        for consequence in active:
            trigger_hours = consequence.get('trigger_hours')

            if trigger_hours is None:
                # Event-based trigger, keep as-is
                remaining.append(consequence)
                continue

            # Update elapsed hours
            hours_elapsed = consequence.get('hours_elapsed', 0) + elapsed_hours
            consequence['hours_elapsed'] = hours_elapsed

            # Check if triggered
            if hours_elapsed >= trigger_hours:
                triggered.append({
                    'id': consequence['id'],
                    'consequence': consequence['consequence'],
                    'trigger': consequence['trigger']
                })

                # Move to resolved
                consequence['resolved'] = self.json_ops.get_timestamp()
                if 'resolved' not in data:
                    data['resolved'] = []
                data['resolved'].append(consequence)
            else:
                remaining.append(consequence)

        # Save updated consequences
        data['active'] = remaining
        self.json_ops.save_json("consequences.json", data)

        return triggered

    def _print_time_report(self, time_of_day: str, date: str, precise_time: str, elapsed_hours: float, consequences_triggered: list):
        """Print formatted report of time update results."""
        time_str = f"{time_of_day}"
        if precise_time:
            time_str += f" ({precise_time})"

        print(f"[SUCCESS] Time updated to: {time_str}, {date}")

        if elapsed_hours > 0:
            print(f"[ELAPSED] {elapsed_hours:.2f}")

        if consequences_triggered:
            print("\nTriggered Events:")
            for tc in consequences_triggered:
                print(f"  ⚠️ [{tc['id']}] {tc['consequence']}")


def main():
    """CLI interface for time management."""
    import argparse

    parser = argparse.ArgumentParser(description='Campaign time management')
    subparsers = parser.add_subparsers(dest='action', help='Action to perform')

    # Update time
    update_parser = subparsers.add_parser('update', help='Update campaign time')
    update_parser.add_argument('time_of_day', help='Descriptive time (e.g., "Evening", "Dawn")')
    update_parser.add_argument('date', help='Campaign date')
    update_parser.add_argument('--elapsed', type=int, default=0, help='Hours elapsed (manual)')
    update_parser.add_argument('--precise-time', help='Exact time HH:MM (auto-calculates elapsed)')
    # Get time
    subparsers.add_parser('get', help='Get current campaign time')

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    try:
        manager = TimeManager()

        if args.action == 'update':
            if not manager.update_time(
                args.time_of_day,
                args.date,
                elapsed_hours=args.elapsed,
                precise_time=args.precise_time
            ):
                sys.exit(1)

        elif args.action == 'get':
            time_info = manager.get_time()
            print(f"Time: {time_info['time_of_day']}")
            print(f"Date: {time_info['current_date']}")
            if time_info.get('precise_time'):
                print(f"Precise: {time_info['precise_time']}")

    except RuntimeError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
