# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Python script (`contribution_art.py`) that paints pixel art
onto a GitHub contribution graph by backdating clusters of throwaway
commits, one cluster per "on" pixel of a JSON-described intensity grid.
There is no build system, package manifest, test suite, or linter — just
the script, the `art/` directory (JSON art files, including `example.json`
and several designs ported from gitfiti's built-in bitmaps), and
`README.md`. Inspired by
[gitfiti](https://github.com/gelstudios/gitfiti/blob/main/gitfiti.py).

**This repo is no longer the canvas.** Unlike the original MVP,
`--generate` never touches this repo's own git history. It creates a
brand-new, disposable GitHub repo (via `gh repo create`) in a fresh temp
directory, generates the backdated commits there, and pushes. `--clean`
deletes that disposable repo (via `gh repo delete`). The only state this
repo carries about that process is `.art_state.json` (gitignored) —
bookkeeping so `--clean` knows which repo to delete, not art itself.

**`--generate` and `--clean` are still real, external, account-visible
actions** — creating and deleting actual GitHub repositories, and (for
`--generate`) querying the account's real contribution data over the
GitHub GraphQL API. The script itself prompts for interactive confirmation
before each (skippable with `--yes`), but when Claude is driving this
script, confirm with the user before running either — same standard as
any other action that's visible to others or hard to reverse. `--clean`
in particular is irreversible: it destroys the canvas repo (and, if
`--repo-name` is pointed at the wrong repo, potentially something else) —
always confirm the exact repo being deleted before running it, and never
run it unattended.

**Why delete-the-repo is the design, not a workaround.** Earlier in this
project's life, the script rewrote *this* repo's own history and relied on
`--clean`/`--reset` + `git push --force` to undo mistakes. That was
confirmed **not** to work: once `art:` commits are pushed and GitHub has
counted them, force-pushing a cleaned history removes the commits from the
repo but does not remove the already-counted squares from the
contribution graph or Activity page — confirmed directly against this
repo's own history on 2026-08-24 (GraphQL `contributionsCollection` still
reported the art commits' contribution count after a force-push clean).
The only fix that empirically worked was deleting and recreating the
GitHub repository — doing that dropped the account's total contribution
count by roughly the art commits' count (likely because the contributions
were same-day/recent and hadn't "settled" into GitHub's permanent record
yet; this should not be assumed to hold for older, established
contributions). The current architecture builds that fix in as the normal
teardown path: every canvas repo is meant to be deleted when you're done
with it, so `--clean` doing a real `gh repo delete` is expected behavior,
not an emergency recovery step — but it's still a one-way door, so still
confirm before running it.

## Commands

```
python3 contribution_art.py <ART_JSON>                                  # preview only, no git/GitHub calls
python3 contribution_art.py <ART_JSON> --generate [--repo-name NAME] [--private] [--year YYYY] [--yes]
python3 contribution_art.py --clean [--repo-name NAME] [--yes]
python3 contribution_art.py --from-text "HI" [--level 1-4] [-o art.json] [--year YYYY]
```

`<ART_JSON>` is required for the plain-preview and `--generate` forms.
`--clean` takes no art file — it reads `.art_state.json` (or `--repo-name`)
to know which canvas repo to delete. `--from-text` is a standalone offline
helper (see Architecture) that never touches git or GitHub. There's no
test/lint/build command; verify changes by running the script and
inspecting the printed preview, `git log` in the temp clone, and/or
`gh repo view`.

## Architecture

The script is one file with a few pipelines:

1. **`FONT` / `render_text(text)`** — the original 5x7 pixel font,
   preserved only as the engine behind the offline `--from-text` helper,
   which renders text and writes it out as a JSON art file. It's not on
   the primary art path anymore.
2. **`load_art_json(path)` / `write_art_json(...)`** — the primary art
   input format: a JSON file with a `year` and a `grid` of 7 strings
   (Sun..Sat), each character `0`-`4` encoding a shade level per
   week-column. Validates shape (7 rows, equal length, ≤53 columns) and
   charset before anything else runs.
3. **`get_start_sunday` / `date_for_pixel`** — map grid `(row, col)` to a
   real calendar date for a given year, Sunday-aligned so row 0 = Sunday
   matches GitHub's graph layout. Unchanged from the original.
4. **`fetch_contribution_days(year)` / `commits_for_level(existing_max)`**
   — shells out to `gh api graphql` for the account's real
   `contributionsCollection` day-counts in the target year, then derives a
   `level -> commit count` mapping that clearly outscales existing activity
   and keeps levels 1-4 well separated (see README's "Shading calibration"
   section for the reasoning and its limits).
5. **`make_commit` / `generate_commits`** — for every "on" pixel (level >
   0), write `commit.txt` in the target repo dir, then create that level's
   calibrated number of commits with `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`
   overridden to that pixel's date. Commit subjects are always
   `art: <date> #<n>`. Level-0 cells are skipped entirely, leaving
   whatever's already on the graph that day untouched.
6. **`create_canvas_repo` / `delete_canvas_repo` / state helpers** — the
   repo lifecycle. `create_canvas_repo` runs `gh repo create <name>
   --public|--private --clone` into a fresh `tempfile.mkdtemp()` dir;
   `delete_canvas_repo` runs `gh repo delete <owner>/<name> --yes`. State
   (`repo_name`, `owner`, `workdir`) round-trips through `.art_state.json`
   so a later `--clean` (possibly a different invocation) knows what to
   tear down.
7. **`cmd_generate` / `cmd_clean` / `cmd_from_text` / `main()`** — argparse
   wires up the flags above; every mutating command (`--generate`,
   `--clean`) prints exactly what it's about to do and requires
   interactive confirmation unless `--yes` is passed.

`TARGET_YEAR` is a constant at the top of the file, overridable per-run via
`--year` or the JSON file's own `year` key.
