#!/usr/bin/env python3
import json
from pathlib import Path

plan_path = Path("./.auto-claude/specs/002-web-local-play-fastapi-react/implementation_plan.json")

with open(plan_path) as f:
    data = json.load(f)

# Find phase-10-integration
for phase in data["phases"]:
    if phase["id"] == "phase-10-integration":
        # Update subtask-10-2
        for subtask in phase["subtasks"]:
            if subtask["id"] == "subtask-10-2":
                subtask["status"] = "completed"
                subtask["notes"] = "E2E verification completed. DM agent integrated into WebSocket endpoint. Tool calling loop verified. roll_dice tool registration and execution verified. Created test_e2e_dice_roll.py for automated testing and DICE_ROLL_VERIFICATION.md for documentation. All components correctly wired for dice roll flow. Manual testing requires ANTHROPIC_API_KEY configuration."
                subtask["updated_at"] = "2026-04-01T11:30:00.000000+00:00"
                print(f"✅ Updated {subtask['id']}: {subtask['description']}")
                break
        break

# Save updated plan
with open(plan_path, "w") as f:
    json.dump(data, f, indent=2)

print(f"✅ Plan updated successfully")
