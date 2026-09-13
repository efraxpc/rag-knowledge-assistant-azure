"""Dibuja la arquitectura implementada en cuatro hojas A4 horizontales."""

from __future__ import annotations

import argparse
import runpy
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUTPUT = Path(__file__).resolve().parent
DRAWING = runpy.run_path(str(OUTPUT.parent / "flujo-completo" / "generate.py"))
BaseSheet = DRAWING["Sheet"]
INK = DRAWING["INK"]
BLUE = DRAWING["BLUE"]
LINE = DRAWING["LINE"]
LOCAL = DRAWING["LOCAL"]
CLOUD = DRAWING["CLOUD"]
NOTE = DRAWING["NOTE"]
WHITE = DRAWING["WHITE"]
PAGES = [
    ("01-mapa-general", "Qué hace cada parte"),
    ("02-dentro-de-la-api", "Cómo se organiza la API"),
    ("03-recorrido-pregunta", "Una pregunta, paso a paso"),
    ("04-publicacion-azure", "Cuando la API se publica en Azure"),
]


class ArchitectureSheet(BaseSheet):
    def __init__(self, page: int, subtitle: str) -> None:
        self.page = page
        self.fig = plt.figure(figsize=(297 / 25.4, 210 / 25.4))
        self.ax = self.fig.add_axes((0, 0, 1, 1))
        self.ax.set(xlim=(0, 297), ylim=(210, 0))
        self.ax.axis("off")
        self.ax.plot([15, 282], [12, 12], color=BLUE, linewidth=2)
        self.text(15, 16, "RAG MANUAL  /  ARQUITECTURA EXPLICADA", 267, 9, "bold", BLUE)
        self.text(15, 24, PAGES[page - 1][1], 267, 21, "bold")
        self.text(15, 36, subtitle, 267, 11)
        self.ax.plot([15, 282], [197, 197], color=LINE, linewidth=0.65)
        self.text(
            15,
            201,
            "Arquitectura implementada · 13 septiembre 2026 · A4 horizontal",
            245,
            8.5,
        )
        self.ax.text(
            282, 201, f"{page} / 4", ha="right", va="top", fontsize=9, color=INK
        )

    def group(
        self, x: float, y: float, w: float, h: float, title: str, color: str
    ) -> None:
        self.ax.add_patch(
            FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="round,pad=0,rounding_size=2",
                facecolor=color,
                edgecolor=LINE,
                linestyle=(0, (4, 3)),
                linewidth=0.7,
                zorder=0,
            )
        )
        self.text(x + 4, y + 3, title, w - 8, 9.5, "bold", BLUE)

    def route(
        self,
        points: list[tuple[float, float]],
        *,
        number: str = "",
        badge: tuple[float, float] | None = None,
        both: bool = False,
        dashed: bool = False,
    ) -> None:
        if len(points) > 2:
            xs, ys = zip(*points[:-1], strict=True)
            self.ax.plot(xs, ys, color=LINE, linewidth=1.15, zorder=2)
        self.ax.add_patch(
            FancyArrowPatch(
                points[-2],
                points[-1],
                arrowstyle="<->" if both else "-|>",
                mutation_scale=11,
                linewidth=1.15,
                color=LINE,
                linestyle="--" if dashed else "-",
                shrinkA=1,
                shrinkB=1,
                zorder=2,
            )
        )
        if number and badge:
            self.ax.add_patch(
                Circle(
                    badge, 2.6, facecolor=WHITE, edgecolor=BLUE, linewidth=0.8, zorder=4
                )
            )
            self.ax.text(
                *badge,
                number,
                ha="center",
                va="center",
                fontsize=9,
                fontweight="bold",
                color=BLUE,
                zorder=5,
            )

    def legend(self, left: list[str], right: list[str], y: float = 173) -> None:
        for x, items in [(15, left), (152, right)]:
            for row, item in enumerate(items):
                self.text(x, y + row * 5.3, item, 130, 10)


