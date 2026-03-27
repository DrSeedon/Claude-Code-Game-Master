import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def load_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def format_money(amount: int, denominations: list) -> str:
    if not denominations:
        return str(amount)
    sorted_denoms = sorted(denominations, key=lambda d: d.get("rate", 1), reverse=True)
    parts = []
    remaining = int(amount)
    for denom in sorted_denoms:
        rate = denom.get("rate", 1)
        if rate <= 0:
            continue
        count = remaining // rate
        remaining %= rate
        if count > 0:
            parts.append(f"{count}{denom.get('symbol', '?')}")
    return " ".join(parts) if parts else f"{amount}"


def bar_color(value: float) -> str:
    if value >= 60:
        return "#dc2626"
    if value >= 30:
        return "#d97706"
    return "#16a34a"


def check_stat_consequences(stat_name: str, stat_value: float, stat_consequences: dict) -> list[str]:
    warnings = []
    for _key, cseq in stat_consequences.items():
        cond = cseq.get("condition", {})
        if cond.get("stat") != stat_name:
            continue
        op = cond.get("operator", ">=")
        threshold = cond.get("value", 0)
        triggered = False
        if op == ">=" and stat_value >= threshold:
            triggered = True
        elif op == ">" and stat_value > threshold:
            triggered = True
        elif op == "<=" and stat_value <= threshold:
            triggered = True
        elif op == "<" and stat_value < threshold:
            triggered = True
        if triggered:
            for effect in cseq.get("effects", []):
                if effect.get("type") == "message":
                    warnings.append(effect.get("text", ""))
    return warnings


def parse_unique_weight(item_str: str) -> float:
    m = re.search(r'\[(\d+(?:\.\d+)?)kg\]', item_str)
    return float(m.group(1)) if m else 0.5


