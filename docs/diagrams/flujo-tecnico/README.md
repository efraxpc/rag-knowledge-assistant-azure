# Flujo técnico de la aplicación y Azure

[PDF de cinco hojas A4](flujo-tecnico-a4.pdf) ·
[Versión para navegador](index.html) ·
[Explicación en palabras simples](../arquitectura/arquitectura-a4.pdf)

Imprime en **A4 horizontal, al 100 %, una página por hoja**. Los márgenes son de
15 mm. El PDF y las láminas SVG contienen texto y figuras vectoriales.

| Hoja | Contenido | SVG | Mermaid |
| --- | --- | --- | --- |
| 1 | Secuencia HTTP: Streamlit, API, Entra, Search y OpenAI. | [Lámina](hojas/01-secuencia.svg) | [Fuente](hojas/01-secuencia.mmd) |
| 2 | Validación JWT, permisos delegados e intercambio OBO. | [Lámina](hojas/02-autenticacion.svg) | [Fuente](hojas/02-autenticacion.mmd) |
| 3 | Extracción, chunking, identificación e indexación de documentos. | [Lámina](hojas/03-ingestion.svg) | [Fuente](hojas/03-ingestion.mmd) |
| 4 | Recuperación textual, decisión por contexto y chat completions. | [Lámina](hojas/04-respuesta.svg) | [Fuente](hojas/04-respuesta.mmd) |
| 5 | Scopes, roles, contratos HTTP y límites de entrada. | [Lámina](hojas/05-contratos.svg) | [Recorrido de los tokens](hojas/05-contratos.mmd) |

Las hojas describen el código revisado el **13 de septiembre de 2026**. Los
rectángulos representan operaciones y los rombos condiciones. El color verde
identifica llamadas a Azure; el rojo, respuestas de error. En la secuencia,
una flecha doble resume una llamada y su resultado. El flujo principal es el de
la home: carga textual y respuestas RAG. Los endpoints vectoriales también
aparecen en la referencia de contratos; reciben embeddings ya calculados.

## Identidad y fronteras de ejecución

El navegador interactúa con Streamlit. Es el proceso Streamlit el que hace las
peticiones HTTP a FastAPI usando `httpx`, con destino fijo configurado por
`APP_API_BASE_URL`. La primera hoja muestra el login OIDC, el callback con código
de autorización y su canje por tokens mediante Streamlit/Authlib y la credencial
del frontend. Streamlit guarda la sesión y
expone el access token para la API mediante `st.user.tokens["access"]`.

FastAPI usa `EntraTokenVerifier`:

- Firma RS256, `kid` y claves JWKS de
  `https://login.microsoftonline.com/<tenant>/discovery/v2.0/keys`.
- `iss=https://login.microsoftonline.com/<tenant>/v2.0`;
  `aud=<client-id-api>` estricto.
- Claims obligatorios: `exp, iat, nbf, iss, aud, tid, oid, ver`;
  tolerancia temporal de 30 segundos.
- `tid` igual al tenant configurado, `ver="2.0"`, `oid` UUID válido.
- `scp` contiene `access_as_user` y `azp` coincide con el client ID de Streamlit.

Después usa `OnBehalfOfCredential` con el token de entrada como
`user_assertion` y con la credencial de la aplicación de la API. Entra emite
tokens delegados de Search y OpenAI; cada recurso aplica RBAC al usuario o grupo.
El consentimiento para emitir el token y la autorización para operar sobre el
recurso son controles distintos.

En una pregunta, las dependencias obtienen **primero el token Search y luego el
de Cognitive Services, antes de buscar contexto**. Por eso un fallo OBO de
OpenAI puede detener una consulta incluso antes de saber si Search devolverá
fragmentos. Los clientes y credenciales se cierran al terminar la petición.

Estas rutas no recurren a `az login` ni a una identidad administrada si falla
OBO. En Azure, Container Apps ejecuta FastAPI; su identidad de infraestructura
sirve para descargar la imagen, no para sustituir al usuario en Search/OpenAI.

## Detalles de datos

La carga normaliza el nombre del archivo y calcula:

```text
document_id = SHA256(source.encode("utf-8") + b"\0" + file_bytes)
chunk_id    = "page-<page-or-0>-offset-<start>"
index_id    = SHA256(JSON([document_id, chunk_id]).encode("utf-8"))
```

El último hash usa la serialización JSON de Python con `ensure_ascii=False`.
Los chunks contienen `document_id, content, source, page`, además de su ID.
En el índice, el ID del chunk se guarda como `chunk_id`; `id` es la clave hash.

El chunking opera por página, normaliza saltos de línea y usa ventanas de
1000 caracteres con solape de 200. PDF usa `pypdf`; TXT/MD usan
`utf-8-sig`, con página nula. Las páginas sin texto generan avisos; un archivo
sin texto extraíble produce 422. No se guarda el archivo original.

La carga textual limita los lotes a 1000 registros y una estimación conservadora
de 15 000 000 bytes, con margen para el envoltorio del SDK. La indexación puede
guardar parte de un lote antes de fallar. Los IDs deterministas permiten
reintentar el mismo archivo; no es una transacción atómica.

