"""Inspect Robobus FBX/DAE mesh pieces with Blender.

Run with Blender:

    blender --background --python inspect_robobus_fbx_objects.py -- \
      --input SKM_robobus117th_axis_safe.fbx \
      --output object_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy  # type: ignore
from mathutils import Vector


def parse_args(argv: list[str]) -> argparse.Namespace:
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Input FBX, DAE, or OBJ file.")
    parser.add_argument("--output", required=True, help="Output JSON report path.")
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def import_visual(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".dae":
        bpy.ops.wm.collada_import(filepath=str(path))
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path), use_image_search=False)
    elif suffix == ".obj":
        bpy.ops.import_scene.obj(filepath=str(path))
    else:
        raise ValueError(f"Unsupported mesh input: {path}")


def object_bbox(obj: bpy.types.Object) -> dict[str, list[float]]:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    minimum = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
    maximum = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
    center = (minimum + maximum) / 2
    return {
        "min": list(minimum),
        "max": list(maximum),
        "extent": list(maximum - minimum),
        "center": list(center),
    }


def object_material_names(obj: bpy.types.Object) -> list[str]:
    return [slot.material.name for slot in obj.material_slots if slot.material]


def main() -> int:
    args = parse_args(sys.argv)
    source = Path(args.input).resolve()
    output = Path(args.output).resolve()

    clear_scene()
    import_visual(source)

    objects = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        bbox = object_bbox(obj)
        extent = bbox["extent"]
        objects.append(
            {
                "name": obj.name,
                "materials": object_material_names(obj),
                "vertices": len(obj.data.vertices),
                "polygons": len(obj.data.polygons),
                "bbox": bbox,
                "max_extent": max(extent),
                "volume_hint": extent[0] * extent[1] * extent[2],
            }
        )

    objects.sort(key=lambda item: item["name"])
    payload = {"input": str(source), "mesh_count": len(objects), "objects": objects}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"input": str(source), "mesh_count": len(objects), "output": str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