def render_inner_html() -> str:
    active_file = ROOT / "world-state" / "active-campaign.txt"
    if not active_file.exists():
        return '<div class="no-campaign">No active campaign (active-campaign.txt missing)</div>'

    campaign_name = active_file.read_text(encoding="utf-8").strip()
    if not campaign_name:
        return '<div class="no-campaign">active-campaign.txt is empty</div>'

    campaign_dir = ROOT / "world-state" / "campaigns" / campaign_name

    overview = load_json(campaign_dir / "campaign-overview.json") or {}
    character = load_json(campaign_dir / "character.json") or {}
    custom_stats_data = load_json(campaign_dir / "module-data" / "custom-stats.json") or {}
    inventory_data = load_json(campaign_dir / "module-data" / "inventory-system.json") or {}
    consequences_data = load_json(campaign_dir / "consequences.json") or {}
    plots_data = load_json(campaign_dir / "plots.json") or []
    npcs_data = load_json(campaign_dir / "npcs.json") or {}
    wiki_data = load_json(campaign_dir / "wiki.json") or {}
    party_inv_data = load_json(campaign_dir / "module-data" / "inventory-party.json") or {}

    display_campaign = overview.get("campaign_name", campaign_name)
    char_name = character.get("name", overview.get("current_character", "Unknown"))
    char_level = character.get("level", "?")
    char_class = character.get("class", "")
    char_race = character.get("race", "")

    game_date = overview.get("current_date", "")
    game_time = overview.get("precise_time", overview.get("time_of_day", ""))
    location = overview.get("player_position", {}).get("current_location", overview.get("current_location", ""))

    hp = character.get("hp", {})
    hp_cur = hp.get("current", 0) if isinstance(hp, dict) else 0
    hp_max = hp.get("max", 1) if isinstance(hp, dict) else 1
    hp_pct = min(100, max(0, int(hp_cur / max(hp_max, 1) * 100)))

    xp = character.get("xp", {})
    xp_cur = xp.get("current", 0) if isinstance(xp, dict) else 0
    xp_next = xp.get("next_level", 1) if isinstance(xp, dict) else 1
    xp_pct = min(100, max(0, int(xp_cur / max(xp_next, 1) * 100)))

    money_raw = character.get("money", 0)
    currency_cfg = overview.get("currency", {})
    denoms = currency_cfg.get("denominations", [])
    money_str = format_money(money_raw, denoms)

    char_stats = custom_stats_data.get("character_stats", {})
    stat_consequences = custom_stats_data.get("stat_consequences", {})

    # --- D&D core stats ---
    ac = character.get("ac", "—")
    raw_stats = character.get("stats", {})
    char_skills = character.get("skills", {})
    prof_bonus = 2 + (char_level - 1) // 4 if isinstance(char_level, int) else 2
    save_proficiencies = [s.lower() for s in character.get("save_proficiencies", [])]

    def mod(score: int) -> str:
        m = (score - 10) // 2
        return f"+{m}" if m >= 0 else str(m)

    stackable = inventory_data.get("stackable", {})
    unique_items = inventory_data.get("unique", [])

    total_weight = 0.0
    for _iname, iinfo in stackable.items():
        if isinstance(iinfo, dict):
            total_weight += iinfo.get("qty", 1) * iinfo.get("weight", 0.5)
        else:
            total_weight += float(iinfo) * 0.5
    for ui in unique_items:
        total_weight += parse_unique_weight(str(ui))

    str_score = raw_stats.get("str", 10) if isinstance(raw_stats, dict) else 10
    carry_max = str_score * 7

    weight_pct = min(200, total_weight / max(carry_max, 1) * 100)
    if weight_pct > 160:
        weight_color = "#dc2626"
        weight_label = "OVERLOADED"
    elif weight_pct > 130:
        weight_color = "#dc2626"
        weight_label = "Heavy"
    elif weight_pct > 100:
        weight_color = "#d97706"
        weight_label = "Encumbered"
    else:
        weight_color = "#16a34a"
        weight_label = "Normal"

    active_consequences = consequences_data.get("active", []) if isinstance(consequences_data, dict) else []

    active_quests = []
    if isinstance(plots_data, list):
        for item in plots_data:
            if isinstance(item, list) and len(item) == 2:
                qname, qdata = item
                if qdata.get("status") not in ("completed", "failed"):
                    active_quests.append((qname, qdata))
            elif isinstance(item, dict) and item.get("status") not in ("completed", "failed"):
                active_quests.append((item.get("id", "?"), item))
    elif isinstance(plots_data, dict):
        for qname, qdata in plots_data.items():
            if qdata.get("status") not in ("completed", "failed"):
                active_quests.append((qname, qdata))

    def _latest_ts(info: dict, fallback_key: str = "created") -> str:
        events = info.get("events", [])
        if events:
            last = events[-1].get("timestamp", "")
            if last:
                return last
        return info.get(fallback_key, "") or ""

    npc_list = []
    if isinstance(npcs_data, dict):
        for npc_name, npc_info in npcs_data.items():
            npc_list.append((npc_name, npc_info))
        npc_list.sort(key=lambda x: _latest_ts(x[1]) if isinstance(x[1], dict) else "", reverse=True)

    active_quests.sort(key=lambda x: _latest_ts(x[1], "created_at") if isinstance(x[1], dict) else "", reverse=True)

    def h(text: str) -> str:
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def stat_bar_html(stat_name: str, stat_info: dict) -> str:
        val = stat_info.get("value", 0)
        max_val = stat_info.get("max", 100)
        pct = min(100, max(0, val / max(max_val, 1) * 100))
        color = bar_color(pct)
        warnings = check_stat_consequences(stat_name, val, stat_consequences)
        warn_html = ""
        for w in warnings:
            warn_html += f'<div class="warn">[!] {h(w)}</div>'
        display_name = stat_name.replace("_", " ").title()
        return f"""
        <div class="stat-item" data-key="stat-{stat_name}" data-val="{val:.1f}">
          <div class="stat-header">
            <span class="stat-name">{h(display_name)}</span>
            <span class="stat-val"><span data-num="{val:.1f}">{val:.1f}</span>/{int(max_val)}</span>
          </div>
          <div class="bar-bg"><div class="bar-fill" data-bar="{pct:.1f}" style="width:{pct:.1f}%;background:{color}"></div></div>
          {warn_html}
        </div>"""

    def attitude_badge(attitude: str) -> str:
        colors = {
            "friendly": ("#16a34a", "friendly"),
            "neutral": ("#6b7280", "neutral"),
            "suspicious": ("#d97706", "suspicious"),
            "hostile": ("#dc2626", "hostile"),
            "ally": ("#2563eb", "ally"),
        }
        color, label = colors.get(attitude, ("#6b7280", attitude))
        return f'<span style="color:{color};font-size:0.7rem;font-weight:700;text-transform:uppercase">[{label}]</span>'

    topbar = """
    <div class="topbar">
      <button class="wiki-btn" id="wiki-btn" onclick="toggleWiki()">Wiki</button>
      <button class="refresh-btn" id="refresh-btn" onclick="refresh()">Refresh</button>
    </div>"""

    header = f"""
    <div class="header">
      <div class="header-left">
        <div class="campaign-title" id="page-title">{h(display_campaign)}</div>
        <div class="char-info" data-key="char-info" data-val="{h(char_name)}|{h(char_class)}|{h(char_race)}|{h(char_level)}">{h(char_name)} &bull; {h(char_class)} {h(char_race)} &bull; Level {h(char_level)}</div>
      </div>
      <div class="header-right">
        <div class="location-info" data-key="location" data-val="{h(location)}">{h(location)}</div>
        <div class="time-info" data-key="time" data-val="{h(game_date)}|{h(game_time)}">{h(game_date)} &bull; {h(game_time)}</div>
      </div>
    </div>"""

    vitals = f"""
    <div class="row row1">
      <div class="card vitals-card" data-key="hp" data-val="{hp_cur}">
        <div class="card-title">HP</div>
        <div class="bar-label"><span data-num="{hp_cur}">{h(hp_cur)}</span> / {h(hp_max)}</div>
        <div class="bar-bg bar-lg"><div class="bar-fill" data-bar="{hp_pct}" style="width:{hp_pct}%;background:#16a34a"></div></div>
      </div>
      <div class="card vitals-card" data-key="xp" data-val="{xp_cur}">
        <div class="card-title">XP</div>
        <div class="bar-label"><span data-num="{xp_cur}">{h(xp_cur)}</span> / {h(xp_next)} &nbsp;<span class="lvl-badge">LVL {h(char_level)}</span></div>
        <div class="bar-bg bar-lg"><div class="bar-fill" data-bar="{xp_pct}" style="width:{xp_pct}%;background:#2563eb"></div></div>
      </div>
      <div class="card vitals-card" style="flex:0 0 80px;text-align:center" data-key="ac" data-val="{ac}">
        <div class="card-title">AC</div>
        <div class="ac-display">{h(ac)}</div>
      </div>
      <div class="card vitals-card" data-key="money" data-val="{money_raw}">
        <div class="card-title">Money</div>
        <div class="money-display" data-num="{money_raw}" data-denoms='{json.dumps(denoms, ensure_ascii=False)}'>{h(money_str)}</div>
      </div>
    </div>"""

    if char_stats:
        stats_html = "".join(stat_bar_html(sname, sinfo) for sname, sinfo in char_stats.items())
        custom_stats_row = f"""
    <div class="row">
      <div class="card full-width">
        <div class="card-title">Custom Stats</div>
        <div class="stats-grid">{stats_html}</div>
      </div>
    </div>"""
    else:
        custom_stats_row = ""

    # --- Ability scores block ---
    stat_labels = [("STR","str"),("DEX","dex"),("CON","con"),("INT","int"),("WIS","wis"),("CHA","cha")]
    abilities_html = ""
    for label, key in stat_labels:
        score = raw_stats.get(key, 10) if isinstance(raw_stats, dict) else 10
        m = mod(int(score))
        abilities_html += f"""
        <div class="ab-cell" data-key="ab-{key}" data-val="{score}">
          <div class="ab-label">{label}</div>
          <div class="ab-score">{score}</div>
          <div class="ab-mod">{m}</div>
        </div>"""

    # --- Saves (auto-calculated from stats + proficiency) ---
    save_stat_order = [("STR", "str", "сил"), ("DEX", "dex", "лов"), ("CON", "con", "вын"),
                       ("INT", "int", "инт"), ("WIS", "wis", "мдр"), ("CHA", "cha", "хар")]
    saves_html = ""
    for label, stat_key, ru_key in save_stat_order:
        score = raw_stats.get(stat_key, 10)
        save_mod = (score - 10) // 2
        is_prof = ru_key in save_proficiencies or stat_key in save_proficiencies
        if is_prof:
            save_mod += prof_bonus
        sign = f"+{save_mod}" if save_mod >= 0 else str(save_mod)
        prof_dot = "●" if is_prof else "○"
        color = "#a78bfa" if is_prof else ("var(--text)" if save_mod >= 0 else "var(--muted)")
        saves_html += f'<div class="sv-row" data-key="save-{stat_key}" data-val="{save_mod}"><span class="sv-label">{prof_dot} {label}</span><span class="sv-val" style="color:{color}">{sign}</span></div>'

    # --- Skills ---
    skills_html = ""
    if isinstance(char_skills, dict):
        sorted_skills = sorted(char_skills.items(), key=lambda x: x[1].get("total", 0) if isinstance(x[1], dict) else int(x[1]), reverse=True)
        for sname, sval in sorted_skills:
            if isinstance(sval, dict):
                total = sval.get("total", 0)
                breakdown = sval.get("breakdown", {})
                note = sval.get("note", "")
                dc_mod = sval.get("dc_mod", 0)
                dc_breakdown = sval.get("dc_breakdown", {})
            else:
                total = int(sval)
                breakdown = {}
                note = ""
                dc_mod = 0
                dc_breakdown = {}

            sign = f"+{total}" if total >= 0 else str(total)
            color = "#fbbf24" if total >= 5 else ("var(--text)" if total >= 3 else "var(--muted)")

            bd_parts = []
            for bk, bv in breakdown.items():
                if bv != 0:
                    bd_parts.append(f"{bk} {bv:+d}" if isinstance(bv, int) else f"{bk} {bv}")
            bd_str = ", ".join(bd_parts) if bd_parts else ""

            dc_parts = []
            if dc_mod != 0:
                for dk, dv in dc_breakdown.items():
                    dc_parts.append(f"{dk} {dv:+d}" if isinstance(dv, int) else f"{dk} {dv}")
                dc_str = f"DC {dc_mod:+d}" + (f" ({', '.join(dc_parts)})" if dc_parts else "")
            else:
                dc_str = ""

            extra_html = ""
            if bd_str:
                extra_html += f'<div class="sk-breakdown">{h(bd_str)}</div>'
            if dc_str:
                extra_html += f'<div class="sk-dc">{h(dc_str)}</div>'
            if note:
                extra_html += f'<div class="sk-note">{h(note)}</div>'

            skills_html += f"""<div class="sk-row" data-key="skill-{sname}" data-val="{total}">
              <div class="sk-main"><span class="sk-name">{h(sname)}</span><span class="sk-val" style="color:{color}">{sign}</span></div>
              {extra_html}
            </div>"""

    dnd_row = f"""
    <div class="row row-three-col">
      <div class="card">
        <div class="card-title">Ability Scores &nbsp;<span style="color:var(--muted);font-weight:400">PROF +{prof_bonus}</span></div>
        <div class="ab-grid">{abilities_html}</div>
      </div>
      <div class="card">
        <div class="card-title">Saving Throws</div>
        <div class="scroll-list">{saves_html if saves_html else '<div class="empty-state">—</div>'}</div>
      </div>
      <div class="card">
        <div class="card-title">Skills</div>
        <div class="scroll-list">{skills_html if skills_html else '<div class="empty-state">—</div>'}</div>
      </div>
    </div>"""

    inv_items = []
    for item_name, item_info in stackable.items():
        if isinstance(item_info, dict):
            qty = item_info.get("qty", 1)
            w_each = item_info.get("weight", 0.5)
        else:
            qty = int(item_info)
            w_each = 0.5
        w_total = qty * w_each
        inv_items.append({"name": item_name, "qty": qty, "w": w_total, "w_str": f"{w_total:.2f}kg" if qty > 1 else f"{w_each:.2f}kg", "unique": False, "key": f"inv-{item_name}"})
    for item in unique_items:
        item_str = str(item)
        w = parse_unique_weight(item_str)
        clean = re.sub(r'\s*\[\d+(?:\.\d+)?kg\]', '', item_str)
        inv_items.append({"name": clean, "qty": 1, "w": w, "w_str": f"{w:.2f}kg" if w else "—", "unique": True, "key": f"inv-u-{clean}"})

    inv_items.sort(key=lambda x: x["w"], reverse=True)

    inv_rows_html = ""
    n_items = len(inv_items)
    for idx, it in enumerate(inv_items):
        t = idx / max(n_items - 1, 1)
        if t < 0.5:
            r, g, b = int(220 + (251-220)*t*2), int(38 + (191-38)*t*2), int(38 + (36-38)*t*2)
        else:
            t2 = (t - 0.5) * 2
            r, g, b = int(251 - (251-22)*t2), int(191 - (191-163)*t2), int(36 + (106-36)*t2)
        w_color = f"#{r:02x}{g:02x}{b:02x}"
        ucls = ' class="inv-unique"' if it["unique"] else ""
        inv_rows_html += f"""<tr{ucls} data-key="{h(it['key'])}" data-val="{it['qty']}">
          <td class="inv-name">{h(it['name'])}</td>
          <td class="inv-qty">{it['qty']}</td>
          <td class="inv-w" style="color:{w_color}">{it['w_str']}</td>
        </tr>"""

    weight_bar_pct = min(100, weight_pct)
    inv_header_html = f"""
    <div class="inv-weight-header" data-key="weight" data-val="{total_weight:.2f}">
      <span class="inv-weight-label">⚖ <span data-num="{total_weight:.2f}">{total_weight:.2f}</span>kg / {carry_max}kg</span>
      <span class="inv-weight-status" style="color:{weight_color}">{weight_label}</span>
    </div>
    <div class="bar-bg" style="margin-bottom:8px">
      <div class="bar-fill" data-bar="{weight_bar_pct:.1f}" style="width:{weight_bar_pct:.1f}%;background:{weight_color}"></div>
    </div>"""

    inv_table_html = f"""
    <table class="inv-table">
      <thead><tr>
        <th>Item</th><th>Qty</th><th>Weight</th>
      </tr></thead>
      <tbody>{inv_rows_html}</tbody>
    </table>""" if inv_rows_html else '<div class="empty-state">Empty</div>'

    quests_html = ""
    if active_quests:
        for qname, qdata in active_quests:
            status = qdata.get("status", "active")
            status_color = "#2563eb" if status == "active" else "#d97706"
            qtype = qdata.get("type", "side")
            type_cls = "quest-type-main" if qtype == "main" else "quest-type-side"
            description = qdata.get("description", "")
            objectives = qdata.get("objectives", [])
            events = qdata.get("events", [])
            created_at = qdata.get("created_at", "")

            objs_html = ""
            for obj in objectives:
                done = obj.get("completed", False)
                text = obj.get("text", "")
                mark = "[x]" if done else "[ ]"
                style = "text-decoration:line-through;opacity:0.5" if done else ""
                objs_html += f'<div class="obj" style="{style}">{mark} {h(text)}</div>'

            done_count = sum(1 for o in objectives if o.get("completed", False))
            total = len(objectives)
            progress_pct = int(done_count / max(total, 1) * 100)
            progress_color = "#16a34a" if progress_pct == 100 else ("#2563eb" if progress_pct > 0 else "var(--border)")

            recent_events = list(reversed(events[-2:])) if len(events) > 1 else events[-2:]
            events_html = ""
            for i, ev in enumerate(recent_events):
                ev_text = ev.get("event", "")
                ev_ts = ev.get("timestamp", "")
                ev_date = ""
                if ev_ts:
                    try:
                        dt = datetime.fromisoformat(ev_ts)
                        ev_date = dt.strftime("%d.%m %H:%M")
                    except Exception:
                        ev_date = ev_ts[:16]
                is_latest = (i == 0)
                ts_attr = f' data-ev-ts="{h(ev_ts)}"' if is_latest and ev_ts else ""
                events_html += f"""
                <div class="quest-event"{ts_attr}>
                  <div class="quest-event-text">{h(ev_text)}</div>
                  <div class="quest-event-time">{h(ev_date)}</div>
                </div>"""

            created_str = ""
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at)
                    created_str = dt.strftime("%d.%m.%Y")
                except Exception:
                    created_str = created_at[:10]

            display_qname = qname.replace("-", " ").replace("_", " ")
            quests_html += f"""
            <div class="quest-item" data-key="quest-{h(qname)}" data-val="{h(status)}|{done_count}/{total}">
              <div class="quest-header">
                <div class="quest-header-left">
                  <span class="quest-type {type_cls}">{h(qtype)}</span>
                  <span class="quest-name">{h(display_qname)}</span>
                </div>
                <span class="quest-status" style="color:{status_color}">[{h(status)}]</span>
              </div>
              <div class="quest-desc">{h(description)}</div>
              <div class="quest-progress">
                <span class="quest-progress-text">{done_count}/{total}</span>
                <div class="quest-progress-bar"><div class="quest-progress-fill" data-bar="{progress_pct}" style="width:{progress_pct}%;background:{progress_color}"></div></div>
              </div>
              {objs_html}
              {events_html}
              <div class="quest-meta">
                <span>Created: {h(created_str)}</span>
              </div>
            </div>"""
    else:
        quests_html = '<div class="empty-state">No active quests</div>'

    row3 = f"""
    <div class="row row-two-col">
      <div class="card">
        <div class="card-title">Inventory</div>
        {inv_header_html}
        <div class="scroll-list inv-scroll">{inv_table_html}</div>
      </div>
      <div class="card">
        <div class="card-title">Active Quests</div>
        <div class="scroll-list inv-scroll">{quests_html}</div>
      </div>
    </div>"""

    def fmt_interval(hrs: float) -> str:
        if hrs >= 720:
            return f"{hrs/720:.0f}mo"
        if hrs >= 168:
            return f"{hrs/168:.0f}w"
        if hrs >= 24:
            return f"{hrs/24:.0f}d"
        return f"{hrs:.0f}h"

    def fmt_progress(acc: float, interval: float) -> float:
        return min(100, max(0, acc / max(interval, 1) * 100))

    timed_conseqs = []
    trigger_conseqs = []
    for c in active_consequences:
        if c.get("trigger_hours") is not None:
            timed_conseqs.append(c)
        else:
            trigger_conseqs.append(c)

    timed_conseqs.sort(key=lambda x: x.get("trigger_hours", 0) - x.get("hours_elapsed", 0))

    conseq_html = ""
    for c in timed_conseqs:
        text = c.get("consequence", "")
        trigger = c.get("trigger", "")
        trigger_h = c.get("trigger_hours", 0)
        elapsed = c.get("hours_elapsed", 0)
        remaining = max(0, trigger_h - elapsed)
        pct = min(100, max(0, elapsed / max(trigger_h, 1) * 100))

        if remaining < 24:
            csq_color = "#dc2626"
            urgency = "csq-urgent"
        elif remaining < 72:
            csq_color = "#d97706"
            urgency = "csq-warning"
        else:
            csq_color = "#16a34a"
            urgency = ""

        cid = text[:30].replace(" ", "-").replace('"', "").replace("'", "")
        conseq_html += f"""
        <div class="csq-card {urgency}" data-key="csq-{h(cid)}" data-val="{remaining:.0f}">
          <div class="csq-card-body">
            <div class="csq-bar-vert" style="background:{csq_color}"></div>
            <div class="csq-card-content">
              <div class="csq-card-header">
                <span class="csq-remaining" style="color:{csq_color}">{fmt_interval(remaining)}</span>
                <span class="csq-total">{fmt_interval(trigger_h)} total</span>
              </div>
              <div class="csq-progress">
                <div class="rec-bar"><div class="rec-bar-fill" data-bar="{pct:.0f}" style="width:{pct:.0f}%;background:{csq_color}"></div></div>
              </div>
              <div class="csq-text">{h(text)}</div>
              <div class="csq-trigger">{h(trigger)}</div>
            </div>
          </div>
        </div>"""

    for c in trigger_conseqs:
        text = c.get("consequence", "")
        trigger = c.get("trigger", "")
        cid = text[:30].replace(" ", "-").replace('"', "").replace("'", "")
        conseq_html += f"""
        <div class="csq-card csq-conditional" data-key="csq-{h(cid)}" data-val="na">
          <div class="csq-card-body">
            <div class="csq-bar-vert" style="background:var(--accent)"></div>
            <div class="csq-card-content">
              <div class="csq-card-header">
                <span class="csq-remaining" style="color:var(--accent2)">conditional</span>
              </div>
              <div class="csq-text">{h(text)}</div>
              <div class="csq-trigger">{h(trigger)}</div>
            </div>
          </div>
        </div>"""

    npcs_html = ""
    for npc_name, npc_info in npc_list:
        if not isinstance(npc_info, dict):
            continue
        attitude = npc_info.get("attitude", "neutral")
        desc = npc_info.get("description", "")
        npc_events = npc_info.get("events", [])
        npc_tags = npc_info.get("tags", {})
        npc_locs = npc_tags.get("locations", []) if isinstance(npc_tags, dict) else []
        npc_quests = npc_tags.get("quests", []) if isinstance(npc_tags, dict) else []
        npc_created = npc_info.get("created", "")

        active_quest_names = {qn for qn, _ in active_quests}
        tags_html = ""
        for loc in npc_locs:
            tags_html += f'<span class="npc-tag npc-tag-loc">{h(loc)}</span>'
        for quest in npc_quests:
            if quest in active_quest_names:
                tags_html += f'<span class="npc-tag npc-tag-quest">{h(quest)}</span>'

        recent_events = list(reversed(npc_events[-2:])) if len(npc_events) > 1 else npc_events[-2:]
        events_html = ""
        for i, ev in enumerate(recent_events):
            ev_text = ev.get("event", "")
            ev_ts = ev.get("timestamp", "")
            ev_date = ""
            if ev_ts:
                try:
                    dt = datetime.fromisoformat(ev_ts)
                    ev_date = dt.strftime("%d.%m %H:%M")
                except Exception:
                    ev_date = ev_ts[:16]
            is_latest = (i == len(recent_events) - 1)
            ts_attr = f' data-ev-ts="{h(ev_ts)}"' if is_latest and ev_ts else ""
            events_html += f"""
            <div class="npc-event"{ts_attr}>
              <div class="npc-event-text">{h(ev_text)}</div>
              <div class="npc-event-time">{h(ev_date)}</div>
            </div>"""

        created_str = ""
        if npc_created:
            try:
                dt = datetime.fromisoformat(npc_created)
                created_str = dt.strftime("%d.%m.%Y")
            except Exception:
                created_str = npc_created[:10]

        npcs_html += f"""
        <div class="npc-item" data-key="npc-{h(npc_name)}" data-val="{h(attitude)}">
          <div class="npc-header">
            <span class="npc-name">{h(npc_name)}</span>
            {attitude_badge(attitude)}
          </div>
          <div class="npc-desc">{h(desc)}</div>
          {f'<div class="npc-tags">{tags_html}</div>' if tags_html else ''}
          {events_html}
          <div class="npc-meta">
            <span>Since: {h(created_str)}</span>
            {f'<span>Events: {len(npc_events)}</span>' if npc_events else ''}
          </div>
        </div>"""

    row4 = f"""
    <div class="row row-two-col">
      <div class="card">
        <div class="card-title">Active Consequences</div>
        <div class="scroll-list">{conseq_html if conseq_html else '<div class="empty-state">None</div>'}</div>
      </div>
      <div class="card">
        <div class="card-title">NPCs</div>
        <div class="scroll-list">{npcs_html if npcs_html else '<div class="empty-state">No NPCs</div>'}</div>
      </div>
    </div>"""

    rec_expenses = custom_stats_data.get("recurring_expenses", [])
    rec_income = custom_stats_data.get("recurring_income", [])

    recurring_html = ""
    if rec_expenses or rec_income:
        exp_html = ""
        for exp in rec_expenses:
            name = exp.get("name", "?")
            interval = exp.get("interval_hours", 24)
            acc = exp.get("accumulated_hours", 0)
            cost = exp.get("cost", 0)
            cost_min = exp.get("cost_min", 0)
            cost_max = exp.get("cost_max", 0)
            cost_str = format_money(cost, denoms) if cost else f"{format_money(cost_min, denoms)}—{format_money(cost_max, denoms)}"
            pct = fmt_progress(acc, interval)
            remaining = max(0, interval - acc)
            exp_html += f"""
            <div class="rec-item" data-key="rec-exp-{h(name)}" data-val="{acc:.0f}">
              <div class="rec-header">
                <span class="rec-name">{h(name)}</span>
                <span class="rec-cost rec-expense">-{cost_str}</span>
              </div>
              <div class="rec-progress">
                <span class="rec-interval">/{fmt_interval(interval)}</span>
                <div class="rec-bar"><div class="rec-bar-fill rec-bar-exp" data-bar="{pct:.0f}" style="width:{pct:.0f}%"></div></div>
                <span class="rec-remaining">{fmt_interval(remaining)}</span>
              </div>
            </div>"""

        inc_html = ""
        for inc in rec_income:
            name = inc.get("name", "?")
            interval = inc.get("interval_hours", 168)
            acc = inc.get("accumulated_hours", 0)
            check = inc.get("check", {})
            outcomes = inc.get("outcomes", {})
            streak = inc.get("fail_streak", 0)
            streak_th = inc.get("streak_threshold", 0)
            hours_per = inc.get("hours_per_check", 0)
            mult = inc.get("income_multiplier", 1)

            pct = fmt_progress(acc, interval)
            remaining = max(0, interval - acc)

            check_str = ""
            fail_pct = 0
            succ_pct = 0
            if check:
                imod = check.get("modifier", 0)
                idc = check.get("dc", 10)
                check_str = f"{check.get('dice', '1d20')}{imod:+d} vs DC {idc}"
                need = idc - imod
                fail_pct = max(0, min(95, (need - 2) * 5))
                succ_pct = max(0, 90 - fail_pct)

            def _dice_rng(dice_str: str, multiplier: int = 1) -> tuple:
                m = re.match(r'(\d+)d(\d+)(?:\+(\d+))?', str(dice_str))
                if not m:
                    return (0, 0)
                n, d, bonus = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
                return ((n + bonus) * multiplier, (n * d + bonus) * multiplier)

            def _oc_money(out: dict) -> str:
                if "income_dice" in out:
                    lo, hi = _dice_rng(out["income_dice"], mult)
                    return f"{format_money(lo, denoms)}-{format_money(hi, denoms)}"
                inc_val = out.get("income", 0) * mult
                if inc_val < 0:
                    return f"-{format_money(abs(inc_val), denoms)}"
                return format_money(inc_val, denoms)

            oc_icons = {"crit_fail": "💀", "fail": "✗", "success": "✓", "crit_success": "⚡"}
            oc_css = {"crit_fail": "oc-cf", "fail": "oc-fail", "success": "oc-succ", "crit_success": "oc-crit"}
            oc_pcts = {"crit_fail": 5, "fail": fail_pct, "success": succ_pct, "crit_success": 5}

            rows_html = ""
            if outcomes and check:
                for oc_key in ["crit_success", "success", "fail", "crit_fail"]:
                    oc = outcomes.get(oc_key, {})
                    if not oc or oc_pcts.get(oc_key, 0) <= 0:
                        continue
                    money_str = _oc_money(oc)
                    hint = oc.get("hint", "")
                    rows_html += f"""
                    <div class="prod-oc-row {oc_css[oc_key]}">
                      <span class="prod-oc-icon">{oc_icons[oc_key]}</span>
                      <span class="prod-oc-pct">{oc_pcts[oc_key]}%</span>
                      <span class="prod-oc-yield">{h(money_str)}</span>
                      {f'<span class="prod-oc-hint">{h(hint)}</span>' if hint else ''}
                    </div>"""

            streak_html = ""
            if streak > 0 and streak_th > 0:
                streak_html = f'<div class="rec-streak">fails: {streak}/{streak_th}</div>'

            work_html = ""
            if hours_per:
                work_html = f'<span class="rec-work">{hours_per}h work</span>'

            chance_bar = ""
            if check:
                chance_bar = f"""<div class="prod-chance-bar">
                  <div class="prod-chance-seg" style="flex:{oc_pcts['crit_success']};background:#fbbf24"></div>
                  <div class="prod-chance-seg" style="flex:{max(succ_pct,1)};background:#4ade80"></div>
                  <div class="prod-chance-seg" style="flex:{max(fail_pct,1)};background:#f87171"></div>
                  <div class="prod-chance-seg" style="flex:{oc_pcts['crit_fail']};background:#991b1b"></div>
                </div>"""

            inc_html += f"""
            <div class="prod-card" data-key="rec-inc-{h(name)}" data-val="{acc:.0f}">
              <div class="prod-card-body">
                {chance_bar}
                <div class="prod-card-content">
                  <div class="prod-card-header">
                    <span class="prod-worker">{h(name)}</span>
                    <span class="prod-check">{h(check_str)}</span>
                  </div>
                  <div class="prod-outcomes">{rows_html}</div>
                  <div class="prod-card-footer">
                    {work_html}{streak_html}
                    <div class="prod-timer">
                      <div class="rec-bar"><div class="rec-bar-fill rec-bar-inc" data-bar="{pct:.0f}" style="width:{pct:.0f}%"></div></div>
                      <span class="prod-timer-text">{fmt_interval(remaining)} / {fmt_interval(interval)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>"""

        rand_events = custom_stats_data.get("random_events", {})
        rand_html = ""
        if rand_events and rand_events.get("enabled"):
            rand_interval = rand_events.get("interval_hours", 168)
            rand_acc = rand_events.get("accumulated_hours", 0)
            rand_pct = fmt_progress(rand_acc, rand_interval)
            rand_remaining = max(0, rand_interval - rand_acc)
            cats = rand_events.get("categories", [])
            cats_html = " ".join(f'<span class="rand-cat">{c.get("emoji","")} {c.get("type","")}</span>' for c in cats)
            rand_html = f"""
          <div class="rec-col">
            <div class="rec-col-title rand-title">Random Events</div>
            <div class="rec-item" data-key="rand-events" data-val="{rand_acc:.0f}">
              <div class="rec-header">
                <span class="rec-name">1d100 every {fmt_interval(rand_interval)}</span>
                <span class="rec-remaining">{fmt_interval(rand_remaining)} left</span>
              </div>
              <div class="rec-progress">
                <span class="rec-interval">/{fmt_interval(rand_interval)}</span>
                <div class="rec-bar"><div class="rec-bar-fill rec-bar-rand" data-bar="{rand_pct:.0f}" style="width:{rand_pct:.0f}%"></div></div>
                <span class="rec-remaining">{fmt_interval(rand_remaining)}</span>
              </div>
              <div class="rand-cats">{cats_html}</div>
            </div>
          </div>"""

        recurring_html = f"""
    <div class="row">
      <div class="card full-width">
        <div class="card-title">Recurring Economy</div>
        <div class="rec-grid">
          <div class="rec-col">
            <div class="rec-col-title rec-expense">Expenses</div>
            {exp_html if exp_html else '<div class="empty-state">None</div>'}
          </div>
        </div>
        <div class="card-title" style="margin-top:8px">Income</div>
        <div class="prod-grid">
          {inc_html if inc_html else '<div class="empty-state">None</div>'}
          {rand_html}
        </div>
      </div>
    </div>"""

    rec_production = custom_stats_data.get("recurring_production", [])
    production_html = ""
    if rec_production:
        def _dice_range(qty) -> str:
            if isinstance(qty, str):
                m = re.match(r'(\d+)d(\d+)(?:\+(\d+))?', qty)
                if m:
                    n, d, b = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
                    return f"{n+b}-{n*d+b}"
                return qty
            return str(qty)

        prod_cards_html = ""
        for prod in rec_production:
            pname = prod.get("name", "?")
            worker = prod.get("worker", "")
            workers_count = prod.get("workers_count", 1)
            interval = prod.get("interval_hours", 24)
            acc = prod.get("accumulated_hours", 0)
            pcheck = prod.get("check", {})
            poutcomes = prod.get("outcomes", {})

            pct = fmt_progress(acc, interval)
            remaining = max(0, interval - acc)

            check_str = ""
            fail_pct = 0
            succ_pct = 0
            if pcheck:
                pmod = pcheck.get("modifier", 0)
                pdc = pcheck.get("dc", 10)
                check_str = f"{pcheck.get('dice', '1d20')}{pmod:+d} vs DC {pdc}"
                need = pdc - pmod
                fail_pct = max(0, min(95, (need - 2) * 5))
                succ_pct = max(0, 90 - fail_pct)

            oc_icons = {"crit_fail": "💀", "fail": "✗", "success": "✓", "crit_success": "⚡"}
            oc_css = {"crit_fail": "oc-cf", "fail": "oc-fail", "success": "oc-succ", "crit_success": "oc-crit"}
            oc_pcts = {"crit_fail": 5, "fail": fail_pct, "success": succ_pct, "crit_success": 5}

            rows_html = ""
            for oc_key in ["crit_success", "success", "fail", "crit_fail"]:
                oc = poutcomes.get(oc_key, {})
                if not oc or oc_pcts.get(oc_key, 0) <= 0:
                    continue
                icon = oc_icons[oc_key]
                css = oc_css[oc_key]
                pct_val = oc_pcts[oc_key]

                produce = oc.get("produce", {})
                prod_parts = []
                for item, qty in produce.items():
                    short = item.split("(")[0].strip()
                    prod_parts.append(f"{_dice_range(qty)} {h(short)}")
                prod_str = ", ".join(prod_parts) if prod_parts else "-"

                consume = oc.get("consume", {})
                cons_parts = []
                for item, qty in consume.items():
                    short = item.split("(")[0].strip()
                    cons_parts.append(f"{_dice_range(qty)} {h(short)}")
                cons_str = ", ".join(cons_parts) if cons_parts else ""

                hint = oc.get("hint", "")

                rows_html += f"""
                <div class="prod-oc-row {css}">
                  <span class="prod-oc-icon">{icon}</span>
                  <span class="prod-oc-pct">{pct_val}%</span>
                  <span class="prod-oc-yield">{prod_str}</span>
                  {f'<span class="prod-oc-hint">{h(hint)}</span>' if hint else ''}
                  {f'<span class="prod-oc-cost">⤷ {cons_str}</span>' if cons_str else ''}
                </div>"""

            chance_bar = f"""<div class="prod-chance-bar">
              <div class="prod-chance-seg" style="flex:{oc_pcts['crit_success']};background:#fbbf24" title="crit {oc_pcts['crit_success']}%"></div>
              <div class="prod-chance-seg" style="flex:{max(succ_pct,1)};background:#4ade80" title="success {succ_pct}%"></div>
              <div class="prod-chance-seg" style="flex:{max(fail_pct,1)};background:#f87171" title="fail {fail_pct}%"></div>
              <div class="prod-chance-seg" style="flex:{oc_pcts['crit_fail']};background:#991b1b" title="crit fail {oc_pcts['crit_fail']}%"></div>
            </div>"""

            prod_cards_html += f"""
            <div class="prod-card" data-key="prod-{h(pname)}" data-val="{acc:.0f}">
              <div class="prod-card-body">
                {chance_bar}
                <div class="prod-card-content">
                  <div class="prod-card-header">
                    <span class="prod-worker">{h(worker)}{f' <span class="prod-wcount">x{workers_count}</span>' if workers_count > 1 else ''}</span>
                    <span class="prod-check">{h(check_str)}</span>
                  </div>
                  <div class="prod-outcomes">{rows_html}</div>
                  <div class="prod-timer">
                    <div class="rec-bar"><div class="rec-bar-fill rec-bar-prod" data-bar="{pct:.0f}" style="width:{pct:.0f}%"></div></div>
                    <span class="prod-timer-text">{fmt_interval(remaining)} / {fmt_interval(interval)}</span>
                  </div>
                </div>
              </div>
            </div>"""

        production_html = f"""
    <div class="row">
      <div class="card full-width">
        <div class="card-title">Production Chain</div>
        <div class="prod-grid">{prod_cards_html}</div>
      </div>
    </div>"""

    party_members = []
    if isinstance(npcs_data, dict):
        for pname, pinfo in npcs_data.items():
            if isinstance(pinfo, dict) and pinfo.get("is_party_member"):
                party_members.append((pname, pinfo))

    party_html = ""
    if party_members:
        party_cards = ""
        for pm_name, pm_info in party_members:
            cs = pm_info.get("character_sheet", {})
            pm_desc = pm_info.get("description", "")
            pm_hp = cs.get("hp", {})
            pm_hp_cur = pm_hp.get("current", 0) if isinstance(pm_hp, dict) else 0
            pm_hp_max = pm_hp.get("max", 1) if isinstance(pm_hp, dict) else 1
            pm_hp_pct = min(100, max(0, int(pm_hp_cur / max(pm_hp_max, 1) * 100)))
            pm_ac = cs.get("ac", "—")
            pm_conditions = cs.get("conditions", [])
            pm_money = cs.get("money", 0)
            pm_money_str = format_money(pm_money, denoms) if pm_money else "—"

            cond_html = ""
            if pm_conditions:
                cond_html = " ".join(f'<span class="pm-cond">{h(c)}</span>' for c in pm_conditions)

            pm_inv = party_inv_data.get(pm_name, {})
            pm_stackable = pm_inv.get("stackable", {})
            pm_unique = pm_inv.get("unique", [])

            inv_rows = ""
            for iname, iinfo in pm_stackable.items():
                qty = iinfo.get("qty", iinfo) if isinstance(iinfo, dict) else int(iinfo)
                inv_rows += f'<div class="pm-inv-row"><span class="pm-inv-name">{h(iname)}</span><span class="pm-inv-qty">{qty}</span></div>'
            for ui in pm_unique:
                clean = re.sub(r'\s*\[\d+(?:\.\d+)?kg\]', '', str(ui))
                inv_rows += f'<div class="pm-inv-row pm-inv-unique"><span class="pm-inv-name">{h(clean)}</span><span class="pm-inv-qty">1</span></div>'

            party_cards += f"""
            <div class="pm-card" data-key="pm-{h(pm_name)}">
              <div class="pm-header">
                <span class="pm-name">{h(pm_name)}</span>
                <span class="pm-ac">AC {h(pm_ac)}</span>
              </div>
              <div class="pm-desc">{h(pm_desc)}</div>
              <div class="pm-vitals">
                <span class="pm-hp-label">{pm_hp_cur}/{pm_hp_max}</span>
                <div class="pm-hp-bar"><div class="pm-hp-fill" style="width:{pm_hp_pct}%"></div></div>
                {f'<span class="pm-money">{h(pm_money_str)}</span>' if pm_money else ''}
              </div>
              {f'<div class="pm-conditions">{cond_html}</div>' if cond_html else ''}
              {f'<div class="pm-inventory"><div class="pm-inv-title">Inventory</div>{inv_rows}</div>' if inv_rows else ''}
            </div>"""

        party_html = f"""
    <div class="row">
      <div class="card full-width">
        <div class="card-title">Party</div>
        <div class="pm-grid">{party_cards}</div>
      </div>
    </div>"""

    return f"{topbar}{header}{vitals}{custom_stats_row}{dnd_row}{row3}{row4}{recurring_html}{production_html}{party_html}"


