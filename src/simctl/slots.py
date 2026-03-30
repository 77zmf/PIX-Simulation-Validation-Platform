from __future__ import annotations

import json
from pathlib import Path

from .config import dump_json, ensure_dir, find_repo_root, load_yaml, utc_now
from .models import RuntimeSlot


def _catalog_path(stack_id: str, repo_root: Path) -> Path:
    return repo_root / "stack" / "slots" / f"{stack_id}_slots.yaml"


def load_slot_catalog(stack_id: str, repo_root: Path | None = None) -> list[RuntimeSlot]:
    root = repo_root or find_repo_root()
    path = _catalog_path(stack_id, root)
    payload = load_yaml(path)
    slots_payload = payload.get("slots", [])
    if not isinstance(slots_payload, list) or not slots_payload:
        raise ValueError(f"{path} must define a non-empty 'slots' list")
    return [RuntimeSlot.from_dict(item, where=f"{path}.slots[{index}]") for index, item in enumerate(slots_payload, start=1)]


def get_slot_by_id(slots: list[RuntimeSlot], slot_id: str) -> RuntimeSlot:
    for slot in slots:
        if slot.slot_id == slot_id:
            return slot
    raise KeyError(f"Unknown slot_id '{slot_id}'")


def slot_lock_dir(repo_root: Path, stack_id: str) -> Path:
    return ensure_dir(repo_root / "artifacts" / "slot_locks" / stack_id)


def slot_lock_path(repo_root: Path, stack_id: str, slot_id: str) -> Path:
    return slot_lock_dir(repo_root, stack_id) / f"{slot_id}.json"


def read_slot_lock(repo_root: Path, stack_id: str, slot_id: str) -> dict[str, object] | None:
    path = slot_lock_path(repo_root, stack_id, slot_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_available_slots(repo_root: Path, stack_id: str, slots: list[RuntimeSlot]) -> list[RuntimeSlot]:
    return [slot for slot in slots if read_slot_lock(repo_root, stack_id, slot.slot_id) is None]


def acquire_slot_lock(
    repo_root: Path,
    stack_id: str,
    slot: RuntimeSlot,
    *,
    run_dir: Path,
    scenario_id: str,
) -> Path:
    path = slot_lock_path(repo_root, stack_id, slot.slot_id)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        raise RuntimeError(
            f"Slot '{slot.slot_id}' is busy with run '{payload.get('run_dir', 'unknown')}'"
        )
    dump_json(
        path,
        {
            "stack_id": stack_id,
            "slot_id": slot.slot_id,
            "scenario_id": scenario_id,
            "run_dir": str(run_dir),
            "acquired_at": utc_now(),
            "carla_rpc_port": slot.carla_rpc_port,
            "traffic_manager_port": slot.traffic_manager_port,
            "ros_domain_id": slot.ros_domain_id,
            "runtime_namespace": slot.runtime_namespace,
            "gpu_id": slot.gpu_id,
            "cpu_affinity": slot.cpu_affinity,
        },
    )
    return path


def release_slot_lock(repo_root: Path, stack_id: str, slot_id: str) -> bool:
    path = slot_lock_path(repo_root, stack_id, slot_id)
    if not path.exists():
        return False
    path.unlink()
    return True
