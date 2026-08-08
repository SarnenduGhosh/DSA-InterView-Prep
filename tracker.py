#!/usr/bin/env python3
"""Scan Java solutions and update progress.json plus PROGRESS.md."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROGRESS_JSON = ROOT / "progress.json"
PROGRESS_MD = ROOT / "PROGRESS.md"
DATE_FORMAT = "%d-%m-%Y %H:%M:%S"
DEFAULT_TARGET_TOTAL = 220

CATEGORIES = [
    "arrays",
    "strings",
    "hashing",
    "two-pointers",
    "sliding-window",
    "linked-list",
    "stack",
    "queue",
    "binary-search",
    "recursion",
    "trees",
    "bst",
    "heap",
    "intervals",
    "backtracking",
    "greedy",
    "graphs",
    "dynamic-programming",
    "tries",
]

SKIP_DIRS = {"build", "dist", "out", "target"}
ACRONYMS = {"bfs", "bst", "dfs", "lca"}
TAG_PATTERN = re.compile(
    r"^\s*(?://|/\*+|\*)?\s*(?:technique|techniques|pattern|patterns)\s*:\s*(.+?)\s*(?:\*/)?\s*$",
    re.IGNORECASE,
)


def load_existing_progress() -> dict:
    if not PROGRESS_JSON.exists():
        return {}

    with PROGRESS_JSON.open("r", encoding="utf-8") as progress_file:
        return json.load(progress_file)


def existing_completion_times(existing: dict) -> dict[str, str]:
    return {
        problem["file"]: problem["completed_at"]
        for problem in existing.get("problems", [])
        if "file" in problem and "completed_at" in problem
    }


def display_name(value: str) -> str:
    words = re.sub(r"(?<!^)(?=[A-Z])", " ", value)
    words = words.replace("_", " ").replace("-", " ")
    words = re.sub(r"\s+", " ", words).strip()
    if not words:
        return "Uncategorized"

    return " ".join(
        word.upper() if word.lower() in ACRONYMS else word.capitalize()
        for word in words.split()
    )


def split_techniques(raw_value: str) -> list[str]:
    techniques = re.split(r"[,|/]", raw_value)
    return [display_name(technique) for technique in techniques if technique.strip()]


def techniques_from_file(java_file: Path) -> list[str]:
    try:
        lines = java_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []

    for line in lines[:80]:
        match = TAG_PATTERN.match(line)
        if match:
            return split_techniques(match.group(1))

    return []


def infer_techniques(category: str, java_file: Path) -> list[str]:
    tagged_techniques = techniques_from_file(java_file)
    if tagged_techniques:
        return tagged_techniques

    relative_to_category = java_file.relative_to(ROOT / category)
    if len(relative_to_category.parts) > 1:
        return [display_name(relative_to_category.parts[0])]

    file_slug = java_file.stem.lower()
    if "sort" in file_slug:
        return ["Sorting"]

    return ["Uncategorized"]


def should_skip(java_file: Path) -> bool:
    relative_parts = java_file.relative_to(ROOT).parts
    return any(part.startswith(".") or part in SKIP_DIRS for part in relative_parts)


def find_java_files() -> list[tuple[str, Path]]:
    java_files: list[tuple[str, Path]] = []

    for category in CATEGORIES:
        category_path = ROOT / category
        if not category_path.exists():
            continue

        for java_file in sorted(category_path.rglob("*.java")):
            if not should_skip(java_file):
                java_files.append((category, java_file))

    return java_files


def build_progress(target_total: int) -> dict:
    existing = load_existing_progress()
    existing_times = existing_completion_times(existing)
    generated_at = datetime.now().strftime(DATE_FORMAT)

    problems = []
    for category, java_file in find_java_files():
        relative_file = java_file.relative_to(ROOT).as_posix()
        completed_at = existing_times.get(relative_file, generated_at)
        techniques = infer_techniques(category, java_file)

        problems.append(
            {
                "category": category,
                "category_name": display_name(category),
                "techniques": techniques,
                "problem": display_name(java_file.stem),
                "file": relative_file,
                "status": "completed",
                "completed_at": completed_at,
            }
        )

    category_counts = Counter(problem["category"] for problem in problems)
    technique_counts = Counter(
        technique for problem in problems for technique in problem["techniques"]
    )
    completed = len(problems)
    percent = round((completed / target_total) * 100, 2) if target_total else 0

    return {
        "generated_at": generated_at,
        "target_total": target_total,
        "totals": {
            "completed": completed,
            "remaining": max(target_total - completed, 0),
            "percent": percent,
        },
        "categories": [
            {
                "category": category,
                "category_name": display_name(category),
                "completed": category_counts.get(category, 0),
            }
            for category in CATEGORIES
        ],
        "techniques": [
            {"technique": technique, "completed": count}
            for technique, count in sorted(technique_counts.items())
        ],
        "problems": sorted(
            problems,
            key=lambda problem: (
                CATEGORIES.index(problem["category"]),
                problem["file"],
            ),
        ),
    }


def progress_bar(percent: float, width: int = 20) -> str:
    filled = round((percent / 100) * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def render_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def render_markdown(progress: dict) -> str:
    totals = progress["totals"]
    completed = totals["completed"]
    target_total = progress["target_total"]
    percent = totals["percent"]

    lines = [
        "# DSA Progress Tracker",
        "",
        f"Generated: {progress['generated_at']}",
        "",
        "## Overall Progress",
        "",
        f"Completed: {completed} / {target_total}",
        "",
        f"{progress_bar(percent)} {percent}%",
        "",
        "## Category Progress",
        "",
    ]

    category_rows = [
        [category["category_name"], str(category["completed"])]
        for category in progress["categories"]
    ]
    lines.extend(render_table(["Category", "Completed"], category_rows))

    lines.extend(["", "## Technique Progress", ""])
    if progress["techniques"]:
        technique_rows = [
            [technique["technique"], str(technique["completed"])]
            for technique in progress["techniques"]
        ]
        lines.extend(render_table(["Technique", "Completed"], technique_rows))
    else:
        lines.append("No Java problems detected yet.")

    lines.extend(["", "## Completed Problems", ""])
    if progress["problems"]:
        problem_rows = [
            [
                problem["category_name"],
                ", ".join(problem["techniques"]),
                f"[{problem['problem']}](./{problem['file']})",
                problem["completed_at"],
            ]
            for problem in progress["problems"]
        ]
        lines.extend(
            render_table(
                ["Category", "Technique", "Problem", "Completed At"], problem_rows
            )
        )
    else:
        lines.append("No Java problems detected yet.")

    lines.extend(
        [
            "",
            "## Tracking Rules",
            "",
            "- Put Java solution files inside the README topic folders.",
            "- Technique is detected from a tag like `// Technique: Sorting`.",
            "- If there is no tag, the first subfolder is used as the technique.",
            "- First completed time stays fixed once saved in `progress.json`.",
            "",
            "## Update Command",
            "",
            "```bash",
            "python3 tracker.py",
            "```",
            "",
        ]
    )

    return "\n".join(lines)


def save_progress(progress: dict) -> None:
    PROGRESS_JSON.write_text(
        json.dumps(progress, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    PROGRESS_MD.write_text(render_markdown(progress), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update progress.json and PROGRESS.md from Java solutions."
    )
    parser.add_argument(
        "--target",
        type=int,
        default=None,
        help="Target number of problems. Defaults to 220 or existing progress.json.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    existing = load_existing_progress()
    target_total = args.target or existing.get("target_total") or DEFAULT_TARGET_TOTAL
    progress = build_progress(target_total)
    save_progress(progress)
    print(
        f"Updated progress: {progress['totals']['completed']} / "
        f"{progress['target_total']} completed"
    )


if __name__ == "__main__":
    main()
