# ADR-0002: Estrutura modular de laudo (Report → NodeReport → Block)

**Status:** 🟡 Proposto  
**Data:** 2026-07-24

## Contexto

O ReportLine deve produzir laudos periciais de forma modular: seções,
subseções e blocos de conteúdo reutilizáveis (texto, tabelas, imagens).
A edição manual fragmentada deve ser substituída por uma árvore editável
e padronizada.

Existe experiência prévia no projeto **Pith** (mesma máquina de desenvolvimento)
com estrutura similar de nós + blocos. O ReportLine adaptará o conceito ao
domínio forense, sem copiar nomes ou implementação literalmente.

## Relacionamentos previstos

```
CustomUser  1 —— 1  Profile
Profile     1 —— N  Report
Report      1 —— N  NodeReport  (árvore hierárquica via parent_id)
NodeReport  1 —— 1  Block
```

## Opções consideradas

### 1. Laudo como documento monolítico (HTML/Markdown em um campo)

- **Prós:** implementação rápida.
- **Contras:** sem modularidade, difícil reutilizar blocos, validação frágil,
  não escala para templates jurídicos complexos.

### 2. Laudo como árvore de nós com blocos desacoplados ✅ (proposta)

- **Prós:** modular, extensível, reutilização de `Block`, validação por tipo,
  alinhado ao Pith e ao domínio pericial (seções aninhadas).
- **Contras:** maior complexidade inicial; exige cuidado com ordenação e
  integridade da árvore.

### 3. Laudo baseado em JSON Schema fixo por template

- **Prós:** validação estruturada.
- **Contras:** rigidez; cada novo tipo de laudo exige novo schema completo.

## Decisão (proposta)

Adotar a **opção 2**, organizada em três apps de domínio:

| App | Model(s) | Papel |
|---|---|---|
| `profiles` | `Profile` | Extensão 1:1 do usuário com dados profissionais |
| `reports` | `Report`, `NodeReport` | Laudo e árvore hierárquica de seções |
| `blocks` | `Block` | Conteúdo tipado e reutilizável |

### Nomes provisórios 🔵

| Nome atual | Alternativas em consideração |
|---|---|
| `Profile` | `ProfessionalProfile`, `ExpertProfile` |
| `Report` | `ForensicReport`, `ExpertReport` |
| `NodeReport` | `ReportNode`, `Section`, `ReportSection` |
| `Block` | `ContentBlock`, `ReportBlock` |

> Os nomes **não estão fechados**. Atualizar este ADR antes de criar migrations.

## Consequências

### Positivas

- Estrutura preparada para crescimento (novos tipos de `Block`, templates).
- Separação clara de responsabilidades entre apps.
- Compatível com CBVs por domínio e testes unitários por regra.

### Negativas / trade-offs

- `NodeReport` com auto-referência exige lógica de árvore (ordenação, exclusão
  em cascata, movimentação de nós).
- `Block.content` como JSON exige validação por `block_type` na camada de
  serviço ou form.
- Três apps novos aumentam superfície de manutenção inicial.

## Questões em aberto

- [ ] Definir nomes finais dos models e apps
- [ ] `Block` é imutável após publicação do laudo ou versionado?
- [ ] `NodeReport` suporta referência a bloco compartilhado entre laudos?
- [ ] Quais `block_type` mínimos para o MVP?
- [ ] Assistência por IA/voz na edição de blocos exige revisão de LGPD e credenciais institucionais ([ADR-0005](./0005-external-api-credentials.md))?

## Referências

- [Modelo de dados — estado alvo](../architecture/02-data-model.md)
- [Mapa de apps](../architecture/03-apps-map.md)
- [ADR-0005: Credenciais de APIs externas](./0005-external-api-credentials.md)
- Projeto Pith (referência local, conceito de árvore + blocos)
