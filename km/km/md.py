#!/usr/bin/env python3
"""
md/qmd -> typ -> pdf batch pipeline

Steps:
  1) *.md  -> *.qmd  (copy/rename; keeps contents unchanged)
  2) *.qmd -> *.typ  (via `quarto pandoc --to typst`)
  3) *.typ -> *.pdf  (via `quarto typst compile`)

Usage:
  python md_qmd_to_typst_pdf.py --root . --recursive
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def ensure_quarto_available() -> None:
    try:
        run(["quarto", "--version"])
    except FileNotFoundError:
        raise SystemExit(
            "ERROR: 'quarto' was not found on PATH. Install Quarto and try again."
        )
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"ERROR: 'quarto --version' failed: {e}")


def convert_md_to_qmd(md_path: Path, overwrite_qmd: bool) -> Path:
    qmd_path = md_path.with_suffix(".qmd")
    if qmd_path.exists() and not overwrite_qmd:
        return qmd_path
    qmd_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(md_path, qmd_path)
    return qmd_path


def qmd_to_typ(qmd_path: Path, typ_path: Path, force: bool) -> None:
    if (not force) and typ_path.exists() and typ_path.stat().st_mtime >= qmd_path.stat().st_mtime:
        return
    typ_path.parent.mkdir(parents=True, exist_ok=True)
    run([
        "quarto", "pandoc",
        str(qmd_path),
        "--to", "typst",
        "--output", str(typ_path),
    ])


def typ_to_pdf(typ_path: Path, pdf_path: Path, force: bool) -> None:
    if not typ_path.exists():
        raise SystemExit(f"ERROR: Missing typ file: {typ_path}")
    if (not force) and pdf_path.exists() and pdf_path.stat().st_mtime >= typ_path.stat().st_mtime:
        return
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    # Typst CLI syntax is: typst compile <INPUT> [OUTPUT]
    # Quarto exposes it as: quarto typst compile ...
    run(["quarto", "typst", "compile", str(typ_path), str(pdf_path)])


def iter_files(root: Path, pattern: str, recursive: bool) -> list[Path]:
    if recursive:
        return sorted(root.rglob(pattern))
    return sorted(root.glob(pattern))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.cwd(), help="Root directory to process")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subdirectories")
    ap.add_argument("--overwrite-qmd", action="store_true", help="Overwrite existing .qmd when copying from .md")
    ap.add_argument("--only-converted", action="store_true",
                    help="Only process .qmd files that were created from .md in this run")
    ap.add_argument("--typ-dir", type=Path, default=Path("_typst"), help="Output directory for .typ files (relative to root)")
    ap.add_argument("--pdf-dir", type=Path, default=Path("_pdf"), help="Output directory for .pdf files (relative to root)")
    ap.add_argument("--force", action="store_true", help="Rebuild even if outputs look up-to-date")
    args = ap.parse_args()

    root = args.root.resolve()
    ensure_quarto_available()

    # 1) md -> qmd
    md_files = [p for p in iter_files(root, "*.md", args.recursive) if p.is_file()]
    converted_qmd: set[Path] = set()
    for md in md_files:
        qmd = convert_md_to_qmd(md, overwrite_qmd=args.overwrite_qmd)
        converted_qmd.add(qmd.resolve())

    # 2) choose qmd set
    if args.only_converted:
        qmd_files = sorted(converted_qmd)
    else:
        qmd_files = [p for p in iter_files(root, "*.qmd", args.recursive) if p.is_file()]
        # include newly converted as well (in case they weren't picked up due to ordering)
        qmd_files = sorted({p.resolve() for p in qmd_files}.union(converted_qmd))

    typ_root = (root / args.typ_dir).resolve()
    pdf_root = (root / args.pdf_dir).resolve()

    # 3) qmd -> typ -> pdf (preserve relative subfolder structure)
    for qmd in qmd_files:
        rel = qmd.resolve().relative_to(root)
        typ_path = (typ_root / rel).with_suffix(".typ")
        pdf_path = (pdf_root / rel).with_suffix(".pdf")

        try:
            qmd_to_typ(qmd, typ_path, force=args.force)
            typ_to_pdf(typ_path, pdf_path, force=args.force)
        except subprocess.CalledProcessError as e:
            print(f"ERROR while processing {qmd}: {e}", file=sys.stderr)

    print(f"Done. Typst: {typ_root} | PDFs: {pdf_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
