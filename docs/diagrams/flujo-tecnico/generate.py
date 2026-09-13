"""Genera diez láminas técnicas A4 con PDF, SVG y fuentes Mermaid."""

from __future__ import annotations

import argparse
import html
from dataclasses import dataclass
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
BLUE = "#24567E"
LINE = "#62788A"
LOCAL = "#EFF4F8"
CLOUD = "#EDF6F2"
NOTE = "#FFF7E8"
WHITE = "#FFFFFF"
TEXT = TextToPath()
ERROR = "#FFF0EC"
PAGES = [
    ("01-secuencia", "Secuencia HTTP y llamadas a Azure"),
    ("02-autenticacion", "Autenticación: JWT y acceso delegado"),
    ("03-ingestion", "Ingestión: del archivo al índice textual"),
    ("04-respuesta", "Consulta RAG: búsqueda, contexto y modelo"),
    ("05-contratos", "Scopes, contratos HTTP y límites"),
    ("06-entra-configuracion", "Entra ID: registros y consentimiento"),
    ("07-rbac", "RBAC: autorización sobre los recursos"),
    ("08-configuracion-local", "Configuración: archivos y procesos locales"),
    ("09-origen-variables", "De dónde sale cada variable"),
    ("10-configuracion-azure", "Configuración: Azure y GitHub Actions"),
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


class TechnicalSheet:
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
            zorder=4,
        )
        return height

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


def entra_configuration() -> TechnicalSheet:
    s = TechnicalSheet(
        6,
        "Configuración previa: dos registros distintos, "
        "permisos delegados y consentimiento.",
    )
    nodes = [
        Node(
            "tenant",
            15,
            51,
            267,
            20,
            "Microsoft Entra ID → Directorio del proyecto",
            "Directory (tenant) ID; usuarios miembros o invitados admitidos.",
            "azure",
        ),
        Node(
            "frontend",
            15,
            82,
            127,
            43,
            "App registration: Streamlit",
            "Application (client) ID + client secret del frontend.\n"
            "Web redirect: localhost:8501/oauth2callback.\n"
            "Destino: .streamlit/secrets.toml [auth.microsoft].",
            "azure",
        ),
        Node(
            "api_reg",
            155,
            82,
            127,
            43,
            "App registration: FastAPI",
            "Application (client) ID distinto; tokens v2 para la API.\n"
            "Expose an API: api://<api-id>/access_as_user.\n"
            "Client secret API → APP_ENTRA_API_CLIENT_SECRET.",
            "azure",
        ),
        Node(
            "frontend_grant",
            15,
            137,
            267,
            20,
            "Permiso delegado del frontend → FastAPI",
            "Streamlit solicita access_as_user; "
            "preautorizar frontend o conceder consentimiento.",
            "azure",
        ),
        Node(
            "downstream_grant",
            15,
            170,
            267,
            23,
            "Permisos delegados de FastAPI → Azure + consentimiento de administrador",
            "Search user_impersonation + Microsoft Cognitive Services "
            "user_impersonation.\n"
            "Habilitan OBO; los roles RBAC del usuario autorizan después los datos.",
            "azure",
        ),
    ]
    for node in nodes:
        s.add(node)
    s.edge("tenant", "frontend", via=[(148.5, 76), (78.5, 76)])
    s.edge("tenant", "api_reg", via=[(148.5, 76), (218.5, 76)])
    s.edge("frontend", "frontend_grant", via=[(78.5, 131), (148.5, 131)])
    s.edge("api_reg", "frontend_grant", via=[(218.5, 131), (148.5, 131)])
    s.edge("frontend_grant", "downstream_grant")
    return s


