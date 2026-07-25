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
| [0002](./0002-report-node-structure.md) | Estrutura modular de laudo (Report → NodeReport → Block) | 🟡 Proposto |

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
