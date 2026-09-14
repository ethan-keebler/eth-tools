# pdf-split-gui

Local macOS tool to page through PDFs, enter page-break starts, and split into
`<stem>-{start}-{end}.pdf` chunks.

## Setup

Requires Homebrew Python 3.11 with Tk:

```bash
brew install python@3.11 python-tk@3.11
cd /Users/eth/dev/eth_tools
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

```bash
pdf-split-gui
# or
python -m pdf_split_gui
```

1. Pick an **input** folder of PDFs and an **output** folder for splits
2. Browse pages (`←`/`→` for 1 page, `↑`/`↓` for 100, or the page buttons); zoom with `+` / `-`
3. Enter 1-indexed chunk starts, e.g. `1, 50, 100`
4. **Split** writes range-named PDFs; **Split & Next** then advances to the next file

### Shortcuts

| Key | Action |
|-----|--------|
| ← / → | Prev / next page (1) |
| ↑ / ↓ | Jump +100 / −100 pages |
| + / - | Zoom in / out |
| B | Add current page as a chunk start |

The line under the page controls shows how many pages you are into the current chunk (from the last start through the page you are on) and how large that chunk is if you do not add another break. The preview line lists every chunk with its page count (e.g. `1-49 (49p) | 50-99 (50p) | 100-250 (151p)`). If you only have `1`, Split warns before writing a single whole-PDF file.
