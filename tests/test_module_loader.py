import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent


def load_module_loader():
    path = PROJECT_ROOT / ".claude" / "additional" / "module_loader.py"
    spec = importlib.util.spec_from_file_location("dm_module_loader", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ModuleLoader


def test_world_travel_is_discovered():
    loader = load_module_loader()(PROJECT_ROOT)

    modules = loader.scan_modules()

    assert modules["world-travel"]["version"] == "2.0.0"


def test_activation_supports_list_shaped_campaign_modules(tmp_path):
    root = tmp_path
    modules_dir = root / ".claude" / "additional" / "modules" / "world-travel"
    modules_dir.mkdir(parents=True)
    (modules_dir / "module.json").write_text(json.dumps({
        "id": "world-travel",
        "name": "World Travel",
        "version": "2.0.0",
        "description": "Travel",
        "dependencies": [],
    }), encoding="utf-8")
    overview = root / "campaign-overview.json"
    overview.write_text(json.dumps({"modules": []}), encoding="utf-8")
    loader = load_module_loader()(root)

    assert loader.set_campaign_module("world-travel", True, overview)
    assert json.loads(overview.read_text(encoding="utf-8"))["modules"] == {
        "world-travel": True
    }
    assert loader.is_module_enabled("world-travel", overview)

    assert loader.set_campaign_module("world-travel", False, overview)
    assert json.loads(overview.read_text(encoding="utf-8"))["modules"] == {
        "world-travel": False
    }
