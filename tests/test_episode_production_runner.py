"""bci-episode-production runner: `diorama-episode` single-episode entry point safety."""
import pytest

from pipeline import diorama_batch_orchestrator as orch


def test_single_episode_refuses_published_project(tmp_path, monkeypatch):
    pid = "diorama_99_published_case"
    (tmp_path / pid / "06_publish").mkdir(parents=True)
    (tmp_path / pid / "06_publish" / "upload_receipt.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(orch, "PROJECTS_DIR", tmp_path)
    called = []
    monkeypatch.setattr(orch, "precheck_diorama_project", lambda *a, **k: called.append(1))
    with pytest.raises(RuntimeError, match="published"):
        orch.run_single_diorama_episode(slug="x", project_id=pid, pillar="brain_history")
    assert not called


def test_single_episode_precheck_only_never_generates(tmp_path, monkeypatch):
    monkeypatch.setattr(orch, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(
        orch,
        "precheck_diorama_project",
        lambda spec, run_tts_clock=True: {
            "project_id": spec["project_id"], "passed": True, "sentences": 53, "clips": 62,
            "words": 500, "tts_duration_sec": 160.0, "issues": [],
        },
    )
    monkeypatch.setattr(orch, "generate_and_finalize_diorama_episode", lambda *a, **k: pytest.fail("must not generate"))
    rep = orch.run_single_diorama_episode(slug="x", project_id="diorama_98_new", pillar="brain_history", precheck_only=True)
    assert rep["mode"] == "precheck_only" and rep["precheck"]["passed"]


def test_single_episode_stops_on_failed_precheck(tmp_path, monkeypatch):
    monkeypatch.setattr(orch, "PROJECTS_DIR", tmp_path)
    monkeypatch.setattr(
        orch,
        "precheck_diorama_project",
        lambda spec, run_tts_clock=True: {
            "project_id": spec["project_id"], "passed": False, "sentences": 0, "clips": 0,
            "words": 0, "tts_duration_sec": None, "issues": ["[cold_open_v7] S1 hook must end with '!'"],
        },
    )
    monkeypatch.setattr(orch, "generate_and_finalize_diorama_episode", lambda *a, **k: pytest.fail("must not generate"))
    with pytest.raises(RuntimeError, match="Precheck failed"):
        orch.run_single_diorama_episode(slug="x", project_id="diorama_97_new", pillar="brain_history")
