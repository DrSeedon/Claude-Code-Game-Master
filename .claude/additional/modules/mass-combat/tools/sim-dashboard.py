#!/usr/bin/env python3
"""Mass Combat simulation dashboard — matplotlib visualization."""

import sys
import random
import re
import argparse
from pathlib import Path
from collections import defaultdict, Counter

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
    unit_type = unit.get("type", "")
    tmpl = templates.get(unit_type, {})
    if tmpl.get("targeting") != "aoe":
        return None
    return {
        "save_dc": tmpl.get("aoe_save_dc", 14),
        "save_type": tmpl.get("aoe_save_type", "DEX"),
        "aoe_targets": tmpl.get("aoe_targets", 3),
        "aoe_mode": tmpl.get("aoe_mode", "blast"),
    }


def is_crewed(unit, templates):
    tmpl = templates.get(unit.get("type", ""), {})
    return tmpl.get("crewed", False)


def group_has_crew(units, group_uids, templates):
    for uid in group_uids:
        if units[uid]["alive"] and not is_crewed(units[uid], templates):
            return True
    return False


def simulate(engine, atk_group, def_group, n_runs=1000):
    snapshot = {uid: dict(u) for uid, u in engine.state["units"].items()}
    templates = engine.templates

    atk_uids = [uid for uid in engine.state["groups"][atk_group]["unit_ids"]
                if engine.state["units"][uid]["alive"]]
    def_uids = [uid for uid in engine.state["groups"][def_group]["unit_ids"]
                if engine.state["units"][uid]["alive"]]

    target_counts = defaultdict(int)
    hit_counts = defaultdict(int)
    damage_totals = defaultdict(int)
    kill_counts = defaultdict(int)
    dmg_per_target_per_run = {uid: [] for uid in def_uids}
    hits_per_run = []
    dmg_per_run = []
    kills_per_run = []

    for _ in range(n_runs):
        for uid in def_uids:
            engine.state["units"][uid] = dict(snapshot[uid])

        run_hits = run_dmg = run_kills = 0
        run_dmg_per_target = defaultdict(int)

        for atk_uid in atk_uids:
            attacker = engine.state["units"][atk_uid]
            alive = [t for t in def_uids if engine.state["units"][t]["alive"]]
            if not alive:
                break

            aoe = get_aoe_info(attacker, templates)

            if is_crewed(attacker, templates) and not group_has_crew(engine.state["units"], atk_uids, templates):
                continue

            if aoe:
                is_spray = aoe["aoe_mode"] == "spray"
                n_targets = min(aoe["aoe_targets"], len(alive))

                if is_spray:
                    w = [engine.state["units"][t].get("weight", 1) for t in alive]
                    chosen = random.choices(alive, weights=w, k=n_targets)
                else:
                    chosen = random.sample(alive, n_targets)

                blast_dmg = roll_damage(attacker["dmg"]) if not is_spray else 0

                for tgt_uid in chosen:
                    target = engine.state["units"][tgt_uid]
                    target_counts[tgt_uid] += 1

                    dmg = roll_damage(attacker["dmg"]) if is_spray else blast_dmg
                    save_roll = random.randint(1, 20)
                    saved = save_roll >= aoe["save_dc"]
                    applied = dmg // 2 if saved else dmg

                    hit_counts[tgt_uid] += 1
                    run_hits += 1
                    damage_totals[tgt_uid] += applied
                    run_dmg += applied
                    run_dmg_per_target[tgt_uid] += applied
                    target["hp"] -= applied
                    if target["hp"] <= 0:
                        target["alive"] = False
                        kill_counts[tgt_uid] += 1
                        run_kills += 1
            else:
                weights = [engine.state["units"][t].get("weight", 1) for t in alive]
                target_uid = random.choices(alive, weights=weights, k=1)[0]
                target = engine.state["units"][target_uid]
                target_counts[target_uid] += 1

                roll = random.randint(1, 20)
                total_atk = roll + attacker["atk"]
                hit = (roll == 20) or (roll != 1 and total_atk >= target["ac"])

                if hit:
                    hit_counts[target_uid] += 1
                    run_hits += 1
                    crit = roll == 20
                    dmg = roll_damage(attacker["dmg"], crit)
                    damage_totals[target_uid] += dmg
                    run_dmg += dmg
                    run_dmg_per_target[target_uid] += dmg
                    target["hp"] -= dmg
                    if target["hp"] <= 0:
                        target["alive"] = False
                        kill_counts[target_uid] += 1
                        run_kills += 1

        hits_per_run.append(run_hits)
        dmg_per_run.append(run_dmg)
        kills_per_run.append(run_kills)
        for uid in def_uids:
            dmg_per_target_per_run[uid].append(run_dmg_per_target.get(uid, 0))

        for uid in def_uids:
            engine.state["units"][uid] = dict(snapshot[uid])

    has_aoe = any(get_aoe_info(engine.state["units"][u], templates) for u in atk_uids)

    return {
        "atk_group": atk_group,
        "def_group": def_group,
        "atk_uids": atk_uids,
        "def_uids": def_uids,
        "snapshot": snapshot,
        "n_runs": n_runs,
        "target_counts": target_counts,
        "hit_counts": hit_counts,
        "damage_totals": damage_totals,
        "kill_counts": kill_counts,
        "dmg_per_target_per_run": dmg_per_target_per_run,
        "hits_per_run": hits_per_run,
        "dmg_per_run": dmg_per_run,
        "kills_per_run": kills_per_run,
        "has_aoe": has_aoe,
    }


