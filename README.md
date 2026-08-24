# contribution-art

Paints pixel art onto a GitHub contribution graph by backdating clusters of
throwaway commits, one cluster per "on" pixel — pushed to a **disposable
GitHub repo the script creates just for this run**, never against a repo
you actually use.

## Prior art

This is a from-scratch rewrite of the same basic trick used by
[gitfiti](https://github.com/gelstudios/gitfiti/blob/main/gitfiti.py),
which pioneered backdated-commit contribution graph art. The main
differences here: art is described as a JSON intensity grid (rather than
gitfiti's bitmap image file), shading is calibrated against your real
contribution data pulled live via the GitHub GraphQL API (rather than
scraping the public profile page), and every run gets its own disposable
GitHub repo created and torn down by the script (rather than reusing one
repo you have to manage by hand).

## Requirements

- Python 3
- Git
- [GitHub CLI (`gh`)](https://cli.github.com/), authenticated
  (`gh auth status`) with at least the `repo` scope. Deleting a canvas
  repo via `--clean` additionally needs the `delete_repo` scope — if it's
  missing, `gh` will prompt you to run `gh auth refresh -s delete_repo`
  the first time you clean up.

## Usage

```
python3 contribution_art.py <ART_JSON>                                  # preview only, no git/GitHub calls
python3 contribution_art.py <ART_JSON> --generate [--repo-name NAME] [--private] [--year YYYY] [--yes]
python3 contribution_art.py --clean [--repo-name NAME] [--yes]
python3 contribution_art.py --from-text "HI" [--level 1-4] [-o art.json] [--year YYYY]
```

### Art format

`<ART_JSON>` is a 7-row grid of shade levels, one row per day-of-week
(row 0 = Sunday .. row 6 = Saturday) and one character per week-column,
matching GitHub's graph layout. Each character is `0`-`4`: `0` leaves that
day untouched, `1`-`4` are increasing shades. Rows must all be the same
length, and the graph is 53 columns wide, so that's the max:

```json
{
  "year": 2025,
  "grid": [
    "0000000000000000000000000000000000000000000000000",
    "0004000400040004000000000000000000000000000000000",
    "0004000400040004000000000000000000000000000000000",
    "0004000400040004000000000000000000000000000000000",
    "0004000400040004000000000000000000000000000000000",
    "0004000400040004000000000000000000000000000000000",
    "0000000000000000000000000000000000000000000000000"
  ]
}
```

See `art/example.json` for a runnable copy of the above, and `art/` for
more. Running the script with just `<ART_JSON>` prints a preview of the
grid and pixel count without touching git or GitHub:

```
python3 contribution_art.py art/example.json
```

### `art/` directory

All art files live in `art/`. Alongside `example.json`, it includes the
built-in bitmap designs from
[gitfiti](https://github.com/gelstudios/gitfiti/blob/main/gitfiti.py),
ported over as JSON grids (gitfiti's original level values, 0-4, map
directly onto this format):

| file | design |
| --- | --- |
| `kitty.json` | gitfiti's mascot cat |
| `oneup.json` / `oneup2.json` | Mario 1-UP mushroom |
| `hackerschool.json` | Hacker School logo |
| `octocat.json` / `octocat2.json` | GitHub's Octocat |
| `hello.json` | "hello" in a hand-drawn bitmap font |
| `heart.json` / `heart1.json` / `heart_shiny.json` | heart variants |
| `hireme.json` | "hire me" bitmap text |
| `beer.json` | beer mug |
| `gliders.json` | Conway's Game of Life gliders |

```
python3 contribution_art.py art/kitty.json
```

### Shading calibration

Shade levels aren't a fixed commit count — GitHub buckets a graph's shades
by quartiles of that year's nonzero day-counts, recomputed after new
commits land. `--generate` fetches your account's actual contribution
counts for the target year via the GitHub GraphQL API and picks commit
counts per level that clearly outscale anything already there and stay
well separated from each other, so the four levels render as four visibly
distinct shades. This is a best-effort calibration against GitHub's
undisclosed bucketing algorithm, not a guaranteed exact match — very
unusual existing activity in the target year could still throw it off.

### Flags

- `--generate` — fetches your real contribution data for calibration,
  shows a preview and confirmation prompt, then creates a new disposable
  GitHub repo and pushes the backdated commits to it.
- `--clean` — deletes the disposable canvas repo created by the last
  `--generate` (tracked in a local `.art_state.json`), after a
  confirmation prompt. This is the only verified way to remove
  already-counted contributions from the graph — force-pushing a cleaned
  history does **not** do it (see `CLAUDE.md`).
- `--repo-name NAME` — use this name for the canvas repo instead of the
  auto-generated `contribution-art-canvas-<timestamp>`. Also lets
  `--clean` target a specific repo without relying on local state.
- `--private` — create the canvas repo as private instead of the default
  public. Private-repo contributions only show on your graph if "Include
  private contributions" is enabled in your GitHub profile settings.
- `--year YYYY` — override the year encoded in the JSON file.
- `--yes` — skip the interactive confirmation prompts (for scripting).
- `--from-text TEXT [--level N] [-o path]` — offline helper that renders
  `TEXT` with the built-in 5x7 font and writes it out as a JSON art file
  (all "on" pixels get `--level`, default 4); doesn't touch git or
  GitHub. Letters and space are supported; digits/punctuation fall back to
  a blank column. `9*5 + 8*1 = 53`, so at most 9 letters fit on one row.

### Typical workflow

```
python3 contribution_art.py --from-text "HI" -o art/hi.json  # or use one of art/*.json, or hand-author your own
python3 contribution_art.py art/hi.json                      # preview
python3 contribution_art.py art/hi.json --generate            # confirm, create canvas repo, push
python3 contribution_art.py --clean                           # confirm, delete the canvas repo
```
