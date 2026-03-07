#!/usr/bin/env python3
"""
Firearms Combat Balance Dashboard — matplotlib visual edition.
Monte Carlo simulations → PNG charts.
"""

import random
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

PROJECT_ROOT = next(p for p in Path(__file__).parents if (p / ".git").exists())
OUTPUT_DIR = PROJECT_ROOT / ".claude" / "additional" / "modules" / "firearms-combat" / "tools"

WEAPONS = {
    "PM Pistol":  {"damage": "2d4+1", "pen": 1, "rpm": 30,  "mag": 8},
    "Glock 17":   {"damage": "2d4+2", "pen": 2, "rpm": 60,  "mag": 17},
    "AK-74":      {"damage": "2d6+2", "pen": 3, "rpm": 650, "mag": 30},
    "AKM":        {"damage": "2d8+3", "pen": 4, "rpm": 600, "mag": 30},
    "M4A1":       {"damage": "2d6+2", "pen": 3, "rpm": 700, "mag": 30},
    "SVD":        {"damage": "2d10+4","pen": 5, "rpm": 30,  "mag": 10},
    "SPAS-12":    {"damage": "3d8+2", "pen": 2, "rpm": 40,  "mag": 8},
}

ENEMIES = {
    "Snork":       {"ac": 14, "hp": 25,  "prot": 1},
    "Bandit":      {"ac": 13, "hp": 20,  "prot": 2},
    "Mercenary":   {"ac": 16, "hp": 30,  "prot": 3},
    "Controller":  {"ac": 12, "hp": 60,  "prot": 0},
    "Exo-Soldier": {"ac": 19, "hp": 45,  "prot": 7},
}

SIMS = 10000
ATTACK_BONUS = 8
IS_SHARP = True

COLORS = {
    "single": "#2ecc71",
    "burst": "#f39c12",
    "full_auto": "#e74c3c",
}
BG_COLOR = "#1a1a2e"
CARD_COLOR = "#16213e"
TEXT_COLOR = "#e0e0e0"
GRID_COLOR = "#2a2a4a"


def roll_damage(dice_str):
    if '+' in dice_str:
        dice_part, bonus = dice_str.split('+')
        bonus = int(bonus)
    elif '-' in dice_str:
        dice_part, bonus_str = dice_str.split('-')
        bonus = -int(bonus_str)
    else:
        dice_part, bonus = dice_str, 0
    n, d = dice_part.split('d')
    return sum(random.randint(1, int(d)) for _ in range(int(n))) + bonus


def pen_vs_prot(damage, pen, prot):
    if pen > prot:
        return damage
    elif pen <= prot / 2:
        return damage // 4
    else:
        return damage // 2


def double_dice(dice_str):
    if 'd' not in dice_str:
        return dice_str
    parts = dice_str.split('d')
    return f"{int(parts[0]) * 2}d{parts[1]}"


def sim_single(weapon, atk, target):
    roll = random.randint(1, 20)
    crit = roll == 20
    hit = crit or (roll != 1 and roll + atk >= target["ac"])
    dmg = 0
    if hit:
        dd = double_dice(weapon["damage"]) if crit else weapon["damage"]
        dmg = pen_vs_prot(roll_damage(dd), weapon["pen"], target["prot"])
    return 1, dmg, 1 if hit else 0


def sim_burst(weapon, atk, target, is_sharp=False):
    step = -2 if is_sharp else -3
    shots = min(3, weapon["mag"])
    total_dmg, total_hits = 0, 0
    for i in range(shots):
        mod = atk + i * step
        roll = random.randint(1, 20)
        crit = roll == 20
        hit = crit or (roll != 1 and roll + mod >= target["ac"])
        if hit:
            total_hits += 1
            dd = double_dice(weapon["damage"]) if crit else weapon["damage"]
            total_dmg += pen_vs_prot(roll_damage(dd), weapon["pen"], target["prot"])
    return shots, total_dmg, total_hits


def sim_full_auto(weapon, atk, target, ammo, is_sharp=False, max_per_target=10):
    step = -2 if is_sharp else -3
    max_shots = int((weapon["rpm"] / 60) * 6)
    shots = min(ammo, max_shots, max_per_target)
    total_dmg, total_hits = 0, 0
    for i in range(shots):
        mod = atk + i * step
        roll = random.randint(1, 20)
        crit = roll == 20
        hit = crit or (roll != 1 and roll + mod >= target["ac"])
        if hit:
            total_hits += 1
            dd = double_dice(weapon["damage"]) if crit else weapon["damage"]
            total_dmg += pen_vs_prot(roll_damage(dd), weapon["pen"], target["prot"])
    return shots, total_dmg, total_hits


