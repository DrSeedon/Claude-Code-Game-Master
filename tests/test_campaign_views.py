import json

from backend.campaign_views import CampaignViewProjector, get_campaign_views


def _write_campaign(tmp_path):
    campaign = tmp_path / "views"
    campaign.mkdir()
    (campaign / "campaign-overview.json").write_text(
        json.dumps(
            {
                "name": "views",
                "campaign_name": "View Test",
                "current_date": "Day 4",
                "precise_time": "14:30",
                "player_position": {"current_location": "Metadata fallback"},
                "currency": {
                    "base": "credit",
                    "denominations": [
                        {
                            "id": "credit",
                            "name": "credit",
                            "symbol": "cr",
                            "rate": 1,
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    world = {
        "meta": {"version": 2, "schema": "graph"},
        "nodes": {
            "player:active": {
                "type": "player",
                "name": "Ada",
                "data": {
                    "class": "Marine",
                    "level": 3,
                    "hp": {"current": 8, "max": 12},
                    "xp": {"current": 90, "next_level": 120},
                    "money": 42,
                    "current_location": "location:base",
                    "conditions": ["wounded"],
                    "stats": {"str": 14},
                    "skills": {"Athletics": 4},
                },
                "inventory": {
                    "stackable": {
                        "Ammo": {"qty": 30, "weight": 0.02},
                        "Rifle": {"qty": 1, "weight": 4.0},
                    },
                    "unique": [{"name": "Dog tags", "weight": 0.1}],
                },
            },
            "location:base": {
                "type": "location",
                "name": "Forward Base",
                "data": {
                    "production": [
                        {
                            "name": "Workshop",
                            "item": "Parts",
                            "qty_dice": "1d4",
                            "interval_hours": 8,
                            "_acc_hours": 2,
                        },
                        {
                            "name": "Secret lab",
                            "item": "Mutagen",
                            "hidden": True,
                        },
                    ]
                },
            },
            "item:stale": {
                "type": "item",
                "name": "Stale edge item",
                "data": {"quantity": 99},
            },
            "npc:ally": {
                "type": "npc",
                "name": "Ally",
                "data": {
                    "party_member": True,
                    "description": "Squad medic",
                    "attitude": "friendly",
                    "character_sheet": {"hp": 7, "hp_max": 10, "ac": 12},
                },
                "inventory": {
                    "stackable": {"Medkit": {"qty": 2, "weight": 0.5}},
                    "unique": [],
                },
            },
            "npc:contact": {
                "type": "npc",
                "name": "Contact",
                "data": {"description": "Known informant", "attitude": "neutral"},
            },
            "npc:public": {
                "type": "npc",
                "name": "Public NPC",
                "data": {"description": "Revealed", "player_visible": True},
            },
            "npc:unknown": {
                "type": "npc",
                "name": "Unknown NPC",
                "data": {"description": "Should not leak"},
            },
            "npc:hidden": {
                "type": "npc",
                "name": "Hidden NPC",
                "data": {"player_visible": True, "hidden": True},
            },
            "quest:visible": {
                "type": "quest",
                "name": "Visible Quest",
                "data": {
                    "status": "active",
                    "description": "Repair the relay",
                    "objectives": [
                        {"text": "Reach the relay", "done": True},
                        {"text": "Discover the saboteur", "hidden": True},
                    ],
                },
            },
            "quest:hidden": {
                "type": "quest",
                "name": "DM Quest",
                "data": {"status": "active", "visibility": "dm-only"},
            },
            "weapon:rifle": {
                "type": "weapon",
                "name": "Rifle",
                "data": {"description": "Service rifle", "mechanics": {"damage": "2d8"}},
            },
            "spell:signal": {
                "type": "spell",
                "name": "Signal",
                "data": {"visibility": "public", "mechanics": {"range": 100}},
            },
            "creature:surprise": {
                "type": "creature",
                "name": "Surprise",
                "data": {"description": "Future enemy", "visibility": "secret"},
            },
            "misc:economy": {
                "type": "misc",
                "name": "Economy",
                "data": {
                    "expenses": [
                        {"name": "Rent", "cost": 5, "per_hours": 24, "_acc": 3},
                        {"name": "Blackmail", "cost": 50, "hidden": True},
                    ],
                    "income": [{"name": "Salary", "amount": 10, "per_hours": 24}],
                    "random_events": {
                        "enabled": True,
                        "types": {"invasion": 100},
                    },
                },
            },
            "consequence:future": {
                "type": "consequence",
                "name": "Future",
                "data": {
                    "description": "Future ambush",
                    "status": "pending",
                    "trigger": "when the player leaves",
                    "hours_remaining": 2,
                },
            },
            "consequence:deadline": {
                "type": "consequence",
                "name": "Deadline",
                "data": {
                    "description": "Known deadline",
                    "status": "pending",
                    "player_visible": True,
                    "trigger": "secret implementation detail",
                    "hours_remaining": 4,
                },
            },
            "consequence:occurred": {
                "type": "consequence",
                "name": "Alarm",
                "data": {
                    "description": "The alarm sounded",
                    "status": "triggered",
                    "trigger": "secret condition",
                    "triggered_at": "14:00",
                },
            },
            "consequence:hidden-occurred": {
                "type": "consequence",
                "name": "Offscreen",
                "data": {
                    "description": "Offscreen faction action",
                    "status": "triggered",
                    "visibility": "dm",
                },
            },
        },
        "edges": [
            {
                "from": "player:active",
                "to": "item:stale",
                "type": "owns",
                "data": {"quantity": 99},
            },
            {"from": "npc:contact", "to": "player:active", "type": "known_by"},
            {"from": "npc:ally", "to": "location:base", "type": "at"},
        ],
    }
    (campaign / "world.json").write_text(
        json.dumps(world, ensure_ascii=False), encoding="utf-8"
    )
    return campaign


def test_snapshot_is_structured_json_safe_and_uses_canonical_player_data(tmp_path):
    campaign = _write_campaign(tmp_path)

    snapshot = get_campaign_views(campaign)

    assert json.loads(json.dumps(snapshot, ensure_ascii=False)) == snapshot
    assert snapshot["campaign"]["location"] == "Forward Base"
    assert snapshot["character"]["hp"] == {"current": 8, "max": 12}
    assert snapshot["character"]["money"]["formatted"] == "42 cr"
    assert snapshot["inventory"] == {
        "owner_id": "player:active",
        "items": [
            {"name": "Ammo", "quantity": 30, "unique": False, "weight": 0.02},
            {"name": "Rifle", "quantity": 1, "unique": False, "weight": 4.0},
            {"name": "Dog tags", "quantity": 1, "unique": True, "weight": 0.1},
        ],
        "total_quantity": 32,
        "total_weight": 4.7,
    }
    assert "Stale edge item" not in {
        item["name"] for item in snapshot["inventory"]["items"]
    }


def test_player_visibility_filters_npcs_quests_wiki_and_consequences(tmp_path):
    projector = CampaignViewProjector(_write_campaign(tmp_path))

    npcs = projector.npcs()
    assert [npc["name"] for npc in npcs["party"]] == ["Ally"]
    assert [npc["name"] for npc in npcs["known"]] == [
        "Ally",
        "Contact",
        "Public NPC",
    ]

    quests = projector.quests()
    assert [quest["name"] for quest in quests] == ["Visible Quest"]
    assert quests[0]["objectives"] == [{"text": "Reach the relay", "done": True}]

    assert [entry["name"] for entry in projector.wiki()] == ["Signal", "Rifle"]

    consequences = projector.consequences()
    assert [item["name"] for item in consequences] == ["Deadline", "Alarm"]
    assert all("trigger" not in item for item in consequences)
    assert "Future" not in {item["name"] for item in consequences}
    assert "Offscreen" not in {item["name"] for item in consequences}


def test_economy_excludes_hidden_schedules_internal_counters_and_random_events(tmp_path):
    economy = CampaignViewProjector(_write_campaign(tmp_path)).economy()

    assert economy["balance"]["formatted"] == "42 cr"
    assert economy["expenses"] == [{"name": "Rent", "cost": 5, "per_hours": 24}]
    assert economy["income"] == [
        {"name": "Salary", "amount": 10, "per_hours": 24}
    ]
    assert economy["production"] == [
        {
            "name": "Workshop",
            "item": "Parts",
            "qty_dice": "1d4",
            "interval_hours": 8,
            "location": "Forward Base",
            "location_id": "location:base",
        }
    ]
    assert "random_events" not in economy


def test_metadata_location_is_last_resort(tmp_path):
    campaign = _write_campaign(tmp_path)
    world = json.loads((campaign / "world.json").read_text(encoding="utf-8"))
    del world["nodes"]["player:active"]["data"]["current_location"]
    world["edges"] = [
        edge
        for edge in world["edges"]
        if not (
            edge.get("from") == "player:active"
            and edge.get("type") == "at"
        )
    ]
    (campaign / "world.json").write_text(json.dumps(world), encoding="utf-8")

    assert CampaignViewProjector(campaign).character()["location"] == "Metadata fallback"
