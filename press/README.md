# The press

The profile README is printed, not written. `print.py` typesets every section
as an SVG plate with the fonts embedded, in light and dark, with a separate
phone cut of each, then writes `README.md` to stitch them together.

| Path | What it is |
| --- | --- |
| `content.py` | All the copy. Edit this. |
| `print.py` | The press: layout, live data, README. |
| `wire.json` | Last good GitHub data, reprinted if the API is down. |
| `fonts/` | Static Newsreader, Libre Franklin and IBM Plex Mono faces (OFL). |
| `img/` | Greyscale photo plates. |
| `tools/` | One-off prep scripts for fonts and images. |
| `../edition/` | Generated plates. Never edit by hand. |

## Run it

```sh
pip install -r press/requirements.txt
python3 press/print.py   # uses GITHUB_TOKEN, else `gh auth token`
```

`.github/workflows/press.yml` runs it every day at 06:00 IST, and again on any
push that touches `press/`. The bot's commits don't count on the contribution
graph. Set a `PRESS_TOKEN` secret only if the built-in token ever gets
rate-limited.

## Add a project

1. Make the cover plate. It must be 16:10.
   `python3 press/tools/prep_images.py path/to/screenshot.png <slug> 760 16:10`
2. Add an entry to `WORK` in `content.py`, with `repo` for the live star count
   or `link` for anything that isn't a GitHub repo.
3. Run the press.

Cards print two to a row, so an odd count leaves the last card alone on its
row.

## Previewing

GitHub's own markdown API shows what its sanitiser keeps:

```sh
gh api -X POST /markdown -f mode=gfm -f context=anirban12d/anirban12d -F text=@README.md
```

## The phone edition: don't "fix" these

- GitHub strips all CSS from a README, so the only responsive tool is
  `<picture>` with width conditions in `<source media>`. It also strips
  `sizes` and every `srcset` candidate after the first, so width descriptors
  don't work.
- GitHub's `themed-picture` script forces a user's chosen theme by rewriting the
  whole `media` of any source that says `prefers-color-scheme: dark`. That
  would erase a width test. The phone sources are written
  `(prefers-color-scheme:dark)`, with no space: the same query to a browser,
  and invisible to the script. Keep the missing space.
- The cost is that on phones, light/dark follows the phone's own setting, not
  a forced GitHub theme. That's why phone plates print on solid paper: if the
  two disagree, the reader still gets a legible sheet.
- Nav segments and cards have their widths fixed in the README HTML, so the
  phone plates keep those proportions and are designed for a 358px column.
