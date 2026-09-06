"""Route compact specifications to agents and verify source/test documentation coverage."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("title", "compact", "source_files", "test_files", "document_role")
SOURCE_SUFFIXES = {".py", ".js", ".mjs", ".ts", ".vue", ".css", ".html"}
EXCLUDED_PREFIXES = (
    "modules/mta_strategy_evaluation/", "docs/en/strategy-evaluation/",
)
EXCLUDED_FILES = {
    "docs/en/dashboard/views.md",
    "dashboard/src/views/KnowledgeBase.vue",
    "dashboard/src/lib/ontologyReviewFixtures.js",
    "dashboard/src/lib/willowGmvModel.js",
    "dashboard/src/components/WillowGmvForecast.vue",
    "dashboard/tests/ontology_review_fixtures.test.js",
    "dashboard/tests/willow_gmv_model.test.js",
    "script/import_ontology_review_fixtures.mjs",
    "script/evaluate_strategies.py",
    "backend/repository/evaluation.py",
}


def in_scope(name: str) -> bool:
    """Bound adoption to Trance-0 without changing other contributors' contracts."""
    return (not name.startswith(EXCLUDED_PREFIXES) and name not in EXCLUDED_FILES
            and (not name.startswith("docs/worklog/") or name in {
                "docs/worklog/index.md", "docs/worklog/ZheyuanWu.md"}))


def metadata(text: str) -> dict:
    """Read the documented scalar-only routing fields without a YAML dependency."""
    result = {}
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    if not match:
        return result
    for line in match[1].splitlines():
        key, separator, value = line.partition(":")
        if separator and key in FIELDS:
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1].replace("''", "'")
            result[key] = value
    return result


def paths(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def inventory(root: Path) -> list[str]:
    """Include tracked and new nonignored files; never crawl generated trees."""
    output = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    )
    return sorted(set(output.decode("utf-8").split("\0")) - {""})


def records(root: Path, files: list[str], include_references: bool = False) -> list[dict]:
    result = []
    for name in files:
        if not in_scope(name) or not name.startswith("docs/en/") or not name.endswith(".md") or not (root / name).is_file():
            continue
        meta = metadata((root / name).read_text(encoding="utf-8-sig"))
        if meta.get("document_role") == "reference" and not include_references:
            continue
        result.append({"path": name, "title": meta.get("title", ""),
                       "compact": meta.get("compact", ""),
                       "source_files": [p for p in paths(meta.get("source_files", "")) if in_scope(p)],
                       "test_files": [p for p in paths(meta.get("test_files", "")) if in_scope(p)]})
    return sorted(result, key=lambda item: item["path"])


def search(items: list[dict], query: str, limit: int = 5) -> list[dict]:
    query = query.lower().replace("\\", "/").strip()
    tokens = set(re.findall(r"[\w]+", query))
    scored = []
    for item in items:
        owned = item["source_files"] + item["test_files"]
        exact = int(query in [p.lower() for p in owned])
        haystack = " ".join([item["path"], item["title"], item["compact"], *owned]).lower()
        words = set(re.findall(r"[\w]+", haystack))
        score = len(tokens & words)
        if exact or score:
            scored.append((exact, score, item))
    return [item for _, _, item in sorted(scored, key=lambda row: (-row[0], -row[1], row[2]["path"]))[:limit]]


def is_test(name: str) -> bool:
    return bool(re.match(r"(?:modules/[^/]+/tests/|backend/tests/|dashboard/tests/|tests/)", name)) and (
        Path(name).name.startswith("test_") and name.endswith(".py") or name.endswith(".test.js")
    )


def is_source(name: str) -> bool:
    return (bool(re.match(r"modules/[^/]+/src/|backend/|dashboard/", name))
            and "/tests/" not in name and not name.endswith("__init__.py")
            and Path(name).suffix in SOURCE_SUFFIXES)


