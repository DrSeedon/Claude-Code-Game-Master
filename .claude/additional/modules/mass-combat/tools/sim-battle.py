#!/usr/bin/env python3
"""Full battle simulation — all groups fight until one side is wiped. Repeat N times.
Detailed per-unit-type analytics dashboard."""

import sys
import random
import re
import argparse
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "additional" / "modules" / "mass-combat" / "lib"))

from mass_combat_engine import MassCombatEngine


def roll_damage(dmg_str, crit=False):
    m = re.match(r'(\d+)d(\d+)([+-]\d+)?', dmg_str)
    if not m:
        return 0
    nd, sides = int(m.group(1)), int(m.group(2))
    mod = int(m.group(3)) if m.group(3) else 0
    dmg = sum(random.randint(1, sides) for _ in range(nd)) + mod
    if crit:
        dmg *= 2
    return max(0, dmg)


def get_aoe_info(unit, templates):
    tmpl = templates.get(unit.get("type", ""), {})
    if tmpl.get("targeting") != "aoe":
        return None
    return {
        "save_dc": tmpl.get("aoe_save_dc", 14),
        "aoe_targets": tmpl.get("aoe_targets", 3),
        "aoe_mode": tmpl.get("aoe_mode", "blast"),
    }


def get_enemy_faction(faction, factions):
    for f in factions:
        if f != faction:
            return f
    return None


def alive_in_faction(units, groups, factions, faction):
    uids = []
    for grp_name in factions.get(faction, []):
        for uid in groups.get(grp_name, {}).get("unit_ids", []):
            if units[uid]["alive"]:
                uids.append(uid)
    return uids


def alive_in_group(units, groups, grp_name):
    return [uid for uid in groups.get(grp_name, {}).get("unit_ids", []) if units[uid]["alive"]]


def is_crewed(unit, templates):
    tmpl = templates.get(unit.get("type", ""), {})
    return tmpl.get("crewed", False)


def group_has_crew(units, groups, grp_name, templates):
    for uid in groups.get(grp_name, {}).get("unit_ids", []):
        if units[uid]["alive"] and not is_crewed(units[uid], templates):
            return True
    return False


def unit_key(uid, snapshot):
    """Stable key for grouping: named heroes by uid, generic units by type."""
    u = snapshot[uid]
    if uid == u["type"] or (not "-" in uid) or (uid.split("-")[-1] and not uid.split("-")[-1].isdigit()):
        return uid
    return u["type"]