def render_wiki_html() -> str:
    active_file = ROOT / "world-state" / "active-campaign.txt"
    if not active_file.exists():
        return '<div class="empty-state">No campaign</div>'
    campaign_name = active_file.read_text(encoding="utf-8").strip()
    if not campaign_name:
        return '<div class="empty-state">No campaign</div>'

    wiki_data = load_json(ROOT / "world-state" / "campaigns" / campaign_name / "wiki.json") or {}
    if not wiki_data:
        return '<div class="empty-state">Wiki is empty</div>'

    def h(text: str) -> str:
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    type_icons = {
        "potion": "🧪", "material": "🌿", "artifact": "🔮",
        "ability": "⚡", "technique": "📜", "effect": "✨",
        "tool": "🔧", "weapon": "⚔️", "armor": "🛡️",
        "book": "📖", "chapter": "📄", "creature": "🐾", "misc": "📦",
    }
    type_colors = {
        "potion": "#4ade80", "material": "#a3e635",
        "artifact": "#c084fc", "ability": "#fbbf24",
        "technique": "#60a5fa", "effect": "#f472b6",
        "tool": "#fb923c", "weapon": "#f87171",
        "armor": "#94a3b8", "book": "#a78bfa", "chapter": "#a78bfa",
        "creature": "#ef4444", "misc": "#6b7280",
    }

    status_icons = {
        "COMPLETE": "✅", "COMPLETE_WITH_GAPS": "⚠️",
        "PARTIAL": "🔶", "LOCKED": "🔒", "": "🔒",
    }

    children_map = {}
    child_ids = set()
    for eid in wiki_data:
        if "." in eid:
            parent_id = eid.rsplit(".", 1)[0]
            children_map.setdefault(parent_id, []).append(eid)
            child_ids.add(eid)

    by_type = {}
    for eid, edata in wiki_data.items():
        if not isinstance(edata, dict):
            continue
        if eid in child_ids:
            continue
        etype = edata.get("type", "misc")
        by_type.setdefault(etype, []).append((eid, edata))

    def render_item(eid, edata, color):
        name = edata.get("name", eid)
        desc = edata.get("description", "")
        mechanics = edata.get("mechanics", {})
        recipe = edata.get("recipe", {})
        refs = edata.get("refs", [])

        mech_parts = []
        skip_keys = {"reading_rules", "total_parts", "current_progress", "unlocks_gained", "unlocks_missed", "status", "sequence"}
        for mk, mv in mechanics.items():
            if mk in skip_keys:
                continue
            mech_parts.append(f"<span class='wiki-mech-key'>{h(mk)}:</span> {h(str(mv))}")
        mech_html = " &bull; ".join(mech_parts) if mech_parts else ""

        recipe_html = ""
        if recipe:
            dc = recipe.get("dc", "")
            skill = recipe.get("skill", "")
            ingredients = recipe.get("ingredients", {})
            tools = recipe.get("tools", [])
            source = recipe.get("source", "")
            rparts = []
            if dc:
                rparts.append(f"DC {dc}")
            if skill:
                rparts.append(h(skill))
            recipe_header = " / ".join(rparts)
            ing_parts = [f"{h(iname)} x{iqty}" for iname, iqty in ingredients.items()]
            ing_str = ", ".join(ing_parts)
            tools_str = ", ".join(h(t) for t in tools)
            recipe_html = f'<div class="wiki-recipe"><span class="wiki-recipe-header">{recipe_header}</span>'
            if ing_str:
                recipe_html += f'<div class="wiki-recipe-ing">{ing_str}</div>'
            if tools_str:
                recipe_html += f'<div class="wiki-recipe-tools">Tools: {tools_str}</div>'
            if source:
                recipe_html += f'<div class="wiki-recipe-src">{h(source)}</div>'
            recipe_html += '</div>'

        refs_html = ""
        if refs:
            ref_links = ", ".join(f'<span class="wiki-ref">{h(r)}</span>' for r in refs)
            refs_html = f'<div class="wiki-refs">Refs: {ref_links}</div>'

        children_html = ""
        if eid in children_map:
            ch_items = []
            for cid in children_map[eid]:
                cd = wiki_data.get(cid, {})
                if not isinstance(cd, dict):
                    continue
                ch_items.append((cid, cd))
            ch_items.sort(key=lambda x: x[1].get("mechanics", {}).get("sequence", 0))

            ch_rows = ""
            for cid, cd in ch_items:
                ch_name = cd.get("name", cid)
                ch_mech = cd.get("mechanics", {})
                ch_status = ch_mech.get("status", "")
                ch_dc = ch_mech.get("dc", "")
                ch_dp = ch_mech.get("dp_cost", "")
                ch_days = ch_mech.get("days", "")
                ch_desc = cd.get("description", "")

                si = status_icons.get(ch_status, "🔒")
                unlocks = ch_mech.get("unlocks_gained", [])
                missed = ch_mech.get("unlocks_missed", [])

                unlocks_html = ""
                if unlocks:
                    unlocks_html = '<div class="ch-unlocks">' + ", ".join(h(u) for u in unlocks) + '</div>'
                missed_html = ""
                if missed:
                    missed_html = '<div class="ch-missed">' + ", ".join(h(m) for m in missed) + '</div>'

                meta_parts = []
                if ch_dc:
                    meta_parts.append(f"DC {ch_dc}")
                if ch_dp:
                    meta_parts.append(f"DP {ch_dp}")
                if ch_days:
                    meta_parts.append(f"{ch_days}d")
                meta_str = " / ".join(meta_parts)

                ch_rows += f"""
                <div class="ch-row">
                  <div class="ch-header">
                    <span class="ch-status">{si}</span>
                    <span class="ch-name">{h(ch_name)}</span>
                    <span class="ch-meta">{h(meta_str)}</span>
                  </div>
                  <div class="ch-desc">{h(ch_desc)}</div>
                  {unlocks_html}
                  {missed_html}
                </div>"""

            children_html = f'<div class="wiki-children"><div class="wiki-children-title">Contents ({len(ch_items)})</div>{ch_rows}</div>'

        progress_html = ""
        if isinstance(mechanics, dict) and mechanics.get("current_progress"):
            progress_html = f'<div class="wiki-progress">{h(mechanics["current_progress"])}</div>'

        return f"""
            <div class="wiki-item" data-key="wiki-{h(eid)}">
              <div class="wiki-item-name" style="color:{color}">{h(name)}</div>
              <div class="wiki-item-desc">{h(desc)}</div>
              {f'<div class="wiki-mech">{mech_html}</div>' if mech_html else ''}
              {progress_html}
              {recipe_html}
              {refs_html}
              {children_html}
            </div>"""

    html = ""
    for etype in ["potion", "technique", "ability", "artifact", "material", "effect", "tool", "weapon", "armor", "book", "creature", "misc"]:
        items = by_type.get(etype, [])
        if not items:
            continue
        icon = type_icons.get(etype, "📦")
        color = type_colors.get(etype, "var(--muted)")
        html += f'<div class="wiki-section"><div class="wiki-type" style="color:{color}">{icon} {etype.upper()} ({len(items)})</div>'

        for eid, edata in sorted(items, key=lambda x: x[1].get("name", x[0])):
            html += render_item(eid, edata, color)

        html += '</div>'

    return html