def rbac_authorization() -> TechnicalSheet:
    s = TechnicalSheet(
        7, "RBAC = principal + rol + scope del recurso. Se evalúa en el servicio Azure."
    )
    nodes = [
        Node(
            "obo_identity",
            15,
            51,
            267,
            24,
            "Entra emite un token OBO para cada destinatario",
            "Principal: usuario (oid) y sus grupos. "
            "El secreto identifica a la API en el intercambio.\n"
            "El rol de la identidad de Container Apps "
            "no sustituye los permisos del usuario.",
            "azure",
        ),
        Node(
            "search_role",
            15,
            88,
            127,
            37,
            "Azure AI Search · Roles de datos",
            "Principal: grupo autorizado de Entra.\n"
            "Rol: Search Index Data Contributor (carga/consulta).\n"
            "Scope: recurso Search; se asigna en Access control (IAM).\n"
            "TF: search_user_group_object_id = Object ID del grupo.",
            "azure",
        ),
        Node(
            "openai_role",
            155,
            88,
            127,
            37,
            "Azure OpenAI · Rol de datos",
            "Principal: usuario o grupo autorizado de Entra.\n"
            "Rol: Cognitive Services OpenAI User.\n"
            "Scope: cuenta Azure OpenAI; Access control (IAM).\n"
            "TF: openai_user_object_ids = Object IDs de usuarios.",
            "azure",
        ),
        Node(
            "search_allowed",
            43,
            137,
            71,
            19,
            "Token + rol\n¿autorizan?",
            kind="decision",
        ),
        Node(
            "openai_allowed",
            183,
            137,
            71,
            19,
            "Token + rol\n¿autorizan?",
            kind="decision",
        ),
        Node(
            "search_ok",
            15,
            174,
            80,
            18,
            "Operación Search",
            "Indexar o consultar.",
            "azure",
        ),
        Node("search_deny", 103, 170, 39, 23, "403 API", "Search deniega.", "error"),
        Node(
            "openai_ok",
            155,
            174,
            80,
            18,
            "Operación OpenAI",
            "Generar respuesta.",
            "azure",
        ),
        Node("openai_deny", 243, 170, 39, 23, "502 API", "OpenAI: HTTP 403.", "error"),
    ]
    for node in nodes:
        s.add(node)
    s.edge("obo_identity", "search_role", via=[(148.5, 81), (78.5, 81)])
    s.edge("obo_identity", "openai_role", via=[(148.5, 81), (218.5, 81)])
    s.edge("search_role", "search_allowed")
    s.edge("openai_role", "openai_allowed")
    s.edge("search_allowed", "search_ok", label="Sí", label_at=(54, 160))
    s.edge(
        "search_allowed",
        "search_deny",
        sp="E",
        label="No",
        label_at=(117, 159),
        via=[(122.5, 146.5)],
    )
    s.edge("openai_allowed", "openai_ok", label="Sí", label_at=(194, 160))
    s.edge(
        "openai_allowed",
        "openai_deny",
        sp="E",
        label="No",
        label_at=(257, 159),
        via=[(262.5, 146.5)],
    )
    return s


def local_configuration() -> TechnicalSheet:
    s = TechnicalSheet(
        8,
        "Archivos en la raíz del proyecto; "
        "Settings y st.secrets leen configuraciones distintas.",
    )
    nodes = [
        Node(
            "dotenv",
            15,
            52,
            127,
            38,
            ".env.example → .env",
            "Copiar y completar APP_ENTRA_*, APP_AZURE_* y URL API.\n"
            "Origen: registros Entra, recursos/índices y deployments.\n"
            "Pydantic lo lee; el launcher no exporta todo el archivo.",
            "note",
        ),
        Node(
            "toml",
            155,
            52,
            127,
            38,
            ".streamlit/secrets.toml.example → secrets.toml",
            "[auth]: redirect_uri, cookie_secret, expose_tokens.\n"
            "[auth.microsoft]: client_id, client_secret, metadata,\n"
            "scope OIDC + api://<api-id>/access_as_user.",
            "note",
        ),
        Node(
            "settings",
            15,
            104,
            127,
            30,
            "get_settings() → Settings(BaseSettings)",
            "Prioridad: environment del proceso > .env > defaults.\n"
            "env_prefix = APP_; valida IDs, endpoints y configuración.",
        ),
        Node(
            "st_secrets",
            155,
            104,
            127,
            30,
            "Streamlit → st.secrets / st.login()",
            "Lee el TOML para OIDC. Frontend secret: valor de Entra.\n"
            "cookie_secret: aleatorio local, no viene de Azure.",
        ),
        Node(
            "processes",
            15,
            151,
            127,
            28,
            "Procesos: Uvicorn + Streamlit",
            "FastAPI: settings → JWT, OBO, Search y OpenAI.\n"
            "Streamlit: settings.api_base_url → destino HTTP.",
        ),
        Node(
            "session",
            155,
            151,
            127,
            28,
            "Sesión Microsoft → access token API",
            "expose_tokens = [access]; require_login() lo obtiene.\n"
            "Token generado en sesión: no se escribe en .env.",
        ),
    ]
    for node in nodes:
        s.add(node)
    s.edge("dotenv", "settings")
    s.edge("settings", "processes")
    s.edge("toml", "st_secrets")
    s.edge("st_secrets", "session")
    s.text(
        15,
        185,
        "run_local.sh exporta APP_API_BASE_URL desde host/puerto "
        "o environment existente; "
        "prevalece sobre .env.",
        267,
        9.5,
    )
    return s


