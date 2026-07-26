# ADR-0004: PostgreSQL como SGBD padrão do projeto

**Status:** ✅ Aceito  
**Data:** 2026-07-26

## Contexto

O ReportLine persiste laudos, relatórios e dados de usuários em um **SGBD**
(Sistema Gerenciador de Banco de Dados) relacional. A escolha do banco impacta
desenvolvimento local, testes, documentação e deploy.

Em ambiente **institucional**, a instituição adotante pode já operar outro SGBD
aprovado (Oracle, SQL Server, MariaDB, etc.) ou impor política de infraestrutura
própria.

## Opções consideradas

### 1. PostgreSQL como padrão do projeto ✅

- **Prós:** robusto, open source, amplamente usado com Django, suporte nativo a
  UUID e JSON, alinhado ao `settings.py` atual.
- **Contras:** em produção institucional, pode exigir adaptação se o órgão
  padronizar outro SGBD.

### 2. Abstração multi-SGBD desde o início

- **Prós:** flexibilidade máxima entre engines.
- **Contras:** complexidade prematura; Django já abstrai SQL, mas dialectos e
  operação divergem na prática.

### 3. Vincular o projeto a um SGBD institucional específico agora

- **Prós:** alinhamento imediato a um órgão.
- **Contras:** bloqueia desenvolvimento e aprendizado local; órgão ainda não
  definido na fase atual.

## Decisão

- **Manter PostgreSQL** como SGBD padrão do ReportLine em desenvolvimento,
  testes e documentação.
- **Não alterar** essa escolha na fase inicial do projeto.
- Em **ambiente institucional**, a instituição adotante **pode utilizar outro
  SGBD a seu critério**, desde que compatível com Django ORM e com os requisitos
  operacionais do ReportLine (transações, integridade referencial, tipos UUID).

O código deve continuar usando o ORM do Django; troca de engine limita-se a
configuração (`DATABASES`) e validação de compatibilidade na implantação.

## Consequências

- README, diagramas de arquitetura e setup local permanecem orientados a
  PostgreSQL.
- Migrações Django são a fonte de verdade do schema; testes devem rodar contra
  PostgreSQL (ou equivalente configurado em CI).
- Implantação institucional exige checklist de compatibilidade do SGBD escolhido
  — fora do escopo da fase atual.
- Credenciais de banco em produção seguem a mesma lógica de segredos
  institucionais das demais integrações ([ADR-0005](./0005-external-api-credentials.md)).
- Não há compromisso de suportar oficialmente todos os backends Django; apenas
  registrar que a escolha final em produção institucional é da instituição.

## Referências

- [Contexto do sistema — persistência](../architecture/01-context.md)
- [Modelo de dados](../architecture/02-data-model.md)
- `reportline/settings.py` — `DATABASES['default']['ENGINE']`
