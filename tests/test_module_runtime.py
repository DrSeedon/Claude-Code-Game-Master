import json
from pathlib import Path

import pytest

from lib.dm_rules_compiler import compile_rules
from lib.module_runtime import ModuleRuntime, ModuleRuntimeError


PROJECT_ROOT = Path(__file__).parent.parent


def _overview(tmp_path, modules):
    path = tmp_path / "campaign-overview.json"
    path.write_text(json.dumps({"modules": modules}), encoding="utf-8")
    return path


def test_damage_provider_is_inactive_without_its_module(tmp_path):
    runtime = ModuleRuntime(
        project_root=PROJECT_ROOT,
        overview_path=_overview(tmp_path, {"firearms-combat": False}),
    )

    assert runtime.call_provider(
        "combat.damage",
        12,
        {"combat_profile": {"pen": 1}},
        {"combat_profile": {"prot": 6}},
    ) is None


def test_damage_provider_is_loaded_from_active_manifest(tmp_path):
    runtime = ModuleRuntime(
        project_root=PROJECT_ROOT,
        overview_path=_overview(tmp_path, {"firearms-combat": True}),
    )

    result = runtime.call_provider(
        "combat.damage",
        12,
        {"combat_profile": {"pen": 1}},
        {"combat_profile": {"prot": 6}},
    )

    assert result == {
        "damage": 3,
        "details": "PEN1/PROT6[QUARTER]",
    }
    assert runtime.action_route("combat.attack.firearm") == (
        "bash modules/firearms-combat/tools/dm-combat.sh resolve"
    )


def test_duplicate_provider_contract_is_rejected(tmp_path):
    modules_dir = tmp_path / "modules"
    for module_id in ("first", "second"):
        module_dir = modules_dir / module_id
        module_dir.mkdir(parents=True)
        (module_dir / "module.json").write_text(
            json.dumps({
                "id": module_id,
                "providers": {"combat.damage": "provider.py:resolve"},
            }),
            encoding="utf-8",
        )
        (module_dir / "provider.py").write_text(
            "def resolve(*args, **kwargs):\n    return {}\n",
            encoding="utf-8",
        )
    overview = _overview(tmp_path, {"first": True, "second": True})

    runtime = ModuleRuntime(project_root=tmp_path, overview_path=overview)

    with pytest.raises(ModuleRuntimeError, match="conflicting 'combat.damage'"):
        runtime.has_provider("combat.damage")


@pytest.mark.parametrize(
    ("modules", "expected", "unexpected"),
    [
        (
            {},
            [
                "no group resolver is active",
                "automatic fire, ammunition salvos, penetration",
            ],
            ["modules/mass-combat", "modules/firearms-combat"],
        ),
        (
            {"mass-combat": True},
            [
                "bash modules/mass-combat/tools/dm-mass-combat.sh",
                "Group damage: use ordinary D&D damage",
            ],
            ["modules/firearms-combat"],
        ),
        (
            {"firearms-combat": True},
            [
                "bash modules/firearms-combat/tools/dm-combat.sh resolve",
                "no group resolver is active",
            ],
            ["modules/mass-combat"],
        ),
        (
            {"mass-combat": True, "firearms-combat": True},
            [
                "bash modules/firearms-combat/tools/dm-combat.sh resolve",
                "bash modules/mass-combat/tools/dm-mass-combat.sh",
                "active damage-profile provider is applied",
            ],
            [],
        ),
    ],
)
def test_compiler_emits_one_resolved_combat_profile(
    tmp_path,
    modules,
    expected,
    unexpected,
):
    output = compile_rules(
        PROJECT_ROOT,
        _overview(tmp_path, modules),
        mode="modules",
    )

    for text in expected:
        assert text in output
    for text in unexpected:
        assert text not in output


def test_combat_modules_do_not_name_each_other():
    firearms_files = (
        list((PROJECT_ROOT / "modules" / "firearms-combat").rglob("*.py"))
        + list((PROJECT_ROOT / "modules" / "firearms-combat").rglob("*.md"))
        + list((PROJECT_ROOT / "modules" / "firearms-combat").rglob("*.json"))
        + list((PROJECT_ROOT / "modules" / "firearms-combat").rglob("*.sh"))
    )
    mass_files = (
        list((PROJECT_ROOT / "modules" / "mass-combat").rglob("*.py"))
        + list((PROJECT_ROOT / "modules" / "mass-combat").rglob("*.md"))
        + list((PROJECT_ROOT / "modules" / "mass-combat").rglob("*.json"))
        + list((PROJECT_ROOT / "modules" / "mass-combat").rglob("*.sh"))
    )

    assert all("mass-combat" not in path.read_text(encoding="utf-8")
               for path in firearms_files)
    assert all("firearms-combat" not in path.read_text(encoding="utf-8")
               for path in mass_files)