def check(root: Path, files: list[str]) -> dict:
    files = [name for name in files if in_scope(name)]
    errors = []
    owners = {field: defaultdict(list) for field in ("source_files", "test_files")}
    pages = records(root, files, include_references=True)
    for name in files:
        if not name.endswith(".md") or not (root / name).is_file():
            continue
        governed = name.startswith(("docs/en/", "docs/version/", "docs/worklog/"))
        if not governed and "/" in name:
            continue
        text = (root / name).read_text(encoding="utf-8-sig")
        if len(text.splitlines()) > 500:
            errors.append(f"{name}: exceeds 500 lines")
        if re.search(r"^(?:<<<<<<< |=======\s*$|>>>>>>> )", text, re.M):
            errors.append(f"{name}: unresolved merge marker")
        if not governed:
            continue
        meta = metadata(text)
        if not meta.get("compact", "").strip() or meta.get("compact") in {">", "|", ">-", "|-"}:
            errors.append(f"{name}: compact must be a nonempty one-line scalar")
        if not name.startswith("docs/en/"):
            continue
        sections = list(re.finditer(r"^## ([^\n]+)\n([\s\S]*?)(?=^## |\Z)", text, re.M))
        source_sections = [s[2] for s in sections if re.match(r"Source Files(?:\s|$)", s[1])]
        verification = [s[2] for s in sections if s[1].strip() == "Verification"]
        for field in owners:
            if meta.get(field) in {">", "|", ">-", "|-"}:
                errors.append(f"{name}: {field} must be comma-separated paths on one line")
            for owned in paths(meta.get(field, "")):
                if not in_scope(owned):
                    continue
                path = Path(owned)
                if path.is_absolute() or ".." in path.parts or "\\" in owned or not (root / path).is_file():
                    errors.append(f"{name}: invalid or missing {field} path {owned}")
                owners[field][owned].append(name)
        sources = [p for p in paths(meta.get("source_files", "")) if in_scope(p)]
        if sources:
            if len(source_sections) != 1:
                errors.append(f"{name}: requires exactly one Source Files section")
            else:
                entries = re.findall(r"^Source:\s*(.*?)(?=\n\s*\n|\Z)", source_sections[0], re.M | re.S)
                mentioned = [p for entry in entries for p in re.findall(r"`([^`]+)`", entry) if in_scope(p)]
                for source in sources:
                    if mentioned.count(source) != 1:
                        errors.append(f"{name}: {source} needs exactly one Source entry")
                for source in set(mentioned) - set(sources):
                    errors.append(f"{name}: Source entry absent from source_files: {source}")
        if any(in_scope(p) for p in paths(meta.get("test_files", ""))):
            if len(verification) != 1:
                errors.append(f"{name}: requires exactly one Verification section")
            else:
                for label in ("Scope", "Cases", "Command", "Limitations"):
                    if f"**{label}:**" not in verification[0]:
                        errors.append(f"{name}: Verification lacks {label}")
    sources = [name for name in files if is_source(name) and (root / name).is_file()]
    tests = [name for name in files if is_test(name) and (root / name).is_file()]
    for name in sorted(set(sources + tests) | set(owners["source_files"])):
        path = root / name
        if path.is_file() and path.suffix in SOURCE_SUFFIXES:
            if re.search(r"^(?:<<<<<<< |=======\s*$|>>>>>>> )", path.read_text(encoding="utf-8-sig"), re.M):
                errors.append(f"{name}: unresolved merge marker")
    for field, expected in (("source_files", sources), ("test_files", tests)):
        for name in sorted(set(expected) | set(owners[field])):
            count = len(owners[field][name])
            if count != 1:
                errors.append(f"{name}: {count} {field} owners: {', '.join(owners[field][name])}")
    return {"errors": sorted(set(errors)), "pages": len(pages), "sources": len(sources), "tests": len(tests),
            "scope": {"name": "Trance-0", "excluded_prefixes": list(EXCLUDED_PREFIXES),
                      "excluded_files": sorted(EXCLUDED_FILES),
                      "worklogs": ["docs/worklog/index.md", "docs/worklog/ZheyuanWu.md"]}}


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("limit must be positive")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("index", "search"):
        command = commands.add_parser(name)
        command.add_argument("--include-references", action="store_true")
        if name == "search":
            command.add_argument("query")
            command.add_argument("--limit", type=positive, default=5)
    commands.add_parser("check")
    args = parser.parse_args()
    files = inventory(ROOT)
    if args.command == "check":
        result = check(ROOT, files)
    else:
        result = records(ROOT, files, args.include_references)
        if args.command == "search":
            result = search(result, args.query, args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(args.command == "check" and bool(result["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
