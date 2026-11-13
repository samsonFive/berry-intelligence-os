"""Export a curated variety profile as self-contained HTML and optional PDF.

This authoring tool intentionally supports the small Markdown subset documented
in reports/README.md. It does not call research services or write trust records.
"""

from __future__ import annotations

import argparse
import base64
import html
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlsplit


STYLE_PATH = Path(__file__).resolve().parents[1] / "reports/templates/variety-commercial-profile.css"
REFERENCE_DEFINITION = re.compile(r"^\[(R\d+)\]:\s+(\S+)\s*$", re.M)


def _external_url(value: str) -> str:
    parsed = urlsplit(html.unescape(value))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Source links must be HTTP or HTTPS URLs: {value!r}")
    return html.escape(html.unescape(value), quote=True)


def _link(label: str, url: str, *, css: str = "", title: str = "") -> str:
    attributes = f' class="{css}"' if css else ""
    attributes += f' title="{html.escape(title, quote=True)}"' if title else ""
    return f'<a{attributes} href="{_external_url(url)}" target="_blank" rel="noopener noreferrer">{label}</a>'


def render_html(source: Path) -> tuple[str, str]:
    source = source.resolve()
    text = source.read_text(encoding="utf-8")
    references = dict(REFERENCE_DEFINITION.findall(text))
    for url in references.values():
        _external_url(url)
    heading = re.search(r"^# (.+)$", text, re.M)
    if not heading:
        raise ValueError("The report needs a level-one title.")
    title = heading[1].strip()

    def inline(value: str) -> str:
        value = html.escape(value)

        def picture(match: re.Match[str]) -> str:
            name, relative = match.groups()
            relative = html.unescape(relative)
            if Path(relative).is_absolute():
                raise ValueError("Image paths must be relative to the report.")
            path = (source.parent / relative).resolve()
            if not path.is_relative_to(source.parent):
                raise ValueError("Images must remain within the report directory tree.")
            mime = mimetypes.guess_type(path.name)[0]
            if mime not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
                raise ValueError(f"Unsupported image format: {path.name}")
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            return f'<img alt="{name}" src="data:{mime};base64,{encoded}">'

        value = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", picture, value)
        value = re.sub(
            r"\[(<img[^>]+>)\]\[(R\d+)\]",
            lambda match: _link(match[1], references[match[2]], css="video-image"),
            value,
        )

        def reference(match: re.Match[str]) -> str:
            label, key = match.groups()
            if re.fullmatch(r"\d+(?:[–,\-]\d+)*", label):
                numbers = []
                for part in label.split(","):
                    span = re.split("[–-]", part)
                    numbers.extend(range(int(span[0]), int(span[-1]) + 1))
                links = [
                    _link(str(number), references[f"R{number:02d}"], css="cite", title=f"Open source {number}")
                    for number in numbers
                ]
                return '<span class="cite-group">' + ",".join(links) + "</span>"
            return _link(label, references[key])

        value = re.sub(r"\[([^\]]+)\]\[(R\d+)\]", reference, value)
        value = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", lambda match: _link(match[1], match[2]), value)
        value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
        return re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", value)

    lines = text.splitlines()
    body = ['<section class="report-page">']
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if line == "<!-- page -->":
            body.append('</section><section class="report-page">')
            index += 1
            continue
        if not line or REFERENCE_DEFINITION.fullmatch(line):
            index += 1
            continue
        if line.startswith("|"):
            block = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                block.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
                index += 1
            if len(block) < 2 or not all(re.fullmatch(r":?-+:?", cell) for cell in block[1]):
                raise ValueError("Tables need a header separator row.")
            rows = ["<thead><tr>" + "".join(f"<th>{inline(cell)}</th>" for cell in block[0]) + "</tr></thead><tbody>"]
            for cells in block[2:]:
                if len(cells) != len(block[0]):
                    raise ValueError("Every table row must have the same number of cells.")
                rows.append("<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in cells) + "</tr>")
            body.append('<div class="table-wrap"><table>' + "".join(rows) + "</tbody></table></div>")
            continue
        heading = re.match(r"^(#{1,3}) (.+)", line)
        if heading:
            level = len(heading[1])
            css = ' class="research-heading"' if heading[2] == "Sources and research links" else ""
            body.append(f"<h{level}{css}>{inline(heading[2])}</h{level}>")
            index += 1
            continue
        if line.startswith("- ") or re.match(r"^\d+\. ", line):
            ordered = not line.startswith("- ")
            tag = "ol" if ordered else "ul"
            items = []
            pattern = r"^\d+\. (.+)" if ordered else r"^- (.+)"
            while index < len(lines):
                match = re.match(pattern, lines[index].strip())
                if not match:
                    break
                items.append("<li>" + inline(match[1]) + "</li>")
                index += 1
            body.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        paragraph = [line]
        index += 1
        while index < len(lines):
            following = lines[index].strip()
            if not following or following.startswith(("#", "|", "- ", "<!--", "[R")) or re.match(r"^\d+\. ", following):
                break
            paragraph.append(following)
            index += 1
        body.append("<p>" + inline(" ".join(paragraph)) + "</p>")
    body.append("</section>")
    style = STYLE_PATH.read_text(encoding="utf-8")
    result = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)} | Variety and commercial profile</title>"
        f"<style>{style}</style></head><body><main>" + "\n".join(body) + "</main></body></html>"
    )
    return result, title


def export_pdf(html_path: Path, pdf_path: Path, title: str) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("PDF export requires locally installed Playwright and Chromium; no dependencies were installed.") from exc
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    footer = (
        '<div style="font:8px Arial;color:#6b746e;width:100%;text-align:right;margin-right:18mm">'
        f'{html.escape(title)} · <span class="pageNumber"></span> / <span class="totalPages"></span></div>'
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, timeout=20000)
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.route(re.compile(r"^https?://"), lambda route: route.abort())
            page.goto(html_path.resolve().as_uri())
            page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
            page.pdf(
                path=str(pdf_path), format="A4", print_background=True,
                prefer_css_page_size=True, display_header_footer=True,
                header_template="<span></span>", footer_template=footer,
            )
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Curated Markdown report")
    parser.add_argument("--html", type=Path, help="Self-contained HTML destination (defaults beside source)")
    parser.add_argument("--pdf", type=Path, help="Optional PDF destination")
    args = parser.parse_args()
    html_path = args.html or args.source.with_suffix(".html")
    if html_path.resolve() == args.source.resolve() or (args.pdf and args.pdf.resolve() in {args.source.resolve(), html_path.resolve()}):
        parser.error("Source, HTML, and PDF paths must be distinct.")
    try:
        document, title = render_html(args.source)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(document, encoding="utf-8")
        print(f"HTML: {html_path}")
        if args.pdf:
            export_pdf(html_path, args.pdf, title)
            print(f"PDF: {args.pdf}")
    except (OSError, KeyError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Report export failed: {exc}\n")


if __name__ == "__main__":
    main()
