"""Deterministic, offline validation of the study content.

Content is organized as reusable, versioned *components* (study/content/, listed
in components.json) that *exams* (study/exams/<slug>/exam.json, listed in
study/exams/index.json) pin per section. Every file is validated against its
JSON Schema, then cross-checked:

- component integrity (valid answer keys, complete distractor rationales,
  exam-prefixed globally-unique IDs, real task statements in the component's
  task_scheme, resolvable lab links) — independent of which exams use them;
- exam integrity (weights, task statements, guide, lab links) and pin
  integrity (pinned component exists, is the right kind, satisfies the pin's
  version range) — parametrized over every exam in the index;
- coverage per exam (per-task question target, tier minimums, one concept per
  task statement).

Mirrors the labs' philosophy: the content cannot silently break the web app.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import jsonschema
import pytest

STUDY_ROOT = Path(__file__).resolve().parent.parent
CONTENT = STUDY_ROOT / "content"
EXAMS_DIR = STUDY_ROOT / "exams"
SCHEMA = STUDY_ROOT / "schema"
LABS_ROOT = STUDY_ROOT.parent / "labs"

MIN_QUESTIONS_PER_TIER = 50
KIND_SCHEMA = {
    "questions": "questions.schema.json",
    "flashcards": "flashcards.schema.json",
    "concepts": "concepts.schema.json",
    "labs": "labs.schema.json",
}
# Item-ID infix per task-tagged kind: <task_scheme>-<infix>-<task>[-NNN].
ID_INFIX = {"questions": "q", "flashcards": "fc", "concepts": "concept"}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


APP = _load(STUDY_ROOT / "app.json")
REGISTRY = _load(CONTENT / "components.json")
COMPONENTS = {c["id"]: c for c in REGISTRY["components"]}
ITEMS = {cid: _load(CONTENT / c["file"]) for cid, c in COMPONENTS.items() if (CONTENT / c["file"]).is_file()}
EXAM_INDEX = _load(EXAMS_DIR / "index.json")
EXAM_SLUGS = EXAM_INDEX["exams"]
EXAMS = {slug: _load(EXAMS_DIR / slug / "exam.json") for slug in EXAM_SLUGS}


def _of_kind(kind: str) -> list[str]:
    return [cid for cid, c in COMPONENTS.items() if c["kind"] == kind]


def _task_ids(slug: str) -> set[str]:
    return {ts["id"] for ts in EXAMS[slug]["task_statements"]}


def _task_domain(slug: str) -> dict[str, int]:
    return {ts["id"]: ts["domain"] for ts in EXAMS[slug]["task_statements"]}


def _pinned(slug: str, section: str) -> list[str]:
    return [pin["component"] for pin in EXAMS[slug]["sections"][section]]


def _all_questions() -> list[dict]:
    return [q for cid in _of_kind("questions") for q in ITEMS[cid]]


def satisfies(version: str, spec: str) -> bool:
    """Exact (1.2.3) or caret (^1, ^1.2, ^1.2.3: same major and >= the given version)."""
    v = tuple(int(x) for x in version.split("."))
    if not spec.startswith("^"):
        return v == tuple(int(x) for x in spec.split("."))
    base = [int(x) for x in spec[1:].split(".")]
    base += [0] * (3 - len(base))
    return v[0] == base[0] and v >= tuple(base)


def test_satisfies_semantics():
    assert satisfies("1.0.0", "^1.0") and satisfies("1.4.2", "^1.2") and satisfies("1.2.0", "1.2.0")
    assert not satisfies("2.0.0", "^1.0") and not satisfies("1.1.9", "^1.2") and not satisfies("1.2.1", "1.2.0")


# --------------------------------------------------------------------------- #
# Schema validation                                                            #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "path, schema_file",
    [
        (STUDY_ROOT / "app.json", "app.schema.json"),
        (CONTENT / "components.json", "components.schema.json"),
        (EXAMS_DIR / "index.json", "exam-index.schema.json"),
    ],
    ids=lambda x: x.name if isinstance(x, Path) else x,
)
def test_manifest_matches_schema(path, schema_file):
    jsonschema.validate(instance=_load(path), schema=_load(SCHEMA / schema_file))


@pytest.mark.parametrize("slug", EXAM_SLUGS)
def test_exam_matches_schema(slug):
    jsonschema.validate(instance=EXAMS[slug], schema=_load(SCHEMA / "exam.schema.json"))


@pytest.mark.parametrize("cid", list(COMPONENTS))
def test_component_matches_schema(cid):
    assert cid in ITEMS, f"{cid} → missing file content/{COMPONENTS[cid]['file']}"
    jsonschema.validate(instance=ITEMS[cid], schema=_load(SCHEMA / KIND_SCHEMA[COMPONENTS[cid]["kind"]]))


# --------------------------------------------------------------------------- #
# Version consistency — app.json's app_version (the engine version) is the    #
# single source of truth; pyproject.toml and serve.py must not drift from it. #
# --------------------------------------------------------------------------- #
def test_app_version_matches_pyproject():
    pyproject = tomllib.loads((STUDY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == APP["app_version"]


def test_app_version_matches_serve_py():
    serve_py = (STUDY_ROOT / "serve.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__ = "([^"]+)"', serve_py, re.MULTILINE)
    assert match, "serve.py must define __version__ = \"X.Y.Z\""
    assert match.group(1) == APP["app_version"]


# --------------------------------------------------------------------------- #
# Component registry — ids unique, every file registered, schemes real.        #
# --------------------------------------------------------------------------- #
def test_component_ids_and_files_unique():
    ids = [c["id"] for c in REGISTRY["components"]]
    files = [c["file"] for c in REGISTRY["components"]]
    assert len(ids) == len(set(ids)), "duplicate component ids"
    assert len(files) == len(set(files)), "two components share a file"


def test_every_content_file_is_registered():
    on_disk = {p.name for p in CONTENT.glob("*.json")} - {"components.json"}
    listed = {c["file"] for c in REGISTRY["components"]}
    assert on_disk == listed, f"components.json out of sync with study/content/ — on disk {on_disk}, listed {listed}"


def test_component_task_schemes_are_real_exams():
    for cid, c in COMPONENTS.items():
        if c["kind"] == "labs":
            assert c["task_scheme"] is None, f"{cid}: labs components are not task-tagged"
        else:
            assert c["task_scheme"] in EXAMS, f"{cid}: task_scheme {c['task_scheme']!r} is not an exam in exams/index.json"


# --------------------------------------------------------------------------- #
# Component items — IDs carry the task_scheme prefix and are globally unique   #
# per kind (progress history is keyed by item id, across every component);    #
# task tags are real task statements of the component's task_scheme exam.    #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("kind", list(ID_INFIX))
def test_item_ids_globally_unique_per_kind(kind):
    ids = [item["id"] for cid in _of_kind(kind) for item in ITEMS[cid]]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"duplicate {kind} ids across components: {dupes}"


@pytest.mark.parametrize("cid", [cid for cid, c in COMPONENTS.items() if c["kind"] in ID_INFIX])
def test_item_ids_prefixed_and_tasks_real(cid):
    comp = COMPONENTS[cid]
    scheme, infix = comp["task_scheme"], ID_INFIX[comp["kind"]]
    tasks, task_domain = _task_ids(scheme), _task_domain(scheme)
    for item in ITEMS[cid]:
        assert item["id"].startswith(f"{scheme}-{infix}-{item['task_statement']}"), f"{cid}: {item['id']}"
        assert item["task_statement"] in tasks, f"{cid}: {item['id']} → unknown task {item['task_statement']}"
        assert item["domain"] == task_domain[item["task_statement"]], f"{cid}: {item['id']} domain mismatch"
        if item.get("lab"):
            assert (LABS_ROOT / item["lab"]).is_dir(), f"{cid}: {item['id']} → missing lab {item['lab']}"


def _correct_set(q):
    """correct is a single letter for a normal item, or a list of 2+ letters
    for a multi-response ('Select N') item."""
    correct = q["correct"]
    return set(correct) if isinstance(correct, list) else {correct}


def test_question_options_are_sequential_A_through_E():
    # 4 options (A-D) is the norm; multi-response items may have 5 (A-E).
    for q in _all_questions():
        keys = [o["key"] for o in q["options"]]
        assert keys == ["A", "B", "C", "D", "E"][: len(keys)], q["id"]


def test_correct_answer_is_a_real_option():
    for q in _all_questions():
        keys = {o["key"] for o in q["options"]}
        assert _correct_set(q) <= keys, q["id"]


def test_every_distractor_has_a_rationale():
    for q in _all_questions():
        option_keys = {o["key"] for o in q["options"]}
        expected = option_keys - _correct_set(q)
        got = set(q["rationale"]["distractors"].keys())
        assert got == expected, f"{q['id']}: distractor rationales {got} != {expected}"


def test_labs_cover_every_lab_dir():
    lab_dirs = sorted(d.name for d in LABS_ROOT.glob("lab-*") if d.is_dir())
    indexed = sorted(l["slug"] for cid in _of_kind("labs") for l in ITEMS[cid])
    assert indexed == lab_dirs, "labs component out of sync with labs/ — run tools/build_labs.py"


def test_labs_slugs_resolve_and_have_content():
    for cid in _of_kind("labs"):
        for l in ITEMS[cid]:
            assert (LABS_ROOT / l["slug"]).is_dir(), l["slug"]
            assert l["readme_html"].strip(), f"{l['slug']} has empty readme_html"


# --------------------------------------------------------------------------- #
# Exam integrity                                                               #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("slug", EXAM_SLUGS)
def test_exam_identity_and_guide(slug):
    exam = EXAMS[slug]
    assert exam["slug"] == slug, f"exams/{slug}/exam.json declares slug {exam['slug']!r}"
    assert exam["code"].replace("-", "").lower() == slug, f"{exam['code']} doesn't match slug {slug}"
    assert (EXAMS_DIR / slug / exam["guide"]).is_file(), f"{slug}: missing guide {exam['guide']}"


@pytest.mark.parametrize("slug", EXAM_SLUGS)
def test_exam_domains_and_tasks(slug):
    exam = EXAMS[slug]
    domain_ids = [d["id"] for d in exam["domains"]]
    task_ids = [ts["id"] for ts in exam["task_statements"]]
    assert sum(d["weight"] for d in exam["domains"]) == 100
    assert len(domain_ids) == len(set(domain_ids)), "duplicate domain ids"
    assert len(task_ids) == len(set(task_ids)), "duplicate task-statement ids"
    for ts in exam["task_statements"]:
        assert ts["domain"] in domain_ids, ts
        assert ts["id"].startswith(f"{ts['domain']}."), ts
        for lab in ts["labs"]:
            assert (LABS_ROOT / lab).is_dir(), f"{slug} {ts['id']} → missing lab {lab}"


@pytest.mark.parametrize("slug", EXAM_SLUGS)
def test_exam_pins_resolve(slug):
    for section, pins in EXAMS[slug]["sections"].items():
        ids = [pin["component"] for pin in pins]
        assert len(ids) == len(set(ids)), f"{slug}.{section}: a component is pinned twice"
        for pin in pins:
            comp = COMPONENTS.get(pin["component"])
            assert comp, f"{slug}.{section}: unknown component {pin['component']!r}"
            assert comp["kind"] == section, f"{slug}.{section}: {comp['id']} is a {comp['kind']} component"
            assert satisfies(comp["version"], pin["version"]), (
                f"{slug}.{section}: {comp['id']} is {comp['version']}, pin requires {pin['version']}"
            )


@pytest.mark.parametrize("slug", EXAM_SLUGS)
def test_exam_pins_use_own_task_scheme(slug):
    # Reusing another exam's component needs a task mapping
    # (study/exams/<slug>/mappings/<component>.json), designed in BL-048.
    # Until then, a foreign-scheme pin would silently mis-tag readiness.
    for section, pins in EXAMS[slug]["sections"].items():
        for pin in pins:
            scheme = COMPONENTS[pin["component"]]["task_scheme"]
            assert scheme in (slug, None), (
                f"{slug}.{section}: {pin['component']} is tagged with {scheme!r} task IDs; "
                "cross-exam task mappings aren't supported yet (BL-048)"
            )


# --------------------------------------------------------------------------- #
# Coverage, per exam                                                           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("slug", EXAM_SLUGS)
def test_each_question_tier_meets_minimum(slug):
    shortfalls = {cid: len(ITEMS[cid]) for cid in _pinned(slug, "questions") if len(ITEMS[cid]) < MIN_QUESTIONS_PER_TIER}
    assert not shortfalls, f"{slug}: tiers below the {MIN_QUESTIONS_PER_TIER}-question minimum: {shortfalls}"


@pytest.mark.parametrize("slug", EXAM_SLUGS)
def test_question_coverage_meets_target(slug):
    # Scoped to the exam's coverage_component (CCAR-F: the Standard tier) — the
    # per-task target was calibrated against it; other tiers have their own
    # (lower) bars (see BL-031 in BACKLOG.md).
    config = EXAMS[slug]["config"]
    assert config["coverage_component"] in _pinned(slug, "questions"), f"{slug}: coverage_component isn't pinned"
    counts = {tid: 0 for tid in _task_ids(slug)}
    for q in ITEMS[config["coverage_component"]]:
        counts[q["task_statement"]] += 1
    target = config["questions_per_task_target"]
    shortfalls = {tid: n for tid, n in counts.items() if n < target}
    assert not shortfalls, f"{slug}: task statements below target {target}: {shortfalls}"


@pytest.mark.parametrize("slug", EXAM_SLUGS)
def test_exactly_one_concept_per_task_statement(slug):
    seen = [c["task_statement"] for cid in _pinned(slug, "concepts") for c in ITEMS[cid]]
    assert len(seen) == len(set(seen)), f"{slug}: more than one concept per task statement"
    missing = _task_ids(slug) - set(seen)
    assert not missing, f"{slug}: missing concept explainers for: {sorted(missing)}"
