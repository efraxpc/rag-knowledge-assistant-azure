"""Genera cinco láminas técnicas A4 con PDF, SVG y fuentes Mermaid."""

from __future__ import annotations

import argparse
import html
import runpy
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

OUTPUT = Path(__file__).resolve().parent
DRAWING = runpy.run_path(str(OUTPUT.parent / "flujo-completo" / "generate.py"))
BaseSheet = DRAWING["Sheet"]
INK, BLUE, LINE, LOCAL, CLOUD, NOTE, WHITE = (
    DRAWING[key] for key in ("INK", "BLUE", "LINE", "LOCAL", "CLOUD", "NOTE", "WHITE")
)
ERROR = "#FFF0EC"
PAGES = [
    ("01-secuencia", "Secuencia HTTP y llamadas a Azure"),
    ("02-autenticacion", "Autenticación: JWT y acceso delegado"),
    ("03-ingestion", "Ingestión: del archivo al índice textual"),
    ("04-respuesta", "Consulta RAG: búsqueda, contexto y modelo"),
    ("05-contratos", "Scopes, contratos HTTP y límites"),
]


@dataclass
class Node:
    name: str
    x: float
    y: float
    w: float
    h: float
    title: str
    body: str = ""
    kind: str = "local"

    def port(self, side: str) -> tuple[float, float]:
        return {
            "N": (self.x + self.w / 2, self.y),
            "S": (self.x + self.w / 2, self.y + self.h),
            "W": (self.x, self.y + self.h / 2),
            "E": (self.x + self.w, self.y + self.h / 2),
        }[side]


