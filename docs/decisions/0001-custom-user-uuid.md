# reportline/docs/decisions/0001-custom-user-uuid.md
# ADR-0001: CustomUser com chave primária UUID

**Status:** ✅ Aceito  
**Data:** 2026-06-25

## Contexto

O ReportLine precisa de um modelo de usuário personalizado desde o início
(`AUTH_USER_MODEL`), pois futuras expansões incluirão dados profissionais
(registro pericial, cargo, etc.) via relação 1:1 com `Profile`.

A chave primária padrão (`AutoField` / inteiro sequencial) expõe volumetria
do banco e facilita ataques de enumeração (IDOR) em endpoints que referenciem
identificadores de usuário.

## Opções consideradas

### 1. Manter `AbstractUser` com PK inteira (padrão Django)

- **Prós:** simplicidade, compatibilidade total com ecossistema Django.
- **Contras:** IDs previsíveis, exposição de métricas, inconsistente com PKs
  UUID previstas para demais entidades.

### 2. `CustomUser` com UUID como PK ✅

- **Prós:** identificadores não sequenciais, alinhamento com demais models
  planejados, mitigação de IDOR.
- **Contras:** UUID ocupa mais espaço em índices; URLs com UUID são mais longas.

## Decisão

Adotar `CustomUser(AbstractUser)` com `id = UUIDField(primary_key=True,
default=uuid.uuid4, editable=False)` no app `accounts`.

## Consequências

- Todas as FKs para usuário usarão UUID.
- Sessões Django armazenam o UUID como string — suportado nativamente.
- Demais entidades do domínio seguirão o mesmo padrão de PK (ADR-0002).
- Em produção institucional, identidade via gov.br (OIDC) — ver [ADR-0003](./0003-govbr-authentication.md).
- Implementado em `accounts/models/custom_user.py` e migração `0001_initial`.

## Referências

- [Modelo de dados — estado atual](../architecture/02-data-model.md)
- [Mapa de apps — accounts](../architecture/03-apps-map.md)
- [ADR-0003: Autenticação gov.br (institucional)](./0003-govbr-authentication.md)
