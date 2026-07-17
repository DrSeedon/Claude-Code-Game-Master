import json
import multiprocessing

from lib.json_ops import JsonOperations


def _concurrent_update(directory: str, key: str, ready, start):
    ready.put(key)
    start.wait()
    assert JsonOperations(directory).update_json("state.json", {key: True})


def test_concurrent_updates_preserve_independent_fields(tmp_path):
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    ready = multiprocessing.Queue()
    start = multiprocessing.Event()
    workers = [
        multiprocessing.Process(
            target=_concurrent_update,
            args=(str(tmp_path), key, ready, start),
        )
        for key in ("clock", "mode", "position", "modules")
    ]
    for worker in workers:
        worker.start()
    for _ in workers:
        ready.get(timeout=5)
    start.set()
    for worker in workers:
        worker.join(timeout=5)
        assert worker.exitcode == 0

    assert json.loads((tmp_path / "state.json").read_text(encoding="utf-8")) == {
        "clock": True,
        "mode": True,
        "position": True,
        "modules": True,
    }
