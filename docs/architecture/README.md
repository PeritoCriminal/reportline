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
| [../decisions/](../decisions/) | Registros de decisão arquitetural (ADRs) |

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
2. Model implementado → atualizar seção **Estado atual** em `02-data-model.md`.
3. Novo app criado → atualizar `03-apps-map.md`.
4. Quando houver models suficientes → complementar com ERD gerado via
   `django-extensions graph_models` (opcional, futuro).