La búsqueda textual pasa `search_text=question` y `top=top_k` a SearchClient.
Si llega `document_id`, añade un filtro OData y escapa las comillas simples.
La home lo envía siempre y usa `top_k=5`; la API permite omitirlo y admite
`top_k` entre 1 y 20.

`AnswerService` construye el contexto con `content, source, page`. El prompt
de sistema pide usar solo esas fuentes y citarlas; el mensaje de usuario incluye
la pregunta y el contexto como JSON delimitado. El adaptador llama:

```text
POST <APP_AZURE_OPENAI_ENDPOINT>/openai/v1/chat/completions
Authorization: Bearer <token Cognitive Services>
model = APP_AZURE_OPENAI_CHAT_DEPLOYMENT
max_completion_tokens = 2000
```

Se valida que exista contenido textual no vacío y que no haya rechazo del
modelo. La respuesta incluye `answer` y `context: list[SearchHit]`; cada hit
contiene IDs, contenido, fuente, página y score. No hay verificación automática
de todas las afirmaciones generadas durante la petición.

Timeouts actuales: carga desde UI 120 s, pregunta desde UI 90 s, conexión UI
5 s. El timeout de generación en la API es configurable; valor predeterminado
60 s. Son configuraciones de timeout de los clientes, no garantías de duración.

## Códigos de error

Los diagramas muestran las ramas principales. Esta tabla precisa los códigos:

| HTTP | Código | Causa |
| --- | --- | --- |
| 401 | `authentication_required` | Bearer ausente o JWT inválido/caducado. |
| 403 | `insufficient_delegated_permission` | `scp` o `azp` incorrectos. |
| 403 | `delegated_authentication_failed` | Entra rechaza el intercambio OBO. |
| 403 | `search_access_denied` | Search rechaza la operación del usuario. |
| 413 | `file_too_large` / `chunk_too_large` | Archivo o fragmento excede su límite. |
| 415 | `unsupported_file_type` | Extensión distinta de PDF, TXT o MD. |
| 422 | `invalid_document` | Nombre, codificación, PDF o contenido no válido. |
| 422 | `invalid_embedding_dimensions` / `invalid_embedding` | Dimensión incorrecta o vector nulo. |
| 502 | `chunk_indexing_failed` | Algún registro no se indexó; puede haber escrituras parciales. |
| 502 | `invalid_text_search_response` / `invalid_vector_store_response` | Respuesta de Search incompatible. |
| 502 | `rag_provider_error` | Fallo del adaptador OpenAI: token, HTTP, rechazo o contenido inválido. |
| 503 | `authentication_not_configured` / `identity_provider_unavailable` | Configuración de identidad ausente o Entra/JWKS no disponibles. |
| 503 | `text_store_not_configured` / `rag_generator_not_configured` / `vector_store_not_configured` | Falta configurar el servicio. |
| 503 | `text_store_unavailable` / `text_search_unavailable` / `vector_store_unavailable` | Operación Search no disponible. |

Un HTTP 403 de OpenAI durante la llamada de chat se transforma en
**502 `rag_provider_error`**. Un rechazo en la preparación OBO se transforma en
**403 `delegated_authentication_failed`**. La etapa del fallo importa.

`ApplicationError` devuelve `{"error":{"code":...,"message":...,"details":...}}`.
El 401 agrega `WWW-Authenticate: Bearer`.
Un error de validación de petición FastAPI/Pydantic devuelve 422 con su formato
habitual `detail`. Las dependencias se resuelven antes del handler; el diagrama
no supone que toda validación del cuerpo ocurra antes de OBO.

## Editar y regenerar

El [generador](generate.py) necesita Python 3.11+ y Matplotlib 3.10. Reutiliza
las funciones de texto del [generador del flujo sencillo](../flujo-completo/generate.py).
Desde la raíz del repositorio:

```bash
MPLCONFIGDIR=/tmp/rag-flow-matplotlib python3 docs/diagrams/flujo-tecnico/generate.py
```

Añade `--preview-dir /tmp/rag-technical-preview` para guardar PNG de revisión.
Las hojas 2–4 generan SVG/PDF y Mermaid desde las mismas definiciones de nodos y
conexiones. La hoja 1 tiene una versión Mermaid de la secuencia. En la hoja 5,
Mermaid representa el recorrido de los tokens; los contratos se presentan como
tabla en el PDF/SVG. Mermaid puede distribuir los nodos de otra manera.

## Fuentes en el repositorio

- [Login](../../../app/ui_auth.py) e [interfaz HTTP](../../../app/streamlit_app.py).
- [Validación JWT](../../../app/core/auth.py) y [OBO/clientes](../../../app/core/resources.py).
- [Dependencias FastAPI](../../../app/api/dependencies.py).
- [Carga](../../../app/services/file_ingestion.py), [extracción](../../../app/services/extraction.py) y [chunking](../../../app/services/chunking.py).
- [Adaptador textual](../../../app/integrations/azure_text_search.py) y [vectorial](../../../app/integrations/azure_search.py).
- [Servicio RAG](../../../app/services/answer.py) y [cliente OpenAI](../../../app/integrations/azure_openai_chat.py).
- [Modelos y límites](../../../app/rag/models.py) y [errores](../../../app/core/exceptions.py).
- [Guía de autenticación](../../entra-auth.md).
