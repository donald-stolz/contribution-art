#!/usr/bin/env python3
"""contribution_art.py"""
import subprocess
import os
import sys
import json
from datetime import date, timedelta

# Year to paint on the contribution graph
TARGET_YEAR = 2025
# Number of commits to create for each "on" pixel
COMMITS_PER_DAY = 15

# 5x7 pixel font: each integer's bits encode which pixels are on
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


# GitHub's contribution graph is 53 columns wide; each letter takes
# LETTER_WIDTH + LETTER_SPACING columns (minus the trailing spacing on the
# last letter), so at most 9 letters (9*5 + 8*1 = 53) will fit on one line.
def render_text(text):
    # Convert to uppercase to match FONT keys
    text = text.upper()
    grid = [[] for _ in range(7)]
    for i, char in enumerate(text):
        # Fall back to space for unknown characters
        if char not in FONT:
            char = " "
        pattern = FONT[char]
        # Extract each bit from the pattern row
        for row in range(7):
            for col in range(LETTER_WIDTH):
                bit = (pattern[row] >> (LETTER_WIDTH - 1 - col)) & 1
                grid[row].append(bool(bit))
        # Add a blank column between letters
        if i < len(text) - 1:
            for row in range(7):
                for _ in range(LETTER_SPACING):
                    grid[row].append(False)
    return grid

def preview(grid):
    # Print grid with day-of-week labels
    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    for row in range(7):
        label = days[row]
        line = " ".join("#" if cell else "." for cell in grid[row])
        print(f"{label} {line}")

def get_start_sunday(year):
    # Find the first Sunday on or before January 1
    jan1 = date(year, 1, 1)
    # isoweekday: 1=Mon..7=Sun, %7 converts Sun's 7 to 0
    weekday = jan1.isoweekday() % 7
    start_sunday = jan1 - timedelta(days=weekday)
    return start_sunday

def date_for_pixel(row, col, start_sunday):
    # Map grid position to a calendar date using Sunday-aligned start
    return start_sunday + timedelta(days=col * 7 + row)

def make_commit(target_date, repo_path, count=1):
    # Copy the current environment and override the date variables
    env = os.environ.copy()
    date_str = target_date.isoformat() + "T12:00:00"
    env["GIT_AUTHOR_DATE"] = date_str
    env["GIT_COMMITTER_DATE"] = date_str
    # Create multiple commits on this date for darker green
    for i in range(count):
        with open(os.path.join(repo_path, "commit.txt"), "w") as f:
            f.write(f"{target_date} commit {i}\n")
        subprocess.run(
            ["git", "add", "commit.txt"],
            cwd=repo_path, env=env, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"art: {target_date} #{i}"],
            cwd=repo_path, env=env, capture_output=True)

def reset_art_commits(repo_path):
    # Walk history back from HEAD to the most recent commit that isn't a
    # generated "art: " commit, then hard-reset to it, dropping the rest
    result = subprocess.run(
        ["git", "log", "--format=%H %s"],
        cwd=repo_path, capture_output=True, text=True)
    base_sha = None
    for line in result.stdout.splitlines():
        sha, _, subject = line.partition(" ")
        if not subject.startswith("art: "):
            base_sha = sha
            break
    if base_sha is None:
        print("\nNo non-art commit found to reset to. Use --clean to start over.")
        return
    subprocess.run(["git", "reset", "--hard", base_sha], cwd=repo_path, capture_output=True)
    print(f"\nReset to {base_sha[:7]} — all 'art:' commits removed.")

def generate_commits(grid, repo_path, commits_per_day):
    # Calculate the Sunday-aligned start date
    start_sunday = get_start_sunday(TARGET_YEAR)
    total_pixels = sum(cell for row in grid for cell in row)
    done = 0
    # Walk through every cell in the grid
    for col in range(len(grid[0])):
        for row in range(7):
            if grid[row][col]:
                target_date = date_for_pixel(row, col, start_sunday)
                make_commit(target_date, repo_path, commits_per_day)
                done += 1
                print(f"\r  Progress: {done}/{total_pixels} pixels", end="", flush=True)
    print()

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 contribution_art.py <TEXT> [--generate] [--clean] [--reset]")
        sys.exit(1)

    text = sys.argv[1]
    generate = "--generate" in sys.argv
    clean = "--clean" in sys.argv
    reset = "--reset" in sys.argv
    repo_path = os.getcwd()

    # Delete old .git and re-initialize for a clean start; skip everything else
    if clean:
        print("\nCleaning up old commits...")
        import shutil
        git_dir = os.path.join(repo_path, ".git")
        if os.path.exists(git_dir):
            shutil.rmtree(git_dir)
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        with open(os.path.join(repo_path, "commit.txt"), "w") as f:
            f.write("initial\n")
        subprocess.run(["git", "add", "commit.txt"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_path, capture_output=True)
        print("  Done. Re-add your remote: git remote add origin <your-repo-url>")
        return

    # Drop all generated "art: " commits and stop; skip everything else
    if reset:
        reset_art_commits(repo_path)
        return

    # Render the text and show preview
    grid = render_text(text)
    print(f"\nPreview for '{text}':\n")
    preview(grid)
    print(f"\nTotal pixels: {sum(cell for row in grid for cell in row)}")
    print(f"\nTotal commits: {sum(cell for row in grid for cell in row) * COMMITS_PER_DAY}")

    if generate:
        print(f"\nGenerating commits for year {TARGET_YEAR}...")
        generate_commits(grid, repo_path, COMMITS_PER_DAY)
        print("\nDone! Push with: git push --force origin main")


if __name__ == "__main__":
    main()
