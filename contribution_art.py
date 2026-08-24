#!/usr/bin/env python3
"""contribution_art.py

Paints pixel art onto a GitHub contribution graph. Art is described as a
JSON grid of shade levels (0-4), calibrated against the account's real
contribution data, and generated as backdated commits pushed to a fresh,
disposable GitHub repo created just for this — never against a repo you
actually use. `--clean` deletes that disposable repo outright, which is
the only verified way to make already-counted contributions disappear
from the graph (see CLAUDE.md).

Inspired by gitfiti (https://github.com/gelstudios/gitfiti/blob/main/gitfiti.py).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta

# Default year to paint on the contribution graph; overridden by --year or
# the JSON file's own "year" key.
TARGET_YEAR = 2025

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".art_state.json")

# 5x7 pixel font: each integer's bits encode which pixels are on. Only used
# by the offline --from-text helper; the primary art input is a JSON grid.
FONT = {
    "A": [0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
    "B": [0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110],
    "C": [0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110],
    "D": [0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110],
    "E": [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111],
    "F": [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000],
    "G": [0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110],
    "H": [0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
    "I": [0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
    "J": [0b00111, 0b00010, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100],
    "K": [0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001],
    "L": [0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111],
    "M": [0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001],
    "N": [0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001],
    "O": [0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
    "P": [0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000],
    "Q": [0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101],
    "R": [0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001],
    "S": [0b01110, 0b10001, 0b10000, 0b01110, 0b00001, 0b10001, 0b01110],
    "T": [0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100],
    "U": [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
    "V": [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100],
    "W": [0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b11011, 0b10001],
    "X": [0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001],
    "Y": [0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100],
    "Z": [0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111],
    " ": [0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000],
}

LETTER_WIDTH = 5
LETTER_SPACING = 1

# GitHub's contribution graph is 53 columns wide.
GRAPH_WIDTH = 53


# --- rendering -----------------------------------------------------------

def render_text(text):
    # Convert to uppercase to match FONT keys; returns a 7 x N bool grid.
    text = text.upper()
    grid = [[] for _ in range(7)]
    for i, char in enumerate(text):
        if char not in FONT:
            char = " "
        pattern = FONT[char]
        for row in range(7):
            for col in range(LETTER_WIDTH):
                bit = (pattern[row] >> (LETTER_WIDTH - 1 - col)) & 1
                grid[row].append(bool(bit))
        if i < len(text) - 1:
            for row in range(7):
                for _ in range(LETTER_SPACING):
                    grid[row].append(False)
    return grid


def preview(level_grid):
    # Print grid with day-of-week labels; "." is off, "1"-"4" is shade level.
    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    for row in range(7):
        label = days[row]
        line = " ".join("." if cell == 0 else str(cell) for cell in level_grid[row])
        print(f"{label} {line}")


def get_start_sunday(year):
    # The Sunday on or *after* Jan 1, not before: GitHub's per-year graph
    # only shows days within that year, so a start date before Jan 1 (e.g.
    # 2025's Jan 1 is a Wednesday, putting the naive start at Dec 29 2024)
    # pushes column 0 partly into the prior year and off the visible graph,
    # clipping the top-left of the art. Starting on/after Jan 1 keeps every
    # column inside the target year.
    jan1 = date(year, 1, 1)
    weekday = jan1.isoweekday() % 7
    if weekday == 0:
        return jan1
    return jan1 + timedelta(days=7 - weekday)


def date_for_pixel(row, col, start_sunday):
    return start_sunday + timedelta(days=col * 7 + row)


# --- JSON art format -------------------------------------------------------

def load_art_json(path):
    with open(path) as f:
        data = json.load(f)
    grid = data.get("grid")
    year = data.get("year", TARGET_YEAR)
    if not isinstance(grid, list) or len(grid) != 7:
        raise ValueError("'grid' must have exactly 7 rows (Sun..Sat)")
    width = len(grid[0]) if grid else 0
    if width == 0 or width > GRAPH_WIDTH:
        raise ValueError(f"grid rows must be 1-{GRAPH_WIDTH} columns wide, got {width}")
    level_grid = []
    for i, row in enumerate(grid):
        if not isinstance(row, str) or len(row) != width:
            raise ValueError(f"row {i} must be a string of length {width}, matching row 0")
        if any(c not in "01234" for c in row):
            raise ValueError(f"row {i} contains characters outside 0-4: {row!r}")
        level_grid.append([int(c) for c in row])
    return level_grid, year


def write_art_json(path, level_grid, year):
    rows = ["".join(str(cell) for cell in row) for row in level_grid]
    with open(path, "w") as f:
        json.dump({"year": year, "grid": rows}, f, indent=2)
        f.write("\n")


# --- shading calibration ---------------------------------------------------

CONTRIBUTIONS_QUERY = """
query($from: DateTime!, $to: DateTime!) {
  viewer {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch_contribution_days(year):
    # Pull this account's real per-day contribution counts for `year` via
    # the GitHub GraphQL API, authenticated through the logged-in gh CLI.
    from_str = f"{year}-01-01T00:00:00Z"
    to_str = f"{year}-12-31T23:59:59Z"
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={CONTRIBUTIONS_QUERY}",
         "-F", f"from={from_str}", "-F", f"to={to_str}"],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to fetch contribution data via gh: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    weeks = data["data"]["viewer"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    counts = {}
    for week in weeks:
        for day in week["contributionDays"]:
            counts[day["date"]] = day["contributionCount"]
    return counts


def commits_for_level(existing_max):
    # GitHub buckets shade levels by quartiles of a year's nonzero day
    # counts, recomputed after our commits land. Our added counts need to
    # dominate any existing activity — not just barely exceed it — so even
    # the lightest art level (1) reads as clearly darker than the busiest
    # real day, with levels spread by clear multiplicative gaps so they
    # sort into distinct buckets in order. This is a best-effort
    # calibration, not a guaranteed replica of GitHub's undisclosed
    # bucketing algorithm.
    base = max((existing_max + 1) * 2, 10)
    step = base
    return {1: base, 2: base + step, 3: base + 2 * step, 4: base + 3 * step}


# --- commit generation -------------------------------------------------

def make_commit(target_date, repo_path, count):
    if count <= 0:
        return
    env = os.environ.copy()
    date_str = target_date.isoformat() + "T12:00:00"
    env["GIT_AUTHOR_DATE"] = date_str
    env["GIT_COMMITTER_DATE"] = date_str
    for i in range(count):
        with open(os.path.join(repo_path, "commit.txt"), "w") as f:
            f.write(f"{target_date} commit {i}\n")
        subprocess.run(["git", "add", "commit.txt"], cwd=repo_path, env=env, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"art: {target_date} #{i}"],
                        cwd=repo_path, env=env, capture_output=True)


def generate_commits(level_grid, repo_path, year, level_commits):
    start_sunday = get_start_sunday(year)
    total_pixels = sum(1 for row in level_grid for cell in row if cell > 0)
    done = 0
    for col in range(len(level_grid[0])):
        for row in range(7):
            level = level_grid[row][col]
            if level > 0:
                target_date = date_for_pixel(row, col, start_sunday)
                make_commit(target_date, repo_path, level_commits[level])
                done += 1
                print(f"\r  Progress: {done}/{total_pixels} pixels", end="", flush=True)
    print()


# --- canvas repo lifecycle -------------------------------------------------

def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


def confirm(prompt, assume_yes):
    if assume_yes:
        return True
    reply = input(f"{prompt} [y/N] ").strip().lower()
    return reply == "y"


def gh_login():
    result = subprocess.run(["gh", "api", "user", "-q", ".login"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("Could not determine GitHub login via gh; run `gh auth login` first.")
    return result.stdout.strip()


def create_canvas_repo(name, private, workdir):
    visibility = "--private" if private else "--public"
    result = subprocess.run(
        ["gh", "repo", "create", name, visibility, "--clone"],
        cwd=workdir, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gh repo create failed: {result.stderr.strip()}")
    return os.path.join(workdir, name)


def delete_canvas_repo(owner, name):
    result = subprocess.run(
        ["gh", "repo", "delete", f"{owner}/{name}", "--yes"],
        capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"gh repo delete failed: {result.stderr.strip()}")


def current_branch(repo_path):
    result = subprocess.run(["git", "branch", "--show-current"],
                             cwd=repo_path, capture_output=True, text=True)
    return result.stdout.strip() or "main"


# --- commands ---------------------------------------------------------

def cmd_generate(args):
    level_grid, year = load_art_json(args.art_json)
    if args.year:
        year = args.year

    print(f"\nFetching your current {year} contribution data...")
    counts = fetch_contribution_days(year)
    existing_max = max(counts.values(), default=0)
    level_commits = commits_for_level(existing_max)
    print(f"  Existing max daily contributions in {year}: {existing_max}")
    print("  Commit counts per shade level:")
    for lvl in range(1, 5):
        print(f"    level {lvl}: {level_commits[lvl]} commits/day")

    total_pixels = sum(1 for row in level_grid for c in row if c > 0)
    total_commits = sum(level_commits[c] for row in level_grid for c in row if c > 0)
    print(f"\nPreview:\n")
    preview(level_grid)
    print(f"\nTotal pixels: {total_pixels}")
    print(f"Total commits: {total_commits}")

    owner = gh_login()
    repo_name = args.repo_name or f"contribution-art-canvas-{int(time.time())}"
    visibility = "private" if args.private else "public"

    print(f"\nAbout to create a new {visibility} GitHub repo: {owner}/{repo_name}")
    print(f"and push {total_commits} backdated commits to it for year {year}.")
    if not confirm("Proceed?", args.yes):
        print("Aborted.")
        return

    workdir = tempfile.mkdtemp(prefix="contribution-art-")
    repo_path = create_canvas_repo(repo_name, args.private, workdir)

    print(f"\nGenerating commits for {year}...")
    generate_commits(level_grid, repo_path, year, level_commits)

    branch = current_branch(repo_path)
    result = subprocess.run(["git", "push", "origin", branch],
                             cwd=repo_path, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git push failed: {result.stderr.strip()}")

    save_state({"repo_name": repo_name, "owner": owner, "workdir": workdir})
    print(f"\nDone! https://github.com/{owner}/{repo_name}")
    print("The contribution graph can take a few minutes to update.")
    print("Run with --clean when you're ready to remove this canvas repo.")


def cmd_clean(args):
    state = load_state()
    repo_name = args.repo_name or (state and state.get("repo_name"))
    if not repo_name:
        print("\nNo canvas repo on record (.art_state.json not found).")
        print("Pass --repo-name to target one explicitly.")
        return
    owner = (state and state.get("owner")) or gh_login()

    print(f"\nAbout to permanently delete GitHub repo: {owner}/{repo_name}")
    print("This destroys the repo (and its history) and cannot be undone.")
    if not confirm("Proceed?", args.yes):
        print("Aborted.")
        return

    delete_canvas_repo(owner, repo_name)
    print(f"  Deleted {owner}/{repo_name}.")

    if state:
        workdir = state.get("workdir")
        if workdir and os.path.exists(workdir):
            shutil.rmtree(workdir, ignore_errors=True)
    clear_state()
    print("  Local state cleared. Run --generate to make a fresh canvas repo.")


def cmd_from_text(args):
    bool_grid = render_text(args.from_text)
    if len(bool_grid[0]) > GRAPH_WIDTH:
        raise ValueError(f"'{args.from_text}' renders wider than {GRAPH_WIDTH} columns")
    level_grid = [[args.level if cell else 0 for cell in row] for row in bool_grid]
    year = args.year or TARGET_YEAR
    write_art_json(args.output, level_grid, year)
    print(f"\nWrote {args.output}\n")
    preview(level_grid)


# --- entry point -----------------------------------------------------------

def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Paint pixel art onto a GitHub contribution graph via a disposable repo.")
    parser.add_argument("art_json", nargs="?",
                         help="Path to a JSON art file (7-row grid of 0-4 intensity levels)")
    parser.add_argument("--generate", action="store_true",
                         help="Create a disposable canvas repo and push the backdated commits")
    parser.add_argument("--clean", action="store_true",
                         help="Delete the canvas repo created by the last --generate")
    parser.add_argument("--from-text", metavar="TEXT",
                         help="Render TEXT with the built-in font and write it as a JSON art file, then exit")
    parser.add_argument("--level", type=int, default=4, choices=[1, 2, 3, 4],
                         help="Shade level to use for --from-text pixels (default: 4)")
    parser.add_argument("-o", "--output", default="art.json",
                         help="Output path for --from-text (default: art.json)")
    parser.add_argument("--repo-name", help="Canvas repo name (default: auto-generated)")
    parser.add_argument("--private", action="store_true", help="Create the canvas repo as private")
    parser.add_argument("--year", type=int, help="Override the year from the JSON file")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation prompts")
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.from_text:
        cmd_from_text(args)
        return

    if args.clean:
        cmd_clean(args)
        return

    if not args.art_json:
        parser.error("ART_JSON is required unless --clean or --from-text is used")

    if args.generate:
        cmd_generate(args)
        return

    # No action flag: preview only, no git/GitHub calls.
    level_grid, year = load_art_json(args.art_json)
    print(f"\nPreview for '{args.art_json}' (year {year}):\n")
    preview(level_grid)
    total_pixels = sum(1 for row in level_grid for c in row if c > 0)
    print(f"\nTotal pixels: {total_pixels}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
