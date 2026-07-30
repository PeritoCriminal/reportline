# ADR-0007: Perfil do perito criminal (SP) — `ForensicExaminerSP`

**Status:** ✅ Aceito  
**Data:** 2026-07-26

## Contexto

O ReportLine precisa identificar **quem** produz o laudo além da autenticação
(`CustomUser`): nome de exibição na assinatura pericial e lotação em equipe
do IC-SP (`ForensicTeam`).

O [ADR-0002](./0002-report-node-structure.md) previa um model genérico `Profile`.
Com a implementação do app `institution_ic_sp` ([ADR-0006](./0006-provisional-institution-ic-sp.md)),
torna-se possível modelar o perfil com vínculo explícito à estrutura pericial
de São Paulo.

## Opções consideradas

### 1. Model genérico `Profile` ✅ (descartado)

- **Prós:** reutilizável para outros estados ou órgãos.
- **Contras:** campos vagos; lotação exigiria abstração prematura.

### 2. Model de domínio `ForensicExaminerSP` ✅

- **Prós:** expressa o bounded context SP; FK direta para `ForensicTeam`;
  nome de laudo (`display_name`) explícito; evolução independente de auth.
- **Contras:** app `profiles` acoplado ao IC-SP; outros estados exigiriam
  models paralelos ou refatoração futura.

### 3. Estender `CustomUser` com campos profissionais

- **Prós:** menos tabelas.
- **Contras:** viola separação auth/perfil; dificulta gov.br e ADR-0001.

## Decisão

- Implementar o app **`profiles`** com model **`ForensicExaminerSP`**.
- Relacionamentos:
  - `CustomUser` **1:1** `ForensicExaminerSP`
  - `ForensicTeam` **1:N** `ForensicExaminerSP` (cada perito em uma equipe;
    cada equipe com vários peritos)
  - `ForensicExaminerSP` **1:N** laudos (via `CustomUser` → `Report`; ver atualização abaixo)
- Campo **`display_name`**: nome exibido na assinatura do laudo.
- Lotação com `on_delete=PROTECT` em `ForensicTeam` — impede apagar equipe
  com peritos lotados.
- Rótulos administrativos: *Perito criminal (SP)* / *Peritos criminais (SP)*.

## Consequências

- O ADR-0002 permanece válido para laudos modulares; **`Profile` foi substituído
  por `ForensicExaminerSP`** no app `profiles`.
- **Atualização (2026-07-30):** `Report.author` referencia `CustomUser` (não
  `ForensicExaminerSP` diretamente), com snapshot textual na exclusão da conta.
  Metadados periciais (`display_name`, lotação) enriquecem laudos na renderização.
  Ver [ADR-0002](./0002-report-node-structure.md) e [07-reports.md](../architecture/07-reports.md).
- Núcleo do perito é inferido via `forensic_examiner.forensic_team.nucleus` ou
  lotação direta em `ForensicNucleus`.
- Campos como registro funcional, classe ou matrícula ficam fora do escopo
  inicial — podem ser adicionados depois.

## Referências

- [App profiles](../architecture/05-profiles.md)
- [App institution_ic_sp](../architecture/04-institution-ic-sp.md)
- [Modelo de dados](../architecture/02-data-model.md)
- [ADR-0002: Estrutura de laudo modular](./0002-report-node-structure.md)
- [ADR-0006: App provisório IC-SP](./0006-provisional-institution-ic-sp.md)