def run_one_battle(snapshot, groups, factions, templates, max_rounds=20):
    units = {uid: dict(u) for uid, u in snapshot.items()}

    faction_names = list(factions.keys())

    per_unit_dmg = defaultdict(int)
    per_unit_kills = defaultdict(int)
    per_unit_death_round = {}

    all_groups_ordered = []
    for faction in faction_names:
        for grp_name in factions[faction]:
            all_groups_ordered.append((grp_name, faction))

    round_num = 0
    while round_num < max_rounds:
        round_num += 1

        f1_alive = len(alive_in_faction(units, groups, factions, faction_names[0]))
        f2_alive = len(alive_in_faction(units, groups, factions, faction_names[1]))
        if f1_alive == 0 or f2_alive == 0:
            break

        random.shuffle(all_groups_ordered)

        for grp_name, faction in all_groups_ordered:
            attackers = alive_in_group(units, groups, grp_name)
            if not attackers:
                continue

            enemy_faction = get_enemy_faction(faction, factions)
            enemy_alive = alive_in_faction(units, groups, factions, enemy_faction)
            if not enemy_alive:
                break

            for atk_uid in attackers:
                attacker = units[atk_uid]
                if not attacker["alive"]:
                    continue

                enemy_alive = alive_in_faction(units, groups, factions, enemy_faction)
                if not enemy_alive:
                    break

                aoe = get_aoe_info(attacker, templates)

                if is_crewed(attacker, templates) and not group_has_crew(units, groups, grp_name, templates):
                    continue

                if aoe:
                    is_spray = aoe["aoe_mode"] == "spray"
                    n_tgt = min(aoe["aoe_targets"], len(enemy_alive))

                    if is_spray:
                        weights = [units[t].get("weight", 1) for t in enemy_alive]
                        chosen = random.choices(enemy_alive, weights=weights, k=n_tgt)
                    else:
                        chosen = random.sample(enemy_alive, n_tgt)

                    blast_dmg = roll_damage(attacker["dmg"]) if not is_spray else 0

                    for tgt_uid in chosen:
                        target = units[tgt_uid]
                        if not target["alive"]:
                            continue
                        dmg_base = roll_damage(attacker["dmg"]) if is_spray else blast_dmg
                        save_roll = random.randint(1, 20)
                        applied = dmg_base // 2 if save_roll >= aoe["save_dc"] else dmg_base
                        per_unit_dmg[atk_uid] += applied
                        target["hp"] -= applied
                        if target["hp"] <= 0 and target["alive"]:
                            target["alive"] = False
                            per_unit_kills[atk_uid] += 1
                            per_unit_death_round[tgt_uid] = round_num
                else:
                    weights = [units[t].get("weight", 1) for t in enemy_alive]
                    target_uid = random.choices(enemy_alive, weights=weights, k=1)[0]
                    target = units[target_uid]
                    roll = random.randint(1, 20)
                    total_atk = roll + attacker["atk"]
                    ac = target["ac"] + (2 if target.get("cover") else 0)
                    hit = (roll == 20) or (roll != 1 and total_atk >= ac)
                    if hit:
                        dmg = roll_damage(attacker["dmg"], crit=(roll == 20))
                        per_unit_dmg[atk_uid] += dmg
                        target["hp"] -= dmg
                        if target["hp"] <= 0 and target["alive"]:
                            target["alive"] = False
                            per_unit_kills[atk_uid] += 1
                            per_unit_death_round[target_uid] = round_num

    survivors = {}
    for uid in units:
        survivors[uid] = units[uid]["alive"]

    return {
        "rounds": round_num,
        "per_unit_dmg": dict(per_unit_dmg),
        "per_unit_kills": dict(per_unit_kills),
        "per_unit_death_round": dict(per_unit_death_round),
        "survivors": dict(survivors),
    }


def simulate_full(engine, n_runs=500):
    snapshot = {uid: dict(u) for uid, u in engine.state["units"].items()}
    groups = engine.state["groups"]
    factions = engine.state["factions"]
    templates = engine.templates

    results = []
    for i in range(n_runs):
        results.append(run_one_battle(snapshot, groups, factions, templates))
        if (i + 1) % 100 == 0:
            print(f"  ... {i+1}/{n_runs}")

    return results, snapshot, groups, factions


def build_type_stats(results, snapshot, n_runs):
    """Aggregate stats by unit_key (named heroes stay individual, generics group by type)."""
    all_keys = set()
    key_to_faction = {}
    key_count = defaultdict(int)

    for uid, u in snapshot.items():
        k = unit_key(uid, snapshot)
        all_keys.add(k)
        key_to_faction[k] = u["faction"]
        key_count[k] += 1

    stats = {}
    for k in all_keys:
        stats[k] = {
            "faction": key_to_faction[k],
            "count": key_count[k],
            "hp": 0, "ac": 0, "dmg_str": "",
            "total_dmg": [], "total_kills": [],
            "survival_rate": 0,
            "avg_death_round": [],
        }

    for uid, u in snapshot.items():
        k = unit_key(uid, snapshot)
        stats[k]["hp"] = u["max_hp"]
        stats[k]["ac"] = u["ac"]
        stats[k]["dmg_str"] = u["dmg"]

    for r in results:
        per_key_dmg = defaultdict(int)
        per_key_kills = defaultdict(int)

        for uid in snapshot:
            k = unit_key(uid, snapshot)
            per_key_dmg[k] += r["per_unit_dmg"].get(uid, 0)
            per_key_kills[k] += r["per_unit_kills"].get(uid, 0)

            if r["survivors"].get(uid, False):
                stats[k]["survival_rate"] += 1

            if uid in r["per_unit_death_round"]:
                stats[k]["avg_death_round"].append(r["per_unit_death_round"][uid])

        for k in all_keys:
            stats[k]["total_dmg"].append(per_key_dmg.get(k, 0))
            stats[k]["total_kills"].append(per_key_kills.get(k, 0))

    for k in all_keys:
        total_units = stats[k]["count"] * n_runs
        stats[k]["survival_pct"] = stats[k]["survival_rate"] / total_units * 100 if total_units else 0
        stats[k]["avg_dmg"] = np.mean(stats[k]["total_dmg"])
        stats[k]["avg_kills"] = np.mean(stats[k]["total_kills"])
        stats[k]["dmg_per_unit"] = stats[k]["avg_dmg"] / stats[k]["count"] if stats[k]["count"] else 0
        stats[k]["kills_per_unit"] = stats[k]["avg_kills"] / stats[k]["count"] if stats[k]["count"] else 0
        if stats[k]["avg_death_round"]:
            stats[k]["mean_death_round"] = np.mean(stats[k]["avg_death_round"])
        else:
            stats[k]["mean_death_round"] = None

    return stats


