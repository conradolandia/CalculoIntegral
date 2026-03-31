#!/usr/bin/env python3
"""
Replace minipage + \\captionof{figure} blocks with proper figure environments.

Single-image pattern (outer \\begin{minipage}{\\textwidth} ... \\captionof{figure} ...):
  - Preserves caption-above-image order (matches existing \\begin{figure}[h] in project).
  - Inner width 0.30\\linewidth + \\includegraphics[width=\\linewidth] -> width=0.30\\textwidth

Multi-image: one block with two inner minipages (side by side) -> figure + two minipages + one caption.

Usage:
  python3 scripts/convert_captionof_to_figure.py [--dry-run] CapAplicaciones.tex ...
  python3 scripts/convert_captionof_to_figure.py [--dry-run]  # all known chapter files
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Files that contain \captionof{figure} in this project
DEFAULT_FILES = (
    "CapAplicaciones.tex",
    "CapIntegDefinid.tex",
    "CapIntegNumer.tex",
    "CapMetodosIntegr.tex",
    "CapTeoremFundCalcu.tex",
)


def extract_braces(s: str, i: int) -> tuple[str, int] | None:
    """If s[i]=='{', return (inner, pos_after_closing)."""
    if i >= len(s) or s[i] != "{":
        return None
    depth = 0
    start = i
    j = i
    while j < len(s):
        c = s[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1 : j], j + 1
        j += 1
    return None


def find_matching_end_minipage(s: str, start: int) -> int | None:
    """Find \\end{minipage} that closes the \\begin{minipage} at start."""
    if not s.startswith("\\begin{minipage}", start):
        return None
    depth = 0
    pos = start
    while pos < len(s):
        b = s.find("\\begin{minipage}", pos)
        e = s.find("\\end{minipage}", pos)
        if e == -1:
            return None
        if b != -1 and b < e:
            depth += 1
            pos = b + len("\\begin{minipage}")
        else:
            depth -= 1
            end_here = e + len("\\end{minipage}")
            if depth == 0:
                return end_here
            pos = end_here
    return None


def parse_inner_minipage_block(s: str, pos: int) -> dict | None:
    """
    Parse \\begin{minipage}{W\\linewidth} ... \\includegraphics ... \\end{minipage}
    Returns {width_str, vspace_lead, includegraphics_options, path, end_pos}
    """
    m = re.match(
        r"(\s*)\\begin\{minipage\}\{([0-9.]+)\\linewidth\}\s*"
        r"(?:\\centering\s*)?"
        r"(\\vspace\{[^}]+\}\s*)?"
        r"\\includegraphics(\[[^\]]*\])?\{([^}]+)\}\s*"
        r"\\end\{minipage\}",
        s[pos:],
        re.DOTALL,
    )
    if not m:
        return None
    rel_end = m.end()
    return {
        "width": m.group(2),
        "vspace_lead": m.group(3) or "",
        "graphics_options": m.group(4) or "[width=\\linewidth]",
        "path": m.group(5).strip(),
        "end_pos": pos + rel_end,
    }


def parse_footer(s: str, pos: int) -> tuple[str, int] | None:
    """After images: optional \\vspace{0.3em}, then \\fuente{...} or parbox Fuente."""
    m = re.match(r"\s*\\vspace\{0\.3em\}\s*", s[pos:])
    if m:
        pos += m.end()
    # \fuente{...}
    m = re.match(r"\s*\\fuente\s*\{", s[pos:])
    if m:
        open_b = pos + m.end() - 1
        br = extract_braces(s, open_b)
        if br:
            _inner, after = br
            return s[pos:after], after
    # \parbox{0.95\linewidth}{...} (contenido variable: acentos, encoding)
    m = re.match(r"\s*\\parbox\{0\.95\\linewidth\}\s*\{", s[pos:])
    if m:
        open_b = pos + m.end() - 1
        br = extract_braces(s, open_b)
        if br:
            _inner, after = br
            return s[pos:after], after
    return None


def convert_outer_block(block: str) -> str | None:
    """
    block = full outer minipage ... \\end{minipage} including the outer begin/end.
    """
    if not block.startswith("\\begin{minipage}{\\textwidth}"):
        return None
    inner = block[len("\\begin{minipage}{\\textwidth}") :]
    # strip leading \centering
    m = re.match(r"\s*\\centering\s*", inner)
    if not m:
        return None
    pos = m.end()
    if not inner[pos:].startswith("\\captionof{figure}"):
        return None
    pos += len("\\captionof{figure}")
    cap = extract_braces(inner, pos)
    if cap is None:
        return None
    caption, pos = cap  # type: ignore[misc]
    # optional \label
    label_line = ""
    m = re.match(r"\s*\\label\{([^}]+)\}\s*", inner[pos:])
    if m:
        label_line = f"    \\label{{{m.group(1)}}}\n"
        pos += m.end()

    inners: list[dict] = []
    while True:
        parsed = parse_inner_minipage_block(inner, pos)
        if not parsed:
            break
        inners.append(parsed)
        pos = parsed["end_pos"]
        hm = re.match(r"(\s*\\hspace\{[^}]+\}\s*)", inner[pos:])
        if hm:
            pos += hm.end()
        else:
            break

    if not inners:
        return None

    foot = parse_footer(inner, pos)
    if foot is None:
        return None
    footer_tex, _fend = foot

    # Build figure body
    lines: list[str] = [
        "\\begin{figure}[htbp]",
        "    \\centering",
        f"    \\caption{{{caption}}}",
    ]
    if label_line:
        lines.append(label_line.rstrip())
    if len(inners) == 1:
        w = inners[0]["width"]
        opts = inners[0]["graphics_options"]
        if opts == "[width=\\linewidth]" or opts is None:
            opts = f"[width={w}\\textwidth]"
        path = inners[0]["path"]
        v = inners[0]["vspace_lead"]
        if v:
            lines.append(f"    {v.strip()}")
        lines.append(f"    \\includegraphics{opts}{{{path}}}")
    else:
        for idx, inn in enumerate(inners):
            w = inn["width"]
            v = inn["vspace_lead"]
            opts = inn["graphics_options"]
            if opts == "[width=\\linewidth]" or not opts:
                opts = "[width=\\linewidth]"
            path = inn["path"]
            lines.append(f"    \\begin{{minipage}}[t]{{{w}\\textwidth}}")
            lines.append("        \\centering")
            if v:
                lines.append(f"        {v.strip()}")
            lines.append(f"        \\includegraphics{opts}{{{path}}}")
            lines.append("    \\end{minipage}")
            if idx < len(inners) - 1:
                lines.append("    \\hspace{1em}")
    lines.append("    \\vspace{0.3em}")
    lines.append(f"    {footer_tex}")
    lines.append("\\end{figure}")
    return "\n".join(lines) + "\n"


def strip_leading_noindent(s: str, start: int) -> tuple[int, str]:
    """If block is preceded by \\noindent + newlines, include that in removal."""
    prefix = ""
    i = start
    if i >= 9 and s[i - 9 : i] == "\\noindent":
        # find start of \noindent
        j = start - 9
        prefix = s[j:start]
        return j, prefix
    return start, prefix


def process_text(text: str) -> tuple[str, int]:
    """Returns new_text, n_replacements."""
    out: list[str] = []
    i = 0
    n = 0
    while i < len(text):
        j = text.find("\\begin{minipage}{\\textwidth}", i)
        if j == -1:
            out.append(text[i:])
            break
        # Must be a captionof figure block
        cap_pos = text.find("\\captionof{figure}", j)
        if cap_pos == -1 or cap_pos > j + 400:
            out.append(text[i : j + 1])
            i = j + 1
            continue
        end = find_matching_end_minipage(text, j)
        if end is None:
            out.append(text[i : j + 1])
            i = j + 1
            continue
        block = text[j:end]
        converted = convert_outer_block(block)
        if converted is None:
            out.append(text[i : j + 1])
            i = j + 1
            continue
        # Optional \noindent immediately before
        start_use = j
        if j >= 9 and text[j - 9 : j] == "\\noindent":
            # also consume following newline(s)
            k = j - 9
            out.append(text[i:k])
            start_use = k
        else:
            out.append(text[i:start_use])
        out.append(converted)
        # skip optional newline after old block
        i = end
        if i < len(text) and text[i] == "\n":
            i += 1
        n += 1
    return "".join(out), n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="TeX files (default: all chapter files)")
    ap.add_argument("--dry-run", action="store_true", help="Print counts only")
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    files = args.files if args.files else list(DEFAULT_FILES)
    total = 0
    for name in files:
        path = root / name
        if not path.is_file():
            print(f"Skip missing: {path}", file=sys.stderr)
            continue
        text = path.read_text(encoding="utf-8")
        new_text, n = process_text(text)
        total += n
        print(f"{name}: {n} replacements")
        if not args.dry_run and n:
            path.write_text(new_text, encoding="utf-8")
    print(f"Total: {total}")


if __name__ == "__main__":
    main()
