# Documentação de Arquitetura — ReportLine

Este diretório concentra a **documentação técnica em desenho** do ReportLine.
Os diagramas são mantidos como código (Mermaid) para versionamento, revisão e
evolução junto com o projeto.

## Índice

| Documento | Conteúdo |
|---|---|
| [01-context.md](./01-context.md) | Visão do sistema, atores e containers |
| [02-data-model.md](./02-data-model.md) | Modelo de dados (ERD) — atual e alvo |
| [03-apps-map.md](./03-apps-map.md) | Mapa de apps Django e dependências |
| [04-institution-ic-sp.md](./04-institution-ic-sp.md) | App provisório — núcleos e equipes IC-SP |
| [../decisions/](../decisions/) | Registros de decisão arquitetural (ADRs) |

### ADRs transversais (institucional e infraestrutura)

| ADR | Tema |
|---|---|
| [0003](../decisions/0003-govbr-authentication.md) | Autenticação gov.br em produção institucional |
| [0004](../decisions/0004-postgresql-sgbd.md) | PostgreSQL padrão; SGBD institucional a critério do órgão |
| [0005](../decisions/0005-external-api-credentials.md) | Credenciais pessoais (dev) vs institucionais (prod) |
| [0006](../decisions/0006-provisional-institution-ic-sp.md) | App provisório de dados institucionais do IC-SP |

Detalhes em [01-context.md](./01-context.md) — seções **Persistência** e **Integrações externas**.

## Legenda de status

| Marcador | Significado |
|---|---|
| ✅ **Implementado** | Existe no código e no banco de dados |
| 🟡 **Planejado** | Definido na arquitetura, ainda não implementado |
| 🔵 **Provisório** | Nome ou estrutura sujeitos a revisão (ver ADR) |

## Convenções desta documentação

- **Diagramas:** Mermaid embutido em Markdown (renderiza no GitHub, GitLab e Cursor).
- **Idioma:** textos explicativos em português; identificadores técnicos em inglês.
- **Sincronização:** ao implementar um model ou app, atualizar o diagrama correspondente
  e marcar o status como implementado.
- **Decisões pendentes:** registrar em `docs/decisions/` antes de congelar nomes no ERD.

## Fluxo de manutenção

1. Nova ideia ou dúvida de nomenclatura → criar ou atualizar ADR.
2. Decisão transversal (auth, SGBD, APIs, compliance) → ADR + seção em `01-context.md`.
3. Model implementado → atualizar seção **Estado atual** em `02-data-model.md`.
4. Novo app criado → atualizar `03-apps-map.md`.
5. Quando houver models suficientes → complementar com ERD gerado via
   `django-extensions graph_models` (opcional, futuro).
