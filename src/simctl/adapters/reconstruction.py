from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .base import AdapterContext


@dataclass
class ReconstructionOutput:
    source: str
    family: str
    stage: str
    artifacts: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class ReconstructionAdapter(ABC):
    @abstractmethod
    def reconstruct(self, context: AdapterContext) -> ReconstructionOutput:
        raise NotImplementedError


class _BasePlaceholderReconstructionAdapter(ReconstructionAdapter):
    source = "placeholder_reconstruction_adapter"
    family = "reconstruction"
    stage = "draft"

    def reconstruct(self, context: AdapterContext) -> ReconstructionOutput:
        run_dir = str(context.metadata.get("run_dir", ""))
        profile_id = context.algorithm_profile
        scenario_id = context.scenario_id
        artifacts = {
            "capture_index": f"{run_dir}/reconstruction/capture_index.json" if run_dir else "reconstruction/capture_index.json",
            "diagnostics": f"{run_dir}/reconstruction/diagnostics.json" if run_dir else "reconstruction/diagnostics.json",
        }
        notes = [
            f"profile_id={profile_id}",
            f"scenario_id={scenario_id}",
            f"future_family={self.family}",
            f"stage={self.stage}",
        ]
        return ReconstructionOutput(
            source=self.source,
            family=self.family,
            stage=self.stage,
            artifacts=artifacts,
            notes=notes,
        )


class MapRefreshReconstructionAdapter(_BasePlaceholderReconstructionAdapter):
    family = "map_refresh"
    stage = "asset_refresh"

    def reconstruct(self, context: AdapterContext) -> ReconstructionOutput:
        output = super().reconstruct(context)
        output.notes.extend(
            [
                "focus=lanelet_alignment_and_localization_support",
                "deliverable=lanelet_update_candidate",
            ]
        )
        return output


class StaticGaussianReconstructionAdapter(_BasePlaceholderReconstructionAdapter):
    family = "static_gaussians"
    stage = "geometry_base"

    def reconstruct(self, context: AdapterContext) -> ReconstructionOutput:
        output = super().reconstruct(context)
        output.artifacts["static_gaussians"] = (
            f"{context.metadata.get('run_dir', '')}/reconstruction/static_gaussians.ply"
            if context.metadata.get("run_dir")
            else "reconstruction/static_gaussians.ply"
        )
        output.notes.extend(
            [
                "focus=static_geometry_and_localization_support",
                "suggested_families=CityGaussianV2,2DGS,LiHi-GS",
            ]
        )
        return output


class DynamicGaussianReconstructionAdapter(_BasePlaceholderReconstructionAdapter):
    family = "dynamic_gaussians"
    stage = "actor_aware_replay"

    def reconstruct(self, context: AdapterContext) -> ReconstructionOutput:
        output = super().reconstruct(context)
        run_dir = context.metadata.get("run_dir", "")
        output.artifacts["dynamic_gaussians"] = (
            f"{run_dir}/reconstruction/dynamic_gaussians.ply" if run_dir else "reconstruction/dynamic_gaussians.ply"
        )
        output.artifacts["dynamic_tracks"] = (
            f"{run_dir}/reconstruction/dynamic_tracks.json" if run_dir else "reconstruction/dynamic_tracks.json"
        )
        output.notes.extend(
            [
                "focus=dynamic_actor_separation_and_temporal_consistency",
                "suggested_families=DrivingGaussian,DeSiRe-GS,4DGS",
            ]
        )
        return output


def load_reconstruction_adapter(profile_id: str) -> ReconstructionAdapter:
    if profile_id == "reconstruction_public_road_map_refresh":
        return MapRefreshReconstructionAdapter()
    if profile_id == "reconstruction_static_public_road_gaussians":
        return StaticGaussianReconstructionAdapter()
    if profile_id == "reconstruction_dynamic_public_road_gaussians":
        return DynamicGaussianReconstructionAdapter()
    raise FileNotFoundError(f"Unable to locate reconstruction adapter for '{profile_id}'")
