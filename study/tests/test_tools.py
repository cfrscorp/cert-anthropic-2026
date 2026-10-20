"""Tests for the CLI/TUI tools' exam plumbing (study/tools/exam_manifest.py):
set resolution through the exam manifests, item tags from the exam's
map.json, per-exam history paths, and the one-time history migrations
(single-exam pre-BL-046 files, then exam-prefixed IDs to pool IDs, BL-050).

All history I/O is redirected to a temp directory — the real .working/ is
never touched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

import content_map  # noqa: E402
import exam_manifest as em  # noqa: E402
import flashcards  # noqa: E402
import quiz  # noqa: E402


@pytest.fixture
def working(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "WORKING", tmp_path)
    return tmp_path


POOL_IDS = json.loads(em.POOL_ID_MIGRATION.read_text())


def _legacy_quiz(working: Path, records: dict) -> Path:
    path = working / "quiz_history.json"
    path.write_text(json.dumps({
        "version": 1,
        "questions": records,
        "sessions": [{"source_files": ["questions-hard.json", "mine.json"], "total": 1, "correct": 1}],
    }))
    return path


# --------------------------------------------------------------------------- #
# Set resolution                                                               #
# --------------------------------------------------------------------------- #
def test_default_exam_and_first_set():
    exam = em.load_exam(em.default_exam())
    assert em.select_set_files(exam, "questions", None) == [em.CONTENT / "questions-standard.json"]


def test_sets_by_label_id_and_all():
    exam = em.load_exam("ccarf")
    assert em.select_set_files(exam, "questions", ["Hard"]) == [em.CONTENT / "questions-hard.json"]
    assert em.select_set_files(exam, "questions", ["questions-intermediate", "hard", "HARD"]) == [
        em.CONTENT / "questions-intermediate.json", em.CONTENT / "questions-hard.json"]
    assert len(em.select_set_files(exam, "questions", ["all"])) == len(exam["sections"]["questions"])
    assert em.select_set_files(exam, "flashcards", None) == [em.CONTENT / "flashcards.json"]


def test_unknown_set_and_exam_are_errors():
    with pytest.raises(SystemExit, match="no questions set 'expert'"):
        em.select_set_files(em.load_exam("ccarf"), "questions", ["expert"])
    with pytest.raises(SystemExit, match="unknown exam 'nope'"):
        em.load_exam("nope")


# --------------------------------------------------------------------------- #
# Item tags come from the exam map                                             #
# --------------------------------------------------------------------------- #
def test_loader_tags_pool_items_from_map_and_skips_unmapped(tmp_path):
    exam = em.load_exam("ccarf")
    tasks = em.item_tasks(exam, "questions")
    assert tasks["q-0001"] == (1, "1.1")
    pool_item = json.loads((em.CONTENT / "questions-standard.json").read_text())[0]
    personal = {**pool_item, "id": "my-q-1", "domain": 5, "task_statement": "5.6"}
    unmapped = {**pool_item, "id": "q-9999"}
    f = tmp_path / "mixed.json"
    f.write_text(json.dumps([pool_item, personal, unmapped]))
    got = {q.id: (q.domain, q.task_statement) for q in quiz.load_questions([f], tasks)}
    assert got == {"q-0001": (1, "1.1"), "my-q-1": (5, "5.6")}


# --------------------------------------------------------------------------- #
# Legacy history migration                                                     #
# --------------------------------------------------------------------------- #
def test_rekey_prefixes_merges_and_maps_sources():
    legacy = {
        "questions": {
            "q-1.1-001": {"attempts": 2, "correct": 1, "last_result": "incorrect", "last_seen": "2026-08-01T00:00:00+00:00", "source": "questions-standard.json"},
            "ccarf-q-1.1-001": {"attempts": 1, "correct": 1, "last_result": "correct", "last_seen": "2026-09-01T00:00:00+00:00", "source": "ccarf-questions-standard.json"},
            "q-2.1-101": {"attempts": 1, "correct": 0, "last_result": "incorrect", "last_seen": None, "source": "questions-lvl2.json"},
        },
        "sessions": [{"source_files": ["questions-hard.json", "mine.json"]}],
    }
    out = em.rekey_legacy_history(legacy, "questions", "ccarf")
    assert set(out["questions"]) == {"ccarf-q-1.1-001", "ccarf-q-2.1-101"}
    merged = out["questions"]["ccarf-q-1.1-001"]
    assert (merged["attempts"], merged["correct"], merged["last_result"]) == (3, 2, "correct")
    assert merged["source"] == "ccarf-questions-standard.json"
    assert out["questions"]["ccarf-q-2.1-101"]["source"] == "questions-lvl2.json"  # unknown names kept
    assert out["sessions"][0]["source_files"] == ["ccarf-questions-hard.json", "mine.json"]
    assert "q-1.1-001" in legacy["questions"], "input must not be mutated"


def test_migration_runs_once_into_default_path_and_keeps_legacy(working):
    legacy = _legacy_quiz(working, {"q-3.1-102": {"attempts": 1, "correct": 1, "last_result": "correct", "last_seen": "x"}})
    target = em.history_path("quiz", "ccarf")
    assert target == working / "quiz_history_ccarf.json"

    notice = em.migrate_legacy_history("quiz", "questions", "ccarf", target)
    assert notice and "1 record" in notice
    assert set(json.loads(target.read_text())["questions"]) == {"ccarf-q-3.1-102"}
    assert legacy.exists()

    # Never over an existing per-exam file (e.g. newer progress, or records
    # from a personal question file with unprefixed IDs).
    data = json.loads(target.read_text())
    data["questions"]["q-9.9-001"] = {"attempts": 1, "correct": 0}
    target.write_text(json.dumps(data))
    assert em.migrate_legacy_history("quiz", "questions", "ccarf", target) is None
    assert "q-9.9-001" in json.loads(target.read_text())["questions"]


def test_migration_skips_explicit_paths_and_other_exams(working):
    _legacy_quiz(working, {"q-1.1-001": {"attempts": 1, "correct": 1}})
    custom = working / "mine_history.json"
    assert em.migrate_legacy_history("quiz", "questions", "ccarf", custom) is None
    assert not custom.exists()
    assert em.migrate_legacy_history("quiz", "questions", "ccdvf", em.history_path("quiz", "ccdvf")) is None


# --------------------------------------------------------------------------- #
# CLI end to end (history redirected into the temp dir)                        #
# --------------------------------------------------------------------------- #
def test_quiz_list_uses_exam_set_and_migrates(working, capsys):
    _legacy_quiz(working, {"q-3.1-102": {"attempts": 1, "correct": 1, "last_result": "correct", "last_seen": "x"}})
    assert quiz.main(["--set", "hard", "--list", "--no-color"]) == 0
    out, err = capsys.readouterr()
    assert "CCAR-F PRACTICE QUIZ" in out
    assert "75 question(s) total" in out
    assert "migrated 1 record(s)" in err and "re-keyed 1 record(s)" in err
    history = json.loads((working / "quiz_history_ccarf.json").read_text())
    assert history["version"] == 2
    assert set(history["questions"]) == {POOL_IDS["questions"]["ccarf-q-3.1-102"]}
    assert history["sessions"][0]["source_files"] == ["questions-hard.json", "mine.json"]


def test_quiz_review_missed_sees_migrated_history(working, capsys):
    hard = json.loads((em.CONTENT / "questions-hard.json").read_text())
    old_id = {new: old for old, new in POOL_IDS["questions"].items()}[hard[0]["id"]]
    missed = old_id.removeprefix("ccarf-")  # the pre-BL-046 unprefixed form
    _legacy_quiz(working, {missed: {"attempts": 1, "correct": 0, "last_result": "incorrect", "last_seen": "x"}})
    assert quiz.main(["--set", "hard", "--review-missed", "--list", "--no-color"]) == 0
    assert "1 question(s) total" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Pool-ID history migration (BL-050)                                           #
# --------------------------------------------------------------------------- #
def test_pool_migration_rekeys_merges_and_backs_up(tmp_path):
    path = tmp_path / "custom_history.json"  # any history path, not just the default
    original = {
        "version": 1,
        "questions": {
            "ccarf-q-1.1-001": {"attempts": 2, "correct": 1, "last_result": "incorrect", "last_seen": "2026-09-01", "source": "ccarf-questions-standard.json"},
            "q-1.1-001": {"attempts": 1, "correct": 1, "last_result": "correct", "last_seen": "2026-09-02", "source": "mine.json"},
        },
        "sessions": [{"source_files": ["ccarf-questions-standard.json", "mine.json"]}],
    }
    path.write_text(json.dumps(original))
    notice = em.migrate_pool_ids(path, "questions", "questions")
    assert notice and "re-keyed 1 record(s)" in notice
    out = json.loads(path.read_text())
    assert out["version"] == 2
    new_id = POOL_IDS["questions"]["ccarf-q-1.1-001"]
    assert out["questions"][new_id]["source"] == "questions-standard.json"
    assert out["questions"]["q-1.1-001"]["source"] == "mine.json", "unmapped (personal) ids are kept"
    assert out["sessions"][0]["source_files"] == ["questions-standard.json", "mine.json"]
    assert json.loads((tmp_path / "custom_history.v1.json").read_text()) == original
    assert em.migrate_pool_ids(path, "questions", "questions") is None, "runs once (version 2)"


def test_pool_migration_merges_collisions_and_skips_bad_files(tmp_path):
    path = tmp_path / "flashcards_history.json"
    old = next(iter(POOL_IDS["flashcards"]))
    path.write_text(json.dumps({"version": 1, "cards": {old: {"attempts": 1, "correct": 0, "last_seen": "a"},
                                                         POOL_IDS["flashcards"][old]: {"attempts": 2, "correct": 2, "last_seen": "b"}}}))
    em.migrate_pool_ids(path, "cards", "flashcards")
    merged = json.loads(path.read_text())["cards"]
    assert merged == {POOL_IDS["flashcards"][old]: {"attempts": 3, "correct": 2, "last_seen": "b"}}
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert em.migrate_pool_ids(bad, "cards", "flashcards") is None
    assert em.migrate_pool_ids(tmp_path / "missing.json", "cards", "flashcards") is None


def test_files_and_set_together_is_an_error(working):
    with pytest.raises(SystemExit) as exc:
        quiz.main([str(em.CONTENT / "questions-hard.json"), "--set", "hard", "--list"])
    assert exc.value.code == 2


def test_reset_keeps_empty_file_while_legacy_exists(working, capsys):
    _legacy_quiz(working, {"q-1.1-001": {"attempts": 1, "correct": 1}})
    target = working / "quiz_history_ccarf.json"
    assert quiz.main(["--reset-history", "--yes", "--no-color"]) == 0
    assert json.loads(target.read_text())["questions"] == {}
    # The next run must not re-import the legacy history over the reset.
    assert quiz.main(["--list", "--no-color"]) == 0
    assert json.loads(target.read_text())["questions"] == {}
    assert "Cleared" in capsys.readouterr().out


def test_reset_deletes_when_no_legacy(working, capsys):
    target = working / "quiz_history_ccarf.json"
    target.write_text(json.dumps({"version": 1, "questions": {}, "sessions": []}))
    assert quiz.main(["--reset-history", "--yes", "--no-color"]) == 0
    assert not target.exists()


def test_flashcards_list_uses_exam_deck(working, capsys):
    assert flashcards.main(["--list", "--no-color"]) == 0
    out = capsys.readouterr().out
    assert "CCAR-F FLASHCARDS" in out
    assert (working / "flashcards_history_ccarf.json").exists() is False  # --list never writes history


# --------------------------------------------------------------------------- #
# Content dependency report (content_map.py)                                   #
# --------------------------------------------------------------------------- #
def _state(**maps):
    return {
        "components": {
            "qs": {"kind": "questions", "version": "1.0.0", "items": ["q-0001", "q-0002", "q-0003"]},
            "old": {"kind": "flashcards", "version": "1.0.0", "items": ["fc-0001"]},
        },
        "exams": {slug: {"code": slug.upper(), "listed": slug == "a", "pins": {"qs": "^1.0"},
                         "map": {"questions": m, "flashcards": {}, "concepts": {}}} for slug, m in maps.items()},
    }


def test_content_map_reverse_view_and_orphans():
    report = content_map.build_report(_state(a={"q-0001": "1.1", "q-0002": "1.2"}, b={"q-0002": "2.4", "q-0404": "1.1"}))
    assert report["components"]["qs"]["pinned_by"] == {"a": "^1.0", "b": "^1.0"}
    assert report["components"]["qs"]["mapped"] == {"a": 2, "b": 1}
    assert report["orphan_items"] == {"qs": ["q-0003"], "old": ["fc-0001"]}
    assert report["orphan_components"] == ["old"]
    assert report["dangling"] == ["b:q-0404"]
    usage = content_map.item_usage(_state(a={"q-0002": "1.2"}, b={"q-0002": "2.4"}), "q-0002")
    assert usage == {"item": "q-0002", "component": "qs", "kind": "questions", "used_by": {"a": "1.2", "b": "2.4"}}


def test_content_map_real_pool_has_no_dangling_entries(capsys):
    report = content_map.build_report(content_map.load_state())
    assert report["dangling"] == []
    assert "ccarf" in report["exams"]
    assert content_map.main(["--orphans"]) == 0
    assert capsys.readouterr().out.strip()
