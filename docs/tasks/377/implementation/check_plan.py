"""Mechanical completeness and dependency checks for the #377 Phase-2 plan."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PLAN = Path(__file__).with_name("plan.md")
MANIFEST = Path(__file__).with_name("plan.manifest.json")

EXPECTED_IDS = [*(f"I{i}" for i in range(13)), "R10"]
REQUIRED_FIELDS = {
    "id",
    "kind",
    "owner",
    "depends_on",
    "files",
    "inputs",
    "red_oracle",
    "delivery_command",
    "acceptance",
    "rollback",
    "boundary",
    "stop",
}
PLAN_TICKET_FIELDS = (
    "Owner",
    "Depends on",
    "Outcome",
    "Future files/symbols",
    "Inputs",
    "RED oracle committed first",
    "Delivery command",
    "Measurable AC",
    "Failure/rollback",
    "Security/privacy/IP boundary",
    "Stop/falsification",
)
FORBIDDEN_SCOPE = (
    "camera/CV",
    "3D",
    "random map generation",
    "full character builder",
    "cross-setting character persistence",
    "commerce",
)


def fail(message: str) -> None:
    raise AssertionError(message)


def load() -> tuple[dict, str]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return data, PLAN.read_text(encoding="utf-8")


def ticket_sections(plan_text: str) -> dict[str, str]:
    pattern = re.compile(r"^### ((?:I\d+|R10)) — .+$", re.MULTILINE)
    matches = list(pattern.finditer(plan_text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(plan_text)
        sections[match.group(1)] = plan_text[match.start() : end]
    return sections


def validate_fields(data: dict, plan_text: str) -> dict[str, dict]:
    tickets = data.get("tickets")
    if not isinstance(tickets, list):
        fail("manifest tickets must be a list")
    by_id: dict[str, dict] = {}
    for ticket in tickets:
        missing = REQUIRED_FIELDS - set(ticket)
        if missing:
            fail(f"{ticket.get('id', '<unknown>')} missing fields: {sorted(missing)}")
        ticket_id = ticket["id"]
        if ticket_id in by_id:
            fail(f"duplicate ticket {ticket_id}")
        for field in REQUIRED_FIELDS - {"depends_on"}:
            if not ticket[field]:
                fail(f"{ticket_id}.{field} is empty")
        command = ticket["delivery_command"]
        required_command_parts = (
            "env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT",
            "uv run --project /ABS/PRIVATE/PROJECT --frozen",
            ticket["red_oracle"],
        )
        if any(part not in command for part in required_command_parts):
            fail(f"{ticket_id} delivery command is not isolated or does not name its oracle")
        by_id[ticket_id] = ticket

    if list(by_id) != EXPECTED_IDS:
        fail(f"ticket order/coverage mismatch: {list(by_id)}")

    sections = ticket_sections(plan_text)
    if list(sections) != EXPECTED_IDS:
        fail(f"plan headings mismatch: {list(sections)}")
    for ticket_id, section in sections.items():
        for field in PLAN_TICKET_FIELDS:
            if f"**{field}:**" not in section:
                fail(f"{ticket_id} plan section missing {field}")
        if by_id[ticket_id]["red_oracle"] not in section:
            fail(f"{ticket_id} plan section does not name manifest RED oracle")

    for phrase in FORBIDDEN_SCOPE:
        if phrase not in plan_text:
            fail(f"plan does not explicitly forbid {phrase}")
    return by_id


def validate_dag(by_id: dict[str, dict], data: dict) -> tuple[list[str], dict[str, int]]:
    indegree = {ticket_id: 0 for ticket_id in by_id}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for ticket_id, ticket in by_id.items():
        for dependency in ticket["depends_on"]:
            if dependency not in by_id:
                fail(f"{ticket_id} has unknown dependency {dependency}")
            if dependency == ticket_id:
                fail(f"{ticket_id} depends on itself")
            outgoing[dependency].append(ticket_id)
            indegree[ticket_id] += 1

    queue = deque(ticket_id for ticket_id in by_id if indegree[ticket_id] == 0)
    order: list[str] = []
    depth: dict[str, int] = {ticket_id: 1 for ticket_id in queue}
    while queue:
        ticket_id = queue.popleft()
        order.append(ticket_id)
        for child in outgoing[ticket_id]:
            depth[child] = max(depth.get(child, 1), depth[ticket_id] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(by_id):
        fail("dependency graph contains a cycle")
    if by_id["I0"]["depends_on"]:
        fail("I0 must be the root")
    if any("R10" in ticket["depends_on"] for ticket in by_id.values()):
        fail("R10 must be the sink")

    ancestors: dict[str, set[str]] = {ticket_id: set() for ticket_id in by_id}
    for ticket_id in order:
        for dependency in by_id[ticket_id]["depends_on"]:
            ancestors[ticket_id].add(dependency)
            ancestors[ticket_id].update(ancestors[dependency])
    for before, after in data["required_order_edges"]:
        if before not in ancestors[after]:
            fail(f"required ordering {before} -> {after} is not enforced")

    spine = data["critical_spine"]
    for before, after in zip(spine, spine[1:]):
        if before not in ancestors[after]:
            fail(f"critical spine is not executable: {before} !-> {after}")
    if len(spine) != max(depth.values()):
        fail(f"critical spine length {len(spine)} != DAG depth {max(depth.values())}")

    for wave in data["parallel_waves"]:
        for left_index, left in enumerate(wave):
            for right in wave[left_index + 1 :]:
                if left in ancestors[right] or right in ancestors[left]:
                    fail(f"declared parallel tickets are dependent: {left}, {right}")
    return order, depth


def validate_seams(plan_text: str, by_id: dict[str, dict]) -> None:
    folded_plan = plan_text.casefold()
    required_phrases = (
        "RoomRunAggregate",
        "transactional current state",
        "same-version projection family",
        "first-party literal DnD/Orchestra reuse is owner-authorized",
        "R9 initial “normal” synthetic envelope",
        "strict `audio_fence` control",
        "physical player dice",
        "public server-generated enemy dice",
        "actual table, scene, and admin browsers",
        "consented physical-room",
        "fully closed synthetic owner-authorized positive row",
        "each table/scene/admin/composite consumer advances only its own durable",
        "projection acknowledgement alone never makes audio eligible",
        "protocol freeze before recruitment opens",
        "participant-admission timestamp follows recruitment",
    )
    for phrase in required_phrases:
        if phrase.casefold() not in folded_plan:
            fail(f"load-bearing seam absent from plan: {phrase}")
    if "I8" not in by_id["I9"]["depends_on"]:
        fail("production content must depend on Core-shaped calibration")
    if by_id["I9"]["kind"] == by_id["I10"]["kind"]:
        fail("production content and production assets must be separate ticket kinds")


def main() -> int:
    data, plan_text = load()
    by_id = validate_fields(data, plan_text)
    order, depth = validate_dag(by_id, data)
    validate_seams(plan_text, by_id)
    print(
        json.dumps(
            {
                "status": "PASS",
                "tickets": len(by_id),
                "topological_order": order,
                "dag_depth": max(depth.values()),
                "critical_spine": data["critical_spine"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