def variable_origins() -> TechnicalSheet:
    s = TechnicalSheet(
        9,
        "Tabla de origen → variable → consumidor. "
        "Cada nombre de la primera columna lleva APP_.",
    )
    table(
        s,
        51,
        [92, 90, 85],
        ["Variable en .env (prefijo APP_)", "Dónde obtener el valor", "Dónde se usa"],
        [
            [
                "ENTRA_TENANT_ID",
                "Entra ID: Overview → Directory (tenant) ID",
                "JWT issuer/tid + OBO; tenant también en metadata OIDC",
            ],
            [
                "ENTRA_API_CLIENT_ID",
                "App registration FastAPI → Application (client) ID",
                "JWT aud; OBO client_id;\nscope API en el TOML",
            ],
            [
                "ENTRA_FRONTEND_CLIENT_ID",
                "App registration Streamlit → Application (client) ID",
                "JWT azp; mismo ID en\n[auth.microsoft].client_id",
            ],
            [
                "ENTRA_API_CLIENT_SECRET",
                "Registro FastAPI → Certificates & secrets → VALUE",
                "OBO; valor del secreto,\nno Secret ID",
            ],
            [
                "AZURE_SEARCH_ENDPOINT",
                "Recurso Search: Overview / output search_service_endpoint",
                "SearchClient.endpoint",
            ],
            [
                "AZURE_SEARCH_TEXT_INDEX_NAME",
                "Search → Indexes; Terraform crea índice textual",
                "SearchClient.index_name",
            ],
            [
                "AZURE_OPENAI_ENDPOINT",
                "Endpoint del recurso / output azure_openai_endpoint",
                "Base HTTPS del cliente chat",
            ],
            [
                "AZURE_OPENAI_CHAT_DEPLOYMENT",
                "Deployment de modelo / output azure_openai_chat_deployment_name",
                "Campo model de chat;\nno el ID del recurso",
            ],
            [
                "API_BASE_URL",
                "Local: launcher host/puerto. Azure: output container_app_url",
                "Streamlit → destino FastAPI",
            ],
        ],
        13.5,
    )
    s.text(
        15,
        184,
        "TOML: client_secret = VALUE del secreto del frontend; "
        "cookie_secret = aleatorio generado. "
        "API y frontend usan secretos distintos.",
        267,
        9.5,
    )
    s.mermaid_override = """flowchart LR
  Entra["Entra: tenant + dos app registrations"] --> IDs["Tenant / API ID / FE ID"]
  IDs --> ENV[".env: APP_ENTRA_*"]
  Entra --> APISecret["VALUE secreto API"]
  APISecret --> ENV
  Entra --> FESecret["VALUE secreto frontend"]
  FESecret --> TOML[".streamlit/secrets.toml"]
  IDs --> TOML
  Random["Generador aleatorio local"] -->|"cookie_secret"| TOML
  Search["Search: endpoint e índice"] --> ENV
  Models["OpenAI: endpoint y deployment"] --> ENV
  Launcher["run_local.sh: host/puerto"] --> Process["Environment: APP_API_BASE_URL"]
  URL["Output container_app_url"] --> Frontend["Configuración del hosting Streamlit"]
  Frontend --> Process
  Process --> Settings
  ENV --> Settings["Pydantic Settings"]
  TOML --> OIDC["Streamlit OIDC"]
"""
    return s


