"""Genera ocho hojas A4 del flujo real del proyecto (requiere Matplotlib)."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402
from matplotlib.textpath import TextToPath  # noqa: E402

OUTPUT = Path(__file__).resolve().parent
INK = "#172C42"
MUTED = "#405569"
BLUE = "#24567E"
LINE = "#62788A"
LOCAL = "#EFF4F8"
CLOUD = "#EDF6F2"
NOTE = "#FFF7E8"
WHITE = "#FFFFFF"
TEXT = TextToPath()
PAGES = [
    ("01-vista-general", "El recorrido completo"),
    ("02-preparacion", "Antes de empezar"),
    ("03-iniciar-sesion", "Entrar con Microsoft"),
    ("04-subir-documentos", "Guardar un documento"),
    ("05-hacer-preguntas", "Hacer una pregunta"),
    ("06-tokens-permisos", "Qué permite cada token"),
    ("07-resolver-errores", "Si algo falla"),
    ("08-publicar-version", "Publicar una nueva versión"),
]


def wrapped(text: str, width: float, size: float, weight: str) -> list[str]:
    prop = FontProperties(family="DejaVu Sans", size=size, weight=weight)
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            points, _, _ = TEXT.get_text_width_height_descent(candidate, prop, False)
            if current and points * 25.4 / 72 > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines


class Sheet:
    def __init__(self, page: int, subtitle: str) -> None:
        self.page = page
        self.fig = plt.figure(figsize=(210 / 25.4, 297 / 25.4))
        self.ax = self.fig.add_axes((0, 0, 1, 1))
        self.ax.set(xlim=(0, 210), ylim=(297, 0))
        self.ax.axis("off")
        self.ax.plot([17, 193], [13, 13], color=BLUE, linewidth=2)
        self.text(17, 17, "RAG MANUAL  /  GUÍA PARA IMPRIMIR", 176, 9, "bold", BLUE)
        self.text(17, 25, PAGES[page - 1][1], 176, 22, "bold")
        self.text(17, 38, subtitle, 176, 11)
        self.ax.plot([17, 193], [280, 280], color=LINE, linewidth=0.65)
        self.text(
            17, 284, "Flujo del proyecto · 13 septiembre 2026 · A4 vertical", 149, 9
        )
        self.ax.text(
            193, 284, f"{page} / 8", ha="right", va="top", fontsize=10, color=INK
        )

    def text(
        self,
        x: float,
        y: float,
        content: str,
        width: float,
        size: float = 11.5,
        weight: str = "normal",
        color: str = INK,
        max_height: float | None = None,
    ) -> float:
        lines = wrapped(content, width, size, weight)
        height = len(lines) * size * 0.46
        if max_height is not None and height > max_height:
            raise ValueError(f"Hoja {self.page}: texto demasiado alto: {content}")
        self.ax.text(
            x,
            y,
            "\n".join(lines),
            va="top",
            ha="left",
            fontsize=size,
            fontweight=weight,
            color=color,
            linespacing=1.3,
        )
        return height

    def box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        body: str,
        color: str = LOCAL,
        number: str = "",
        size: float = 11.5,
    ) -> None:
        self.ax.add_patch(
            FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="round,pad=0,rounding_size=2",
                facecolor=color,
                edgecolor=LINE,
                linewidth=0.8,
            )
        )
        left = x + 5
        if number:
            self.ax.text(
                x + 5,
                y + 5,
                number,
                fontsize=12,
                fontweight="bold",
                color=BLUE,
                va="top",
            )
            left += 10
        available = w - (left - x) - 5
        title_height = self.text(left, y + 4, title, available, 12.5, "bold")
        self.text(
            left,
            y + 5 + title_height,
            body,
            available,
            size,
            max_height=h - title_height - 8,
        )

    def arrow(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        label: str = "",
        label_x: float | None = None,
        label_y: float | None = None,
    ) -> None:
        self.ax.add_patch(
            FancyArrowPatch(
                (x1, y1),
                (x2, y2),
                arrowstyle="-|>",
                mutation_scale=11,
                linewidth=1.15,
                color=LINE,
                shrinkA=1,
                shrinkB=1,
            )
        )
        if label:
            self.text(
                label_x if label_x is not None else x1 + 3,
                label_y if label_y is not None else (y1 + y2) / 2 - 2,
                label,
                60,
                10,
                "bold",
                BLUE,
            )

    def note(self, y: float, title: str, body: str, height: float = 24) -> None:
        self.box(17, y, 176, height, title, body, NOTE, size=10.5)

    def steps(self, items: list[tuple[str, str, str]], y: float = 55) -> float:
        for index, (title, body, location) in enumerate(items):
            self.box(
                17,
                y,
                176,
                26,
                title,
                body,
                CLOUD if location == "azure" else LOCAL,
                str(index + 1),
            )
            if index < len(items) - 1:
                self.arrow(105, y + 26, 105, y + 34)
            y += 34
        return y - 8

    def decision(self, x: float, y: float, w: float, h: float, title: str) -> None:
        self.ax.add_patch(
            Polygon(
                [
                    (x + w / 2, y),
                    (x + w, y + h / 2),
                    (x + w / 2, y + h),
                    (x, y + h / 2),
                ],
                facecolor=WHITE,
                edgecolor=LINE,
                linewidth=1,
            )
        )
        self.ax.text(
            x + w / 2,
            y + h / 2,
            title,
            ha="center",
            va="center",
            fontsize=11.5,
            fontweight="bold",
            color=INK,
        )


def overview() -> Sheet:
    s = Sheet(
        1, "Objetivo: encontrar información en tus documentos y responder con fuentes."
    )
    s.steps(
        [
            (
                "Abres la página en tu equipo",
                "Streamlit es la pantalla que usas en el navegador.",
                "local",
            ),
            (
                "Microsoft comprueba quién eres",
                "Entra ID permite entrar con una cuenta autorizada. Ver hoja 3.",
                "azure",
            ),
            (
                "Subes un documento",
                (
                    "FastAPI es la API: el programa que recibe el archivo y prepara "
                    "su texto."
                ),
                "local",
            ),
            (
                "Azure guarda los fragmentos",
                "AI Search almacena partes del texto para encontrarlas después.",
                "azure",
            ),
            (
                "Escribes una pregunta",
                "La API busca hasta cinco fragmentos del documento seleccionado.",
                "local",
            ),
            (
                "Lees una respuesta con fuentes",
                "Azure OpenAI redacta la respuesta; la página te la muestra.",
                "azure",
            ),
        ]
    )
    s.note(
        254,
        "Local y nube trabajan juntos",
        (
            "La pantalla y la API corren en tu equipo. Identidad, búsqueda y "
            "modelo están en Azure."
        ),
        24,
    )
    return s


def preparation() -> Sheet:
    s = Sheet(
        2, "Se prepara al configurar el proyecto. Después puedes usarlo cada día."
    )
    s.steps(
        [
            (
                "El administrador prepara Azure",
                (
                    "Prepara la búsqueda, un espacio para guardar texto y un modelo "
                    "listo para responder."
                ),
                "azure",
            ),
            (
                "Registra dos aplicaciones",
                (
                    "Una identifica a Streamlit y otra a FastAPI. Cada una tiene su "
                    "propia contraseña, llamada secreto."
                ),
                "azure",
            ),
            (
                "Da acceso a las personas",
                (
                    "La cuenta debe pertenecer al directorio de Entra o aceptar una "
                    "invitación."
                ),
                "azure",
            ),
            (
                "Autoriza a la API y al usuario",
                (
                    "Permite que la API actúe en tu nombre y que tu cuenta use la "
                    "búsqueda y el modelo."
                ),
                "azure",
            ),
            (
                "Configura y arranca tu equipo",
                (
                    "Completa .env y .streamlit/secrets.toml. Ejecuta "
                    "./scripts/run_local.sh."
                ),
                "local",
            ),
        ]
    )
    s.box(
        17,
        230,
        176,
        43,
        "Permisos que usa este proyecto",
        (
            "Para documentos: Search Index Data Contributor.\nPara "
            "respuestas: Cognitive Services OpenAI User.\nAbre "
            "http://localhost:8501 para empezar."
        ),
        NOTE,
        size=11,
    )
    return s


def login() -> Sheet:
    s = Sheet(
        3,
        "El resultado esperado es volver a la home con la sección «Subir documentos».",
    )
    s.steps(
        [
            (
                "Pulsas «Iniciar sesión con Microsoft»",
                "La página te lleva al inicio de sesión de Microsoft.",
                "local",
            ),
            (
                "Entra ID comprueba tu cuenta",
                (
                    "Inicias sesión y completas las verificaciones que pida tu "
                    "organización."
                ),
                "azure",
            ),
            (
                "Microsoft devuelve un código temporal",
                "El navegador vuelve a localhost:8501/oauth2callback.",
                "azure",
            ),
            (
                "Streamlit intercambia ese código",
                (
                    "Usa su propio secreto para recibir la identidad y un token para "
                    "FastAPI."
                ),
                "local",
            ),
            (
                "La sesión queda reconocida",
                (
                    "El navegador guarda una cookie para recordar tu sesión. "
                    "Streamlit conserva el acceso al token."
                ),
                "local",
            ),
            (
                "Se abre la home del proyecto",
                "Con una sesión y un token disponibles, aparece «Subir documentos».",
                "local",
            ),
        ]
    )
    s.note(
        254,
        "Token = comprobante temporal de acceso",
        "La API revisará el token en cada carga y cada pregunta. Ver hojas 4, 5 y 6.",
        24,
    )
    return s


def upload() -> Sheet:
    s = Sheet(
        4, "Seleccionar el archivo no lo guarda: debes pulsar «Procesar y guardar»."
    )
    s.steps(
        [
            (
                "Seleccionas PDF, TXT o Markdown",
                (
                    "El archivo puede pesar hasta 10 MiB. El PDF debe contener texto "
                    "seleccionable."
                ),
                "local",
            ),
            (
                "Pulsas «Procesar y guardar»",
                "Streamlit envía a FastAPI el archivo y tu token de acceso.",
                "local",
            ),
            (
                "La API comprueba el acceso",
                (
                    "Valida tu token y pide a Entra acceso a Search en tu nombre. "
                    "Ver hoja 6."
                ),
                "local",
            ),
            (
                "La API prepara el texto",
                (
                    "Extrae el texto y lo divide en partes pequeñas que repiten un "
                    "poco de texto para mantener el contexto."
                ),
                "local",
            ),
            (
                "Search guarda los fragmentos",
                "Cada parte conserva el nombre del documento y, si existe, su página.",
                "azure",
            ),
            (
                "La home confirma el resultado",
                "Ves cuántos fragmentos se guardaron. Ya puedes hacer una pregunta.",
                "local",
            ),
        ]
    )
    s.note(
        254,
        "Qué se almacena",
        (
            "Se guardan partes del texto. El original no se conserva; los "
            "escaneos no se convierten en texto."
        ),
        24,
    )
    return s


def question() -> Sheet:
    s = Sheet(5, "Primero se busca en el documento; después se prepara la respuesta.")
    s.box(
        17,
        55,
        176,
        25,
        "1  Envías una pregunta",
        "Streamlit manda la pregunta, el documento elegido y tu token a la API.",
    )
    s.arrow(105, 80, 105, 87)
    s.box(
        17,
        87,
        176,
        27,
        "2  La API valida el acceso y busca",
        (
            "Pide acceso a Search y OpenAI en tu nombre. Busca por texto "
            "hasta cinco partes del documento."
        ),
    )
    s.arrow(105, 114, 105, 122)
    s.decision(66, 122, 78, 27, "¿Hay fragmentos?")
    s.arrow(66, 135.5, 49, 158, "No", 42, 140)
    s.arrow(144, 135.5, 152, 158, "Sí", 153, 140)
    s.box(
        17,
        160,
        77,
        42,
        "3a  No hay información",
        "La API avisa que no encontró información suficiente. No llama al modelo.",
        NOTE,
    )
    s.box(
        105,
        160,
        88,
        42,
        "3b  OpenAI recibe el caso",
        (
            "Recibe la pregunta y los fragmentos. Se le pide usar ese texto "
            "y citar sus fuentes."
        ),
        CLOUD,
    )
    s.arrow(149, 202, 149, 211)
    s.box(
        105,
        212,
        88,
        30,
        "4  El modelo responde",
        "Redacta una respuesta basada en los fragmentos recibidos.",
        CLOUD,
    )
    s.arrow(55, 202, 55, 249)
    s.arrow(149, 242, 149, 249)
    s.box(
        17,
        250,
        176,
        24,
        "5  Ves el resultado en la home",
        "La API devuelve la respuesta y las fuentes; Streamlit muestra la respuesta.",
    )
    return s


def tokens() -> Sheet:
    s = Sheet(
        6,
        (
            "La carga usa Search. Las preguntas usan Search y OpenAI. En "
            "ambos casos, se revisan tus permisos."
        ),
    )
    s.box(
        17,
        55,
        176,
        28,
        "1  Streamlit entrega tu token a FastAPI",
        (
            "Este token está destinado a la API. FastAPI comprueba que sea "
            "auténtico, no haya vencido y permita la operación."
        ),
    )
    s.arrow(105, 83, 105, 91)
    s.box(
        17,
        92,
        176,
        32,
        "2  FastAPI pide acceso en tu nombre",
        (
            "Envía a Entra tu token y el secreto de la API. Este intercambio "
            "se llama On-Behalf-Of, o «en nombre de»."
        ),
    )
    s.arrow(83, 124, 58, 141)
    s.arrow(127, 124, 153, 141)
    s.box(
        17,
        143,
        83,
        38,
        "3a  Token para Search",
        "Entra entrega un token destinado al servicio de búsqueda.",
        CLOUD,
    )
    s.box(
        110,
        143,
        83,
        38,
        "3b  Token para OpenAI",
        "Entra entrega otro token para el recurso Microsoft Cognitive Services.",
        CLOUD,
    )
    s.arrow(58.5, 181, 58.5, 190)
    s.arrow(151.5, 181, 151.5, 190)
    s.box(
        17,
        192,
        83,
        34,
        "4a  Guardar o buscar",
        "Search comprueba si el usuario puede leer o guardar texto.",
        CLOUD,
    )
    s.box(
        110,
        192,
        83,
        34,
        "4b  Generar respuesta",
        "OpenAI revisa si el usuario tiene permiso para usar el modelo.",
        CLOUD,
    )
    s.box(
        17,
        235,
        176,
        39,
        "Los nombres que verás en la configuración",
        (
            "Search: https://search.azure.com/.default\nOpenAI: "
            "https://cognitiveservices.azure.com/.default\nCognitive Services "
            "es el recurso de autenticación que usa OpenAI."
        ),
        NOTE,
        size=10.5,
    )
    return s


def errors() -> Sheet:
    s = Sheet(7, "Identifica dónde se detuvo el recorrido y corrige ese paso.")
    s.text(17, 55, "LO QUE OCURRE", 72, 10, "bold", BLUE)
    s.text(105, 55, "CÓMO CONTINUAR", 88, 10, "bold", BLUE)
    rows = [
        (
            "Cuenta fuera del directorio",
            "AADSTS50020",
            "Añadir la cuenta",
            (
                "Usa una cuenta del directorio o acepta una invitación como "
                "usuario externo."
            ),
        ),
        (
            "Secreto de Streamlit inválido",
            "AADSTS7000215 en login",
            "Revisar su valor",
            (
                "Guarda el valor del secreto del registro Streamlit. El ID del "
                "secreto no sirve."
            ),
        ),
        (
            "Sesión caducada",
            "La API responde 401",
            "Volver a iniciar sesión",
            "Cierra sesión, entra de nuevo y repite la operación.",
        ),
        (
            "Falla el acceso delegado",
            "delegated_authentication_failed",
            "Revisar la API",
            (
                "Revisa el secreto de la API y la autorización para acceder al "
                "servicio correcto."
            ),
        ),
        (
            "El usuario no tiene permiso",
            "Search u OpenAI rechazan acceso",
            "Revisar sus permisos",
            (
                "El administrador permite a tu cuenta usar el servicio que "
                "falló. Ver hoja 2."
            ),
        ),
        (
            "Archivo que no se puede leer",
            "Formato, tamaño o contenido",
            "Corregir el archivo",
            "Usa PDF con texto, TXT o Markdown, de hasta 10 MiB; vuelve a cargarlo.",
        ),
    ]
    y = 64
    for title, body, fix, detail in rows:
        s.box(17, y, 77, 31, title, body, NOTE, size=10)
        s.arrow(95, y + 15.5, 104, y + 15.5)
        s.box(105, y, 88, 31, fix, detail, LOCAL, size=10.5)
        y += 35
    return s


def publication() -> Sheet:
    s = Sheet(
        8,
        (
            "Este recorrido ocurre al publicar cambios. No se ejecuta con "
            "cada pregunta del usuario."
        ),
    )
    s.box(
        17,
        55,
        176,
        26,
        "1  GitHub comprueba el código",
        (
            "Ejecuta pruebas y revisa su formato. Las propuestas de cambio "
            "pasan por este control."
        ),
    )
    s.arrow(105, 81, 105, 94)
    s.text(109, 83, "Al actualizar main o iniciar el flujo manual", 84, 9)
    s.box(
        17,
        95,
        176,
        27,
        "2  Prueba documentos y preguntas conocidos",
        (
            "Carga documentos de prueba en un espacio separado y genera "
            "respuestas con la versión nueva."
        ),
        CLOUD,
    )
    s.arrow(105, 122, 105, 130)
    s.box(
        17,
        131,
        176,
        37,
        "3  Otro modelo revisa las respuestas",
        (
            "Puntúa de 1 a 5 el apoyo en los documentos, la relevancia, la "
            "información cubierta y las citas. Guarda un informe."
        ),
        CLOUD,
    )
    s.arrow(105, 168, 105, 177)
    s.decision(65, 178, 80, 30, "¿Todos los casos\ncumplen el mínimo?")
    s.arrow(65, 193, 54, 222, "No", 38, 207)
    s.arrow(145, 193, 151, 222, "Sí", 154, 207)
    s.box(
        17,
        224,
        78,
        33,
        "4a  Se detiene",
        "El equipo revisa el informe, corrige y vuelve a probar.",
        NOTE,
    )
    s.box(
        106,
        224,
        87,
        33,
        "4b  Se publica la API",
        "Empaqueta la API y la actualiza en Azure Container Apps.",
        CLOUD,
    )
    s.text(
        17,
        261,
        (
            "Mínimo actual: 4 en cada nota y ninguna afirmación importante "
            "sin respaldo.\nEste despliegue publica FastAPI; el alojamiento "
            "de Streamlit se configura aparte."
        ),
        176,
        10,
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
    sheets = [
        overview,
        preparation,
        login,
        upload,
        question,
        tokens,
        errors,
        publication,
    ]
    vectors = OUTPUT / "hojas"
    vectors.mkdir(exist_ok=True)
    if args.preview_dir:
        args.preview_dir.mkdir(parents=True, exist_ok=True)
    with PdfPages(OUTPUT / "flujo-completo-a4.pdf") as pdf:
        pdf.infodict().update(
            {
                "Title": "RAG Manual: flujo completo en ocho hojas A4",
                "Subject": "Guía en español sencillo para imprimir",
                "Author": "RAG Manual",
            }
        )
        for (slug, _), factory in zip(PAGES, sheets, strict=True):
            sheet = factory()
            pdf.savefig(sheet.fig)
            sheet.fig.savefig(vectors / f"{slug}.svg")
            if args.preview_dir:
                sheet.fig.savefig(args.preview_dir / f"{slug}.png", dpi=130)
            plt.close(sheet.fig)
    sections = "\n".join(
        f'<section><img src="hojas/{slug}.svg" alt="Hoja {i}: {title}"></section>'
        for i, (slug, title) in enumerate(PAGES, start=1)
    )
    html = (
        """<!doctype html>
<html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAG Manual · Flujo completo en A4</title>
<style>
body { margin:0; background:#e8ecf0; font-family:system-ui,sans-serif; }
header { max-width:760px; margin:24px auto; padding:0 16px; }
section { width:210mm; height:297mm; margin:20px auto; background:white; }
img { display:block; width:100%; height:100%; }
@media screen and (max-width:820px) {
  section { width:100%; height:auto; aspect-ratio:210/297; }
}
@page { size:A4 portrait; margin:0; }
@media print {
  body { background:white; }
  header { display:none; }
  section { margin:0; break-after:page; }
  section:last-child { break-after:auto; }
}
</style>
<header><h1>RAG Manual: el flujo completo</h1>
<p>Ocho hojas A4 verticales. Imprime el PDF al 100 % o usa la opción
de imprimir del navegador, sin encabezados ni pies del navegador.</p>
<p><a href="flujo-completo-a4.pdf">Abrir el PDF para imprimir</a></p></header>
"""
        + sections
        + "\n</html>\n"
    )
    (OUTPUT / "index.html").write_text(html, encoding="utf-8")
    print(f"Generadas {len(PAGES)} hojas A4 en {OUTPUT}")


if __name__ == "__main__":
    main()