def plot_dashboard(results, snapshot, groups, factions, n_runs):
    stats = build_type_stats(results, snapshot, n_runs)
    faction_names = list(factions.keys())
    f1, f2 = faction_names[0], faction_names[1]

    rounds_list = [r["rounds"] for r in results]

    f1_keys = sorted([k for k, s in stats.items() if s["faction"] == f1],
                     key=lambda k: stats[k]["avg_dmg"], reverse=True)
    f2_keys = sorted([k for k, s in stats.items() if s["faction"] == f2],
                     key=lambda k: stats[k]["avg_dmg"], reverse=True)
    all_keys = f1_keys + f2_keys

    def make_label(k):
        s = stats[k]
        n = s["count"]
        prefix = f"{k}" if n == 1 else f"{k} ×{n}"
        return f"{prefix}\nAC{s['ac']} HP{s['hp']} {s['dmg_str']}"

    C_E = "#e94560"
    C_A = "#2a9d8f"
    C_GOLD = "#ffd700"

    fig = plt.figure(figsize=(22, 16))
    fig.patch.set_facecolor("#1a1a2e")
    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)

    def style_ax(ax):
        ax.set_facecolor("#16213e")
        ax.tick_params(colors="white", labelsize=7)
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        for spine in ax.spines.values():
            spine.set_color("#333")

    # ─── 1. Avg Damage per Unit Type (horizontal bar) ───
    ax = fig.add_subplot(gs[0, 0])
    style_ax(ax)
    y = np.arange(len(all_keys))
    vals = [stats[k]["avg_dmg"] for k in all_keys]
    bar_c = [C_E if stats[k]["faction"] == f1 else C_A for k in all_keys]
    labels = [make_label(k) for k in all_keys]
    bars = ax.barh(y, vals, color=bar_c, edgecolor="white", linewidth=0.3)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6, color="white")
    ax.set_xlabel("Avg Total Damage / Battle")
    ax.set_title("Damage Output by Unit Type (total)")
    ax.invert_yaxis()
    for bar, v in zip(bars, vals):
        ax.text(bar.get_width() + max(vals)*0.01, bar.get_y() + bar.get_height()/2,
                f"{v:.0f}", va="center", fontsize=7, color="white")

    # ─── 2. Avg Damage PER UNIT (efficiency) ───
    ax = fig.add_subplot(gs[0, 1])
    style_ax(ax)
    vals2 = [stats[k]["dmg_per_unit"] for k in all_keys]
    bars = ax.barh(y, vals2, color=bar_c, edgecolor="white", linewidth=0.3)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6, color="white")
    ax.set_xlabel("Avg Damage per Unit / Battle")
    ax.set_title("Damage Efficiency (per single unit)")
    ax.invert_yaxis()
    for bar, v in zip(bars, vals2):
        ax.text(bar.get_width() + max(vals2)*0.01, bar.get_y() + bar.get_height()/2,
                f"{v:.1f}", va="center", fontsize=7, color="white")

    # ─── 3. Avg Kills per Unit Type ───
    ax = fig.add_subplot(gs[0, 2])
    style_ax(ax)
    vals3 = [stats[k]["avg_kills"] for k in all_keys]
    bars = ax.barh(y, vals3, color=bar_c, edgecolor="white", linewidth=0.3)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6, color="white")
    ax.set_xlabel("Avg Kills / Battle")
    ax.set_title("Kill Output by Unit Type")
    ax.invert_yaxis()
    for bar, v in zip(bars, vals3):
        ax.text(bar.get_width() + max(vals3)*0.01, bar.get_y() + bar.get_height()/2,
                f"{v:.1f}", va="center", fontsize=7, color="white")

    # ─── 4. Survival Rate ───
    ax = fig.add_subplot(gs[1, 0])
    style_ax(ax)
    vals4 = [stats[k]["survival_pct"] for k in all_keys]
    bars = ax.barh(y, vals4, color=bar_c, edgecolor="white", linewidth=0.3)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6, color="white")
    ax.set_xlabel("Survival %")
    ax.set_title("Survival Rate")
    ax.set_xlim(0, 105)
    ax.invert_yaxis()
    for bar, v in zip(bars, vals4):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                f"{v:.0f}%", va="center", fontsize=7, color="white")

    # ─── 5. Mean Death Round ───
    ax = fig.add_subplot(gs[1, 1])
    style_ax(ax)
    death_keys = [k for k in all_keys if stats[k]["mean_death_round"] is not None]
    dy = np.arange(len(death_keys))
    dvals = [stats[k]["mean_death_round"] for k in death_keys]
    dlabels = [make_label(k) for k in death_keys]
    dcolors = [C_E if stats[k]["faction"] == f1 else C_A for k in death_keys]
    bars = ax.barh(dy, dvals, color=dcolors, edgecolor="white", linewidth=0.3)
    ax.set_yticks(dy)
    ax.set_yticklabels(dlabels, fontsize=6, color="white")
    ax.set_xlabel("Avg Round of Death")
    ax.set_title("When Units Die (lower = dies faster)")
    ax.invert_yaxis()
    for bar, v in zip(bars, dvals):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2,
                f"R{v:.1f}", va="center", fontsize=7, color=C_GOLD)

    # ─── 6. Battle Duration ───
    ax = fig.add_subplot(gs[1, 2])
    style_ax(ax)
    ax.hist(rounds_list, bins=range(1, max(rounds_list) + 2), color="#533483",
            edgecolor="#1a1a2e", alpha=0.9, align="left")
    avg_r = np.mean(rounds_list)
    ax.axvline(avg_r, color=C_GOLD, linestyle="--", linewidth=2, label=f"Mean={avg_r:.1f}")
    ax.set_xlabel("Rounds")
    ax.set_ylabel("Frequency")
    ax.set_title("Battle Duration")
    ax.legend(fontsize=8, facecolor="#1a1a2e", edgecolor="#333", labelcolor="white")

    # ─── 7. Damage Share Pie — Enemies ───
    ax = fig.add_subplot(gs[2, 0])
    style_ax(ax)
    e_vals = [(k, stats[k]["avg_dmg"]) for k in f1_keys if stats[k]["avg_dmg"] > 0]
    if e_vals:
        e_names, e_dmgs = zip(*e_vals)
        e_pcts = [d / sum(e_dmgs) * 100 for d in e_dmgs]
        e_labels = [f"{n} ({p:.0f}%)" for n, p in zip(e_names, e_pcts)]
        e_colors = plt.cm.Reds(np.linspace(0.3, 0.9, len(e_vals)))
        ax.pie(e_dmgs, labels=e_labels, colors=e_colors, startangle=90,
               textprops={"color": "white", "fontsize": 7})
    ax.set_title(f"Damage Share — {f1}", color=C_E)

    # ─── 8. Damage Share Pie — Allies ───
    ax = fig.add_subplot(gs[2, 1])
    style_ax(ax)
    a_vals = [(k, stats[k]["avg_dmg"]) for k in f2_keys if stats[k]["avg_dmg"] > 0]
    if a_vals:
        a_names, a_dmgs = zip(*a_vals)
        a_pcts = [d / sum(a_dmgs) * 100 for d in a_dmgs]
        a_labels = [f"{n} ({p:.0f}%)" for n, p in zip(a_names, a_pcts)]
        a_colors = plt.cm.BuGn(np.linspace(0.3, 0.9, len(a_vals)))
        ax.pie(a_dmgs, labels=a_labels, colors=a_colors, startangle=90,
               textprops={"color": "white", "fontsize": 7})
    ax.set_title(f"Damage Share — {f2}", color=C_A)

    # ─── 9. Summary Table ───
    ax = fig.add_subplot(gs[2, 2])
    style_ax(ax)
    ax.axis("off")

    f1_total_dmg = sum(stats[k]["avg_dmg"] for k in f1_keys)
    f2_total_dmg = sum(stats[k]["avg_dmg"] for k in f2_keys)
    f1_total_kills = sum(stats[k]["avg_kills"] for k in f1_keys)
    f2_total_kills = sum(stats[k]["avg_kills"] for k in f2_keys)
    f1_count = sum(stats[k]["count"] for k in f1_keys)
    f2_count = sum(stats[k]["count"] for k in f2_keys)
    f1_surv = sum(stats[k]["survival_pct"] * stats[k]["count"] for k in f1_keys) / f1_count if f1_count else 0
    f2_surv = sum(stats[k]["survival_pct"] * stats[k]["count"] for k in f2_keys) / f2_count if f2_count else 0

    f1_wins = sum(1 for r in results
                  if all(not r["survivors"].get(uid, False)
                         for grp in factions[f2] for uid in groups[grp]["unit_ids"])
                  and any(r["survivors"].get(uid, False)
                          for grp in factions[f1] for uid in groups[grp]["unit_ids"]))
    f2_wins = n_runs - f1_wins

    lines = [
        f"{'':>18s}  {'enemies':>10s}  {'allies':>10s}",
        f"{'Units':>18s}  {f1_count:>10d}  {f2_count:>10d}",
        f"{'Avg Total Dmg':>18s}  {f1_total_dmg:>10.0f}  {f2_total_dmg:>10.0f}",
        f"{'Avg Total Kills':>18s}  {f1_total_kills:>10.1f}  {f2_total_kills:>10.1f}",
        f"{'Avg Survival':>18s}  {f1_surv:>9.0f}%  {f2_surv:>9.0f}%",
        f"{'Win Rate':>18s}  {f1_wins/n_runs*100:>9.0f}%  {f2_wins/n_runs*100:>9.0f}%",
        f"{'Avg Rounds':>18s}  {np.mean(rounds_list):>10.1f}",
    ]
    text = "\n".join(lines)
    ax.text(0.05, 0.95, text, transform=ax.transAxes, fontsize=9,
            verticalalignment="top", fontfamily="monospace", color="white")
    ax.set_title("Battle Summary")

    fig.suptitle(
        f"Full Battle Sim: {f1} ({f1_count}) vs {f2} ({f2_count})  |  {n_runs} battles",
        fontsize=15, fontweight="bold", y=0.99, color="white"
    )

    plt.tight_layout(rect=[0, 0.01, 1, 0.96])
    out = Path(__file__).parent / "sim-battle.png"
    plt.savefig(str(out), dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full Battle Simulation Dashboard")
    parser.add_argument("-n", "--runs", type=int, default=500, help="Number of battle simulations")
    parser.add_argument("--max-rounds", type=int, default=20, help="Max rounds per battle")
    args = parser.parse_args()

    engine = MassCombatEngine()
    engine._load()

    print(f"Running {args.runs} full battle simulations (max {args.max_rounds} rounds each)...")
    results, snapshot, groups, factions = simulate_full(engine, args.runs)
    plot_dashboard(results, snapshot, groups, factions, args.runs)
