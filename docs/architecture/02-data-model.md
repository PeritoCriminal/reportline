# Modelo de Dados (ERD)

Relacionamentos entre entidades do domínio ReportLine.

> **Nota:** nomes marcados com 🔵 são provisórios. Consulte os ADRs antes de
> implementar.
>
> **SGBD:** PostgreSQL é o padrão do projeto; em ambiente institucional, outro
> SGBD pode ser adotado a critério da instituição ([ADR-0004](../decisions/0004-postgresql-sgbd.md)).

---

## Estado atual ✅

Somente autenticação está implementada.

```mermaid
erDiagram
    CustomUser {
        uuid id PK "UUIDv4"
        string username UK
        string password
        string email
        string first_name
        string last_name
        boolean is_staff
        boolean is_active
        boolean is_superuser
        datetime date_joined
        datetime last_login
    }
```

**App:** `accounts`  
**Model:** `accounts.CustomUser`  
**Decisão:** [ADR-0001](../decisions/0001-custom-user-uuid.md)

Em ambiente **institucional**, a autenticação dos peritos migrará para Login
**gov.br** (OIDC), com possível extensão do model para CPF/`sub` OIDC — ver
[ADR-0003](../decisions/0003-govbr-authentication.md).

---

## Estado alvo 🟡

Estrutura prevista para laudos modulares, inspirada conceitualmente no projeto
**Pith** (árvore de nós + blocos de conteúdo), com adaptações ao domínio forense
do ReportLine.

```mermaid
erDiagram
    CustomUser ||--|| Profile : "has (1:1)"
    Profile ||--o{ Report : "owns (1:N)"
    Report ||--o{ NodeReport : "contains (1:N)"
    NodeReport ||--|| Block : "renders (1:1)"

    CustomUser {
        uuid id PK
        string username UK
    }

    Profile {
        uuid id PK
        uuid user_id FK "UK — relação 1:1"
        string professional_registration "🔵 provisório"
        string job_title "🔵 provisório"
        datetime created_at
        datetime updated_at
    }

    Report {
        uuid id PK
        uuid profile_id FK
        string title
        string status "🔵 draft | published"
        datetime created_at
        datetime updated_at
    }

    NodeReport {
        uuid id PK
        uuid report_id FK
        uuid parent_id FK "auto-referência — árvore"
        uuid block_id FK
        int order "ordem entre irmãos"
        string node_type "🔵 provisório"
        datetime created_at
    }

    Block {
        uuid id PK
        string block_type "🔵 text | table | image..."
        json content "🔵 payload flexível"
        datetime created_at
        datetime updated_at
    }
```

### Cardinalidades

| Relação | Tipo | Descrição |
|---|---|---|
| `CustomUser` → `Profile` | 1:1 | Cada usuário tem exatamente um perfil profissional |
| `Profile` → `Report` | 1:N | Um perito possui vários laudos |
| `Report` → `NodeReport` | 1:N | Um laudo é composto por vários nós |
| `NodeReport` → `Block` | 1:1 | Cada nó referencia um bloco de conteúdo |
| `NodeReport` → `NodeReport` | 1:N | Hierarquia (pai → filhos) para seções aninhadas |

### Observações de modelagem

1. **`NodeReport` como árvore:** além do FK para `Report`, prevê `parent_id`
   (auto-referência) para seções e subseções — padrão similar ao Pith.
2. **`Block` desacoplado:** permite reutilizar tipos de conteúdo e evoluir
   o payload (`JSONField`) sem reestruturar a árvore.
3. **UUID em todas as PKs:** alinhado à decisão do `CustomUser` (ADR-0001).
4. **Nomes provisórios:** `Profile`, `Report`, `NodeReport`, `Block` podem
   ser renomeados — ver [ADR-0002](../decisions/0002-report-node-structure.md).

---

## Mapa entidade → app (previsto)

| Entidade | App Django | Status |
|---|---|---|
| `CustomUser` | `accounts` | ✅ |
| `Profile` | `profiles` | 🟡 |
| `Report` | `reports` | 🟡 |
| `NodeReport` | `reports` | 🟡 |
| `Block` | `blocks` | 🟡 |

---

## Próximos passos de documentação

- [ ] Atualizar seção **Estado atual** ao implementar `Profile`
- [ ] Documentar fluxo de criação de laudo em `04-flows/create-report.md`
- [ ] Complementar com ERD gerado automaticamente quando models existirem

## Referências

- [Contexto do sistema](./01-context.md)
- [Mapa de apps](./03-apps-map.md)
- [ADR-0001: CustomUser com UUID](../decisions/0001-custom-user-uuid.md)
- [ADR-0002: Estrutura de laudo modular](../decisions/0002-report-node-structure.md)
- [ADR-0003: Autenticação gov.br (institucional)](../decisions/0003-govbr-authentication.md)
- [ADR-0004: PostgreSQL como SGBD padrão](../decisions/0004-postgresql-sgbd.md)
- [ADR-0005: Credenciais de APIs externas](../decisions/0005-external-api-credentials.md)
