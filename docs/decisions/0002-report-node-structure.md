# ADR-0002: Estrutura modular de relatório (Report → ReportNode → ReportBlock)

**Status:** ✅ Aceito  
**Data:** 2026-07-24  
**Implementado:** 2026-07-30 (models e migração inicial)

## Contexto

O ReportLine deve produzir laudos periciais de forma modular: seções,
subseções e blocos de conteúdo reutilizáveis (texto, tabelas, imagens).
A edição manual fragmentada deve ser substituída por uma árvore editável
e padronizada.

Existe experiência prévia no projeto **Pith** (mesma máquina de desenvolvimento)
com estrutura similar de nós + blocos. O ReportLine adaptará o conceito ao
domínio forense, sem copiar nomes ou implementação literalmente.

## Relacionamentos implementados

```
CustomUser           1 —— N  Report              (author FK, SET_NULL + snapshot)
Report               1 —— N  ReportNode          (árvore hierárquica via parent)
ReportNode           1 —— 1  ReportBlock
```

Relacionamentos adjacentes já existentes:

```
CustomUser           1 —— 1  ForensicExaminerSP   (ADR-0007)
ForensicTeam         1 —— N  ForensicExaminerSP   (ADR-0007)
```

> **Autor do relatório:** o FK aponta para `CustomUser`, não para
> `ForensicExaminerSP`, para escalar a outros tipos de servidor. Metadados
> periciais (lotação, `display_name`) podem ser resolvidos na renderização
> a partir do perfil ativo do usuário. Ao excluir a conta, o relatório
> permanece com snapshot textual (`author_username`, `author_display_name`).

## Opções consideradas

### 1. Laudo como documento monolítico (HTML/Markdown em um campo)

- **Prós:** implementação rápida.
- **Contras:** sem modularidade, difícil reutilizar blocos, validação frágil,
  não escala para templates jurídicos complexos.

### 2. Laudo como árvore de nós com blocos desacoplados ✅ (adotado)

- **Prós:** modular, extensível, validação por tipo, alinhado ao Pith e ao
  domínio pericial (seções aninhadas).
- **Contras:** maior complexidade inicial; exige cuidado com ordenação e
  integridade da árvore.

### 3. Laudo baseado em JSON Schema fixo por template

- **Prós:** validação estruturada.
- **Contras:** rigidez; cada novo tipo de laudo exige novo schema completo.

### 4. Apps separados `reports` + `blocks`

- **Prós:** blocos reutilizáveis entre laudos sem duplicar conteúdo.
- **Contras:** superfície de manutenção maior no início.

## Decisão

Adotar a **opção 2**, concentrada em **um app `reports`** (opção 4 descartada
na fase inicial — blocos genéricos ficam no mesmo bounded context):

| App | Model(s) | Papel |
|---|---|---|
| `profiles` | `ForensicExaminerSP` ✅ | Extensão 1:1 do usuário; lotação e nome no laudo |
| `reports` | `Report`, `ReportNode`, `ReportBlock` ✅ | Relatório, árvore e blocos genéricos de conteúdo |

### Nomes adotados ✅

| Nome anterior (provisório) | Nome implementado |
|---|---|
| `ForensicReport`, `ExpertReport` | `Report` |
| `NodeReport`, `Section` | `ReportNode` |
| `Block`, `ContentBlock` | `ReportBlock` |

### Tipos genéricos de bloco (MVP)

| `block_type` | Uso |
|---|---|
| `heading` | Títulos (`title_level` 0–9 + texto em `content`) |
| `paragraph` | Parágrafos |
| `link` | Hiperlinks |
| `ordered_list` | Lista numerada |
| `unordered_list` | Lista com marcadores |
| `table` | Tabelas |
| `image` | Imagens |

Laudos periciais específicos **mapearão papéis semânticos** (ex.: número do
laudo) sobre esses blocos genéricos — camada futura, fora do escopo desta ADR.

## Consequências

### Positivas

- Estrutura preparada para crescimento (novos `block_type`, templates periciais).
- App único simplifica dependências e testes iniciais.
- Compatível com CBVs por domínio e testes unitários por regra.
- Relatórios sobrevivem à exclusão do autor (auditoria institucional).

### Negativas / trade-offs

- `ReportNode` com auto-referência exige lógica de árvore (ordenação, exclusão
  em cascata, movimentação de nós) — a implementar nas views/serviços.
- `ReportBlock.content` como JSON exige validação por `block_type` na camada de
  serviço ou form.
- Blocos não são compartilhados entre relatórios (1:1 com nó); reutilização
  exigiria extrair app `blocks` ou templates no futuro.

## Questões em aberto

- [x] Definir nomes finais de models (`Report`, `ReportNode`, `ReportBlock`)
- [x] Quais `block_type` mínimos para o MVP genérico
- [ ] `ReportBlock` é imutável após publicação do relatório ou versionado?
- [ ] Camada de laudo pericial específico (mapeamento semântico → blocos genéricos)
- [ ] Assistência por IA/voz na edição de blocos exige revisão de LGPD e credenciais institucionais ([ADR-0005](./0005-external-api-credentials.md))

## Referências

- [Modelo de dados](../architecture/02-data-model.md)
- [App reports](../architecture/07-reports.md)
- [Mapa de apps](../architecture/03-apps-map.md)
- [ADR-0005: Credenciais de APIs externas](./0005-external-api-credentials.md)
- [ADR-0007: ForensicExaminerSP](./0007-forensic-examiner-sp.md)
