"""Tests for the CLI/TUI tools' exam plumbing (study/tools/exam_manifest.py):
set resolution through the exam manifests, per-exam history paths, and the
one-time migration of single-exam (pre-BL-046) history files.

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

import exam_manifest as em  # noqa: E402
import flashcards  # noqa: E402
import quiz  # noqa: E402


@pytest.fixture
def working(tmp_path, monkeypatch):
    monkeypatch.setattr(em, "WORKING", tmp_path)
    return tmp_path


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
    assert em.select_set_files(exam, "questions", None) == [em.CONTENT / "ccarf-questions-standard.json"]


def test_sets_by_label_id_and_all():
    exam = em.load_exam("ccarf")
    assert em.select_set_files(exam, "questions", ["Hard"]) == [em.CONTENT / "ccarf-questions-hard.json"]
    assert em.select_set_files(exam, "questions", ["ccarf-questions-intermediate", "hard", "HARD"]) == [
        em.CONTENT / "ccarf-questions-intermediate.json", em.CONTENT / "ccarf-questions-hard.json"]
    assert len(em.select_set_files(exam, "questions", ["all"])) == len(exam["sections"]["questions"])
    assert em.select_set_files(exam, "flashcards", None) == [em.CONTENT / "ccarf-flashcards.json"]


def test_unknown_set_and_exam_are_errors():
    with pytest.raises(SystemExit, match="no questions set 'expert'"):
        em.select_set_files(em.load_exam("ccarf"), "questions", ["expert"])
    with pytest.raises(SystemExit, match="unknown exam 'nope'"):
        em.load_exam("nope")


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
    assert "migrated 1 record(s)" in err
    assert (working / "quiz_history_ccarf.json").exists()


def test_quiz_review_missed_sees_migrated_history(working, capsys):
    hard = json.loads((em.CONTENT / "ccarf-questions-hard.json").read_text())
    missed = hard[0]["id"].removeprefix("ccarf-")
    _legacy_quiz(working, {missed: {"attempts": 1, "correct": 0, "last_result": "incorrect", "last_seen": "x"}})
    assert quiz.main(["--set", "hard", "--review-missed", "--list", "--no-color"]) == 0
    assert "1 question(s) total" in capsys.readouterr().out


def test_files_and_set_together_is_an_error(working):
    with pytest.raises(SystemExit) as exc:
        quiz.main([str(em.CONTENT / "ccarf-questions-hard.json"), "--set", "hard", "--list"])
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
