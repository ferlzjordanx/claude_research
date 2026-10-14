#!/usr/bin/env python3
"""Build reference.docx with the guide's required typography.

Times New Roman body 12 pt; title 16 pt bold; unit headings (H1) 14 pt
bold with a page break; subsection headings (H2/H3) 13 pt bold; code
Courier New 11 pt; single spacing, 2 pt before / 3 pt after.
"""

import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
TNR = ('<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
       'w:eastAsia="Times New Roman" w:cs="Times New Roman"/>')
COURIER = ('<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" '
           'w:eastAsia="Courier New" w:cs="Courier New"/>')
SPACING = '<w:spacing w:before="40" w:after="60" w:line="240" w:lineRule="auto"/>'


def para_style(sid, name, ppr="", rpr="", based="Normal", nxt="BodyText"):
    return (f'<w:style w:type="paragraph" w:customStyle="1" w:styleId="{sid}">'
            f'<w:name w:val="{name}"/><w:basedOn w:val="{based}"/>'
            f'<w:next w:val="{nxt}"/><w:qFormat/>'
            f'<w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>')


def heading(level, size, page_break=False):
    pb = "<w:pageBreakBefore/>" if page_break else ""
    ppr = (f'<w:keepNext/><w:keepLines/>{pb}'
           f'<w:spacing w:before="160" w:after="80" w:line="240" w:lineRule="auto"/>'
           f'<w:outlineLvl w:val="{level - 1}"/>')
    rpr = f'{TNR}<w:b/><w:bCs/><w:color w:val="000000"/><w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    return para_style(f"Heading{level}", f"heading {level}", ppr, rpr)


STYLES = {
    "Normal": ('<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
               '<w:name w:val="Normal"/><w:qFormat/>'
               f'<w:pPr>{SPACING}</w:pPr>'
               f'<w:rPr>{TNR}<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style>'),
    "BodyText": para_style("BodyText", "Body Text", SPACING, ""),
    "FirstParagraph": para_style("FirstParagraph", "First Paragraph", SPACING, "", based="BodyText"),
    "Compact": para_style("Compact", "Compact", '<w:spacing w:before="20" w:after="20"/>', "", based="BodyText"),
    "Title": para_style("Title", "Title",
                        '<w:jc w:val="center"/><w:spacing w:before="240" w:after="120"/>',
                        f'{TNR}<w:b/><w:bCs/><w:sz w:val="32"/><w:szCs w:val="32"/>'),
    "Subtitle": para_style("Subtitle", "Subtitle", '<w:jc w:val="center"/><w:spacing w:before="60" w:after="120"/>',
                           f'{TNR}<w:sz w:val="26"/><w:szCs w:val="26"/>'),
    "Author": para_style("Author", "Author", '<w:jc w:val="center"/>', TNR),
    "Date": para_style("Date", "Date", '<w:jc w:val="center"/>', TNR),
    "Heading1": heading(1, 28, page_break=True),
    "Heading2": heading(2, 26),
    "Heading3": heading(3, 26),
    "Heading4": heading(4, 24),
    "BlockText": para_style("BlockText", "Block Text",
                            '<w:ind w:left="360"/>' + SPACING, f'{TNR}<w:i/>', based="BodyText"),
    "VerbatimChar": ('<w:style w:type="character" w:customStyle="1" w:styleId="VerbatimChar">'
                     '<w:name w:val="Verbatim Char"/><w:basedOn w:val="DefaultParagraphFont"/>'
                     f'<w:rPr>{COURIER}<w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:style>'),
    "Hyperlink": ('<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/>'
                  '<w:basedOn w:val="DefaultParagraphFont"/>'
                  '<w:rPr><w:color w:val="0563C1"/><w:u w:val="single"/></w:rPr></w:style>'),
    "Table": ('<w:style w:type="table" w:default="1" w:styleId="Table"><w:name w:val="Table"/>'
              '<w:basedOn w:val="TableNormal"/><w:tblPr><w:tblStyleRowBandSize w:val="1"/>'
              '<w:tblBorders>'
              '<w:top w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
              '<w:left w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
              '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
              '<w:right w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
              '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
              '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="808080"/>'
              '</w:tblBorders><w:tblCellMar><w:left w:w="80" w:type="dxa"/>'
              '<w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr>'
              '<w:tblStylePr w:type="firstRow"><w:rPr><w:b/></w:rPr>'
              '<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="E7E6E6"/></w:tcPr></w:tblStylePr>'
              '</w:style>'),
}

SOURCE_CODE = (
    '<w:style w:type="paragraph" w:customStyle="1" w:styleId="SourceCode">'
    '<w:name w:val="Source Code"/><w:basedOn w:val="Normal"/><w:link w:val="VerbatimChar"/>'
    '<w:pPr><w:wordWrap w:val="off"/><w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
    '<w:shd w:val="clear" w:color="auto" w:fill="F4F4F4"/></w:pPr>'
    f'<w:rPr>{COURIER}<w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:style>')

SECT = ('<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" '
        'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>')


def main():
    default = HERE / "ref-default.docx"
    subprocess.run(["pandoc", "-o", str(default), "--print-default-data-file",
                    "reference.docx"], check=True)
    out = HERE / "reference.docx"
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(default) as z:
            z.extractall(tmp)
        styles = Path(tmp, "word/styles.xml")
        s = styles.read_text(encoding="utf-8")
        s = re.sub(r"<w:docDefaults>.*?</w:docDefaults>",
                   '<w:docDefaults><w:rPrDefault><w:rPr>' + TNR +
                   '<w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="en-US"/>'
                   '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>' + SPACING +
                   '</w:pPr></w:pPrDefault></w:docDefaults>', s, flags=re.S)
        for sid, xml in STYLES.items():
            pattern = rf'<w:style [^>]*w:styleId="{sid}"[^>]*>.*?</w:style>'
            if re.search(pattern, s, flags=re.S):
                s = re.sub(pattern, lambda _m, x=xml: x, s, count=1, flags=re.S)
            else:
                s = s.replace("</w:styles>", xml + "</w:styles>")
        s = s.replace("</w:styles>", SOURCE_CODE + "</w:styles>")
        styles.write_text(s, encoding="utf-8")
        doc = Path(tmp, "word/document.xml")
        d = doc.read_text(encoding="utf-8")
        if "<w:sectPr" in d:
            d = re.sub(r"<w:sectPr\s*/>|<w:sectPr.*?</w:sectPr>", SECT, d,
                       flags=re.S)
        else:
            d = d.replace("</w:body>", SECT + "</w:body>")
        doc.write_text(d, encoding="utf-8")
        if out.exists():
            out.unlink()
        shutil.make_archive(str(out.with_suffix("")), "zip", tmp)
        out.with_suffix(".zip").rename(out)
    default.unlink()
    print("wrote", out)


if __name__ == "__main__":
    main()