def overview() -> ArchitectureSheet:
    s = ArchitectureSheet(
        1,
        "Los recuadros muestran las piezas. Los números indican el recorrido; "
        "algunas flechas van y vuelven.",
    )
    s.group(15, 50, 132, 118, "EN TU EQUIPO", LOCAL)
    s.group(162, 50, 120, 118, "EN AZURE", CLOUD)
    s.box(22, 70, 34, 30, "Tú", "Archivo y pregunta", WHITE, size=11)
    s.box(68, 68, 71, 33, "Streamlit", "La pantalla de la home\nlocalhost:8501", WHITE)
    s.box(68, 123, 71, 34, "FastAPI", "La API hace el trabajo\n127.0.0.1:8000", WHITE)
    s.box(
        173,
        65,
        99,
        29,
        "Entra ID",
        "Comprueba tu cuenta y entrega tokens de acceso.",
        WHITE,
    )
    s.box(173, 104, 99, 25, "AI Search", "Guarda y busca partes del texto.", WHITE)
    s.box(
        173, 140, 99, 25, "Azure OpenAI", "Redacta usando el texto encontrado.", WHITE
    )
    s.route([(56, 84), (68, 84)], number="1", badge=(62, 79), both=True)
    s.route([(139, 80), (173, 80)], number="2", badge=(156, 75), both=True)
    s.route([(92, 101), (92, 123)], number="3", badge=(92, 112))
    s.route(
        [(139, 128), (152, 128), (152, 98), (183, 98), (183, 94)],
        number="4",
        badge=(152, 111),
    )
    s.route(
        [(139, 137), (159, 137), (159, 116), (173, 116)], number="5", badge=(159, 130)
    )
    s.route([(139, 151), (173, 151)], number="6", badge=(156, 151), both=True)
    s.route([(117, 123), (117, 101)], number="7", badge=(117, 112))
    s.legend(
        [
            "1 Abres la home.",
            "2 Microsoft comprueba tu cuenta.",
            "3 Envías un archivo o una pregunta.",
            "4 La API pide acceso en tu nombre.",
        ],
        [
            "5 Search guarda o busca texto.",
            "6 OpenAI redacta cuando hay información.",
            "7 El resultado vuelve a la pantalla.",
            "Un token es un comprobante temporal de acceso.",
        ],
    )
    return s


def inside_api() -> ArchitectureSheet:
    s = ArchitectureSheet(
        2,
        "La pantalla envía una petición. La API reparte el trabajo "
        "y se comunica con Azure.",
    )
    s.group(15, 51, 65, 118, "PANTALLA", LOCAL)
    s.group(86, 51, 114, 118, "DENTRO DE FASTAPI", LOCAL)
    s.group(213, 51, 69, 118, "SERVICIOS AZURE", CLOUD)
    s.box(
        21,
        85,
        53,
        45,
        "Streamlit",
        "Envía tu archivo o pregunta y muestra el resultado.",
        WHITE,
    )
    s.box(
        92,
        65,
        102,
        27,
        "Puerta de entrada",
        "Recibe la petición y comprueba tu token.",
        WHITE,
    )
    s.box(
        92,
        102,
        102,
        27,
        "Trabajo principal",
        "Al cargar: prepara texto.\nAl preguntar: busca y responde.",
        WHITE,
    )
    s.box(
        92,
        140,
        102,
        26,
        "Conectores con Azure",
        "Envían el trabajo a cada servicio y recogen su resultado.",
        WHITE,
    )
    s.box(219, 64, 57, 28, "Entra ID", "Comprueba quién pide acceso.", WHITE, size=10.5)
    s.box(219, 102, 57, 28, "AI Search", "Guarda y encuentra texto.", WHITE, size=10.5)
    s.box(219, 140, 57, 26, "Azure OpenAI", "Genera la respuesta.", WHITE, size=10.5)
    s.route([(74, 94), (83, 94), (83, 79), (92, 79)], number="1", badge=(83, 87))
    s.route([(194, 78), (219, 78)], number="2", badge=(206, 78), both=True)
    s.route([(143, 92), (143, 102)], number="3", badge=(143, 97))
    s.route([(143, 129), (143, 140)], number="4", badge=(143, 134.5))
    s.route(
        [(194, 146), (206, 146), (206, 117), (219, 117)], number="5", badge=(206, 133)
    )
    s.route([(194, 158), (219, 158)], number="5", badge=(206, 158), both=True)
    s.route([(92, 154), (82, 154), (82, 118), (74, 118)], number="6", badge=(82, 144))
    s.legend(
        [
            "1 Recibir el archivo o la pregunta.",
            "2 Comprobar el token y pedir acceso.",
            "3 Elegir y realizar el trabajo solicitado.",
        ],
        [
            "4 Preparar las llamadas a Azure.",
            "5 Guardar, buscar o generar según la petición.",
            "6 Entregar el resultado a la pantalla.",
        ],
    )
    s.text(
        15,
        190,
        "La carga guarda texto dividido; la pregunta usa ese texto "
        "como base para la respuesta.",
        267,
        10,
    )
    return s


