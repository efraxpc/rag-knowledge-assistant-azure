<div align="center">

# Assistente de Conhecimento RAG no Azure

**Assistente para consultar manuais com respostas fundamentadas, citações verificáveis e segurança baseada no Microsoft Entra ID.**

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Azure](https://img.shields.io/badge/Microsoft-Azure-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/)
[![Terraform](https://img.shields.io/badge/IaC-Terraform-844FBA?logo=terraform&logoColor=white)](https://www.terraform.io/)
[![Controle de qualidade e implantação](https://github.com/efraxpc/rag-knowledge-assistant-azure/actions/workflows/quality-gate-deploy.yml/badge.svg)](https://github.com/efraxpc/rag-knowledge-assistant-azure/actions/workflows/quality-gate-deploy.yml)

[Início rápido](#início-rápido) · [Arquitetura](#arquitetura) · [API](#api) · [Documentação](#documentação)

</div>

---

Este projeto implementa um fluxo de **Retrieval-Augmented Generation (RAG)** de
ponta a ponta no Azure. Ele permite carregar documentos, recuperar os trechos
mais relevantes e gerar uma resposta usando exclusivamente o contexto
encontrado. Cada resposta preserva as fontes utilizadas, e o fluxo se abstém de
responder quando os manuais não contêm informações suficientes.

A solução inclui uma interface conversacional com Streamlit, uma API FastAPI,
orquestração com LangGraph, Azure AI Search, Azure OpenAI, autenticação delegada
com o Entra ID, infraestrutura Terraform e um controle de qualidade baseado em
avaliação por LLM.

## Visão geral

<p align="center">
  <a href="docs/diagrams/linkedin/azure-rag-architecture-linkedin.png">
    <img
      src="docs/diagrams/linkedin/azure-rag-architecture-linkedin.png"
      alt="Arquitetura do assistente RAG seguro no Azure"
      width="900"
    />
  </a>
</p>

## Funcionalidades

- Interface de chatbot com login pelo Microsoft Entra ID.
- Upload de arquivos PDF com texto, TXT e Markdown de até 10 MiB.
- Extração, fragmentação e indexação do conteúdo no Azure AI Search.
- Perguntas sobre todos os manuais ou sobre um documento específico.
- Geração com o Azure OpenAI limitada ao contexto recuperado.
- Citações por fonte e página, com validação e correção controlada.
- Segunda tentativa de recuperação por meio da simplificação da consulta.
- Listagem de documentos e exclusão lógica de todos os seus trechos.
- API REST documentada com Swagger e ReDoc.
- Infraestrutura como código com Terraform e acesso por RBAC.
- Pipeline com testes, lint, avaliação RAG e implantação condicionada à qualidade.

> [!NOTE]
> A exclusão é lógica: os trechos recebem `deleted_at` e deixam de aparecer nas
> buscas e listagens, mas não são removidos fisicamente do índice.

## Como funciona

1. O usuário faz login no Streamlit pelo Entra ID.
2. O FastAPI valida o JWT e usa On-Behalf-Of para acessar os serviços do Azure
   com a identidade delegada do usuário.
3. O documento é dividido em trechos e armazenado no Azure AI Search.
4. O LangGraph recupera o contexto relevante para a pergunta.
5. O Azure OpenAI gera uma resposta exclusivamente com esses trechos.
6. O grafo verifica as citações e corrige ou rejeita respostas não confiáveis.

Se a primeira busca não encontrar contexto, o grafo poderá simplificar a
consulta e buscar mais uma vez. Se ainda assim não houver evidências
suficientes, ele responderá de forma segura, sem inventar informações.

## Arquitetura

| Camada | Tecnologia | Responsabilidade |
|---|---|---|
| Interface | Streamlit | Chat, autenticação, upload e gerenciamento de manuais |
| API | FastAPI + Pydantic | Contratos HTTP, validação e serviços da aplicação |
| Orquestração | LangGraph | Recuperação, contexto, geração e controle de citações |
| Recuperação | Azure AI Search | Índices textual e vetorial opcional |
| Geração | Azure OpenAI | Respostas RAG e avaliação de qualidade |
| Identidade | Microsoft Entra ID | OIDC, JWT, On-Behalf-Of e acesso delegado |
| Ambiente de execução | Azure Container Apps | Execução da API com dimensionamento gerenciado |
| Entrega | GitHub Actions + ACR | Controle de qualidade, imagem OCI e implantação imutável |
| Infraestrutura | Terraform | Recursos do Azure, identidades, funções e índices |

A arquitetura aplica o princípio do privilégio mínimo: o pipeline usa
identidades separadas para `evaluation` e `production`, enquanto as requisições
da aplicação usam a identidade do usuário, e não uma chave compartilhada do
Search ou do OpenAI.

## Início rápido

### Requisitos

- Python 3.11 ou superior.
- Uma conta do Azure para executar o fluxo RAG completo.
- Azure CLI e Terraform para preparar a infraestrutura.
- Um registro de aplicativo no Entra ID para usar a interface autenticada.

### 1. Preparar o ambiente

```bash
git clone https://github.com/efraxpc/rag-knowledge-assistant-azure.git
cd rag-knowledge-assistant-azure

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

### 2. Configurar o Azure

Preencha no `.env` os recursos que serão usados pela aplicação:

```dotenv
APP_AZURE_SEARCH_ENDPOINT="https://<servico>.search.windows.net"
APP_AZURE_SEARCH_TEXT_INDEX_NAME="rag-text-chunks"

APP_AZURE_OPENAI_ENDPOINT="https://<recurso>.cognitiveservices.azure.com"
APP_AZURE_OPENAI_CHAT_DEPLOYMENT="<implantacao-gerador>"

APP_ENTRA_TENANT_ID="<tenant-id>"
APP_ENTRA_API_CLIENT_ID="<client-id-api>"
APP_ENTRA_API_CLIENT_SECRET="<segredo-api>"
APP_ENTRA_FRONTEND_CLIENT_ID="<client-id-streamlit>"
```

As quatro variáveis `APP_ENTRA_*` são configuradas em conjunto. Não faça commit
do arquivo `.env`, de segredos, tokens nem de arquivos de estado do Terraform.
Consulte o [guia de autenticação](docs/entra-auth.md) para registrar a API e o
frontend, configurar o OBO e atribuir as permissões necessárias.

### 3. Iniciar a aplicação

```bash
./scripts/run_local.sh
```

Quando ambos os serviços estiverem prontos:

- Chat: <http://localhost:8501>
- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health check: <http://localhost:8000/api/v1/health>

Para reiniciar a API e a interface, liberando primeiro suas portas:

```bash
./scripts/run_local.sh restart
```

Você também pode alterar as portas:

```bash
RAG_API_PORT=8080 RAG_UI_PORT=8502 ./scripts/run_local.sh
```

## Uso

Na interface web:

1. Entre com sua conta Microsoft.
2. Carregue um PDF, TXT ou Markdown e selecione **Procesar y guardar**.
3. Escolha o documento que deseja consultar.
4. Digite uma pergunta no chat.
5. Confira a resposta, as citações e os trechos recuperados.

Você também pode chamar a API com um token destinado ao registro do aplicativo
FastAPI.

### Carregar um documento

```bash
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -F "file=@manual.pdf"
```

### Fazer uma pergunta

```bash
curl -X POST http://localhost:8000/api/v1/queries/answer \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Qual manutenção o equipamento requer?",
    "document_id": "<document-id>",
    "top_k": 5
  }'
```

Exemplo resumido de resposta:

```json
{
  "answer": "A manutenção deve ser realizada a cada seis meses [manual.pdf, p. 12].",
  "context": [
    {
      "id": "page-12-chunk-1",
      "document_id": "<document-id>",
      "content": "...",
      "source": "manual.pdf",
      "page": 12,
      "score": 8.42
    }
  ]
}
```

## API

Todos os endpoints usam o prefixo `/api/v1`.

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/health` | Verifica o estado da API |
| `POST` | `/documents/upload` | Extrai, fragmenta e indexa um arquivo |
| `GET` | `/documents` | Lista os documentos ativos |
| `DELETE` | `/documents/{document_id}` | Aplica exclusão lógica ao documento e aos seus trechos |
| `POST` | `/queries/answer` | Recupera o contexto e gera uma resposta com citações |
| `POST` | `/documents/chunks` | Indexa trechos com embeddings pré-calculados |
| `POST` | `/queries/search` | Executa uma busca vetorial opcional |

Com exceção do health check, as operações exigem um bearer token válido quando
o Entra ID está configurado. Os esquemas completos estão disponíveis no
Swagger.

## Testes e qualidade

Os testes são determinísticos e não precisam se conectar a recursos reais do
Azure:

```bash
pytest
ruff check .
ruff format --check .
```

O workflow do GitHub Actions executa:

```text
testes + lint
    → indexar o corpus de avaliação
    → gerar respostas com o RAG candidato
    → avaliar groundedness, relevance, completeness e citation quality
    → criar a imagem no ACR
    → implantar no Azure Container Apps
```

A implantação só continua se todos os casos atingirem o limite configurado. O
GitHub se autentica no Azure por OIDC, sem segredos de cliente permanentes. A
configuração completa está no
[guia LLM-as-a-judge](docs/llm-as-a-judge.md).

## Infraestrutura

O Terraform gerencia o Azure AI Search, os índices, as identidades, as
atribuições RBAC, as implantações do Azure OpenAI, a observabilidade e a
configuração do Container Apps.

```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -check
terraform validate
terraform plan
```

Sempre revise o plano antes de aplicá-lo. Alguns recursos, como a conta do Azure
AI Services e o ACR, são integrados como recursos preexistentes. Consulte o
[README de infraestrutura](infrastructure/terraform/README.md) antes de fazer
alterações no Azure.

## Estrutura do repositório

```text
app/
├── api/              # Endpoints FastAPI versionados
├── commands/         # Preparação de índices e avaliação
├── core/             # Configuração, autenticação e erros
├── evaluation/       # Contratos e lógica do controle de qualidade
├── integrations/     # Clientes do Azure Search e Azure OpenAI
├── rag/              # Modelos e contratos do domínio
├── schemas/          # Esquemas HTTP com Pydantic
├── services/         # Ingestão, recuperação e geração
├── main.py           # Aplicação FastAPI
└── streamlit_app.py  # Interface conversacional

evaluations/          # Corpus e cenários de avaliação
infrastructure/       # Infraestrutura do Azure com Terraform
docs/                 # Guias e diagramas técnicos
tests/                # Testes automatizados
```

## Documentação

| Tema | Documento |
|---|---|
| Fluxo RAG e decisões do LangGraph | [Fluxo do LangGraph](docs/langgraph-flow.md) |
| Upload, fragmentação e exclusão lógica | [Ingestão de documentos](docs/file-ingestion.md) |
| Microsoft Entra ID, JWT e OBO | [Autenticação delegada](docs/entra-auth.md) |
| Índice e busca vetorial opcional | [Armazenamento vetorial](docs/vector-store.md) |
| Avaliação e controle de qualidade | [LLM-as-a-judge](docs/llm-as-a-judge.md) |
| Identidades OIDC do pipeline | [GitHub OIDC](docs/github-oidc-identities.mmd) |
| Infraestrutura do Azure | [Terraform](infrastructure/terraform/README.md) |
| Visão técnica para impressão | [Arquitetura A4](docs/diagrams/arquitectura/arquitectura-a4.pdf) |
| Fluxo técnico completo | [Diagrama técnico A4](docs/diagrams/flujo-tecnico/flujo-tecnico-a4.pdf) |

## Escopo atual

- A recuperação principal é textual; o contrato vetorial aceita embeddings
  pré-calculados, mas a aplicação ainda não os gera.
- Os PDFs devem conter texto extraível. Documentos digitalizados precisam de
  OCR antes do upload.
- O arquivo original não é armazenado: somente seus trechos são indexados.
- A exclusão lógica não inclui restauração nem remoção definitiva automática.

---

<div align="center">

Criado com FastAPI, LangGraph e serviços gerenciados do Azure para demonstrar
um RAG seguro, observável e avaliável de ponta a ponta.

</div>
