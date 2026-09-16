# RAG Manual API

Estructura base de una API con FastAPI, configuración por variables de entorno,
rutas versionadas y pruebas automatizadas.

Consulta el [flujo completo en ocho hojas A4](docs/diagrams/flujo-completo/flujo-completo-a4.pdf),
explicado con palabras simples y listo para imprimir.

También está disponible el [flujo de la aplicación y sus partes de Azure en cinco hojas A4](docs/diagrams/arquitectura/arquitectura-a4.pdf),
desde el inicio de sesión hasta la respuesta, con pasos numerados y la función
de cada servicio.

Para revisar endpoints, JWT/OBO, RBAC, registros de Entra y el origen/destino de
la configuración local y Azure, consulta el
[diagrama de flujo técnico en diez hojas A4](docs/diagrams/flujo-tecnico/flujo-tecnico-a4.pdf).

La [visión técnica global en una página A4](docs/diagrams/vision-global/vision-global-a4.pdf)
resume el flujo, la identidad, RBAC y la configuración en un solo mapa.

El [flujo RAG con LangGraph](docs/langgraph-flow.md) explica las decisiones,
límites, verificación de citas y una demostración offline paso a paso.

## Requisitos

- Python 3.11 o superior

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Ejecución

Inicia la API y la interfaz juntas con:

```bash
./scripts/run_local.sh
```

El script usa los puertos `8000` y `8501` y detiene ambos servicios al pulsar
`Ctrl+C`. Puedes personalizarlos mediante `RAG_API_PORT` y `RAG_UI_PORT`:

```bash
RAG_API_PORT=8080 RAG_UI_PORT=8502 ./scripts/run_local.sh
```

Para reiniciar ambos servicios desde otra terminal, ejecuta:

```bash
./scripts/run_local.sh restart
```

`restart` detiene por completo la instancia registrada antes de iniciar otra; si
no responde a la señal de terminación, fuerza el cierre de su launcher y sus
procesos descendientes. Si no hay una instancia registrada, en Linux también
detecta y detiene instancias anteriores de este mismo script que no tengan
archivo PID. Antes de reiniciar, también detiene cualquier proceso que esté
escuchando en los puertos configurados para la API y la interfaz. La opción
`start` no detiene procesos ajenos: si encuentra un puerto ocupado, informa del
conflicto y no inicia los servicios. El mensaje de disponibilidad aparece cuando
la API y la interfaz responden a sus comprobaciones de salud.

También puedes iniciar cada servicio por separado. Inicia la API en una
terminal:

```bash
uvicorn app.main:app --reload
```

En otra terminal, inicia la interfaz web:

```bash
streamlit run app/streamlit_app.py
```

La interfaz estará disponible en <http://localhost:8501>. Usa
`APP_API_BASE_URL` para apuntarla a una API que no se ejecute en
`http://localhost:8000`.

La sección **Tus manuales** muestra los archivos guardados en el índice
textual, incluso después de abrir una sesión nueva, con su cantidad de
fragmentos. Selecciona un **Documento para consultar** para hacer preguntas sin
volver a subirlo. La lista se guarda en caché durante 30 segundos por token;
**Actualizar documentos** fuerza una nueva consulta y las cargas exitosas
actualizan la lista inmediatamente. **Eliminar manual** pide confirmación y
oculta globalmente el documento y todos sus fragmentos, sin borrarlos físicamente.

La interfaz requiere iniciar sesión con Microsoft. FastAPI valida el token de
acceso y usa el flujo On-Behalf-Of para conectarse a Azure AI Search con la
identidad del usuario. Consulta la [guía de autenticación](docs/entra-auth.md)
para crear los registros de aplicación y configurar permisos y secretos.

Los errores del backend aparecen en la terminal donde ejecutas Uvicorn o
`./scripts/run_local.sh`. Los errores controlados incluyen método, ruta, estado
HTTP y código; los fallos `5xx` también muestran el traceback y la causa original
(por ejemplo, el error del SDK de Azure). Los errores de validación se registran
como advertencias. No hace falta activar `APP_DEBUG`; las respuestas HTTP
conservan sus mensajes controlados. Uvicorn registra las excepciones no controladas.

Esta versión permite cargar PDF con texto, TXT y Markdown desde Streamlit,
dividirlos en fragmentos y guardarlos en Azure AI Search con el botón
**Procesar y guardar**. Consulta la [guía de carga de archivos](docs/file-ingestion.md)
para preparar el índice de texto y configurar el entorno.

La API también permite indexar y recuperar chunks con embeddings precalculados
mediante el patrón Adapter. La generación de embeddings y el OCR siguen pendientes.
Las respuestas interactivas y el gate de CI comparten el mismo flujo RAG con
LangGraph sobre el índice textual, de modo que CI evalúa el código candidato
que atiende la API.

Consulta la [guía del almacén vectorial](docs/vector-store.md) para configurar
Entra ID, preparar el índice y probar los endpoints:

- `POST /api/v1/documents/chunks`: indexación de chunks con embeddings.
- `POST /api/v1/queries/search`: recuperación vectorial de chunks.
- `POST /api/v1/documents/upload`: carga de un archivo y almacenamiento textual.
- `GET /api/v1/documents`: lista de documentos del índice textual. Requiere un
  token delegado y permisos de lectura de Azure AI Search. Ejemplo de respuesta:
  `{"documents": [{"document_id": "...", "source": "manual.pdf", "indexed_chunks": 4}]}`.
- `DELETE /api/v1/documents/{document_id}`: marca el documento y sus chunks como
  eliminados; las consultas y el listado dejan de utilizarlos.
- `POST /api/v1/queries/answer`: búsqueda textual y respuesta RAG con citas.

La documentación interactiva estará disponible en:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health check: <http://localhost:8000/api/v1/health>

## Pruebas y calidad

```bash
pytest
ruff check .
ruff format --check .
```

El workflow `quality-gate-deploy.yml` ejecuta tests y lint, genera respuestas de
la versión candidata sobre el corpus versionado, aplica los evaluadores oficiales
de Azure para groundedness y relevance junto con la rúbrica del dominio y
solo despliega el commit si todos los casos pasan. Terraform declara los
identificadores de esos evaluadores, sus entradas y el umbral del gate. Consulta la
[guía de evaluación](docs/llm-as-a-judge.md) para configurar los entornos de
GitHub y ejecutar el mismo flujo localmente.

## Estructura

```text
app/
├── api/             # Rutas HTTP versionadas
├── core/            # Configuración y componentes compartidos
├── integrations/    # Adaptadores de proveedores: Azure AI Search
├── rag/             # Contratos y modelos del RAG
├── schemas/         # Modelos Pydantic de entrada y salida
├── services/        # Servicios de ingesta y consulta
├── main.py          # Creación de la API
└── streamlit_app.py # Interfaz web básica
tests/               # Pruebas automatizadas
docs/                # Arquitectura y uso del almacén vectorial
infrastructure/      # Infraestructura como código con Terraform
```

## Infraestructura en Azure

La base de Terraform está en `infrastructure/terraform`. Incluye autenticación
mediante Azure CLI, Azure Key Vault con RBAC y el despliegue de la API en Azure
Container Apps usando una imagen privada de Azure Container Registry. También
aprovisiona Azure AI Search con autenticación Entra ID y acceso RBAC para la
identidad administrada de la aplicación.
Consulta las instrucciones en
[`infrastructure/terraform/README.md`](infrastructure/terraform/README.md).