def run_sims(weapon, target, atk=ATTACK_BONUS, is_sharp=IS_SHARP):
    results = {}
    for mode in ["single", "burst", "full_auto"]:
        dmgs, hits_list, ammos, kills = [], [], [], 0
        for _ in range(SIMS):
            t = dict(target)
            if mode == "single":
                a, d, h = sim_single(weapon, atk, t)
            elif mode == "burst":
                a, d, h = sim_burst(weapon, atk, t, is_sharp)
            else:
                a, d, h = sim_full_auto(weapon, atk, t, weapon["mag"], is_sharp)
            dmgs.append(d)
            hits_list.append(h)
            ammos.append(a)
            if d >= t["hp"]:
                kills += 1
        avg_a = sum(ammos) / SIMS
        results[mode] = {
            "avg_dmg": sum(dmgs) / SIMS,
            "avg_hits": sum(hits_list) / SIMS,
            "avg_ammo": avg_a,
            "kill_pct": kills / SIMS * 100,
            "dpa": (sum(dmgs) / SIMS) / avg_a if avg_a > 0 else 0,
            "dmg_dist": dmgs,
        }
    return results


def style_ax(ax, title=None):
    ax.set_facecolor(CARD_COLOR)
    ax.tick_params(colors=TEXT_COLOR, labelsize=9)
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.yaxis.label.set_color(TEXT_COLOR)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    ax.grid(True, color=GRID_COLOR, alpha=0.5, linewidth=0.5)
    if title:
        ax.set_title(title, color=TEXT_COLOR, fontsize=11, fontweight='bold', pad=10)