def label(uid, snap):
    t = snap[uid].get("type", "?")
    w = snap[uid].get("weight", 1)
    ac = snap[uid]["ac"]
    hp = snap[uid]["max_hp"]
    s = f"{uid}\n({t}, AC{ac}, HP{hp})"
    if w > 1:
        s += f"\nw={w}"
    return s


def plot_dashboard(d):
    snap = d["snapshot"]
    uids = d["def_uids"]
    n = d["n_runs"]
    labels = [label(uid, snap) for uid in uids]

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(
        f"Mass Combat Sim: {d['atk_group']} ({len(d['atk_uids'])}) → "
        f"{d['def_group']} ({len(uids)})  |  {n} runs"
        + ("  [AOE units present]" if d.get("has_aoe") else ""),
        fontsize=14, fontweight="bold", y=0.98
    )
    fig.patch.set_facecolor("#1a1a2e")
    colors = ["#e94560", "#0f3460", "#533483", "#16213e", "#e76f51", "#2a9d8f",
              "#f4a261", "#264653", "#e9c46a", "#2b2d42", "#8d99ae", "#ef476f",
              "#06d6a0"]

    for ax in axes.flat:
        ax.set_facecolor("#16213e")
        ax.tick_params(colors="white", labelsize=8)
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        for spine in ax.spines.values():
            spine.set_color("#333")

    bar_colors = [colors[i % len(colors)] for i in range(len(uids))]

    # 1 — Target Selection
    ax = axes[0, 0]
    total_shots = sum(d["target_counts"].values())
    actual = [d["target_counts"].get(u, 0) / total_shots * 100 if total_shots else 0 for u in uids]
    x = np.arange(len(uids))

    if d.get("has_aoe"):
        bars = ax.bar(x, actual, color="#e94560", edgecolor="white", linewidth=0.5)
        ax.set_title("Target Selection (incl. AOE splash)")
        for i, a in enumerate(actual):
            ax.text(i, a + 0.3, f"{a:.0f}%", ha="center", fontsize=7, color="#ff6b81")
    else:
        total_w = sum(snap[u].get("weight", 1) for u in uids)
        expected = [snap[u].get("weight", 1) / total_w * 100 for u in uids]
        w_bar = 0.35
        ax.bar(x - w_bar/2, expected, w_bar, label="Expected", color="#0f3460", edgecolor="white", linewidth=0.5)
        ax.bar(x + w_bar/2, actual, w_bar, label="Actual", color="#e94560", edgecolor="white", linewidth=0.5)
        ax.set_title("Target Selection (weight)")
        ax.legend(fontsize=8, facecolor="#1a1a2e", edgecolor="#333", labelcolor="white")
        for i, (e, a) in enumerate(zip(expected, actual)):
            ax.text(i - w_bar/2, e + 0.3, f"{e:.0f}%", ha="center", fontsize=7, color="#8899aa")
            ax.text(i + w_bar/2, a + 0.3, f"{a:.0f}%", ha="center", fontsize=7, color="#ff6b81")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7, color="white")
    ax.set_ylabel("%")

    # 2 — Hit/Affect Rate
    ax = axes[0, 1]
    hit_actual = []
    for u in uids:
        targeted = d["target_counts"].get(u, 0)
        hits = d["hit_counts"].get(u, 0)
        hit_actual.append(hits / targeted * 100 if targeted else 0)

    bars = ax.bar(x, hit_actual, color="#2a9d8f", edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7, color="white")
    ax.set_ylabel("%")
    ax.set_title("Hit/Affect Rate per Target" + (" (AOE = always hit)" if d.get("has_aoe") else ""))
    for i, a in enumerate(hit_actual):
        ax.text(i, a + 0.5, f"{a:.0f}%", ha="center", fontsize=7, color="#80cbc4")

    # 3 — Kill Rate per target
    ax = axes[0, 2]
    kill_pcts = [d["kill_counts"].get(u, 0) / n * 100 for u in uids]
    bars = ax.bar(x, kill_pcts, color=bar_colors, edgecolor="white", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7, color="white")
    ax.set_ylabel("%")
    ax.set_title("Kill Rate per Target (per round)")
    for bar, pct in zip(bars, kill_pcts):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f"{pct:.1f}%", ha="center", fontsize=8, color="white", fontweight="bold")

    # 4 — Damage distribution (boxplot)
    ax = axes[1, 0]
    dmg_data = [d["dmg_per_target_per_run"][u] for u in uids]
    bp = ax.boxplot(dmg_data, patch_artist=True, tick_labels=labels,
                    medianprops=dict(color="white", linewidth=2),
                    whiskerprops=dict(color="white"),
                    capprops=dict(color="white"),
                    flierprops=dict(marker=".", markerfacecolor="#e94560", markersize=3, markeredgecolor="none"))
    for patch, c in zip(bp["boxes"], bar_colors):
        patch.set_facecolor(c)
        patch.set_edgecolor("white")
    ax.tick_params(axis="x", labelsize=7)
    ax.set_ylabel("Damage")
    ax.set_title("Damage Distribution per Target")
    for i, u in enumerate(uids):
        avg = np.mean(dmg_data[i])
        ax.text(i + 1, avg, f"μ={avg:.1f}", ha="center", va="bottom", fontsize=7, color="#ffd700")

    # 5 — Total damage histogram
    ax = axes[1, 1]
    ax.hist(d["dmg_per_run"], bins=30, color="#e94560", edgecolor="#1a1a2e", alpha=0.9)
    avg_dmg = np.mean(d["dmg_per_run"])
    ax.axvline(avg_dmg, color="#ffd700", linestyle="--", linewidth=2, label=f"Mean={avg_dmg:.1f}")
    ax.set_xlabel("Total Damage per Round")
    ax.set_ylabel("Frequency")
    ax.set_title("Total Damage Distribution")
    ax.legend(fontsize=8, facecolor="#1a1a2e", edgecolor="#333", labelcolor="white")

    # 6 — Kills per round distribution
    ax = axes[1, 2]
    kill_counter = Counter(d["kills_per_run"])
    max_kills = max(d["kills_per_run"]) if d["kills_per_run"] else 0
    k_range = list(range(max_kills + 1))
    k_counts = [kill_counter.get(k, 0) / n * 100 for k in k_range]
    bars = ax.bar(k_range, k_counts, color="#2a9d8f", edgecolor="white", linewidth=0.5)
    ax.set_xlabel("Kills per Round")
    ax.set_ylabel("%")
    ax.set_title("Kill Count Distribution")
    ax.set_xticks(k_range)
    for bar, pct in zip(bars, k_counts):
        if pct > 0.5:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                    f"{pct:.1f}%", ha="center", fontsize=8, color="white", fontweight="bold")

    avg_kills = np.mean(d["kills_per_run"])
    if avg_kills < 0.5:
        verdict = "TOO HARD"
        vc = "#e94560"
    elif avg_kills < 1.5:
        verdict = "BALANCED"
        vc = "#2a9d8f"
    elif avg_kills < 2.5:
        verdict = "FAIR"
        vc = "#ffd700"
    else:
        verdict = "TOO EASY"
        vc = "#e94560"
    fig.text(0.5, 0.01,
             f"Avg hits: {np.mean(d['hits_per_run']):.1f}/{len(d['atk_uids'])}  |  "
             f"Avg dmg: {avg_dmg:.1f}  |  "
             f"Avg kills: {avg_kills:.1f}/{len(uids)}  |  "
             f"Verdict: {verdict}",
             ha="center", fontsize=11, color=vc, fontweight="bold")

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    out = Path(__file__).parent / "sim-dashboard.png"
    plt.savefig(str(out), dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mass Combat Simulation Dashboard")
    parser.add_argument("attacker", help="Attacking group name")
    parser.add_argument("defender", help="Defending group name")
    parser.add_argument("-n", "--runs", type=int, default=1000, help="Number of simulation runs")
    args = parser.parse_args()

    engine = MassCombatEngine()
    engine._load()
    data = simulate(engine, args.attacker, args.defender, args.runs)
    plot_dashboard(data)
