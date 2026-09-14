"""Renderiza las fuentes Mermaid como ocho hojas A4 horizontales y un PDF."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import NotRequired, TypedDict

from playwright.sync_api import sync_playwright
from pypdf import PdfReader


class Page(TypedDict):
    slug: str
    title: str
    subtitle: str
    continuation: str
    notes: NotRequired[list[str]]


OUTPUT = Path(__file__).resolve().parent
FONT_SIZE = 20
CSS = """
* { box-sizing:border-box; }
body { margin:0; background:#e8ecf0; color:#172c42;
       font-family:Arial,sans-serif; }
.toolbar { max-width:1100px; margin:24px auto; padding:0 12px; }
.sheet { width:297mm; height:210mm; padding:12mm; margin:20px auto;
         background:white; overflow:hidden; }
.sheet-header { height:28mm; border-top:2px solid #24567e; padding-top:2mm; }
.eyebrow { font-size:9pt; color:#24567e; letter-spacing:.5px; }
h1 { margin:2mm 0 1mm; font-size:20pt; line-height:1.1; }
.subtitle { margin:1mm 0; font-size:11pt; line-height:1.25; }
.drawing { width:273mm; height:118mm; }
.drawing > svg { display:block; width:100%; height:100%; max-width:none; }
.notes { height:27mm; display:grid; grid-template-columns:1fr 1fr;
         align-content:center; gap:2mm 7mm; font-size:11pt; line-height:1.25; }
.notes p { margin:0; }
.sheet-footer { height:13mm; border-top:1px solid #8795a1; padding-top:2mm;
                display:flex; gap:8mm; align-items:flex-start; font-size:9pt;
                line-height:1.3; }
.sheet-footer p { margin:0; flex:1; }
.sheet-footer span { white-space:nowrap; }
.sheet-footer a { color:inherit; text-decoration:none; }
@page { size:A4 landscape; margin:0; }
@media print {
  body { background:white; }
  .toolbar { display:none; }
  .sheet { margin:0; break-after:page; }
  .sheet:last-child { break-after:auto; }
}
"""


def find_browser() -> str:
    cache = Path.home() / ".cache/puppeteer/chrome-headless-shell"
    cached = sorted(cache.glob("**/chrome-headless-shell"))
    for browser in cached:
        if browser.is_file():
            return str(browser)
    for name in ("google-chrome", "chromium", "chromium-browser"):
        if browser := shutil.which(name):
            return browser
    raise SystemExit("Instala Chromium o indica su ejecutable con --browser.")


def render_sources(pages: list[Page], browser: str) -> None:
    mermaid = shutil.which("mmdc")
    if mermaid is None:
        raise SystemExit("Falta mmdc: instala @mermaid-js/mermaid-cli.")
    with tempfile.TemporaryDirectory(prefix="rag-langgraph-a4-") as temporary:
        work = Path(temporary)
        config = work / "mermaid.json"
        config.write_text(
            json.dumps(
                {
                    "theme": "base",
                    "themeVariables": {
                        "fontFamily": "DejaVu Sans, Arial, sans-serif",
                        "fontSize": f"{FONT_SIZE}px",
                        "primaryColor": "#eff4f8",
                        "primaryBorderColor": "#526d82",
                        "primaryTextColor": "#172c42",
                        "lineColor": "#62788a",
                        "secondaryColor": "#e6f3ff",
                        "tertiaryColor": "#fff4d8",
                    },
                    "flowchart": {
                        "htmlLabels": True,
                        "nodeSpacing": 16,
                        "rankSpacing": 18,
                        "padding": 6,
                        "diagramPadding": 4,
                        "wrappingWidth": 280,
                    },
                }
            ),
            encoding="utf-8",
        )
        puppeteer = work / "puppeteer.json"
        puppeteer.write_text(
            json.dumps(
                {
                    "executablePath": browser,
                    "args": ["--no-sandbox", "--disable-setuid-sandbox"],
                }
            ),
            encoding="utf-8",
        )
        for page in pages:
            source = OUTPUT / "hojas" / f"{page['slug']}.mmd"
            destination = source.with_suffix(".svg")
            subprocess.run(
                [
                    mermaid,
                    "-q",
                    "-i",
                    str(source),
                    "-o",
                    str(destination),
                    "-c",
                    str(config),
                    "-p",
                    str(puppeteer),
                    "--svgId",
                    f"sheet-{page['slug']}",
                    "-w",
                    "1600",
                ],
                check=True,
            )
            print(f"Renderizada {page['slug']}", flush=True)


def make_html(pages: list[Page]) -> None:
    sections = []
    for number, page in enumerate(pages, 1):
        svg = (OUTPUT / "hojas" / f"{page['slug']}.svg").read_text(encoding="utf-8")
        title = html.escape(page["title"])
        subtitle = html.escape(page["subtitle"])
        continuation = html.escape(page["continuation"])
        source = f"hojas/{page['slug']}.mmd"
        notes = "".join(f"<p>{html.escape(note)}</p>" for note in page.get("notes", []))
        sections.append(
            f'<section class="sheet" id="hoja-{number}">'
            '<div class="sheet-header">'
            '<div class="eyebrow">RAG MANUAL / LANGGRAPH / FLUJO IMPLEMENTADO</div>'
            f'<h1>{title}</h1><p class="subtitle">{subtitle}</p></div>'
            f'<div class="drawing">{svg}</div><div class="notes">{notes}</div>'
            '<footer class="sheet-footer">'
            f"<p>{continuation}</p><span>Hoja {number} / {len(pages)}<br/>"
            f'<a href="{source}">Fuente Mermaid</a> · A4 horizontal</span>'
            "</footer></section>"
        )
    document = (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>LangGraph · Ocho hojas A4</title><style>{CSS}</style></head>"
        '<body><div class="toolbar"><h2>Flujo de LangGraph en ocho hojas</h2>'
        "<p>Imprime en A4 horizontal, al 100 %, sin encabezados del navegador.</p>"
        '<p><a href="langgraph-a4.pdf">PDF para imprimir</a> · '
        '<a href="README.md">Índice y fuentes</a> · '
        '<a href="../../langgraph-flujo-explicado.mmd">Diagrama completo</a></p>'
        "</div>" + "\n".join(sections) + "</body></html>"
    )
    (OUTPUT / "index.html").write_text(document, encoding="utf-8")


def print_pdf(browser: str, preview_dir: Path | None) -> None:
    with sync_playwright() as playwright:
        chromium = playwright.chromium.launch(
            executable_path=browser, args=["--no-sandbox"]
        )
        page = chromium.new_page(viewport={"width": 1300, "height": 900})
        page.goto((OUTPUT / "index.html").as_uri())
        page.emulate_media(media="print")
        page.evaluate("document.fonts.ready")
        if preview_dir:
            preview_dir.mkdir(parents=True, exist_ok=True)
            for number, section in enumerate(page.locator(".sheet").all(), 1):
                section.screenshot(path=str(preview_dir / f"hoja-{number:02}.png"))
        # Comprobar que al ajustar cada SVG la letra siga siendo imprimible.
        sizes = page.evaluate(
            """() => [...document.querySelectorAll('.drawing')].map(box => {
                const svg = box.querySelector('svg');
                const view = svg.viewBox.baseVal;
                return Math.min(box.clientWidth / view.width,
                                box.clientHeight / view.height);
            })"""
        )
        unreadable = []
        for number, scale in enumerate(sizes, 1):
            points = FONT_SIZE * scale * 72 / 96
            if points < 10:
                unreadable.append(str(number))
            print(f"Hoja {number}: letra efectiva {points:.1f} pt", flush=True)
        if unreadable:
            raise ValueError(
                f"Simplifica las hojas {', '.join(unreadable)} "
                "para alcanzar una letra efectiva de 10 pt."
            )
        page.pdf(
            path=str(OUTPUT / "langgraph-a4.pdf"),
            format="A4",
            landscape=True,
            print_background=True,
            prefer_css_page_size=True,
        )
        chromium.close()
    reader = PdfReader(OUTPUT / "langgraph-a4.pdf")
    if len(reader.pages) != 8:
        raise ValueError(f"Se esperaban ocho páginas, se generaron {len(reader.pages)}")
    for page in reader.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if abs(width - 841.89) > 1 or abs(height - 595.28) > 1:
            raise ValueError("Una página no tiene tamaño A4 horizontal")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", help="Ejecutable de Chromium o Chrome")
    parser.add_argument("--preview-dir", type=Path)
    args = parser.parse_args()
    pages = json.loads((OUTPUT / "pages.json").read_text(encoding="utf-8"))
    if len(pages) != 8:
        raise ValueError("El índice debe contener ocho hojas")
    browser = args.browser or find_browser()
    render_sources(pages, browser)
    make_html(pages)
    print_pdf(browser, args.preview_dir)
    print(f"Generado {OUTPUT / 'langgraph-a4.pdf'}")


if __name__ == "__main__":
    main()
