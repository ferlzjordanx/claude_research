#!/usr/bin/env python3
"""Post-process the pandoc output: render code blocks at 7.5 pt so ~120-column diagrams fit the page width."""
import re
import shutil
import sys
import tempfile
import zipfile

CODE_SIZE = "15"     # half-points → 7.5 pt for highlighted source code
DIAGRAM_SIZE = "13"  # 6.5 pt for plain (unhighlighted) blocks: ASCII diagrams up to ~125 columns fit


def shrink_code(xml: str) -> str:
    def fix_paragraph(m: re.Match) -> str:
        para = m.group(0)
        if not re.search(r'<w:pStyle w:val="SourceCode"\s*/>', para):
            return para
        # Plain blocks use only VerbatimChar runs; highlighted blocks use token styles (KeywordTok, ...).
        styles = set(re.findall(r'<w:rStyle w:val="(\w+)"', para))
        size = DIAGRAM_SIZE if styles and styles <= {"VerbatimChar"} else CODE_SIZE
        # Add/replace an explicit size on every run in a code paragraph (direct formatting beats character styles).
        def fix_run_props(rp: re.Match) -> str:
            inner = re.sub(r'<w:sz w:val="\d+"\s*/>', "", rp.group(1))
            return f'<w:rPr>{inner}<w:sz w:val="{size}"/></w:rPr>'
        para = re.sub(r"<w:rPr>(.*?)</w:rPr>", fix_run_props, para)
        para = re.sub(r"<w:r>(?!<w:rPr>)", f'<w:r><w:rPr><w:sz w:val="{size}"/></w:rPr>', para)
        return para
    xml = re.sub(r"<w:p>.*?</w:p>|<w:p .*?</w:p>", fix_paragraph, xml, flags=re.S)
    # Schema-complete page margins (header/footer/gutter are required attributes).
    return re.sub(r"<w:pgMar ([^>]*?)\s*/>",
                  lambda m: m.group(0) if "w:header" in m.group(1)
                  else f'<w:pgMar {m.group(1)} w:header="720" w:footer="720" w:gutter="0" />', xml)


def main(path: str) -> None:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx").name
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = shrink_code(data.decode("utf-8")).encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, path)


if __name__ == "__main__":
    main(sys.argv[1])
