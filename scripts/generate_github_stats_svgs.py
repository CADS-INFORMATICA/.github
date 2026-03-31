#!/usr/bin/env python3
"""Generate SVG charts for commit activity and code frequency using GitHub stats endpoints."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OWNER = "CADS-INFORMATICA"
REPO = ".github"
API_BASE = f"https://api.github.com/repos/{OWNER}/{REPO}/stats"
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"


def fetch_json(path: str, retries: int = 8) -> list:
    url = f"{API_BASE}/{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "cads-stats-chart-generator",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 202:
                    time.sleep(2 + attempt)
                    continue
                if resp.status != 200:
                    raise RuntimeError(f"Unexpected status {resp.status} for {url}")
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 202:
                time.sleep(2 + attempt)
                continue
            raise

    raise RuntimeError(f"GitHub stats endpoint still computing after {retries} attempts: {url}")


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def svg_template(title: str, subtitle: str, inner: str) -> str:
    return f"""<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"1000\" height=\"320\" role=\"img\" aria-labelledby=\"title desc\">\n  <title id=\"title\">{esc(title)}</title>\n  <desc id=\"desc\">{esc(subtitle)}</desc>\n  <defs>\n    <style>\n      .bg {{ fill: #ffffff; }}\n      .title {{ font: 600 24px -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif; fill: #24292f; }}\n      .subtitle {{ font: 400 14px -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif; fill: #57606a; }}\n      .axis {{ stroke: #d0d7de; stroke-width: 1; }}\n      .label {{ font: 400 12px -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif; fill: #57606a; }}\n      .value {{ font: 500 11px -apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif; fill: #57606a; }}\n    </style>\n  </defs>\n  <rect class=\"bg\" x=\"0\" y=\"0\" width=\"1000\" height=\"320\" rx=\"8\"/>\n  <text class=\"title\" x=\"24\" y=\"42\">{esc(title)}</text>\n  <text class=\"subtitle\" x=\"24\" y=\"64\">{esc(subtitle)}</text>\n  {inner}\n</svg>\n"""


def generate_commit_activity_svg(data: list[dict]) -> str:
    weeks = data[-52:] if len(data) > 52 else data
    chart_left = 24
    chart_top = 86
    chart_width = 952
    chart_height = 196
    bar_gap = 2
    bar_width = (chart_width - bar_gap * (len(weeks) - 1)) / max(len(weeks), 1)

    max_total = max((w.get("total", 0) for w in weeks), default=0)
    if max_total <= 0:
        max_total = 1

    bars = []
    for i, week in enumerate(weeks):
        total = int(week.get("total", 0))
        h = (total / max_total) * chart_height
        x = chart_left + i * (bar_width + bar_gap)
        y = chart_top + (chart_height - h)
        ts = int(week.get("week", 0))
        date_txt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d %b %Y") if ts else "Unknown"
        bars.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{h:.2f}" fill="#2da44e">'
            f'<title>{esc(date_txt)}: {total} commits</title></rect>'
        )

    tick_labels = []
    for idx, label in [(0, "52w"), (13, "39w"), (26, "26w"), (39, "13w"), (51, "Now")]:
        pos = chart_left + (min(idx, len(weeks) - 1) * (bar_width + bar_gap))
        tick_labels.append(f'<text class="label" x="{pos:.2f}" y="304">{label}</text>')

    max_label = f'<text class="value" x="980" y="96" text-anchor="end">max {max_total}</text>'

    inner = "\n  ".join(
        [
            f'<line class="axis" x1="{chart_left}" y1="{chart_top + chart_height}" x2="{chart_left + chart_width}" y2="{chart_top + chart_height}"/>',
            f'<line class="axis" x1="{chart_left}" y1="{chart_top}" x2="{chart_left}" y2="{chart_top + chart_height}"/>',
            *bars,
            *tick_labels,
            max_label,
        ]
    )

    return svg_template("Commit Activity", "Commits per week (last 52 weeks)", inner)


def generate_code_frequency_svg(data: list[list[int]]) -> str:
    weeks = data[-52:] if len(data) > 52 else data
    chart_left = 24
    chart_top = 86
    chart_width = 952
    chart_height = 196
    zero_y = chart_top + chart_height / 2
    bar_gap = 2
    bar_width = (chart_width - bar_gap * (len(weeks) - 1)) / max(len(weeks), 1)

    max_add = max((int(w[1]) for w in weeks), default=0)
    max_del = max((abs(int(w[2])) for w in weeks), default=0)
    max_abs = max(max_add, max_del, 1)

    bars = []
    for i, week in enumerate(weeks):
        ts, additions, deletions = int(week[0]), int(week[1]), int(week[2])
        x = chart_left + i * (bar_width + bar_gap)

        add_h = (additions / max_abs) * (chart_height / 2)
        del_h = (abs(deletions) / max_abs) * (chart_height / 2)

        date_txt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d %b %Y")

        if add_h > 0:
            bars.append(
                f'<rect x="{x:.2f}" y="{zero_y - add_h:.2f}" width="{bar_width:.2f}" height="{add_h:.2f}" fill="#2da44e">'
                f'<title>{esc(date_txt)}: +{additions} additions, {deletions} deletions</title></rect>'
            )
        if del_h > 0:
            bars.append(
                f'<rect x="{x:.2f}" y="{zero_y:.2f}" width="{bar_width:.2f}" height="{del_h:.2f}" fill="#cf222e">'
                f'<title>{esc(date_txt)}: +{additions} additions, {deletions} deletions</title></rect>'
            )

    legend = [
        '<rect x="820" y="34" width="12" height="12" fill="#2da44e"/><text class="label" x="838" y="44">Additions</text>',
        '<rect x="910" y="34" width="12" height="12" fill="#cf222e"/><text class="label" x="928" y="44">Deletions</text>',
    ]

    tick_labels = []
    for idx, label in [(0, "52w"), (13, "39w"), (26, "26w"), (39, "13w"), (51, "Now")]:
        pos = chart_left + (min(idx, len(weeks) - 1) * (bar_width + bar_gap))
        tick_labels.append(f'<text class="label" x="{pos:.2f}" y="304">{label}</text>')

    max_label = f'<text class="value" x="980" y="96" text-anchor="end">max +/- {max_abs}</text>'

    inner = "\n  ".join(
        [
            f'<line class="axis" x1="{chart_left}" y1="{zero_y}" x2="{chart_left + chart_width}" y2="{zero_y}"/>',
            f'<line class="axis" x1="{chart_left}" y1="{chart_top}" x2="{chart_left}" y2="{chart_top + chart_height}"/>',
            *bars,
            *legend,
            *tick_labels,
            max_label,
        ]
    )

    return svg_template("Code Frequency", "Additions and deletions per week (last 52 weeks)", inner)


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    commit_activity = fetch_json("commit_activity")
    code_frequency = fetch_json("code_frequency")

    (ASSETS_DIR / "commit-activity.svg").write_text(
        generate_commit_activity_svg(commit_activity), encoding="utf-8"
    )
    (ASSETS_DIR / "code-frequency.svg").write_text(
        generate_code_frequency_svg(code_frequency), encoding="utf-8"
    )

    print("Generated assets/commit-activity.svg")
    print("Generated assets/code-frequency.svg")


if __name__ == "__main__":
    main()
