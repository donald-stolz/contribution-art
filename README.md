# contribution-art

Paints text onto your GitHub contribution graph by backdating a burst of
throwaway commits, one cluster per "on" pixel of a 5x7 pixel font.

## Requirements

- Python 3
- Git

## Usage

```
python3 contribution_art.py <TEXT> [--generate] [--clean] [--reset]
```

`<TEXT>` is required and is rendered with the built-in 5x7 font (letters,
digits are not supported, unsupported characters fall back to a blank
column). The graph is 53 columns wide, so at most 9 characters fit on one
row (`9*5 + 8*1 = 53`).

Running the script with just `<TEXT>` prints a preview of the pixel grid
and the resulting pixel/commit counts without touching git:

```
python3 contribution_art.py HI
```

### Flags

- `--generate` — after the preview, back-dates and creates the commits for
  `TARGET_YEAR` (set at the top of the script, currently 2025), one
  commit per day-of-week/week-column pixel that's "on",
  `COMMITS_PER_DAY` times each (currently 15, for a darker green).
- `--clean` — wipes `.git` entirely, re-initializes the repo, and makes a
  single `initial commit`. Runs on its own; nothing else in the script
  runs when this flag is set. You'll need to re-add your remote
  afterwards (`git remote add origin <your-repo-url>`).
- `--reset` — removes every generated `art:` commit by hard-resetting to
  the most recent commit that isn't one, leaving any real work
  underneath untouched. Runs on its own; nothing else in the script runs
  when this flag is set.

`<TEXT>` must still be passed with `--clean` and `--reset` even though it
isn't used for those actions.

### Typical workflow

```
python3 contribution_art.py HI --clean       # start from a fresh repo
python3 contribution_art.py HI --generate    # preview + create the commits
git push --force origin main                 # publish the rewritten history
python3 contribution_art.py HI --reset       # undo, if you want to try again
```

`--generate` and `--clean`/`--reset` rewrite commit history, so pushing
requires `--force`.
