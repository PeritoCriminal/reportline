# ADR-0006: App provisório de dados institucionais do IC-SP

**Status:** ✅ Aceito  
**Data:** 2026-07-26

## Contexto

O ReportLine precisa referenciar a estrutura organizacional do **Instituto de
Criminalística de São Paulo (IC-SP)** — núcleos periciais e equipes de perícias
criminalísticas — para vincular perfis de peritos, filtros de laudos e fluxos
operacionais durante o desenvolvimento.

Em ambiente **institucional**, esses dados devem vir do cadastro oficial da
**Superintendência da Polícia Técnico-Científica (SPTC)**, não de uma base
local mantida pelo projeto.

## Opções consideradas

### 1. App Django dedicado com seed local ✅

- **Prós:** disponível offline em dev; schema estável para FKs futuras; fácil
  de substituir ou desativar; dados versionados no repositório.
- **Contras:** risco de desatualização em relação ao organograma oficial; exige
  manutenção manual até integração institucional.

### 2. Hardcode em fixtures JSON estáticas

- **Prós:** simplicidade inicial.
- **Contras:** menos flexível para evolução; sem flag explícita de provisoriedade;
  admin e consultas ORM mais trabalhosos.

### 3. Integração imediata com API/sistema institucional

- **Prós:** dados sempre atualizados.
- **Contras:** dependência de infraestrutura inexistente na fase atual; bloqueia
  desenvolvimento local.

## Decisão

- Criar o app **`institution_ic_sp`** com models `Institution`, `ForensicNucleus`
  e `ForensicTeam`.
- Popular a base via **data migration** (`0002_load_ic_sp_seed_data`) e comando
  `load_ic_sp_data`, a partir do **Decreto nº 42.847/1998** e organograma SPTC
  (rev. 15).
- Marcar o cadastro como **provisório** (`Institution.is_provisional = True`).
- Manter o app durante todo o projeto; em produção institucional, **substituir**
  por integração equivalente ou desativar o app, preservando contratos de FK
  nos apps consumidores.

## Consequências

- Apps futuros (`profiles`, `reports`) podem referenciar `ForensicNucleus` e
  `ForensicTeam` por UUID estável.
- Alterações no organograma oficial exigem atualização de
  `institution_ic_sp/data/ic_sp_seed.py` e nova migration ou `--clear` no comando.
- Logos institucionais (`sp_logo`, `sptc_logo`) ficam em `MEDIA_ROOT` e **não**
  são versionados no Git; em deploy/hospedagem, o operador deve garantir pasta
  persistente, backup e upload inicial (ver
  [04-institution-ic-sp.md](../architecture/04-institution-ic-sp.md#logos-e-mídia-no-deploy)).
- O app **não** implementa sincronização automática com sistemas externos.
- Documentação detalhada em
  [04-institution-ic-sp.md](../architecture/04-institution-ic-sp.md).

## Referências

- [App institution_ic_sp](../architecture/04-institution-ic-sp.md)
- [Mapa de apps](../architecture/03-apps-map.md)
- [Modelo de dados — instituição](../architecture/02-data-model.md#dados-institucionais-ic-sp-)
- Decreto nº 42.847/1998 — estrutura do IC-SP
- Organograma SPTC rev. 15 — códigos NPC/EPC
