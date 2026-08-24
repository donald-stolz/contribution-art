# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Python script (`contribution_art.py`) that paints text onto a
GitHub contribution graph by backdating clusters of throwaway commits, one
cluster per "on" pixel of a built-in 5x7 pixel font. There is no build
system, package manifest, test suite, or linter — just the script, plus
`commit.txt` (the file it repeatedly rewrites/commits) and `README.md`.

**This repo is also the live canvas the script operates on.** `repo_path`
in the script is always `os.getcwd()`, so running it from here rewrites
*this* repository's own history, and `origin` is already set to a real
GitHub remote (`github.com/donald-stolz/contribution-art`). Treat
`--generate`, `--clean`, and `--reset` as destructive, history-rewriting
operations against a real remote-tracked repo — confirm with the user
before running any of them, and never `git push --force` without explicit
instruction.

**`--clean`/`--reset` + force-push does NOT undo the contribution graph.**
Once `art:` commits have been pushed to `origin/main` and GitHub has
counted them, rewriting local history and force-pushing the clean state
back removes the commits from the repo but does **not** remove the
already-counted squares from the contribution graph or the Activity page —
confirmed directly against this repo's own history on 2026-08-24 (GraphQL
`contributionsCollection` still reported the art commits' contribution
count after a force-push clean). This contradicts GitHub's own docs, which
claim contributions persist even after the source repo is deleted — but
empirically, on this account, deleting and recreating
`donald-stolz/contribution-art` *did* drop the account's total contribution
count by roughly the art commits' count (likely because the contributions
were same-day/recent and hadn't "settled" into GitHub's permanent record
yet — older, established contributions may behave differently and this
should not be assumed to work in general). **The verified reset procedure,
if `art:` commits were ever pushed, is: delete the GitHub repository and
recreate it (same name/visibility), then push the local non-art commit
history to it** — not `--clean`/`--reset` alone. This is an account-level,
hard-to-reverse action (destroys stars/issues/PR history) — always confirm
with the user before deleting a repo, and never do it silently as part of
running the script.

## Commands

```
python3 contribution_art.py <TEXT>                    # preview only, no git changes
python3 contribution_art.py <TEXT> --generate          # preview + create backdated commits
python3 contribution_art.py <TEXT> --clean              # wipe .git, reinit, single "initial commit"
python3 contribution_art.py <TEXT> --reset               # hard-reset away all generated "art: " commits
```

`<TEXT>` is required for every invocation (including `--clean`/`--reset`,
which ignore it). `--clean` and `--reset` run standalone — nothing else in
`main()` executes when either is set. There's no test/lint/build command;
verify changes by running the script and inspecting the printed preview
and/or `git log`.

## Architecture

The script is one linear pipeline, top to bottom:

1. **`FONT`** — a dict mapping uppercase letters (and space) to seven
   5-bit integers, one per font row; each bit is a pixel. Digits and
   punctuation aren't defined and fall back to a blank column.
2. **`render_text(text)`** — unrolls `FONT` bit patterns into a `7 x N`
   boolean grid (7 rows for days-of-week, N columns for weeks), inserting
   one blank column between letters. The 53-column GitHub graph width caps
   this at 9 letters (`9*5 + 8*1 = 53`).
3. **`get_start_sunday` / `date_for_pixel`** — map grid `(row, col)` to a
   real calendar date for `TARGET_YEAR`, Sunday-aligned so row 0 = Sunday
   matches GitHub's graph layout.
4. **`make_commit` / `generate_commits`** — for every "on" pixel, write
   `commit.txt`, then create `COMMITS_PER_DAY` commits with
   `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` overridden to that pixel's date
   (darker green = more commits on that day). Commit subjects are always
   `art: <date> #<n>`.
5. **`reset_art_commits`** — walks `git log` from HEAD, finds the newest
   commit whose subject doesn't start with `art: `, and hard-resets to it,
   dropping every generated commit above it while preserving real work
   underneath.
6. **`main()`** — parses `sys.argv` flags, always prints a preview via
   `preview(grid)`, and only mutates git state when `--generate`,
   `--clean`, or `--reset` is passed.

`TARGET_YEAR` and `COMMITS_PER_DAY` are constants at the top of the file —
edit them directly rather than adding CLI flags for something this small.