def main():
    fig = plt.figure(figsize=(20, 24), facecolor=BG_COLOR)
    fig.suptitle("FIREARMS COMBAT — BALANCE DASHBOARD",
                 color="#00d4ff", fontsize=18, fontweight='bold', y=0.98)
    fig.text(0.5, 0.965,
             f"{SIMS:,} simulations per scenario  |  Attack +{ATTACK_BONUS} (Sharpshooter)  |  All weapons from template",
             ha='center', color=TEXT_COLOR, fontsize=10, alpha=0.7)

    gs = gridspec.GridSpec(4, 2, hspace=0.35, wspace=0.3,
                           left=0.07, right=0.95, top=0.94, bottom=0.04)

    # ═══════════════════════════════════════════════════════════════
    # CHART 1: DPA by weapon (grouped bar)
    # ═══════════════════════════════════════════════════════════════
    ax1 = fig.add_subplot(gs[0, 0])
    style_ax(ax1, "Damage Per Ammo (DPA) vs Bandit")

    wnames = list(WEAPONS.keys())
    bandit = ENEMIES["Bandit"]
    dpa_data = {m: [] for m in ["single", "burst", "full_auto"]}
    for wn in wnames:
        r = run_sims(WEAPONS[wn], bandit)
        for m in dpa_data:
            dpa_data[m].append(r[m]["dpa"])

    x = np.arange(len(wnames))
    w = 0.25
    for i, mode in enumerate(["single", "burst", "full_auto"]):
        ax1.bar(x + i * w, dpa_data[mode], w, color=COLORS[mode], label=mode, alpha=0.9)
    ax1.set_xticks(x + w)
    ax1.set_xticklabels(wnames, rotation=30, ha='right', fontsize=8)
    ax1.set_ylabel("Damage per round spent")
    ax1.legend(facecolor=CARD_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    # ═══════════════════════════════════════════════════════════════
    # CHART 2: Kill % heatmap (AK-74 vs all enemies)
    # ═══════════════════════════════════════════════════════════════
    ax2 = fig.add_subplot(gs[0, 1])
    style_ax(ax2, "One-Round Kill % — AK-74")

    enemy_names = list(ENEMIES.keys())
    modes = ["single", "burst", "full_auto"]
    kill_matrix = []
    for en in enemy_names:
        r = run_sims(WEAPONS["AK-74"], ENEMIES[en])
        kill_matrix.append([r[m]["kill_pct"] for m in modes])

    kill_arr = np.array(kill_matrix)
    im = ax2.imshow(kill_arr, cmap='RdYlGn', aspect='auto', vmin=0, vmax=100)
    ax2.set_xticks(range(len(modes)))
    ax2.set_xticklabels(modes, fontsize=9)
    ax2.set_yticks(range(len(enemy_names)))
    ax2.set_yticklabels([f"{n}\n({ENEMIES[n]['hp']}hp AC{ENEMIES[n]['ac']})" for n in enemy_names], fontsize=8)
    for i in range(len(enemy_names)):
        for j in range(len(modes)):
            v = kill_arr[i, j]
            color = "black" if v > 50 else "white"
            ax2.text(j, i, f"{v:.0f}%", ha='center', va='center', color=color, fontsize=10, fontweight='bold')
    cbar = fig.colorbar(im, ax=ax2, shrink=0.8)
    cbar.ax.yaxis.set_tick_params(color=TEXT_COLOR)
    cbar.ax.yaxis.set_ticklabels(cbar.ax.yaxis.get_ticklabels(), color=TEXT_COLOR)

    # ═══════════════════════════════════════════════════════════════
    # CHART 3: Full-auto accuracy decay curve
    # ═══════════════════════════════════════════════════════════════
    ax3 = fig.add_subplot(gs[1, 0])
    style_ax(ax3, "Full Auto Accuracy Decay — Hit % by Shot #")

    for ac_label, ac_val, ls in [("AC 12 (Controller)", 12, "-"),
                                  ("AC 14 (Snork)", 14, "--"),
                                  ("AC 16 (Mercenary)", 16, "-."),
                                  ("AC 19 (Exo)", 19, ":")]:
        shots = list(range(1, 31))
        hit_pcts = []
        for s in shots:
            mod = ATTACK_BONUS + (s - 1) * (-2 if IS_SHARP else -3)
            need = ac_val - mod
            chance = max(5, min(95, (21 - need) / 20 * 100))
            hit_pcts.append(chance)
        ax3.plot(shots, hit_pcts, ls, linewidth=2, label=ac_label)

    ax3.axhline(y=50, color='#ff6b6b', alpha=0.4, linestyle='--', linewidth=1)
    ax3.text(28, 52, "50%", color='#ff6b6b', fontsize=8, alpha=0.6)
    ax3.axhline(y=5, color='#ff6b6b', alpha=0.3, linestyle=':', linewidth=1)
    ax3.text(28, 7, "nat-20 only", color='#ff6b6b', fontsize=7, alpha=0.5)
    ax3.set_xlabel("Shot number")
    ax3.set_ylabel("Hit chance %")
    ax3.set_ylim(0, 100)
    ax3.legend(facecolor=CARD_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    # ═══════════════════════════════════════════════════════════════
    # CHART 4: Damage distribution histograms (AK-74 vs Bandit)
    # ═══════════════════════════════════════════════════════════════
    ax4 = fig.add_subplot(gs[1, 1])
    style_ax(ax4, "Damage Distribution — AK-74 vs Bandit (1 round)")

    r_ak = run_sims(WEAPONS["AK-74"], ENEMIES["Bandit"])
    bandit_hp = ENEMIES["Bandit"]["hp"]

    for mode in ["single", "burst", "full_auto"]:
        data = r_ak[mode]["dmg_dist"]
        ax4.hist(data, bins=40, alpha=0.5, color=COLORS[mode], label=mode, density=True)

    ax4.axvline(x=bandit_hp, color='white', linestyle='--', linewidth=2, alpha=0.8)
    ax4.text(bandit_hp + 1, ax4.get_ylim()[1] * 0.9, f"Bandit HP={bandit_hp}",
             color='white', fontsize=9, fontweight='bold')
    ax4.set_xlabel("Total damage dealt")
    ax4.set_ylabel("Density")
    ax4.legend(facecolor=CARD_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    # ═══════════════════════════════════════════════════════════════
    # CHART 5: Avg damage by weapon per mode (horizontal bar)
    # ═══════════════════════════════════════════════════════════════
    ax5 = fig.add_subplot(gs[2, 0])
    style_ax(ax5, "Avg Damage per Round vs Bandit")

    y_pos = np.arange(len(wnames))
    h = 0.25
    for i, mode in enumerate(["single", "burst", "full_auto"]):
        vals = []
        for wn in wnames:
            r = run_sims(WEAPONS[wn], bandit)
            vals.append(r[mode]["avg_dmg"])
        ax5.barh(y_pos + i * h, vals, h, color=COLORS[mode], label=mode, alpha=0.9)

    ax5.axvline(x=bandit["hp"], color='white', linestyle='--', alpha=0.5)
    ax5.text(bandit["hp"] + 0.5, len(wnames) - 0.3, f"HP={bandit['hp']}", color='white', fontsize=8)
    ax5.set_yticks(y_pos + h)
    ax5.set_yticklabels(wnames, fontsize=9)
    ax5.set_xlabel("Avg damage")
    ax5.legend(facecolor=CARD_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    # ═══════════════════════════════════════════════════════════════
    # CHART 6: Ammo cost to kill (multi-round sim)
    # ═══════════════════════════════════════════════════════════════
    ax6 = fig.add_subplot(gs[2, 1])
    style_ax(ax6, "Ammo Cost to Kill One Bandit (avg rounds)")

    ammo_data = {m: [] for m in modes}
    for wn in wnames:
        weapon = WEAPONS[wn]
        for mode in modes:
            kills_ammo = []
            for _ in range(SIMS):
                hp_left = bandit["hp"]
                total_ammo = 0
                rnd = 0
                while hp_left > 0 and rnd < 50:
                    rnd += 1
                    t = {"ac": bandit["ac"], "hp": hp_left, "prot": bandit["prot"]}
                    if mode == "single":
                        a, d, _ = sim_single(weapon, ATTACK_BONUS, t)
                    elif mode == "burst":
                        a, d, _ = sim_burst(weapon, ATTACK_BONUS, t, IS_SHARP)
                    else:
                        a, d, _ = sim_full_auto(weapon, ATTACK_BONUS, t, weapon["mag"], IS_SHARP)
                    total_ammo += a
                    hp_left -= d
                kills_ammo.append(total_ammo)
            ammo_data[mode].append(sum(kills_ammo) / len(kills_ammo))

    for i, mode in enumerate(modes):
        ax6.bar(x + i * w, ammo_data[mode], w, color=COLORS[mode], label=mode, alpha=0.9)

    ax6.set_xticks(x + w)
    ax6.set_xticklabels(wnames, rotation=30, ha='right', fontsize=8)
    ax6.set_ylabel("Ammo rounds to kill")
    ax6.legend(facecolor=CARD_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR, fontsize=8)

    # ═══════════════════════════════════════════════════════════════
    # CHART 7: PEN vs PROT effectiveness matrix
    # ═══════════════════════════════════════════════════════════════
    ax7 = fig.add_subplot(gs[3, 0])
    style_ax(ax7, "PEN vs PROT — Damage Scaling Matrix")

    pen_range = range(1, 8)
    prot_range = range(0, 8)
    matrix = []
    for prot in prot_range:
        row = []
        for pen in pen_range:
            if pen > prot:
                row.append(100)
            elif pen <= prot / 2:
                row.append(25)
            else:
                row.append(50)
        matrix.append(row)

    pen_arr = np.array(matrix)
    im2 = ax7.imshow(pen_arr, cmap='RdYlGn', aspect='auto', vmin=0, vmax=100)
    ax7.set_xticks(range(len(list(pen_range))))
    ax7.set_xticklabels([str(p) for p in pen_range], fontsize=9)
    ax7.set_yticks(range(len(list(prot_range))))
    ax7.set_yticklabels([str(p) for p in prot_range], fontsize=9)
    ax7.set_xlabel("Weapon PEN")
    ax7.set_ylabel("Armor PROT")

    for i, prot in enumerate(prot_range):
        for j, pen in enumerate(pen_range):
            v = pen_arr[i, j]
            c = "black" if v > 60 else "white"
            ax7.text(j, i, f"{v}%", ha='center', va='center', color=c, fontsize=9, fontweight='bold')

    weapon_pen_labels = {w: WEAPONS[w]["pen"] for w in WEAPONS}
    for wn, pen in weapon_pen_labels.items():
        if 1 <= pen <= 7:
            ax7.annotate(wn, xy=(pen - 1, -0.7), fontsize=6, color=TEXT_COLOR,
                        ha='center', rotation=45, alpha=0.7)

    # ═══════════════════════════════════════════════════════════════
    # CHART 8: Balance scorecard (text panel)
    # ═══════════════════════════════════════════════════════════════
    ax8 = fig.add_subplot(gs[3, 1])
    ax8.set_facecolor(CARD_COLOR)
    ax8.axis('off')
    ax8.set_title("BALANCE VERDICT", color="#00d4ff", fontsize=12, fontweight='bold', pad=10)

    r_bandit = run_sims(WEAPONS["AK-74"], ENEMIES["Bandit"])
    r_merc = run_sims(WEAPONS["AK-74"], ENEMIES["Mercenary"])
    r_snork = run_sims(WEAPONS["AK-74"], ENEMIES["Snork"])

    lines = []
    lines.append(("AK-74 Full Auto vs Bandit (20hp):", "header"))
    fa_kb = r_bandit["full_auto"]["kill_pct"]
    status = "[!] OVERPOWERED" if fa_kb > 90 else ("[OK]OK" if fa_kb > 50 else "[X] WEAK")
    lines.append((f"  Kill rate: {fa_kb:.0f}% → {status}", "warn" if fa_kb > 90 else "ok"))

    lines.append(("", ""))
    lines.append(("AK-74 Full Auto vs Snork (25hp):", "header"))
    fa_ks = r_snork["full_auto"]["kill_pct"]
    status = "[!] OVERPOWERED" if fa_ks > 90 else "[OK]OK"
    lines.append((f"  Kill rate: {fa_ks:.0f}% → {status}", "warn" if fa_ks > 90 else "ok"))

    lines.append(("", ""))
    lines.append(("AK-74 Full Auto vs Mercenary (30hp AC16):", "header"))
    fa_km = r_merc["full_auto"]["kill_pct"]
    status = "[OK]BALANCED" if 20 < fa_km < 70 else ("[!] TOO EASY" if fa_km >= 70 else "[OK]HARD")
    lines.append((f"  Kill rate: {fa_km:.0f}% → {status}", "warn" if fa_km >= 70 else "ok"))

    lines.append(("", ""))
    lines.append(("DPA Efficiency (vs Bandit):", "header"))
    s_dpa = r_bandit["single"]["dpa"]
    b_dpa = r_bandit["burst"]["dpa"]
    f_dpa = r_bandit["full_auto"]["dpa"]
    lines.append((f"  Single: {s_dpa:.1f}  Burst: {b_dpa:.1f}  Auto: {f_dpa:.1f}", "ok"))
    ratio = f_dpa / s_dpa if s_dpa > 0 else 0
    if ratio < 0.5:
        lines.append((f"  Auto/Single ratio: {ratio:.0%} → [OK]Good ammo tradeoff", "ok"))
    else:
        lines.append((f"  Auto/Single ratio: {ratio:.0%} → ⚠️  Auto too efficient", "warn"))

    lines.append(("", ""))
    lines.append(("CURRENT CONFIG:", "header"))
    lines.append(("  Penalty: -3/shot (sharp: -2)  |  Cap: 10 shots/target", "ok"))
    lines.append(("", ""))
    lines.append(("SUGGESTIONS:", "header"))
    if fa_kb > 90:
        lines.append(("  → Still OP! Consider raising penalty or lowering cap", "warn"))
    if fa_km >= 70:
        lines.append(("  → Buff Mercenary: HP 30→45, PROT 3→5", "suggest"))
    if fa_kb <= 90 and fa_km < 70:
        lines.append(("  → System is balanced! No changes needed.", "ok"))

    y = 0.95
    for text, kind in lines:
        if kind == "header":
            color, weight, size = "#00d4ff", "bold", 10
        elif kind == "warn":
            color, weight, size = "#e74c3c", "normal", 9
        elif kind == "suggest":
            color, weight, size = "#f39c12", "normal", 9
        elif kind == "ok":
            color, weight, size = "#2ecc71", "normal", 9
        else:
            color, weight, size = TEXT_COLOR, "normal", 9
        ax8.text(0.05, y, text, transform=ax8.transAxes, fontsize=size,
                color=color, fontweight=weight, fontfamily='monospace',
                verticalalignment='top')
        y -= 0.06

    out_path = OUTPUT_DIR / "balance-dashboard.png"
    fig.savefig(out_path, dpi=150, facecolor=BG_COLOR)
    plt.close()
    print(f"[SUCCESS] Dashboard saved to: {out_path}")


if __name__ == "__main__":
    main()
