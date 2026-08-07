# reportline/docs/decisions/README.md
# Architecture Decision Records (ADRs)

Registro de decisões arquiteturais do ReportLine. Cada ADR documenta o
**contexto**, as **opções consideradas**, a **decisão** tomada e as
**consequências**.

## Por que ADRs?

- Nomes de models e apps ainda estão em definição.
- Evita perder o raciocínio quando o projeto escalar.
- Permite revisitar decisões sem reescrever diagramas inteiros.

## Índice

| ADR | Título | Status |
|---|---|---|
| [0001](./0001-custom-user-uuid.md) | CustomUser com chave primária UUID | ✅ Aceito |
| [0002](./0002-report-node-structure.md) | Estrutura modular de relatório (Report → ReportNode → ReportBlock) | ✅ Aceito |
| [0003](./0003-govbr-authentication.md) | Autenticação em fases (local → Google → gov.br) | 🟡 Proposto (fases 0–1 ✅) |
| [0004](./0004-postgresql-sgbd.md) | PostgreSQL como SGBD padrão do projeto | ✅ Aceito |
| [0005](./0005-external-api-credentials.md) | Credenciais de APIs externas (pessoais vs institucionais) | ✅ Aceito |
| [0006](./0006-provisional-institution-ic-sp.md) | App provisório de dados institucionais do IC-SP | ✅ Aceito |
| [0007](./0007-forensic-examiner-sp.md) | Perfil do perito criminal (SP) — `ForensicExaminerSP` | ✅ Aceito |
| [0008](./0008-ai-pii-sanitization.md) | Sanitização local de PII antes de APIs externas de IA | ✅ Aceito |

## Template para novos ADRs

```markdown
# ADR-XXXX: Título da decisão

**Status:** Proposto | Aceito | Substituído | Obsoleto
**Data:** AAAA-MM-DD

## Contexto
Por que essa decisão é necessária?

## Opções consideradas
1. Opção A — prós / contras
2. Opção B — prós / contras

## Decisão
O que foi escolhido e por quê.

## Consequências
Impactos positivos, negativos e trade-offs.
```
