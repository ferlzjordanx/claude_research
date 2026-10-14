#!/usr/bin/env python3
"""Assemble the training guide.

1. Expand include directives in guide-src/*.md:
     {{file projects/unit01-python/solution/quotes/retry.py}}
     {{files projects/unit01-python/solution}}   (every source file)
     {{tree projects/unit01-python/solution}}
   so the code printed in the document is exactly the code on disk.
2. Convert with pandoc using reference.docx (typography rules).
3. Post-process: force Courier New 11 pt on every code run.
"""

import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = ROOT / "FDE_FullStack_Interview_Guide.docx"
MAX_CODE_COLS = 76

SKIP_DIRS = {"node_modules", "__pycache__", ".pytest_cache", ".mypy_cache",
             ".ruff_cache", "dist", ".venv", "venv", ".git", "coverage"}
SKIP_FILES = {"package-lock.json", ".DS_Store"}
SKIP_SUFFIX = {".pyc", ".db", ".sqlite", ".png", ".ico", ".svg", ".lock"}
LANG = {".py": "python", ".ts": "typescript", ".tsx": "tsx",
        ".js": "javascript", ".json": "json", ".yml": "yaml",
        ".yaml": "yaml", ".toml": "toml", ".md": "markdown",
        ".html": "html", ".css": "css", ".sql": "sql", ".sh": "bash",
        ".ini": "ini", ".cfg": "ini", ".txt": "text", ".mako": "text"}
SPECIAL = {"Dockerfile": "dockerfile", "Jenkinsfile": "groovy",
           "Makefile": "makefile", ".env.example": "bash",
           ".dockerignore": "text", ".gitignore": "text"}


def lang_for(path: Path) -> str:
    return SPECIAL.get(path.name) or LANG.get(path.suffix, "text")


def source_files(directory: Path) -> list[Path]:
    files = []
    for p in sorted(directory.rglob("*")):
        rel_parts = p.relative_to(directory).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if p.is_file() and p.name not in SKIP_FILES \
                and p.suffix not in SKIP_SUFFIX:
            files.append(p)
    # README first, then config, then source, tests last
    def key(p: Path):
        rel = p.relative_to(directory).as_posix()
        return (0 if p.name == "README.md" else
                2 if "/tests/" in "/" + rel or rel.startswith("tests/")
                else 1, rel)
    return sorted(files, key=key)


def fence(text: str) -> str:
    return "````" if "```" in text else "```"


def file_block(path: Path, base: Path) -> str:
    text = path.read_text(encoding="utf-8").rstrip("\n")
    rel = path.relative_to(base).as_posix()
    f = fence(text)
    return (f"**File: `{rel}`**\n\n{f}{lang_for(path)}\n{text}\n{f}\n")


def tree(directory: Path) -> str:
    lines = [directory.name + "/"]

    def walk(d: Path, prefix: str) -> None:
        entries = [e for e in sorted(d.iterdir(), key=lambda e: (e.is_file(), e.name))
                   if e.name not in SKIP_DIRS and e.name not in SKIP_FILES
                   and e.suffix not in SKIP_SUFFIX]
        for i, e in enumerate(entries):
            last = i == len(entries) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{e.name}"
                         + ("/" if e.is_dir() else ""))
            if e.is_dir():
                walk(e, prefix + ("    " if last else "│   "))
    walk(directory, "")
    return "```text\n" + "\n".join(lines) + "\n```\n"


def expand(md: str) -> str:
    def repl(m: re.Match) -> str:
        kind, arg = m.group(1), m.group(2).strip()
        target = ROOT / arg
        if not target.exists():
            sys.exit(f"include not found: {arg}")
        if kind == "file":
            return file_block(target, _project_root(target))
        if kind == "files":
            return "\n".join(file_block(p, target) for p in source_files(target))
        return tree(target)
    return re.sub(r"\{\{(file|files|tree) ([^}]+)\}\}", repl, md)


def _project_root(path: Path) -> Path:
    # Show paths relative to the starter/solution folder when possible.
    for parent in path.parents:
        if parent.name in {"starter", "solution"}:
            return parent
    return ROOT


def check_widths(md: str) -> None:
    in_code, n_wide = False, 0
    for line in md.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code and len(line) > MAX_CODE_COLS:
            n_wide += 1
            if n_wide <= 15:
                print(f"  wide code line ({len(line)}): {line[:60]}...")
    if n_wide:
        print(f"WARNING: {n_wide} code lines exceed {MAX_CODE_COLS} columns")


CODE_RUN_PROPS = ('<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" '
                  'w:eastAsia="Courier New" w:cs="Courier New"/>'
                  '<w:sz w:val="22"/><w:szCs w:val="22"/>')


def postprocess(path: Path) -> None:
    with zipfile.ZipFile(path) as zin:
        items = [(i, zin.read(i.filename)) for i in zin.infolist()]
    out = []
    for info, data in items:
        if info.filename == "word/document.xml":
            xml = data.decode("utf-8")

            def fix_para(m: re.Match) -> str:
                p = m.group(0)
                if 'w:val="SourceCode"' not in p:
                    return p

                def fix_rpr(r: re.Match) -> str:
                    inner = re.sub(r"<w:rFonts[^>]*/>|<w:sz [^>]*/>|<w:szCs [^>]*/>",
                                   "", r.group(1))
                    # rStyle must stay first inside rPr
                    style = re.match(r"(<w:rStyle [^>]*/>)?(.*)", inner, re.S)
                    return f"<w:rPr>{style.group(1) or ''}{CODE_RUN_PROPS}{style.group(2)}</w:rPr>"
                p = re.sub(r"<w:rPr>(.*?)</w:rPr>", fix_rpr, p, flags=re.S)
                p = re.sub(r"<w:r>(?!<w:rPr>)", f"<w:r><w:rPr>{CODE_RUN_PROPS}</w:rPr>", p)
                return p
            xml = re.sub(r"<w:p>.*?</w:p>|<w:p .*?</w:p>", fix_para, xml, flags=re.S)
            data = xml.encode("utf-8")
        out.append((info, data))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for info, data in out:
            zout.writestr(info, data)


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--check":
        # Validate one chapter (includes resolve, code widths) without
        # writing the document: python3 build.py --check 06-unit06.md
        check_widths(expand((HERE / sys.argv[2]).read_text("utf-8")))
        print("checked", sys.argv[2])
        return
    sources = sorted(HERE.glob("[0-9]*.md"))
    combined = "\n\n".join(expand(p.read_text(encoding="utf-8")) for p in sources)
    check_widths(combined)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as tmp:
        tmp.write(combined)
    (HERE / "build").mkdir(exist_ok=True)
    (HERE / "build" / "combined.md").write_text(combined, encoding="utf-8")
    subprocess.run([
        "pandoc", tmp.name, "-f",
        "markdown+pipe_tables+fenced_code_blocks+task_lists+yaml_metadata_block",
        "--reference-doc", str(HERE / "reference.docx"),
        "--highlight-style", "tango", "--toc", "--toc-depth=2",
        "-o", str(OUTPUT)], check=True)
    postprocess(OUTPUT)
    print("wrote", OUTPUT)


if __name__ == "__main__":
    main()