def question() -> ArchitectureSheet:
    s = ArchitectureSheet(
        3,
        "Lee las flechas de arriba hacia abajo. Cada columna "
        "es una pieza de la arquitectura.",
    )
    s.group(15, 49, 107, 127, "EN TU EQUIPO", LOCAL)
    s.group(128, 49, 154, 127, "EN AZURE", CLOUD)
    columns = [
        (19, "Streamlit", "Tu pantalla"),
        (73, "FastAPI", "Coordina"),
        (132, "Entra ID", "Da acceso"),
        (183, "AI Search", "Busca texto"),
        (234, "OpenAI", "Redacta"),
    ]
    centers = []
    for x, title, body in columns:
        s.box(x, 60, 44, 20, title, body, WHITE, size=10)
        center = x + 22
        centers.append(center)
        s.ax.plot(
            [center, center],
            [80, 173],
            color=LINE,
            linestyle=(0, (2, 3)),
            linewidth=0.7,
        )
    events = [
        (0, 1, "Pregunta + token"),
        (1, 2, "Pide acceso"),
        (2, 1, "Devuelve tokens"),
        (1, 3, "Busca en el documento"),
        (3, 1, "Devuelve partes del texto"),
        (1, 4, "Pregunta + partes encontradas"),
        (4, 1, "Respuesta con fuentes"),
        (1, 0, "Muestra la respuesta"),
    ]
    for index, (source, destination, label) in enumerate(events, start=1):
        y = 88 + (index - 1) * 11.2
        x1, x2 = centers[source], centers[destination]
        s.route(
            [(x1, y), (x2, y)],
            number=str(index),
            badge=(min(x1, x2) + 5, y),
            dashed=source > destination,
        )
        s.text(min(x1, x2) + 11, y - 5, label, abs(x1 - x2) - 12, 9.5)
    s.text(
        15,
        180,
        "En el paso 3, la API obtiene acceso a Search y a OpenAI en tu nombre.",
        267,
        10,
    )
    s.text(
        15,
        187,
        "Si Search no encuentra texto, la API avisa que falta información "
        "y no pide al modelo una respuesta.",
        267,
        10,
    )
    return s


