from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pymupdf
from PIL import Image, ImageTk

from pdf_split_gui.splitter import chunk_ranges, parse_page_breaks, split_pdf_by_page_breaks


class PdfSplitApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PDF Split GUI")
        self.geometry("1100x850")
        self.minsize(800, 600)

        self.input_dir: Path | None = None
        self.output_dir: Path | None = None
        self.pdf_paths: list[Path] = []
        self.pdf_index = 0

        self.doc: pymupdf.Document | None = None
        self.page_index = 0  # 0-indexed
        self.zoom = 1.25
        self._photo: ImageTk.PhotoImage | None = None
        self._preview_names: list[str] = []

        self._build_ui()
        self.bind("<Left>", lambda _e: self.prev_page())
        self.bind("<Right>", lambda _e: self.next_page())
        self.bind("<Up>", lambda _e: self.skip_pages(100))
        self.bind("<Down>", lambda _e: self.skip_pages(-100))
        self.bind("<plus>", lambda _e: self.zoom_in())
        self.bind("<minus>", lambda _e: self.zoom_out())
        self.bind("<equal>", lambda _e: self.zoom_in())  # = key without shift
        self.bind("b", lambda _e: self.add_break_at_current())
        self.bind("B", lambda _e: self.add_break_at_current())

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.X)

        ttk.Button(top, text="Input folder…", command=self.pick_input_dir).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(top, text="Output folder…", command=self.pick_output_dir).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        self.dirs_var = tk.StringVar(value="No folders selected")
        ttk.Label(top, textvariable=self.dirs_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        nav = ttk.Frame(self, padding=(8, 0, 8, 8))
        nav.pack(fill=tk.X)

        ttk.Button(nav, text="◀ Prev PDF", command=self.prev_pdf).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(nav, text="Next PDF ▶", command=self.next_pdf).pack(side=tk.LEFT, padx=(0, 12))
        self.file_var = tk.StringVar(value="No PDF loaded")
        ttk.Label(nav, textvariable=self.file_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        page_nav = ttk.Frame(self, padding=(8, 0, 8, 8))
        page_nav.pack(fill=tk.X)

        ttk.Button(page_nav, text="◀−100", command=lambda: self.skip_pages(-100)).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(page_nav, text="◀ Page", command=self.prev_page).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(page_nav, text="Page ▶", command=self.next_page).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(page_nav, text="+100 ▶", command=lambda: self.skip_pages(100)).pack(
            side=tk.LEFT, padx=(0, 12)
        )
        ttk.Label(page_nav, text="Go to:").pack(side=tk.LEFT)
        self.goto_var = tk.StringVar()
        goto_entry = ttk.Entry(page_nav, textvariable=self.goto_var, width=8)
        goto_entry.pack(side=tk.LEFT, padx=(4, 4))
        goto_entry.bind("<Return>", lambda _e: self.goto_page())
        ttk.Button(page_nav, text="Go", command=self.goto_page).pack(side=tk.LEFT, padx=(0, 12))
        self.page_var = tk.StringVar(value="Page —")
        ttk.Label(page_nav, textvariable=self.page_var).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(page_nav, text="Zoom −", command=self.zoom_out).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(page_nav, text="Zoom +", command=self.zoom_in).pack(side=tk.LEFT)

        chunk_row = ttk.Frame(self, padding=(8, 0, 8, 8))
        chunk_row.pack(fill=tk.X)
        self.chunk_var = tk.StringVar(value="Chunk —")
        ttk.Label(chunk_row, textvariable=self.chunk_var).pack(side=tk.LEFT)

        # Scrollable canvas for the page image
        canvas_frame = ttk.Frame(self, padding=(8, 0, 8, 8))
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, background="#2b2b2b", highlightthickness=0)
        vbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        hbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", lambda _e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda _e: self.canvas.yview_scroll(1, "units"))

        bottom = ttk.Frame(self, padding=8)
        bottom.pack(fill=tk.X)

        ttk.Label(bottom, text="Chunk starts:").pack(side=tk.LEFT)
        self.breaks_var = tk.StringVar(value="1")
        self.breaks_var.trace_add("write", lambda *_: self._update_preview())
        breaks_entry = ttk.Entry(bottom, textvariable=self.breaks_var, width=36)
        breaks_entry.pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)
        ttk.Button(bottom, text="Add current page (B)", command=self.add_break_at_current).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(bottom, text="Clear", command=self.clear_breaks).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(bottom, text="Split", command=self.split_current).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(bottom, text="Split & Next", command=self.split_and_next).pack(side=tk.LEFT)

        self.preview_var = tk.StringVar(value="Chunks: (enter starts like 1, 50, 100)")
        ttk.Label(self, textvariable=self.preview_var, padding=(8, 0, 8, 4)).pack(fill=tk.X)

        self.status_var = tk.StringVar(value="Pick input and output folders to begin.")
        ttk.Label(self, textvariable=self.status_var, padding=(8, 0, 8, 8)).pack(fill=tk.X)

    def _on_mousewheel(self, event: tk.Event) -> None:
        # macOS sends delta in multiples of ±1; Windows ±120
        delta = -1 * int(event.delta)
        if abs(event.delta) >= 120:
            delta = -1 * int(event.delta / 120)
        self.canvas.yview_scroll(delta, "units")

    def pick_input_dir(self) -> None:
        path = filedialog.askdirectory(title="Select input folder of PDFs")
        if not path:
            return
        self.input_dir = Path(path)
        self.pdf_paths = sorted(self.input_dir.glob("*.pdf")) + sorted(
            self.input_dir.glob("*.PDF")
        )
        # de-dupe while preserving order
        seen: set[Path] = set()
        unique: list[Path] = []
        for p in self.pdf_paths:
            if p.resolve() not in seen:
                seen.add(p.resolve())
                unique.append(p)
        self.pdf_paths = unique
        self.pdf_index = 0
        self._update_dirs_label()
        if not self.pdf_paths:
            self.status_var.set(f"No PDFs found in {self.input_dir}")
            self._close_doc()
            return
        self.load_current_pdf()

    def pick_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Select output folder for splits")
        if not path:
            return
        self.output_dir = Path(path)
        self._update_dirs_label()
        self.status_var.set(f"Output: {self.output_dir}")

    def _update_dirs_label(self) -> None:
        inn = str(self.input_dir) if self.input_dir else "(none)"
        out = str(self.output_dir) if self.output_dir else "(none)"
        n = len(self.pdf_paths)
        self.dirs_var.set(f"in: {inn}  |  out: {out}  |  {n} PDF(s)")

    def _close_doc(self) -> None:
        if self.doc is not None:
            self.doc.close()
            self.doc = None
        self.page_index = 0
        self.canvas.delete("all")
        self._photo = None
        self.file_var.set("No PDF loaded")
        self.page_var.set("Page —")
        self.chunk_var.set("Chunk —")

    def load_current_pdf(self) -> None:
        if not self.pdf_paths:
            self._close_doc()
            return
        self.pdf_index = max(0, min(self.pdf_index, len(self.pdf_paths) - 1))
        path = self.pdf_paths[self.pdf_index]
        self._close_doc()
        self.doc = pymupdf.open(path)
        self.page_index = 0
        self.breaks_var.set("1")
        self.file_var.set(f"[{self.pdf_index + 1}/{len(self.pdf_paths)}] {path.name}")
        self.render_page()
        self._update_preview()
        self.status_var.set(
            f"Loaded {path.name} ({self.doc.page_count} pages). "
            "Navigate to each new section start and press B, or type starts like 1, 50, 100."
        )

    def prev_pdf(self) -> None:
        if not self.pdf_paths:
            return
        self.pdf_index = max(0, self.pdf_index - 1)
        self.load_current_pdf()

    def next_pdf(self) -> None:
        if not self.pdf_paths:
            return
        if self.pdf_index >= len(self.pdf_paths) - 1:
            self.status_var.set("Already on last PDF.")
            return
        self.pdf_index += 1
        self.load_current_pdf()

    def skip_pages(self, delta: int) -> None:
        if self.doc is None:
            return
        self.page_index = max(0, min(self.doc.page_count - 1, self.page_index + delta))
        self.render_page()

    def prev_page(self) -> None:
        self.skip_pages(-1)

    def next_page(self) -> None:
        self.skip_pages(1)

    def goto_page(self) -> None:
        if self.doc is None:
            return
        try:
            page = int(self.goto_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid page", "Enter a page number.")
            return
        if page < 1 or page > self.doc.page_count:
            messagebox.showerror(
                "Invalid page", f"Page must be between 1 and {self.doc.page_count}."
            )
            return
        self.page_index = page - 1
        self.render_page()

    def zoom_in(self) -> None:
        self.zoom = min(4.0, self.zoom + 0.25)
        self.render_page()

    def zoom_out(self) -> None:
        self.zoom = max(0.5, self.zoom - 0.25)
        self.render_page()

    def render_page(self) -> None:
        if self.doc is None:
            return
        page = self.doc.load_page(self.page_index)
        mat = pymupdf.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._photo)
        self.canvas.configure(scrollregion=(0, 0, pix.width, pix.height))
        self.page_var.set(
            f"Page {self.page_index + 1} / {self.doc.page_count}  (zoom {self.zoom:.2f}x)"
        )
        self.goto_var.set(str(self.page_index + 1))
        self._update_chunk_counter()

    def clear_breaks(self) -> None:
        self.breaks_var.set("1")
        self._update_preview()

    def add_break_at_current(self) -> None:
        if self.doc is None:
            return
        page = self.page_index + 1
        try:
            existing = parse_page_breaks(self.breaks_var.get() or "1", self.doc.page_count)
        except ValueError:
            existing = [1]
        if page not in existing:
            existing.append(page)
        existing = sorted(set(existing))
        self.breaks_var.set(", ".join(str(p) for p in existing))
        self.status_var.set(f"Added break at page {page}")
        self._update_preview()

    def _update_chunk_counter(self) -> None:
        if self.doc is None:
            self.chunk_var.set("Chunk —")
            return
        page = self.page_index + 1
        n_pages = self.doc.page_count
        text = self.breaks_var.get().strip() or "1"
        try:
            breaks = parse_page_breaks(text, n_pages)
            ranges = chunk_ranges(breaks, n_pages)
        except ValueError:
            self.chunk_var.set("Chunk — (invalid starts)")
            return
        for start, end in ranges:
            if start <= page <= end:
                so_far = page - start + 1
                full = end - start + 1
                self.chunk_var.set(
                    f"Chunk size: [{so_far}] pages"
                )
                return
        self.chunk_var.set("Chunk —")

    def _update_preview(self) -> None:
        if self.doc is None:
            self.preview_var.set("Chunks: (load a PDF)")
            self._update_chunk_counter()
            return
        text = self.breaks_var.get().strip()
        if not text:
            self.preview_var.set("Chunks: (enter starts like 1, 50, 100)")
            self._update_chunk_counter()
            return
        try:
            breaks = parse_page_breaks(text, self.doc.page_count)
            ranges = chunk_ranges(breaks, self.doc.page_count)
        except ValueError as e:
            self.preview_var.set(f"Chunks: invalid — {e}")
            self._update_chunk_counter()
            return
        stem = self.pdf_paths[self.pdf_index].stem if self.pdf_paths else "file"
        names = [f"{stem}-{start}-{end}.pdf" for start, end in ranges]
        labeled = "  |  ".join(f"{s}-{e} ({e - s + 1}p)" for s, e in ranges)
        self.preview_var.set(
            f"Chunks ({len(ranges)}): {labeled}"
            + ("" if len(ranges) > 1 else "  ← add more starts or this writes the whole PDF")
        )
        # Keep full names in status-friendly form via tooltip-ish status on hover not needed;
        # store for split confirm.
        self._preview_names = names
        self._update_chunk_counter()

    def split_current(self) -> list[Path] | None:
        if self.doc is None or not self.pdf_paths:
            messagebox.showwarning("No PDF", "Load a PDF first.")
            return None
        if self.output_dir is None:
            messagebox.showwarning("No output folder", "Pick an output folder first.")
            return None

        path = self.pdf_paths[self.pdf_index]
        try:
            breaks = parse_page_breaks(self.breaks_var.get(), self.doc.page_count)
            ranges = chunk_ranges(breaks, self.doc.page_count)
        except Exception as e:
            messagebox.showerror("Split failed", str(e))
            return None

        if len(ranges) == 1:
            start, end = ranges[0]
            proceed = messagebox.askyesno(
                "Only one chunk",
                f"Page breaks are just {breaks!r}, so this would write one file "
                f"covering pages {start}-{end} (the whole PDF).\n\n"
                "Add more chunk start pages (type them, or press B on each start page).\n\n"
                "Write the whole PDF anyway?",
            )
            if not proceed:
                return None

        summary = "\n".join(f"  {path.stem}-{s}-{e}.pdf  (pages {s}-{e})" for s, e in ranges)
        if not messagebox.askyesno(
            "Confirm split",
            f"Write {len(ranges)} file(s) to:\n{self.output_dir}\n\n{summary}\n\nContinue?",
        ):
            return None

        try:
            out_paths = split_pdf_by_page_breaks(path, breaks, self.output_dir)
        except Exception as e:
            messagebox.showerror("Split failed", str(e))
            return None

        names = ", ".join(p.name for p in out_paths)
        self.status_var.set(f"Wrote {len(out_paths)} file(s): {names}")
        return out_paths

    def split_and_next(self) -> None:
        if self.split_current() is None:
            return
        if self.pdf_index < len(self.pdf_paths) - 1:
            self.pdf_index += 1
            self.load_current_pdf()
        else:
            self.status_var.set(self.status_var.get() + "  |  Done — last PDF.")


def main() -> None:
    app = PdfSplitApp()
    app.mainloop()


if __name__ == "__main__":
    main()
