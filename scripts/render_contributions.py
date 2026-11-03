"""Render the activity card and update the README block.

Uses CONTRIBUTIONS_TOKEN when set so private pushes, merges, and counts are
included. Otherwise it renders from public activity.
"""

import html
import json
import math
import os
import struct
import urllib.parse
import urllib.request
import zlib

LOGIN = "0x-minato"
ROOT = os.path.join(os.path.dirname(__file__), "..")
README = os.path.join(ROOT, "README.md")
SVG_OUT = os.path.join(ROOT, "assets", "activity.svg")
PNG_OUT = os.path.join(ROOT, "assets", "activity.png")
START = "<!-- activity:start -->"
END = "<!-- activity:end -->"
SKIP_REPOS = {f"{LOGIN}/{LOGIN}"}

BG = (13, 17, 23, 255)
PANEL = (22, 27, 34, 255)
BORDER = (48, 54, 61, 255)
TEXT = (230, 237, 243, 255)
MUTED = (139, 148, 158, 255)
GREEN = (63, 185, 80, 255)
GREEN_FILL = (63, 185, 80, 95)
PURPLE = (163, 113, 247, 255)
BLUE = (124, 156, 255, 255)
TRACK = (33, 38, 45, 255)

FONT = {
    " ": ["00000"] * 7,
    "%": ["11001", "11010", "00100", "01000", "10110", "00110", "00000"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    "/": ["00001", "00010", "00100", "01000", "10000", "00000", "00000"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
}


def request(url, token=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def short_repo(full_name):
    return full_name.split("/", 1)[-1].replace("---", "-")


def collect(token):
    if token:
        events = request("https://api.github.com/user/events?per_page=80", token)
    else:
        events = request(f"https://api.github.com/users/{LOGIN}/events/public?per_page=80")

    push_counts = {}
    push_order = []
    for event in events:
        if event.get("type") != "PushEvent":
            continue
        name = event["repo"]["name"]
        if name in SKIP_REPOS:
            continue
        if name not in push_counts:
            push_order.append(name)
            push_counts[name] = 0
        push_counts[name] += 1

    pushed = [(name, push_counts[name]) for name in push_order[:3]]
    if len(pushed) < 3:
        repos = request(f"https://api.github.com/users/{LOGIN}/repos?sort=pushed&per_page=10", token)
        for repo in repos:
            full = repo["full_name"]
            if full in SKIP_REPOS or any(r == full for r, _ in pushed):
                continue
            pushed.append((full, 1))
            if len(pushed) == 3:
                break

    query = urllib.parse.quote(f"author:{LOGIN} type:pr is:merged")
    search = request(
        f"https://api.github.com/search/issues?q={query}&sort=updated&order=desc&per_page=8",
        token,
    )
    merged = []
    for item in search.get("items", []):
        repo_url = item.get("repository_url", "")
        repo_name = "/".join(repo_url.rsplit("/", 2)[-2:]) if "/" in repo_url else ""
        merged.append((repo_name, item["title"], item["html_url"]))
        if len(merged) == 3:
            break

    # Mix across the screenshot's four axes: commits, pull requests, review, issues.
    # Public values come from the GitHub activity overview when no token is present.
    mix = {"commits": 47, "prs": 46, "review": 7, "issues": 0}
    if token:
        graphql = """
        query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              totalCommitContributions
              totalPullRequestContributions
              totalPullRequestReviewContributions
              totalIssueContributions
            }
          }
        }
        """
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": graphql, "variables": {"login": LOGIN}}).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "profile-readme",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.load(response)["data"]["user"]["contributionsCollection"]
            raw = {
                "commits": data["totalCommitContributions"],
                "prs": data["totalPullRequestContributions"],
                "review": data["totalPullRequestReviewContributions"],
                "issues": data["totalIssueContributions"],
            }
            total = sum(raw.values()) or 1
            mix = {key: round(val * 100 / total) for key, val in raw.items()}
        except Exception:
            pass

    return pushed, merged, mix, bool(token)


def radar_points(cx, cy, radius, mix):
    # Left = commits, bottom = PRs, top = code review, right = issues (matches GitHub's axes).
    def scale(pct):
        if pct <= 0:
            return 6
        return max(14, round(radius * (pct / 60.0) ** 0.85))

    left = (cx - min(radius, scale(mix["commits"])), cy)
    top = (cx, cy - min(radius, scale(mix["review"])))
    right = (cx + min(radius, scale(mix["issues"])), cy)
    bottom = (cx, cy + min(radius, scale(mix["prs"])))
    return left, top, right, bottom


def render_svg(pushed, merged, mix, private):
    width, height = 840, 290
    cx, cy, radius = 670, 158, 78
    left, top, right, bottom = radar_points(cx, cy, radius, mix)
    poly = f"{left[0]},{left[1]} {top[0]},{top[1]} {right[0]},{right[1]} {bottom[0]},{bottom[1]}"
    scope = "PUBLIC + PRIVATE" if private else "PUBLIC"

    max_push = max((count for _, count in pushed), default=1)
    push_rows = []
    for index, (full, count) in enumerate(pushed):
        y = 78 + index * 28
        name = html.escape(short_repo(full))
        bar_w = max(36, round(150 * (count / max_push)))
        unit = "push" if count == 1 else "pushes"
        push_rows.append(
            f'<circle cx="34" cy="{y - 4}" r="4" fill="#3FB950"/>'
            f'<text x="48" y="{y}" fill="#E6EDF3" font-size="13" font-weight="600">{name}</text>'
            f'<text x="210" y="{y}" fill="#8B949E" font-size="12">{count} {unit}</text>'
            f'<rect x="280" y="{y - 9}" width="150" height="8" rx="4" fill="#21262D"/>'
            f'<rect x="280" y="{y - 9}" width="{bar_w}" height="8" rx="4" fill="#3FB950"/>'
        )

    merge_rows = []
    for index, (repo_name, title, _) in enumerate(merged[:2]):
        y = 204 + index * 30
        short = short_repo(repo_name) if repo_name else ""
        shown = title if len(title) <= 34 else title[:31] + "..."
        label = html.escape(f"{short} · {shown}" if short else shown)
        merge_rows.append(
            f'<circle cx="34" cy="{y - 4}" r="4" fill="#A371F7"/>'
            f'<text x="48" y="{y}" fill="#E6EDF3" font-size="13">{label}</text>'
            f'<rect x="372" y="{y - 13}" width="58" height="18" rx="9" fill="#271B3A"/>'
            f'<text x="401" y="{y - 1}" text-anchor="middle" fill="#D2A8FF" font-size="11" font-weight="600">merged</text>'
        )

    dots = "".join(
        f'<circle cx="{x}" cy="{y}" r="4.5" fill="#E6EDF3" stroke="#3FB950" stroke-width="2"/>'
        for x, y in (left, top, right, bottom)
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none">
  <style>
    text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; }}
  </style>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="14" fill="#0D1117" stroke="#30363D"/>
  <line x1="472" y1="24" x2="472" y2="{height - 24}" stroke="#21262D"/>

  <text x="28" y="34" fill="#8B949E" font-size="11" font-weight="600" letter-spacing="1.2">RECENT PUSHES</text>
  <text x="430" y="34" text-anchor="end" fill="#7C9CFF" font-size="11" font-weight="600" letter-spacing="1">{scope}</text>
  {"".join(push_rows)}

  <text x="28" y="172" fill="#8B949E" font-size="11" font-weight="600" letter-spacing="1.2">RECENT MERGES</text>
  {"".join(merge_rows)}

  <text x="500" y="34" fill="#8B949E" font-size="11" font-weight="600" letter-spacing="1.2">ACTIVITY MIX</text>
  <line x1="{cx - radius}" y1="{cy}" x2="{cx + radius}" y2="{cy}" stroke="#3FB950" stroke-opacity="0.45" stroke-width="1.5"/>
  <line x1="{cx}" y1="{cy - radius}" x2="{cx}" y2="{cy + radius}" stroke="#3FB950" stroke-opacity="0.45" stroke-width="1.5"/>
  <polygon points="{poly}" fill="#3FB950" fill-opacity="0.28" stroke="#3FB950" stroke-width="2"/>
  {dots}

  <text x="{cx}" y="{cy - radius - 22}" text-anchor="middle" fill="#E6EDF3" font-size="12" font-weight="600">{mix["review"]}%</text>
  <text x="{cx}" y="{cy - radius - 8}" text-anchor="middle" fill="#8B949E" font-size="11">Code review</text>

  <text x="{cx}" y="{cy + radius + 18}" text-anchor="middle" fill="#E6EDF3" font-size="12" font-weight="600">{mix["prs"]}%</text>
  <text x="{cx}" y="{cy + radius + 32}" text-anchor="middle" fill="#8B949E" font-size="11">Pull requests</text>

  <text x="{cx - radius - 10}" y="{cy - 4}" text-anchor="end" fill="#E6EDF3" font-size="12" font-weight="600">{mix["commits"]}%</text>
  <text x="{cx - radius - 10}" y="{cy + 11}" text-anchor="end" fill="#8B949E" font-size="11">Commits</text>

  <text x="{cx + radius + 10}" y="{cy + 4}" fill="#8B949E" font-size="11">Issues</text>
</svg>
"""
    os.makedirs(os.path.dirname(SVG_OUT), exist_ok=True)
    with open(SVG_OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(svg)


def blend(dst, src):
    sr, sg, sb, sa = src
    if sa >= 255:
        return (sr, sg, sb, 255)
    dr, dg, db, _ = dst
    alpha = sa / 255.0
    return (
        round(sr * alpha + dr * (1 - alpha)),
        round(sg * alpha + dg * (1 - alpha)),
        round(sb * alpha + db * (1 - alpha)),
        255,
    )


def draw_text(pixels, text, x, y, scale, color):
    cursor = x
    for ch in text.upper():
        glyph = FONT.get(ch, FONT[" "])
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit != "1":
                    continue
                for sy in range(scale):
                    for sx in range(scale):
                        px = cursor + col * scale + sx
                        py = y + row * scale + sy
                        if 0 <= py < len(pixels) and 0 <= px < len(pixels[0]):
                            pixels[py][px] = color
        cursor += 6 * scale
    return cursor


def draw_line(pixels, x0, y0, x1, y1, color, thickness=1):
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        x = round(x0 + (x1 - x0) * i / steps)
        y = round(y0 + (y1 - y0) * i / steps)
        for dy in range(-thickness // 2, thickness // 2 + 1):
            for dx in range(-thickness // 2, thickness // 2 + 1):
                py, px = y + dy, x + dx
                if 0 <= py < len(pixels) and 0 <= px < len(pixels[0]):
                    pixels[py][px] = blend(pixels[py][px], color)


def fill_polygon(pixels, pts, color):
    ys = [p[1] for p in pts]
    for y in range(max(0, min(ys)), min(len(pixels), max(ys) + 1)):
        xs = []
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            if y1 == y2:
                continue
            if min(y1, y2) <= y < max(y1, y2):
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            for x in range(max(0, round(xs[i])), min(len(pixels[0]), round(xs[i + 1]) + 1)):
                pixels[y][x] = blend(pixels[y][x], color)


def fill_circle(pixels, cx, cy, r, color):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r and 0 <= y < len(pixels) and 0 <= x < len(pixels[0]):
                pixels[y][x] = color


def fill_rect(pixels, x, y, w, h, color):
    for py in range(max(0, y), min(len(pixels), y + h)):
        for px in range(max(0, x), min(len(pixels[0]), x + w)):
            pixels[py][px] = color


def render_png(pushed, merged, mix, private):
    width, height = 840, 290
    pixels = [[BG for _ in range(width)] for _ in range(height)]
    for x in range(width):
        pixels[0][x] = BORDER
        pixels[height - 1][x] = BORDER
    for y in range(height):
        pixels[y][0] = BORDER
        pixels[y][width - 1] = BORDER
    for y in range(24, height - 24):
        pixels[y][472] = TRACK

    draw_text(pixels, "RECENT PUSHES", 28, 24, 2, MUTED)
    scope = "PUBLIC + PRIVATE" if private else "PUBLIC"
    draw_text(pixels, scope, 430 - len(scope) * 12, 24, 2, BLUE)

    max_push = max((count for _, count in pushed), default=1)
    for index, (full, count) in enumerate(pushed):
        y = 66 + index * 28
        fill_circle(pixels, 34, y + 6, 4, GREEN)
        draw_text(pixels, short_repo(full)[:14], 48, y, 2, TEXT)
        fill_rect(pixels, 260, y + 2, 170, 10, TRACK)
        bar_w = max(36, round(170 * (count / max_push)))
        fill_rect(pixels, 260, y + 2, bar_w, 10, GREEN)

    draw_text(pixels, "RECENT MERGES", 28, 162, 2, MUTED)
    for index, (repo_name, title, _) in enumerate(merged[:2]):
        y = 194 + index * 32
        fill_circle(pixels, 34, y + 6, 4, PURPLE)
        short = short_repo(repo_name) if repo_name else ""
        line = f"{short} / {title}" if short else title
        draw_text(pixels, line[:24], 48, y, 2, TEXT)
        fill_rect(pixels, 366, y - 2, 64, 18, (39, 27, 58, 255))
        draw_text(pixels, "MERGED", 374, y + 4, 1, PURPLE)

    draw_text(pixels, "ACTIVITY MIX", 500, 24, 2, MUTED)
    cx, cy, radius = 670, 158, 76
    left, top, right, bottom = radar_points(cx, cy, radius, mix)
    fill_polygon(pixels, [left, top, right, bottom], GREEN_FILL)
    draw_line(pixels, cx - radius, cy, cx + radius, cy, (63, 185, 80, 120), 1)
    draw_line(pixels, cx, cy - radius, cx, cy + radius, (63, 185, 80, 120), 1)
    for a, b in ((left, top), (top, right), (right, bottom), (bottom, left)):
        draw_line(pixels, a[0], a[1], b[0], b[1], GREEN, 2)
    for pt in (left, top, right, bottom):
        fill_circle(pixels, pt[0], pt[1], 4, TEXT)

    draw_text(pixels, f"{mix['review']}% REVIEW", cx - 30, cy - radius - 18, 1, TEXT)
    draw_text(pixels, f"{mix['prs']}% PRS", cx - 22, cy + radius + 12, 1, TEXT)
    draw_text(pixels, f"{mix['commits']}%", cx - radius - 34, cy - 8, 2, TEXT)
    draw_text(pixels, "COMMITS", cx - radius - 46, cy + 10, 1, MUTED)
    draw_text(pixels, "ISSUES", cx + radius + 8, cy - 3, 1, MUTED)

    raw = bytearray()
    for row in pixels:
        raw.append(0)
        for r, g, b, a in row:
            raw.extend((r, g, b, a))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    with open(PNG_OUT, "wb") as handle:
        handle.write(png)


def readme_block(pushed, merged):
    push_links = " · ".join(
        f'<a href="https://github.com/{full}">{short_repo(full)}</a>' for full, _ in pushed
    )
    merge_links = " · ".join(
        f'<a href="{url}">{html.escape(title)}</a>' for _, title, url in merged[:2]
    )
    return "\n".join(
        [
            '<div align="center">',
            "",
            '<img src="assets/activity.svg" alt="Recent GitHub activity" width="840">',
            "",
            f"pushed → {push_links}<br>",
            f"merged → {merge_links}",
            "",
            "</div>",
        ]
    )


def main():
    token = os.environ.get("CONTRIBUTIONS_TOKEN", "").strip() or None
    pushed, merged, mix, private = collect(token)
    render_svg(pushed, merged, mix, private)
    render_png(pushed, merged, mix, private)
    block = readme_block(pushed, merged)
    with open(README, encoding="utf-8") as handle:
        text = handle.read()
    before, rest = text.split(START, 1)
    _, after = rest.split(END, 1)
    updated = f"{before}{START}\n{block}\n{END}{after}"
    with open(README, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
    print("rendered activity card", "private" if private else "public")


if __name__ == "__main__":
    main()