def azure_configuration() -> TechnicalSheet:
    s = TechnicalSheet(
        10,
        "Terraform configura la API; "
        "GitHub Environments configura los jobs. Son ámbitos distintos.",
    )
    nodes = [
        Node(
            "terraform_input",
            15,
            51,
            127,
            35,
            "Terraform → recursos, outputs e inputs",
            "Endpoints Search/OpenAI y nombre del deployment.\n"
            "Inputs: entra_tenant_id, API/FE client IDs.\n"
            "Secret API: TF_VAR_entra_api_client_secret o creación opcional.",
            "azure",
        ),
        Node(
            "github_input",
            155,
            51,
            127,
            35,
            "GitHub → Environments: evaluation / production",
            "vars: AZURE_CLIENT_ID, AZURE_TENANT_ID,\n"
            "AZURE_SUBSCRIPTION_ID; desde Azure/outputs.\n"
            "evaluation: EVAL_AZURE_* desde recursos/outputs.\n"
            "production: nombres ACR, imagen, RG y Container App.",
        ),
        Node(
            "container_env",
            15,
            100,
            127,
            44,
            "Container Apps → env y secretRef",
            "env: APP_AZURE_*, APP_ENTRA_* IDs, APP_ENVIRONMENT.\n"
            "Secret: entra-api-client-secret.\n"
            "env APP_ENTRA_API_CLIENT_SECRET → referencia al secret.\n"
            "Terraform inyecta valores; no copia el .env local.",
            "azure",
        ),
        Node(
            "runner_env",
            155,
            100,
            127,
            44,
            "GitHub Actions → environment del runner",
            "Workflow mapea vars.EVAL_AZURE_* a APP_AZURE_*.\n"
            "azure/login OIDC → identidades eval / producción.\n"
            "Eval: Search + OpenAI. Prod: build ACR + update app.\n"
            "Este workflow no usa client secret de Azure.",
        ),
        Node(
            "runtime_env",
            15,
            159,
            127,
            21,
            "FastAPI → Settings → JWT/OBO/clientes",
            "Variables del proceso prevalecen sobre defaults.",
        ),
        Node(
            "release",
            155,
            159,
            127,
            21,
            "CI → imagen aprobada → nueva revisión",
            "CI actualiza la imagen; Terraform mantiene los env.",
            "azure",
        ),
    ]
    for node in nodes:
        s.add(node)
    s.edge("terraform_input", "container_env")
    s.edge("container_env", "runtime_env")
    s.edge("github_input", "runner_env")
    s.edge("runner_env", "release")
    s.text(
        15,
        186,
        "Key Vault está preparado, sin conexión actual como fuente de env. "
        "Streamlit configura su TOML y URL API en su hosting.",
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
    sheets = OUTPUT / "hojas"
    sheets.mkdir(parents=True, exist_ok=True)
    if args.preview_dir:
        args.preview_dir.mkdir(parents=True, exist_ok=True)
    with PdfPages(OUTPUT / "flujo-tecnico-a4.pdf") as pdf:
        pdf.infodict().update(
            {
                "Title": "RAG Manual: flujo técnico de aplicación y Azure",
                "Subject": (
                    "Diez hojas A4: flujo, Entra, RBAC y configuración local/Azure"
                ),
                "Author": "RAG Manual",
            }
        )
        for (slug, _), factory in zip(
            PAGES,
            [
                sequence,
                authentication,
                ingestion,
                answer,
                contracts,
                entra_configuration,
                rbac_authorization,
                local_configuration,
                variable_origins,
                azure_configuration,
            ],
            strict=True,
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
<p>Diez hojas A4 horizontales. Imprime al 100 %, una página por hoja.</p>
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
