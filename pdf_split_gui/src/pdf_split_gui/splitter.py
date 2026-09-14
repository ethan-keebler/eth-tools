from __future__ import annotations

from pathlib import Path

import pymupdf


def parse_page_breaks(text: str, n_pages: int) -> list[int]:
    """Parse a comma/space/semicolon-separated list of 1-indexed chunk start pages."""
    cleaned = text.replace(",", " ").replace(";", " ").replace("\n", " ")
    raw = cleaned.split()
    if not raw:
        raise ValueError("enter chunk start pages, e.g. 1, 50, 100")

    starts: list[int] = []
    for tok in raw:
        try:
            starts.append(int(tok))
        except ValueError as e:
            raise ValueError(
                f"invalid page number {tok!r} — enter starts like: 1, 50, 100"
            ) from e

    starts = sorted(set(starts))
    if starts[0] != 1:
        starts = [1, *starts]
    if any(p < 1 or p > n_pages for p in starts):
        raise ValueError(f"page breaks must be in range 1..{n_pages}: {starts}")
    return starts


def chunk_ranges(starts: list[int], n_pages: int) -> list[tuple[int, int]]:
    """Turn 1-indexed chunk starts into inclusive (start, end) page ranges."""
    starts = sorted({int(p) for p in starts})
    if not starts:
        raise ValueError("page_breaks must be non-empty")
    if starts[0] != 1:
        starts = [1, *starts]
    if any(p < 1 or p > n_pages for p in starts):
        raise ValueError(f"page_breaks out of range 1..{n_pages}: {starts}")

    ranges: list[tuple[int, int]] = []
    for i, start in enumerate(starts):
        end = (starts[i + 1] - 1) if i + 1 < len(starts) else n_pages
        if end < start:
            raise ValueError(f"empty range at start={start}")
        ranges.append((start, end))
    return ranges


def split_pdf_by_page_breaks(
    input_path: str | Path,
    page_breaks: list[int],
    dest_dir: str | Path,
) -> list[Path]:
    """
    Split a PDF into chunks at the given 1-indexed page starts.

    page_breaks example: [1, 50, 100]
      -> <stem>-1-49.pdf
      -> <stem>-50-99.pdf
      -> <stem>-100-<last>.pdf
    """
    input_path = Path(input_path)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    src = pymupdf.open(input_path)
    try:
        n_pages = src.page_count
        if n_pages == 0:
            raise ValueError(f"empty pdf: {input_path}")

        ranges = chunk_ranges(page_breaks, n_pages)
        stem = input_path.stem
        out_paths: list[Path] = []
        for start, end in ranges:
            dst = pymupdf.open()
            try:
                dst.insert_pdf(src, from_page=start - 1, to_page=end - 1)
                out_path = dest_dir / f"{stem}-{start}-{end}.pdf"
                dst.save(out_path)
                out_paths.append(out_path)
            finally:
                dst.close()

        return out_paths
    finally:
        src.close()
