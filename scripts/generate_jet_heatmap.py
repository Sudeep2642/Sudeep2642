#!/usr/bin/env python3
"""
Generates a GitHub contribution heatmap SVG rendered with a "jet" color scale
(dark blue -> cyan -> yellow -> red, low -> high activity), instead of GitHub's
default green scale.

Requires:
    - env var GITHUB_TOKEN (or PAT_TOKEN) with at least `read:user` scope
    - env var GITHUB_USERNAME (defaults to the repo owner in Actions)

Outputs:
    dist/light.svg   - jet heatmap on a light background
    dist/dark.svg    - jet heatmap on a dark background
    dist/github-jet.svg - alias of dark.svg, for direct <img> embeds
"""

import os
import sys
import json
import urllib.request

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def fetch_contributions(username: str, token: str) -> dict:
    req = urllib.request.Request(
        GITHUB_GRAPHQL_URL,
        data=json.dumps({"query": QUERY, "variables": {"login": username}}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "jet-heatmap-generator",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read().decode())

    if "errors" in payload:
        raise RuntimeError(f"GitHub GraphQL error: {payload['errors']}")

    calendar = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return calendar


def jet_color(t: float) -> str:
    """
    Approximates matplotlib's 'jet' colormap without needing matplotlib.
    t is normalized 0..1 (activity level). Returns a hex color string.
    """
    t = max(0.0, min(1.0, t))

    def clamp(v):
        return max(0.0, min(1.0, v))

    r = clamp(1.5 - abs(4 * t - 3))
    g = clamp(1.5 - abs(4 * t - 2))
    b = clamp(1.5 - abs(4 * t - 1))

    return "#{:02x}{:02x}{:02x}".format(
        int(r * 255), int(g * 255), int(b * 255)
    )


def build_svg(calendar: dict, username: str, dark: bool) -> str:
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]
    max_count = max(
        (day["contributionCount"] for week in weeks for day in week["contributionDays"]),
        default=1,
    )
    max_count = max(max_count, 1)

    cell = 11
    gap = 3
    step = cell + gap
    left_pad = 30
    top_pad = 40

    n_weeks = len(weeks)
    width = left_pad + n_weeks * step + 20
    height = top_pad + 7 * step + 30

    bg = "#0d1117" if dark else "#ffffff"
    fg = "#e6edf3" if dark else "#1f2328"
    muted = "#8b949e" if dark else "#57606a"
    empty_cell = "#161b22" if dark else "#ebedf0"

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )
    parts.append(f'<rect width="100%" height="100%" fill="{bg}" rx="10"/>')
    parts.append(
        f'<text x="{left_pad}" y="22" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
        f'font-size="14" font-weight="700" fill="{fg}">{username} — contributions (jet scale)</text>'
    )
    parts.append(
        f'<text x="{left_pad}" y="{height - 10}" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
        f'font-size="11" fill="{muted}">{total} contributions in the last year</text>'
    )

    for wi, week in enumerate(weeks):
        for di, day in enumerate(week["contributionDays"]):
            count = day["contributionCount"]
            x = left_pad + wi * step
            y = top_pad + di * step

            if count == 0:
                color = empty_cell
            else:
                t = count / max_count
                color = jet_color(t)

            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
                f'fill="{color}"><title>{day["date"]}: {count} contributions</title></rect>'
            )

    # Legend (low -> high)
    legend_x = width - 150
    legend_y = 24
    parts.append(
        f'<text x="{legend_x - 28}" y="{legend_y + 8}" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
        f'font-size="10" fill="{muted}">less</text>'
    )
    for i in range(10):
        t = i / 9
        parts.append(
            f'<rect x="{legend_x + i * 10}" y="{legend_y}" width="8" height="8" rx="1" fill="{jet_color(t)}"/>'
        )
    parts.append(
        f'<text x="{legend_x + 105}" y="{legend_y + 8}" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
        f'font-size="10" fill="{muted}">more</text>'
    )

    parts.append("</svg>")
    return "".join(parts)


def main():
    username = os.environ.get("GITHUB_USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER")
    token = os.environ.get("PAT_TOKEN") or os.environ.get("GITHUB_TOKEN")

    if not username:
        print("ERROR: set GITHUB_USERNAME (or run inside GitHub Actions).", file=sys.stderr)
        sys.exit(1)
    if not token:
        print("ERROR: set GITHUB_TOKEN or PAT_TOKEN.", file=sys.stderr)
        sys.exit(1)

    calendar = fetch_contributions(username, token)

    os.makedirs("dist", exist_ok=True)

    light_svg = build_svg(calendar, username, dark=False)
    dark_svg = build_svg(calendar, username, dark=True)

    with open("dist/light.svg", "w") as f:
        f.write(light_svg)
    with open("dist/dark.svg", "w") as f:
        f.write(dark_svg)
    # alias used directly in the README <img> tag
    with open("dist/github-jet.svg", "w") as f:
        f.write(dark_svg)

    print(f"Generated heatmap for {username}: {calendar['totalContributions']} total contributions.")


if __name__ == "__main__":
    main()
