from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STUB_PROBE_PATH = REPO_ROOT / "tools" / "codex" / "write_stub_metric_probe.py"
SUMMARY_PATH = REPO_ROOT / "tools" / "codex" / "summarize_run_artifacts.py"


def _load_stub_probe_module():
    spec = importlib.util.spec_from_file_location("write_stub_metric_probe", STUB_PROBE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["write_stub_metric_probe"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_summary_module():
    spec = importlib.util.spec_from_file_location("summarize_run_artifacts", SUMMARY_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["summarize_run_artifacts"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CodexToolTests(unittest.TestCase):
    def test_write_stub_metric_probe_creates_runtime_evidence_metrics(self) -> None:
        module = _load_stub_probe_module()
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir = Path(tempdir) / "run"
            output = module.write_stub_metric_probe(run_dir)

            self.assertEqual(output["kind"], "stub_metric_probe")
            self.assertTrue(output["overall_passed"])
            self.assertEqual(output["profile"], "codex_stub_smoke")
            self.assertEqual(output["scope"], "stub_only")
            self.assertIn("not_ubuntu_runtime_acceptance", output["assumptions"])
            self.assertEqual(output["metrics"]["route_completion"], 1.0)
            self.assertEqual(output["metrics"]["collision_count"], 0.0)
            self.assertGreaterEqual(output["metrics"]["min_ttc_sec"], 1.5)

            expected_path = (
                run_dir
                / "runtime_verification"
                / "metric_probe_codex_stub_smoke"
                / "metric_probe_codex_stub_smoke.json"
            )
            self.assertTrue(expected_path.exists())
            saved = json.loads(expected_path.read_text(encoding="utf-8"))
            self.assertEqual(saved, output)

    def test_summarize_run_reports_finalize_and_runtime_evidence_links(self) -> None:
        module = _load_summary_module()
        with tempfile.TemporaryDirectory() as tempdir:
            run_root = Path(tempdir) / "runs"
            run_dir = run_root / "run_001"
            run_dir.mkdir(parents=True)
            runtime_evidence = run_dir / "runtime_evidence_summary.json"
            runtime_evidence.write_text(json.dumps({"metrics": {"route_completion": 1.0}}), encoding="utf-8")
            (run_dir / "run_result.json").write_text(
                json.dumps(
                    {
                        "run_id": "run_001",
                        "status": "passed",
                        "finalized_at": "2026-04-24T00:00:00+00:00",
                        "runtime_evidence_path": str(runtime_evidence),
                        "artifacts": {"runtime_evidence_summary": str(runtime_evidence)},
                    }
                ),
                encoding="utf-8",
            )
            report_dir = run_root / "report"
            report_dir.mkdir()
            (report_dir / "summary.json").write_text(json.dumps({"total_runs": 1}), encoding="utf-8")

            summary = module.summarize_run(run_root)

            self.assertTrue(summary["chain_presence"]["run_result"])
            self.assertTrue(summary["chain_presence"]["report_summary"])
            self.assertTrue(summary["chain_presence"]["runtime_evidence"])
            self.assertTrue(summary["chain_presence"]["finalized"])
            self.assertEqual(summary["latest_runtime_evidence"], str(runtime_evidence))


if __name__ == "__main__":
    unittest.main()
