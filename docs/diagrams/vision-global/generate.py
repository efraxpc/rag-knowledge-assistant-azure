"""Dibuja una visión técnica global en una página A4, sin regenerar el PDF detallado."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch  # noqa: E402
from matplotlib.textpath import TextToPath  # noqa: E402

OUTPUT = Path(__file__).resolve().parent
INK, BLUE, LINE = "#172C42", "#24567E", "#62788A"
LOCAL, CLOUD, NOTE, WHITE = "#EFF4F8", "#EDF6F2", "#FFF7E8", "#FFFFFF"
TEXT = TextToPath()


@dataclass
class Card:
    x: float
    y: float
    w: float
    h: float
    title: str
    body: str
    color: str = LOCAL
    size: float = 8.5


class GlobalDiagram:
    def __init__(self) -> None:
        self.fig = plt.figure(figsize=(297 / 25.4, 210 / 25.4))
        self.ax = self.fig.add_axes((0, 0, 1, 1))
        self.ax.set(xlim=(0, 297), ylim=(210, 0))
        self.ax.axis("off")
        self.ax.plot([12, 285], [10, 10], color=BLUE, linewidth=2)
        self.text(12, 14, "RAG MANUAL  /  VISIÓN TÉCNICA GLOBAL", 273, 9, "bold", BLUE)
        self.text(12, 21, "Aplicación, identidad y configuración", 273, 20, "bold")
        self.text(
            12,
            33,
            "1 Inicio de sesión → 2 Petición API → 3 OBO "
            "→ 4 Search → 5 OpenAI → 6 Resultado.",
            273,
            9.5,
        )
        self.ax.plot([12, 285], [200, 200], color=LINE, linewidth=0.6)
        self.text(
            12,
            203,
            "13 septiembre 2026 · A4 horizontal · "
            "Detalle: diagrama técnico de 10 hojas",
            260,
            8,
        )
        self.ax.text(285, 203, "1 / 1", ha="right", va="top", fontsize=8, color=INK)

    def text(
        self,
        x: float,
        y: float,
        content: str,
        width: float,
        size: float = 9,
        weight: str = "normal",
        color: str = INK,
        max_height: float | None = None,
    ) -> float:
        prop = FontProperties(family="DejaVu Sans", size=size, weight=weight)
        lines = []
        for paragraph in content.split("\n"):
            current = ""
            for word in paragraph.split():
                candidate = f"{current} {word}".strip()
                points, _, _ = TEXT.get_text_width_height_descent(
                    candidate, prop, False
                )
                if current and points * 25.4 / 72 > width:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            lines.append(current)
        height = len(lines) * size * 0.44
        if max_height is not None and height > max_height:
            raise ValueError(f"Texto fuera del recuadro: {content}")
        self.ax.text(
            x,
            y,
            "\n".join(lines),
            ha="left",
            va="top",
            fontsize=size,
            fontweight=weight,
            color=color,
            linespacing=1.2,
            zorder=4,
        )
        return height

    def card(self, c: Card) -> None:
        self.ax.add_patch(
            FancyBboxPatch(
                (c.x, c.y),
                c.w,
                c.h,
                boxstyle="round,pad=0,rounding_size=1.8",
                facecolor=c.color,
                edgecolor=LINE,
                linewidth=0.75,
                zorder=3,
            )
        )
        title_height = self.text(c.x + 3.5, c.y + 2.5, c.title, c.w - 7, 10, "bold")
        self.text(
            c.x + 3.5,
            c.y + 3.5 + title_height,
            c.body,
            c.w - 7,
            c.size,
            max_height=c.h - title_height - 5.5,
        )

    def arrow(
        self,
        points: list[tuple[float, float]],
        *,
        number: str = "",
        badge: tuple[float, float] | None = None,
        both: bool = False,
        configuration: bool = False,
    ) -> None:
        color = LINE if configuration else BLUE
        if len(points) > 2:
            xs, ys = zip(*points[:-1], strict=True)
            self.ax.plot(
                xs,
                ys,
                color=color,
                linewidth=1,
                linestyle="--" if configuration else "-",
                zorder=2,
            )
        self.ax.add_patch(
            FancyArrowPatch(
                points[-2],
                points[-1],
                arrowstyle="<->" if both else "-|>",
                mutation_scale=9,
                linewidth=1,
                color=color,
                linestyle="--" if configuration else "-",
                zorder=2,
                shrinkA=1,
                shrinkB=1,
            )
        )
        if number and badge:
            self.ax.add_patch(
                Circle(
                    badge, 2.3, facecolor=WHITE, edgecolor=BLUE, linewidth=0.8, zorder=5
                )
            )
            self.ax.text(
                *badge,
                number,
                ha="center",
                va="center",
                fontsize=8,
                fontweight="bold",
                color=BLUE,
                zorder=6,
            )


def draw() -> GlobalDiagram:
    s = GlobalDiagram()
    s.text(12, 41, "ORIGEN → CONFIGURACIÓN → CONSUMIDOR", 273, 8.2, "bold", BLUE)
    cards = [
        Card(
            12,
            46,
            71,
            34,
            "Config UI: secrets.toml",
            "Entra frontend → client ID + secret VALUE.\n"
            "Tenant / API ID → metadata y scope API.\n"
            "Callback registrado; cookie_secret aleatorio.\n"
            "st.secrets → login OIDC.",
            NOTE,
        ),
        Card(
            105,
            46,
            83,
            34,
            "Config local: .env → Settings",
            "Entra → tenant, API/FE IDs + secret API VALUE.\n"
            "Search → endpoint e índice.\n"
            "OpenAI → endpoint y deployment.\n"
            "Environment del proceso > .env > defaults.",
            NOTE,
        ),
        Card(
            210,
            46,
            75,
            34,
            "Config Azure: Terraform",
            "Inputs Entra + recursos/outputs → env APP_*.\n"
            "Secret API → entra-api-client-secret → secretRef.\n"
            "FastAPI en Container Apps; UI alojada aparte.",
            NOTE,
        ),
        Card(
            12,
            97,
            71,
            48,
            "Navegador → Streamlit",
            "Home: login, PDF/TXT/MD y preguntas.\n"
            "Proceso Streamlit → HTTP a FastAPI.\n"
            "APP_API_BASE_URL: launcher local o URL API Azure.\n"
            "Bearer: access token destinado a la API.\n"
            "Muestra answer + context/fuentes.",
            LOCAL,
            9,
        ),
        Card(
            105,
            96,
            83,
            72,
            "FastAPI · /api/v1",
            "JWT: RS256/JWKS, iss, aud, tid, exp;\n"
            "scp contiene access_as_user; azp=frontend client ID.\n"
            "OBO: assertion usuario + client secret API.\n"
            "UPLOAD · POST /documents/upload\n"
            "Extrae texto; chunks 1000 / solape 200.\n"
            "ANSWER · POST /queries/answer\n"
            "Search textual; document_id; top_k=5 (UI).\n"
            "Con contexto → chat; sin contexto → aviso.\n"
            "Respuesta: {answer, context}.\n"
            "401 JWT; 403 scope/OBO; 5xx proveedor.",
            LOCAL,
            9,
        ),
        Card(
            210,
            88,
            75,
            26,
            "Microsoft Entra ID",
            "Tenant; registros API y Streamlit.\n"
            "OIDC: login. OBO: tokens de usuario.\n"
            "Permisos delegados + consentimiento.",
            CLOUD,
        ),
        Card(
            210,
            122,
            75,
            22,
            "Azure AI Search · RBAC usuario",
            "Guardar / buscar → chunks a API.\n"
            "RBAC: Search Index Data Contributor\n"
            "Scope RBAC: recurso Search.",
            CLOUD,
        ),
        Card(
            210,
            152,
            75,
            22,
            "Azure OpenAI · RBAC usuario",
            "Chat: pregunta + chunks desde API.\n"
            "RBAC: Cognitive Services OpenAI User\n"
            "Scope RBAC: cuenta OpenAI.",
            CLOUD,
        ),
        Card(
            12,
            177,
            176,
            21,
            "Publicación: GitHub Environments → OIDC → Azure",
            "vars.EVAL_* → runner APP_* → Search CI + chat/juez. "
            "Production → build ACR → actualiza imagen.\n"
            "Identidades CI distintas; Container Apps → ACR: AcrPull. "
            "Terraform mantiene env; CI cambia imagen.",
            CLOUD,
            8,
        ),
        Card(
            199,
            177,
            86,
            21,
            "Apoyo y controles",
            "Log Analytics: registros. Key Vault: no conectado.\n"
            "Consentimiento → token; RBAC → datos.",
            NOTE,
            8,
        ),
    ]
    for c in cards:
        s.card(c)
    s.arrow([(47.5, 80), (47.5, 97)], configuration=True)
    s.arrow([(146.5, 80), (146.5, 96)], configuration=True)
    s.arrow([(210, 63), (199, 63), (199, 96), (188, 96)], configuration=True)
    s.arrow(
        [(83, 110), (93, 110), (93, 85), (205, 85), (205, 99), (210, 99)],
        number="1",
        badge=(174, 85),
    )
    s.arrow([(83, 121), (105, 121)], number="2", badge=(94, 121))
    s.arrow(
        [(188, 111), (195, 111), (195, 106), (210, 106)], number="3", badge=(199, 106)
    )
    s.arrow([(188, 133), (210, 133)], number="4", badge=(199, 133), both=True)
    s.arrow([(188, 161), (210, 161)], number="5", badge=(199, 161), both=True)
    s.arrow([(105, 155), (94, 155), (94, 138), (83, 138)], number="6", badge=(94, 148))
    s.text(12, 151, "Scopes OBO:", 71, 8.5, "bold", BLUE)
    s.text(
        12,
        157,
        "https://search.azure.com/.default\n"
        "https://cognitiveservices.azure.com/.default",
        78,
        8,
    )
    s.text(
        12,
        171,
        "Continua: uso. Discontinua: config. OBO de ambos recursos antes de buscar.",
        176,
        8,
    )
    return s


MERMAID = """flowchart LR
  subgraph Sources["ORIGEN Y CONFIGURACIÓN"]
    EntraValues["Entra: tenant, client IDs y VALUE de dos secretos"]
    AzureValues["Search/OpenAI: endpoints, índice, deployment; URL API"]
    Local[".env + environment → Pydantic Settings"]
    TOML["secrets.toml → st.secrets; cookie_secret aleatorio"]
    TF["Terraform: inputs + recursos"]
    EnvAzure["Container Apps env APP_* + secretRef entra-api-client-secret"]
    EntraValues -.-> Local
    EntraValues -.-> TOML
    AzureValues -.-> Local
    EntraValues -.-> TF
    AzureValues -.-> TF
    TF -.-> EnvAzure
  end
  Browser["Navegador"] --> UI["Streamlit: home, archivos y preguntas"]
  TOML -.-> UI
  Local -.-> UI
  Local -.-> API["FastAPI: JWT RS256/JWKS, aud, iss, tid, exp, scp, azp"]
  EnvAzure -.-> API
  Entra["Microsoft Entra ID: tenant + apps + consentimiento"]
  UI <-->|"OIDC: código y canje por token API"| Entra
  UI -->|"Bearer API; POST upload / answer"| API
  API <-->|"OBO: token usuario + credencial API"| Entra
  API --> Upload["PDF/TXT/MD → chunks 1000 / solape 200"]
  Search["Azure AI Search: Search Index Data Contributor; scope recurso"]
  Principal["RBAC: usuario/grupo; scope del recurso"] -.-> Search
  Upload -->|"token Search"| Search
  API --> Query["Búsqueda textual; document_id; top_k UI=5"]
  Query <-->|"search.azure.com/.default; fragmentos"| Search
  Query --> Context{"¿Hay contexto?"}
  Context -->|"No"| Notice["Aviso; context=[]"]
  OpenAI["Azure OpenAI: Cognitive Services OpenAI User; scope cuenta"]
  Principal -.-> OpenAI
  Context -->|"Sí: pregunta + chunks"| OpenAI
  OpenAI -->|"Respuesta"| Result["answer + context"]
  Notice --> Result
  Result --> UI
  subgraph Release["PUBLICACIÓN Y APOYO"]
    GHV["GitHub Environments vars; identidades OIDC separadas"]
    Eval["evaluation: runner APP_* → Search CI + chat/juez"]
    Prod["production: build ACR → actualiza imagen Container Apps"]
    Logs["Log Analytics: registros"]
    KV["Key Vault: provisionado; API no lo lee"]
    GHV --> Eval --> Prod
    Prod --> CA["Container Apps: FastAPI; AcrPull para ACR"]
    CA --> Logs
  end
  CA -.-> API
  classDef cloud fill:#EDF6F2,stroke:#62788A,color:#172C42
  classDef config fill:#FFF7E8,stroke:#62788A,color:#172C42
  class Entra,Search,OpenAI,CA,Logs,KV cloud
  class Local,TOML,TF,EnvAzure,GHV config
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    matplotlib.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "figure.facecolor": WHITE,
        }
    )
    sheet = draw()
    with PdfPages(OUTPUT / "vision-global-a4.pdf") as pdf:
        pdf.infodict().update(
            {
                "Title": "RAG Manual: visión técnica global",
                "Subject": "Una página A4: flujo, Entra, RBAC, variables y publicación",
                "Author": "RAG Manual",
            }
        )
        pdf.savefig(sheet.fig)
    sheet.fig.savefig(OUTPUT / "vision-global.svg")
    (OUTPUT / "vision-global.mmd").write_text(MERMAID, encoding="utf-8")
    if args.preview:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        sheet.fig.savefig(args.preview, dpi=170)
    plt.close(sheet.fig)
    (OUTPUT / "index.html").write_text(
        """<!doctype html>
<html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAG Manual · Visión técnica global</title>
<style>
body { margin:0; background:#e8ecf0; font-family:system-ui,sans-serif; }
header { max-width:1060px; margin:20px auto; padding:0 16px; }
main { width:297mm; height:210mm; margin:20px auto; background:white; }
img { display:block; width:100%; height:100%; }
@media screen and (max-width:1140px) {
  main { width:100%; height:auto; aspect-ratio:297/210; }
}
@page { size:A4 landscape; margin:0; }
@media print {
  body { background:white; }
  header { display:none; }
  main { margin:0; }
}
</style>
<header><h1>Visión técnica global en una página</h1>
<p>A4 horizontal, al 100 %. El PDF detallado de diez hojas se conserva.</p>
<p><a href="vision-global-a4.pdf">PDF de una página</a> ·
<a href="../flujo-tecnico/flujo-tecnico-a4.pdf">PDF detallado: diez hojas</a></p>
</header>
<main><img src="vision-global.svg" alt="Flujo global de aplicación, Entra ID,
RBAC, configuración local/Azure y publicación"></main>
</html>
""",
        encoding="utf-8",
    )
    print(f"Generada visión global de una página en {OUTPUT}")


if __name__ == "__main__":
    main()
