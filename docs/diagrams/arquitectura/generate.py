"""Dibuja el flujo de la aplicación y las partes de Azure en cinco hojas A4."""

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
INK, BLUE, LINE = (DRAWING[key] for key in ("INK", "BLUE", "LINE"))
LOCAL, CLOUD, NOTE, WHITE = (
    DRAWING[key] for key in ("LOCAL", "CLOUD", "NOTE", "WHITE")
)
PAGES = [
    ("01-flujo-completo", "El recorrido completo de la aplicación"),
    ("02-iniciar-sesion", "Primero: entrar y llegar a la home"),
    ("03-guardar-documento", "Después: subir y guardar el documento"),
    ("04-preguntar", "Ahora: preguntar y recibir una respuesta"),
    ("05-partes-azure", "Qué hace cada parte de Azure"),
]


class ArchitectureSheet(BaseSheet):
    def __init__(self, page: int, subtitle: str) -> None:
        self.page = page
        self.fig = plt.figure(figsize=(297 / 25.4, 210 / 25.4))
        self.ax = self.fig.add_axes((0, 0, 1, 1))
        self.ax.set(xlim=(0, 297), ylim=(210, 0))
        self.ax.axis("off")
        self.ax.plot([15, 282], [12, 12], color=BLUE, linewidth=2)
        self.text(
            15,
            16,
            "RAG MANUAL  /  FLUJO DE LA APLICACIÓN Y AZURE",
            267,
            9,
            "bold",
            BLUE,
        )
        self.text(15, 24, PAGES[page - 1][1], 267, 20, "bold")
        self.text(15, 36, subtitle, 267, 11)
        self.ax.plot([15, 282], [197, 197], color=LINE, linewidth=0.65)
        self.text(
            15, 201, "Flujo implementado · 13 septiembre 2026 · A4 horizontal", 245, 8.5
        )
        self.ax.text(
            282,
            201,
            f"{page} / {len(PAGES)}",
            ha="right",
            va="top",
            fontsize=9,
            color=INK,
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
        self.text(x + 4, y + 3, title, w - 8, 9, "bold", BLUE)

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
            self.ax.plot(
                xs,
                ys,
                color=LINE,
                linewidth=1.1,
                linestyle="--" if dashed else "-",
                zorder=2,
            )
        self.ax.add_patch(
            FancyArrowPatch(
                points[-2],
                points[-1],
                arrowstyle="<->" if both else "-|>",
                mutation_scale=10,
                linewidth=1.1,
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
                    badge,
                    2.3,
                    facecolor=WHITE,
                    edgecolor=BLUE,
                    linewidth=0.8,
                    zorder=4,
                )
            )
            self.ax.text(
                *badge,
                number,
                ha="center",
                va="center",
                fontsize=8.3,
                fontweight="bold",
                color=BLUE,
                zorder=5,
            )

    def step(
        self,
        number: int,
        y: float,
        title: str,
        body: str,
        *,
        azure: bool = False,
        h: float = 20,
    ) -> None:
        self.ax.add_patch(
            FancyBboxPatch(
                (24, y),
                175,
                h,
                boxstyle="round,pad=0,rounding_size=2",
                facecolor=CLOUD if azure else LOCAL,
                edgecolor=LINE,
                linewidth=0.8,
            )
        )
        self.ax.add_patch(
            Circle(
                (24, y + h / 2),
                3.7,
                facecolor=WHITE,
                edgecolor=BLUE,
                linewidth=0.8,
            )
        )
        self.ax.text(
            24,
            y + h / 2,
            str(number),
            ha="center",
            va="center",
            fontsize=11,
            fontweight="bold",
            color=BLUE,
        )
        self.text(31, y + 2.2, title, 163, 11, "bold", max_height=5.2)
        self.text(31, y + 8.2, body, 163, 10.5, max_height=h - 9.1)

    def role(self, y: float, h: float, title: str, body: str) -> None:
        self.box(211, y, 71, h, title, body, CLOUD, size=10.5)


def overview() -> ArchitectureSheet:
    s = ArchitectureSheet(
        1, "Lee de arriba hacia abajo: entras, guardas un documento y preguntas."
    )
    s.group(15, 49, 107, 142, "EN TU EQUIPO", LOCAL)
    s.group(128, 49, 154, 142, "SERVICIOS DE AZURE", CLOUD)
    columns = [
        (19, "Streamlit", "Tu pantalla"),
        (73, "FastAPI", "Coordina todo"),
        (132, "Entra ID", "Da acceso"),
        (183, "AI Search", "Guarda y busca"),
        (234, "OpenAI", "Redacta"),
    ]
    centers = []
    for x, title, body in columns:
        s.box(x, 60, 44, 23, title, body, WHITE, size=9.5)
        center = x + 22
        centers.append(center)
        s.ax.plot(
            [center, center],
            [83, 189],
            color=LINE,
            linestyle=(0, (2, 3)),
            linewidth=0.65,
            zorder=1,
        )
    events = [
        (0, 2, "Inicias sesión", False),
        (2, 0, "Acceso; vuelves a la home", False),
        (0, 1, "Archivo + token", False),
        (1, 2, "Acceso a Search", True),
        (1, 3, "Guarda el texto dividido", False),
        (3, 1, "Confirma guardado", False),
        (1, 0, "Documento listo", False),
        (0, 1, "Pregunta + token", False),
        (1, 2, "Acceso a Search y OpenAI", True),
        (1, 3, "Busca y recibe partes del texto", True),
        (1, 4, "Envía pregunta + texto; recibe respuesta", True),
        (1, 0, "Respuesta y fuentes", False),
    ]
    for index, (source, destination, label, both) in enumerate(events, 1):
        y = 89 + (index - 1) * 8.7
        x1, x2 = centers[source], centers[destination]
        s.route(
            [(x1, y), (x2, y)],
            number=str(index),
            badge=(min(x1, x2) + 4, y),
            both=both,
            dashed=source > destination,
        )
        s.text(min(x1, x2) + 9, y - 4.5, label, abs(x1 - x2) - 10, 9)
    s.text(
        15,
        192,
        "Flecha doble: envío y regreso. Token: pase temporal. "
        "La API lleva el texto de Search a OpenAI.",
        267,
        9,
    )
    return s


def login() -> ArchitectureSheet:
    s = ArchitectureSheet(
        2, "Azure comprueba quién eres. La pantalla abre la home para subir documentos."
    )
    items = [
        (
            "Streamlit: abres la pantalla",
            "Entras en localhost:8501 y pulsas Iniciar sesión con Microsoft.",
            False,
        ),
        (
            "Microsoft Entra ID: comprueba tu cuenta",
            "Inicias sesión con una cuenta admitida en el directorio del proyecto.",
            True,
        ),
        (
            "Streamlit + Entra ID: preparan el acceso a la API",
            "La pantalla obtiene un token: un pase temporal destinado a FastAPI.",
            True,
        ),
        (
            "Streamlit: muestra la home",
            "Vuelves a la página principal, donde aparece Subir documentos.",
            False,
        ),
    ]
    for index, (title, body, azure) in enumerate(items, 1):
        y = 58 + (index - 1) * 32
        s.step(index, y, title, body, azure=azure, h=25)
        if index < len(items):
            s.route([(111.5, y + 25), (111.5, y + 32)])
    s.role(
        58,
        46,
        "Microsoft Entra ID",
        "Es la puerta de acceso de Microsoft. Comprueba tu identidad "
        "y entrega pases para las aplicaciones.",
    )
    s.box(
        211,
        113,
        71,
        38,
        "El pase para la API",
        "La pantalla lo envía al cargar un archivo o hacer una pregunta.",
        NOTE,
        size=10.5,
    )
    s.box(
        211,
        160,
        71,
        32,
        "Permisos del usuario",
        "Search y OpenAI comprueban qué puedes hacer en cada recurso.",
        NOTE,
        size=10.5,
    )
    s.text(
        24,
        186,
        "Resultado: ya estás en la home. Continúa con la hoja 3.",
        175,
        10,
        "bold",
    )
    return s


def upload() -> ArchitectureSheet:
    s = ArchitectureSheet(
        3, "El archivo pasa por la API; su texto queda guardado en Azure AI Search."
    )
    items = [
        (
            "Streamlit → FastAPI: envía el documento",
            "Eliges el archivo y pulsas Procesar y guardar. Viaja junto al token.",
            False,
        ),
        (
            "FastAPI: comprueba el acceso",
            "Valida que el pase sea correcto y que la petición venga de la pantalla.",
            False,
        ),
        (
            "Microsoft Entra ID: da acceso a Search",
            "La API pide otro pase, válido para usar Search en tu nombre.",
            True,
        ),
        (
            "FastAPI: prepara el texto",
            "Lee el archivo y lo divide en partes con el nombre "
            "del documento y la página cuando existe.",
            False,
        ),
        (
            "Azure AI Search: guarda las partes",
            "Comprueba tus permisos y almacena el texto para poder buscarlo después.",
            True,
        ),
        (
            "FastAPI → Streamlit: confirma la carga",
            "Ves el documento procesado y puedes empezar a preguntar sobre él.",
            False,
        ),
    ]
    for index, (title, body, azure) in enumerate(items, 1):
        y = 52 + (index - 1) * 24
        s.step(index, y, title, body, azure=azure)
        if index < len(items):
            s.route([(111.5, y + 20), (111.5, y + 24)])
    s.role(
        52,
        42,
        "Microsoft Entra ID",
        "Entrega el pase de Search. La API actúa con los permisos "
        "de tu cuenta o grupo.",
    )
    s.role(
        103,
        43,
        "Azure AI Search",
        "Es el almacén y buscador del texto. Conserva las partes, "
        "el nombre del archivo y la página cuando existe.",
    )
    s.box(
        211,
        155,
        71,
        37,
        "Qué se guarda",
        "Texto dividido, no el archivo original. PDF con texto, TXT "
        "o Markdown; hasta 10 MiB.",
        NOTE,
        size=10.5,
    )
    return s


def question() -> ArchitectureSheet:
    s = ArchitectureSheet(
        4,
        "La API busca información primero y entrega ese texto "
        "al modelo para responder.",
    )
    items = [
        (
            "Streamlit → FastAPI: envía tu pregunta",
            "La API recibe pregunta, referencia del documento y token. "
            "Comprueba el acceso.",
            False,
        ),
        (
            "Microsoft Entra ID: da dos pases",
            "La API obtiene acceso a Search y a Azure OpenAI, siempre en tu nombre.",
            True,
        ),
        (
            "Azure AI Search: busca en el documento",
            "Recibe la consulta de la API y le devuelve "
            "hasta cinco partes relacionadas.",
            True,
        ),
        (
            "FastAPI: revisa lo encontrado",
            "Con texto, prepara la pregunta y sus fuentes. "
            "Sin texto, salta al paso 6 con un aviso.",
            False,
        ),
        (
            "Azure OpenAI: redacta la respuesta",
            "La API le envía pregunta y partes del texto; "
            "le pide responder usando esas fuentes.",
            True,
        ),
        (
            "FastAPI → Streamlit: muestra el resultado",
            "Ves la respuesta y sus fuentes, o el aviso de información insuficiente.",
            False,
        ),
    ]
    for index, (title, body, azure) in enumerate(items, 1):
        y = 52 + (index - 1) * 24
        s.step(index, y, title, body, azure=azure)
        if index < len(items):
            s.route([(111.5, y + 20), (111.5, y + 24)])
    s.route([(24, 137), (16, 137), (16, 182), (20, 182)], dashed=True)
    s.role(
        52,
        32,
        "Microsoft Entra ID",
        "Entrega un pase para Search y otro para OpenAI.",
    )
    s.role(
        93,
        35,
        "Azure AI Search",
        "Encuentra texto útil. Lo devuelve a la API, "
        "que prepara la consulta al modelo.",
    )
    s.role(
        137,
        35,
        "Azure OpenAI",
        "Es el redactor. Recibe las partes elegidas y genera una respuesta.",
    )
    s.text(
        211,
        178,
        "Cognitive Services es el nombre del permiso para OpenAI; no añade otro paso.",
        71,
        10,
        max_height=16,
    )
    return s


def azure_parts() -> ArchitectureSheet:
    s = ArchitectureSheet(
        5, "Cada pieza tiene un trabajo. Estas son las que usa o prepara el proyecto."
    )
    s.text(15, 49, "AL ENTRAR, CARGAR Y PREGUNTAR", 130, 9.5, "bold", BLUE)
    s.text(152, 49, "AL EJECUTAR LA API PUBLICADA EN AZURE", 130, 9.5, "bold", BLUE)
    cards = [
        (
            15,
            59,
            "Microsoft Entra ID",
            "Comprueba tu identidad y entrega pases. Actúa al iniciar sesión "
            "y cuando la API pide acceso a Search u OpenAI.",
            CLOUD,
        ),
        (
            15,
            94,
            "Azure AI Search",
            "Guarda partes del documento durante la carga. Al preguntar, "
            "busca texto relacionado y lo devuelve a la API.",
            CLOUD,
        ),
        (
            15,
            129,
            "Azure OpenAI",
            "El modelo de chat redacta con el texto que envía la API. "
            "También se usa otro modelo para evaluar calidad antes de publicar.",
            CLOUD,
        ),
        (
            15,
            164,
            "FastAPI: quien une las piezas",
            "En local corre en tu equipo; publicada, en Container Apps. "
            "Lleva las peticiones y los resultados entre pantalla y Azure.",
            LOCAL,
        ),
        (
            152,
            59,
            "Azure Container Apps",
            "Ejecuta la API en Azure y recibe las peticiones de la pantalla. "
            "Streamlit necesita alojamiento por separado.",
            CLOUD,
        ),
        (
            152,
            94,
            "Azure Container Registry",
            "Guarda el paquete de la API, llamado imagen. "
            "Container Apps lo descarga para ejecutar esa versión.",
            CLOUD,
        ),
        (
            152,
            129,
            "Azure Log Analytics",
            "Recoge registros del entorno de Container Apps. "
            "Sirven para revisar qué ocurrió cuando hay un problema.",
            CLOUD,
        ),
        (
            152,
            164,
            "Azure Key Vault",
            "Es un almacén de secretos preparado por Terraform. "
            "La API actual todavía no lo consulta directamente.",
            CLOUD,
        ),
    ]
    for x, y, title, body, color in cards:
        s.box(x, y, 130, 29, title, body, color, size=10.5)
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
                "Title": "RAG Manual: flujo completo de la aplicación y Azure",
                "Author": "RAG Manual",
                "Subject": "Cinco hojas A4 horizontales",
            }
        )
        for (slug, _), factory in zip(
            PAGES, [overview, login, upload, question, azure_parts], strict=True
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
<title>RAG Manual · Flujo de la aplicación y Azure</title>
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
<header><h1>El flujo de la aplicación y sus partes de Azure</h1>
<p>Cinco hojas A4 horizontales. Sigue los pasos desde la entrada hasta la respuesta.</p>
<p>Imprime al 100 %, una página por hoja, sin encabezados del navegador.</p>
<p><a href="arquitectura-a4.pdf">Abrir el PDF para imprimir</a></p></header>
"""
        + sections
        + "\n</html>\n"
    )
    (OUTPUT / "index.html").write_text(html, encoding="utf-8")
    print(f"Generadas {len(PAGES)} hojas del flujo de la aplicación en {OUTPUT}")


if __name__ == "__main__":
    main()