class TechnicalSheet(BaseSheet):
    def __init__(self, page: int, subtitle: str) -> None:
        self.page = page
        self.nodes: dict[str, Node] = {}
        self.links: list[tuple[str, str, str]] = []
        self.mermaid_override: str | None = None
        self.fig = plt.figure(figsize=(297 / 25.4, 210 / 25.4))
        self.ax = self.fig.add_axes((0, 0, 1, 1))
        self.ax.set(xlim=(0, 297), ylim=(210, 0))
        self.ax.axis("off")
        self.ax.plot([15, 282], [12, 12], color=BLUE, linewidth=2)
        self.text(
            15, 16, "RAG MANUAL  /  FLUJO TÉCNICO IMPLEMENTADO", 267, 9, "bold", BLUE
        )
        self.text(15, 24, PAGES[page - 1][1], 267, 20, "bold")
        self.text(15, 36, subtitle, 267, 10.5)
        self.ax.plot([15, 282], [197, 197], color=LINE, linewidth=0.65)
        self.text(
            15, 201, "Código revisado: 13 septiembre 2026 · A4 horizontal", 245, 8.5
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

    def add(self, node: Node) -> None:
        self.nodes[node.name] = node
        color = {"azure": CLOUD, "error": ERROR, "note": NOTE}.get(node.kind, LOCAL)
        if node.kind == "decision":
            self.ax.add_patch(
                Polygon(
                    [node.port(side) for side in ("N", "E", "S", "W")],
                    facecolor=WHITE,
                    edgecolor=LINE,
                    linewidth=1,
                    zorder=3,
                )
            )
            self.ax.text(
                node.x + node.w / 2,
                node.y + node.h / 2,
                node.title,
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
                color=INK,
                zorder=4,
            )
            return
        self.ax.add_patch(
            FancyBboxPatch(
                (node.x, node.y),
                node.w,
                node.h,
                boxstyle="round,pad=0,rounding_size=2",
                facecolor=color,
                edgecolor=LINE,
                linewidth=0.8,
                zorder=3,
            )
        )
        height = self.text(
            node.x + 4, node.y + 2.8, node.title, node.w - 8, 10.8, "bold"
        )
        if node.body:
            self.text(
                node.x + 4,
                node.y + 3.8 + height,
                node.body,
                node.w - 8,
                10,
                max_height=node.h - height - 5.5,
            )

    def path(
        self,
        points: list[tuple[float, float]],
        *,
        label: str = "",
        label_at: tuple[float, float] | None = None,
        both: bool = False,
        dashed: bool = False,
        size: float = 9,
    ) -> None:
        if len(points) > 2:
            xs, ys = zip(*points[:-1], strict=True)
            self.ax.plot(
                xs,
                ys,
                color=LINE,
                linewidth=1,
                linestyle="--" if dashed else "-",
                zorder=2,
            )
        self.ax.add_patch(
            FancyArrowPatch(
                points[-2],
                points[-1],
                arrowstyle="<->" if both else "-|>",
                mutation_scale=10,
                linewidth=1,
                color=LINE,
                linestyle="--" if dashed else "-",
                shrinkA=1,
                shrinkB=1,
                zorder=2,
            )
        )
        if label and label_at:
            self.text(*label_at, label, 165, size, color=BLUE)

    def edge(
        self,
        source: str,
        target: str,
        *,
        sp: str = "S",
        tp: str = "N",
        label: str = "",
        label_at: tuple[float, float] | None = None,
        via: list[tuple[float, float]] | None = None,
    ) -> None:
        self.links.append((source, target, label))
        self.path(
            [self.nodes[source].port(sp), *(via or []), self.nodes[target].port(tp)],
            label=label,
            label_at=label_at,
        )

    def mermaid(self) -> str:
        if self.mermaid_override:
            return self.mermaid_override
        lines = ["flowchart TB"]
        for node in self.nodes.values():
            content = html.escape(node.title + ("\n" + node.body if node.body else ""))
            content = content.replace("\n", "<br/>")
            shape = f'{{"{content}"}}' if node.kind == "decision" else f'["{content}"]'
            lines.append(f"  {node.name}{shape}:::{node.kind}")
        for source, target, label in self.links:
            arrow = f' -->|"{html.escape(label)}"|' if label else " -->"
            lines.append(f"  {source}{arrow} {target}")
        for name, color in [
            ("local", LOCAL),
            ("azure", CLOUD),
            ("error", ERROR),
            ("note", NOTE),
            ("decision", WHITE),
        ]:
            lines.append(f"  classDef {name} fill:{color},stroke:{LINE},color:{INK}")
        return "\n".join(lines) + "\n"


def sequence() -> TechnicalSheet:
    s = TechnicalSheet(
        1,
        "Cliente HTTP: proceso Streamlit. FastAPI coordina Azure "
        "con la identidad del usuario.",
    )
    cols = [
        ("UI", 19, "Streamlit", "localhost:8501"),
        ("API", 73, "FastAPI", "localhost:8000"),
        ("Entra", 132, "Entra ID", "OIDC / OBO"),
        ("Search", 183, "AI Search", "Índice textual"),
        ("OpenAI", 234, "Azure OpenAI", "Chat completions"),
    ]
    centers = {}
    for name, x, title, body in cols:
        s.add(
            Node(
                name,
                x,
                52,
                44,
                22,
                title,
                body,
                "local" if name in {"UI", "API"} else "azure",
            )
        )
        centers[name] = x + 22
        s.ax.plot(
            [x + 22, x + 22],
            [74, 185],
            color=LINE,
            linestyle=(0, (2, 3)),
            linewidth=0.65,
        )
    events = [
        ("UI", "Entra", 'st.login("microsoft"): OIDC', False),
        ("Entra", "UI", "GET /oauth2callback: code + state", False),
        ("UI", "Entra", "Canje de code + credencial frontend", False),
        ("Entra", "UI", "id_token + access_token para API", False),
        ("UI", "API", "POST /documents/upload", False),
        ("API", "Entra", "OBO: scope Search", False),
        ("Entra", "API", "Access token Search", False),
        ("API", "Search", "upload_documents(chunks)", False),
        ("Search", "API", "IndexingResult[]", False),
        ("API", "UI", "200 UploadDocumentResponse", False),
        ("UI", "API", "POST /queries/answer", False),
        ("API", "Entra", "OBO: Search y OpenAI", True),
        ("API", "Search", "search(question, document_id, top_k)", True),
        ("API", "OpenAI", "POST /openai/v1/chat/completions", True),
        ("API", "UI", "200 RagAnswerResponse", False),
    ]
    mermaid = ["sequenceDiagram", "  autonumber"]
    for name, _, title, body in cols:
        mermaid.append(f"  participant {name} as {title} ({body})")
    for index, (source, target, label, both) in enumerate(events):
        y = 82 + index * 102 / (len(events) - 1)
        x1, x2 = centers[source], centers[target]
        s.path(
            [(x1, y), (x2, y)],
            both=both,
            dashed=source in {"Entra", "Search"},
            label=label,
            label_at=(min(x1, x2) + 3, y - 4.4),
            size=8.6,
        )
        arrow = "->>" if source not in {"Entra", "Search"} else "-->>"
        mermaid.append(f"  {source}{arrow}{target}: {label}")
        if both:
            mermaid.append(f"  {target}-->>{source}: Resultado de la operación")
    s.text(
        15,
        189,
        "Rutas UI → API bajo /api/v1; Authorization: Bearer <token API>. "
        "La flecha doble resume request + response.",
        267,
        9,
    )
    mermaid.append(
        "  Note over API,OpenAI: Sin contexto se omite chat; "
        "ambos tokens OBO ya se obtuvieron."
    )
    s.mermaid_override = "\n".join(mermaid) + "\n"
    return s


def authentication() -> TechnicalSheet:
    s = TechnicalSheet(
        2,
        "Pipeline compartido por documentos y consultas; "
        "el secreto de FastAPI autentica el intercambio OBO.",
    )
    nodes = [
        Node(
            "request",
            15,
            52,
            169,
            20,
            "require_user() → HTTPBearer",
            "Lee Authorization: Bearer. Si falta, devuelve 401.",
        ),
        Node(
            "jwt",
            15,
            82,
            169,
            30,
            "EntraTokenVerifier.verify() → JWKS del tenant",
            "RS256 + kid; firma, iss, aud estricto; exp/iat/nbf (leeway: 30 s).\n"
            "tid = tenant; ver = 2.0; oid = UUID.\n"
            "scp contiene access_as_user; azp = client ID de Streamlit.",
        ),
        Node("valid", 65, 123, 69, 18, "JWT y permisos\n¿válidos?", kind="decision"),
        Node(
            "obo",
            15,
            154,
            169,
            34,
            "API → Entra ID: OnBehalfOfCredential",
            "tenant_id + client_id API + client_secret API + user_assertion.\n"
            "get_token(scope) antes de ejecutar el servicio.\n"
            "Upload: Search. Answer: Search y luego Azure OpenAI.",
            "azure",
        ),
        Node(
            "jwks_error",
            208,
            79,
            74,
            29,
            "503 · Fallo JWKS",
            "identity_provider_unavailable",
            "error",
        ),
        Node(
            "auth_error",
            208,
            116,
            74,
            33,
            "401 / 403",
            "401: JWT ausente o inválido.\n403: scp o azp no permiten acceso.",
            "error",
        ),
        Node(
            "obo_error",
            208,
            159,
            74,
            34,
            "403 / 503 · Fallo OBO",
            "403: intercambio rechazado.\n503: Entra no disponible.",
            "error",
        ),
    ]
    for node in nodes:
        s.add(node)
    s.edge("request", "jwt")
    s.edge("jwt", "valid")
    s.edge("valid", "obo", label="Sí", label_at=(103, 144))
    s.edge("valid", "auth_error", sp="E", tp="W", label="No", label_at=(158, 127))
    s.edge("jwt", "jwks_error", sp="E", tp="W")
    s.edge("obo", "obo_error", sp="E", tp="W")
    s.text(
        15,
        191,
        "Éxito → clientes por petición. "
        "RBAC autoriza después la operación en Search/OpenAI.",
        180,
        8.6,
    )
    return s


def ingestion() -> TechnicalSheet:
    s = TechnicalSheet(
        3,
        "POST /api/v1/documents/upload · "
        "Dependencias: JWT → OBO(Search) → FileIngestionService.",
    )
    nodes = [
        Node(
            "upload",
            15,
            52,
            169,
            20,
            "upload_document(file: UploadFile)",
            "multipart/form-data; ingest(filename, file.file).",
        ),
        Node(
            "valid",
            55,
            81,
            89,
            18,
            "Nombre, formato y tamaño\n¿válidos?",
            kind="decision",
        ),
        Node(
            "extract",
            15,
            108,
            169,
            34,
            "extract_text() → chunk_pages()",
            "PDF: pypdf; TXT/MD: UTF-8-SIG; sin OCR.\n"
            "Ventana: 1000 caracteres; solape: 200; no cruza páginas.\n"
            "document_id = SHA256(source + NUL + bytes).",
        ),
        Node(
            "index",
            15,
            152,
            169,
            23,
            "API → Azure AI Search: upload_documents()",
            "Lotes: hasta 1000 registros y límite conservador de 15 MB.\n"
            "IDs estables; se verifica succeeded por registro.",
            "azure",
        ),
        Node("result", 15, 181, 169, 12, "200 · UploadDocumentResponse"),
        Node(
            "file_error",
            208,
            67,
            74,
            38,
            "415 / 413 / 422",
            "415: extensión no admitida.\n413: archivo > 10 MiB.\n"
            "422: nombre inválido.",
            "error",
        ),
        Node(
            "text_error",
            208,
            114,
            74,
            29,
            "422 · invalid_document",
            "UTF-8 inválido; PDF cifrado, ilegible o sin texto.",
            "error",
        ),
        Node(
            "index_error",
            208,
            153,
            74,
            40,
            "403 / 502 / 503",
            "403: acceso denegado.\n502: algún registro falló.\n"
            "503: índice inaccesible.",
            "error",
        ),
    ]
    for node in nodes:
        s.add(node)
    s.edge("upload", "valid")
    s.edge("valid", "extract", label="Sí", label_at=(103, 100))
    s.edge("valid", "file_error", sp="E", tp="W", label="No", label_at=(167, 82))
    s.edge("extract", "text_error", sp="E", tp="W")
    s.edge("extract", "index")
    s.edge("index", "index_error", sp="E", tp="W")
    s.edge("index", "result")
    return s


def answer() -> TechnicalSheet:
    s = TechnicalSheet(
        4,
        "POST /api/v1/queries/answer · "
        "Pydantic: question, document_id opcional y top_k.",
    )
    nodes = [
        Node(
            "dependencies",
            15,
            52,
            169,
            23,
            "get_answer_service() → AnswerService.answer()",
            "JWT → OBO(Search) → OBO(Cognitive Services).\n"
            "Ambos tokens se obtienen antes de buscar.",
        ),
        Node(
            "search",
            15,
            85,
            169,
            24,
            "AzureTextSearchAdapter → Azure AI Search",
            "search_text = question; top = top_k.\n"
            "Filtro OData por document_id si se proporciona.",
            "azure",
        ),
        Node("empty", 62, 119, 75, 18, "context\n¿está vacío?", kind="decision"),
        Node(
            "chat",
            15,
            146,
            169,
            27,
            "API → AzureOpenAIChatClient.complete()",
            "POST /openai/v1/chat/completions; model = deployment.\n"
            "messages: system + user JSON; max_completion_tokens = 2000.\n"
            "Pregunta + contexto con content, source y page.",
            "azure",
        ),
        Node("result", 15, 182, 169, 11, "200 · RagAnswerResponse {answer, context}"),
        Node(
            "search_error",
            208,
            78,
            74,
            30,
            "403 / 503 / 502",
            "Acceso / servicio Search / respuesta incompatible.",
            "error",
        ),
        Node(
            "no_context",
            208,
            117,
            74,
            28,
            "200 · Sin contexto",
            "answer = aviso;\ncontext = []. No llama al modelo.",
            "note",
        ),
        Node(
            "chat_error",
            208,
            157,
            74,
            36,
            "502 · rag_provider_error",
            "Fallo de token, HTTP, rechazo o respuesta inválida/vacía.",
            "error",
        ),
    ]
    for node in nodes:
        s.add(node)
    s.edge("dependencies", "search")
    s.edge("search", "empty")
    s.edge("search", "search_error", sp="E", tp="W")
    s.edge("empty", "no_context", sp="E", tp="W", label="Sí", label_at=(170, 123))
    s.edge("empty", "chat", label="No", label_at=(103, 138))
    s.edge("chat", "chat_error", sp="E", tp="W")
    s.edge("chat", "result")
    return s


def table(
    s: TechnicalSheet,
    y: float,
    widths: list[float],
    headers: list[str],
    rows: list[list[str]],
    row_height: float,
) -> None:
    x = 15
    for width, header in zip(widths, headers, strict=True):
        s.ax.add_patch(
            FancyBboxPatch(
                (x, y),
                width,
                8,
                boxstyle="square,pad=0",
                facecolor=LOCAL,
                edgecolor=LINE,
                linewidth=0.6,
            )
        )
        s.text(x + 3, y + 2, header, width - 6, 9.8, "bold")
        x += width
    for row_index, row in enumerate(rows):
        x = 15
        for width, content in zip(widths, row, strict=True):
            top = y + 8 + row_index * row_height
            s.ax.add_patch(
                FancyBboxPatch(
                    (x, top),
                    width,
                    row_height,
                    boxstyle="square,pad=0",
                    facecolor=WHITE,
                    edgecolor=LINE,
                    linewidth=0.5,
                )
            )
            s.text(x + 3, top + 2, content, width - 6, 9.5, max_height=row_height - 3)
            x += width


def contracts() -> TechnicalSheet:
    s = TechnicalSheet(
        5,
        "Scopes distintos por destinatario. "
        "Consentimiento de Entra y roles de datos son controles separados.",
    )
    table(
        s,
        51,
        [44, 127, 96],
        ["Destino del token", "Scope solicitado", "Control / rol de datos"],
        [
            [
                "FastAPI",
                "api://<api-client-id>/access_as_user",
                "aud = client ID API;\nscp incluye access_as_user",
            ],
            [
                "Azure AI Search",
                "https://search.azure.com/.default",
                "Search Index Data Contributor\n(carga y consulta de la home)",
            ],
            [
                "Azure OpenAI",
                "https://cognitiveservices.azure.com/.default",
                "Cognitive Services OpenAI User",
            ],
        ],
        15,
    )
    s.text(
        15,
        110,
        "CONTRATOS · Prefijo /api/v1 · Respuestas de éxito: HTTP 200",
        267,
        9.5,
        "bold",
        BLUE,
    )
    table(
        s,
        118,
        [71, 102, 94],
        ["Método y ruta", "Entrada / límites", "Salida"],
        [
            [
                "POST /documents/upload",
                "file: PDF con texto / TXT / MD; ≤ 10 MiB",
                "document_id, source,\nindexed_chunks, warnings",
            ],
            [
                "POST /queries/answer",
                "question: 1–4000 caracteres;\n"
                "top_k: 1–20 (UI: 5); document_id opcional",
                "answer: string;\ncontext: SearchHit[]",
            ],
            [
                "POST /documents/chunks",
                "chunks: 1–1000; embeddings precalculados",
                "indexed_chunks",
            ],
            [
                "POST /queries/search",
                "embedding precalculado; top_k: 1–50;\n"
                "document_id opcional; índice vectorial",
                "matches: SearchHit[]",
            ],
            [
                "GET /health",
                "Público; no prueba conexiones con Azure",
                "Estado y configuración",
            ],
        ],
        13,
    )
    s.mermaid_override = """sequenceDiagram
  participant UI as Streamlit
  participant API as FastAPI
  participant Entra as Microsoft Entra ID
  participant Search as Azure AI Search
  participant OpenAI as Azure OpenAI
  UI->>API: Bearer API; scp access_as_user; aud client ID API
  API->>Entra: OBO; scope https://search.azure.com/.default
  Entra-->>API: Access token Search
  API->>Entra: OBO; scope https://cognitiveservices.azure.com/.default
  Entra-->>API: Access token OpenAI
  API->>Search: Bearer Search; servicio aplica RBAC
  Search-->>API: Contexto
  API->>OpenAI: Bearer OpenAI; servicio aplica RBAC
  OpenAI-->>API: Respuesta
"""
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
    sheets = OUTPUT / "hojas"
    sheets.mkdir(parents=True, exist_ok=True)
    if args.preview_dir:
        args.preview_dir.mkdir(parents=True, exist_ok=True)
    with PdfPages(OUTPUT / "flujo-tecnico-a4.pdf") as pdf:
        pdf.infodict().update(
            {
                "Title": "RAG Manual: flujo técnico de aplicación y Azure",
                "Subject": (
                    "Cinco hojas A4: secuencia, JWT/OBO, ingestión, RAG y contratos"
                ),
                "Author": "RAG Manual",
            }
        )
        for (slug, _), factory in zip(
            PAGES, [sequence, authentication, ingestion, answer, contracts], strict=True
        ):
            sheet = factory()
            pdf.savefig(sheet.fig)
            sheet.fig.savefig(sheets / f"{slug}.svg")
            (sheets / f"{slug}.mmd").write_text(sheet.mermaid(), encoding="utf-8")
            if args.preview_dir:
                sheet.fig.savefig(args.preview_dir / f"{slug}.png", dpi=150)
            plt.close(sheet.fig)
    sections = "\n".join(
        f'<section><img src="hojas/{slug}.svg" alt="Hoja {i}: {title}"></section>'
        for i, (slug, title) in enumerate(PAGES, 1)
    )
    page = (
        """<!doctype html>
<html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RAG Manual · Flujo técnico</title>
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
<header><h1>Flujo técnico de la aplicación y Azure</h1>
<p>Cinco hojas A4 horizontales. Imprime al 100 %, una página por hoja.</p>
<p><a href="flujo-tecnico-a4.pdf">Abrir PDF</a> ·
<a href="README.md">Contratos, errores y fuentes</a></p></header>
"""
        + sections
        + "\n</html>\n"
    )
    (OUTPUT / "index.html").write_text(page, encoding="utf-8")
    print(f"Generadas {len(PAGES)} hojas técnicas en {OUTPUT}")


if __name__ == "__main__":
    main()