def deployed() -> ArchitectureSheet:
    s = ArchitectureSheet(
        4,
        "La API pasa de tu equipo a un servicio de Azure. "
        "El texto de los documentos sigue en Search.",
    )
    s.group(15, 50, 76, 119, "PREPARAR Y PUBLICAR", LOCAL)
    s.group(104, 50, 178, 119, "EN AZURE", CLOUD)
    s.box(
        21,
        65,
        64,
        38,
        "GitHub Actions",
        "Prueba el código y las respuestas. Publica cuando los controles pasan.",
        WHITE,
        size=11,
    )
    s.box(
        21,
        122,
        64,
        39,
        "Terraform",
        "Crea los recursos y configura sus permisos y conexiones.",
        WHITE,
        size=11,
    )
    s.box(
        113,
        65,
        73,
        37,
        "Container Registry",
        "Guarda la imagen: el paquete con la API lista para ejecutar.",
        WHITE,
        size=11,
    )
    s.box(
        204,
        65,
        69,
        37,
        "Container Apps",
        "Ejecuta FastAPI en Azure y recibe las peticiones.",
        WHITE,
        size=11,
    )
    s.box(
        113,
        130,
        73,
        28,
        "Azure OpenAI",
        "Genera respuestas y permite evaluar su calidad.",
        WHITE,
        size=11,
    )
    s.box(
        204,
        130,
        69,
        28,
        "AI Search",
        "Conserva y busca los fragmentos de documentos.",
        WHITE,
        size=11,
    )
    s.route([(85, 142), (96, 142), (96, 162), (104, 162)], number="1", badge=(96, 151))
    s.route([(85, 83), (113, 83)], number="2", badge=(99, 83))
    s.route([(186, 83), (204, 83)], number="3", badge=(195, 83))
    s.route([(230, 102), (230, 130)], number="4", badge=(230, 122), both=True)
    s.route(
        [(215, 102), (215, 109), (149, 109), (149, 130)], number="4", badge=(149, 121)
    )
    s.legend(
        [
            "1 Terraform prepara y mantiene la infraestructura.",
            "2 GitHub prepara y guarda el paquete aprobado.",
            "3 Container Apps ejecuta la nueva API.",
        ],
        [
            "4 La API usa Search y OpenAI en nombre del usuario.",
            "Streamlit se aloja por separado; apunta a esa API.",
            "Entra mantiene el inicio de sesión y el acceso.",
        ],
    )
    s.text(
        15,
        190,
        "Apoyo de infraestructura: Log Analytics guarda registros "
        "y Key Vault ofrece un almacén de secretos.",
        267,
        9.5,
    )
    return s


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview-dir", type=Path)
    args = parser.parse_args()
    matplotlib.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "figure.facecolor": WHITE,
        }
    )
    vectors = OUTPUT / "hojas"
    vectors.mkdir(exist_ok=True)
    if args.preview_dir:
        args.preview_dir.mkdir(parents=True, exist_ok=True)
    with PdfPages(OUTPUT / "arquitectura-a4.pdf") as pdf:
        pdf.infodict().update(
            {
                "Title": "RAG Manual: arquitectura paso a paso",
                "Author": "RAG Manual",
                "Subject": "Cuatro hojas A4 horizontales",
            }
        )
        for (slug, _), factory in zip(
            PAGES, [overview, inside_api, question, deployed], strict=True
        ):
            sheet = factory()
            pdf.savefig(sheet.fig)
            sheet.fig.savefig(vectors / f"{slug}.svg")
            if args.preview_dir:
                sheet.fig.savefig(args.preview_dir / f"{slug}.png", dpi=150)
            plt.close(sheet.fig)
    sections = "\n".join(
        f'<section><img src="hojas/{slug}.svg" alt="Hoja {index}: {title}"></section>'
        for index, (slug, title) in enumerate(PAGES, start=1)
    )
    html = (
        """<!doctype html>
<html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAG Manual · Arquitectura paso a paso</title>
<style>
body { margin:0; background:#e8ecf0; font-family:system-ui,sans-serif; }
header { max-width:1060px; margin:24px auto; padding:0 16px; }
section { width:297mm; height:210mm; margin:20px auto; background:white; }
img { display:block; width:100%; height:100%; }
@media screen and (max-width:1140px) {
  section { width:100%; height:auto; aspect-ratio:297/210; }
}
@page { size:A4 landscape; margin:0; }
@media print {
  body { background:white; }
  header { display:none; }
  section { margin:0; break-after:page; }
  section:last-child { break-after:auto; }
}
</style>
<header><h1>Arquitectura del proyecto, paso a paso</h1>
<p>Cuatro hojas A4 horizontales. Imprime al 100 %, una página por hoja.</p>
<p><a href="arquitectura-a4.pdf">Abrir el PDF para imprimir</a></p></header>
"""
        + sections
        + "\n</html>\n"
    )
    (OUTPUT / "index.html").write_text(html, encoding="utf-8")
    print(f"Generadas {len(PAGES)} hojas de arquitectura en {OUTPUT}")


if __name__ == "__main__":
    main()
