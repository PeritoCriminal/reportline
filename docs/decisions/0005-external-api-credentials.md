# ADR-0005: Credenciais de APIs externas (pessoais vs institucionais)

**Status:** ✅ Aceito  
**Data:** 2026-07-26

## Contexto

O ReportLine prevê integrações com serviços externos — por exemplo, **APIs de
inteligência artificial** (assistentes, geração ou revisão de texto), **comando
por voz** (Google e equivalentes) e **outras APIs** de apoio à produção de
laudos e relatórios.

Na **fase de desenvolvimento**, o projeto é operado localmente pelo autor com
credenciais **pessoais** (contas, quotas e faturamento particulares).

Em **ambiente institucional**, o uso desses serviços passa a envolver dados
sensíveis, responsabilidade do órgão e políticas de contratação/compliance. Chaves
pessoais **não** devem ser reutilizadas em produção institucional.

## Opções consideradas

### 1. Credenciais pessoais em todos os ambientes

- **Prós:** simplicidade no início.
- **Contras:** viola governança institucional; expõe o desenvolvedor a risco
  legal/financeiro; impede auditoria e rotação formal de segredos.

### 2. Credenciais pessoais só em desenvolvimento; institucionais em produção ✅

- **Prós:** alinhado à fase atual do projeto e ao deploy futuro; separação clara
  de responsabilidade; compatível com `.env` local e secret store institucional.
- **Contras:** exige checklist na implantação e possivelmente contratos/licenças
  distintos por órgão.

### 3. Hardcode ou repositório de chaves no código

- **Prós:** nenhum relevante para produção.
- **Contras:** risco grave de vazamento; `.gitignore` já exclui `.env` por design.

## Decisão

- **Desenvolvimento (atual):** credenciais **pessoais** do desenvolvedor, lidas
  exclusivamente via **variáveis de ambiente** (arquivo `.env` local, fora do Git)
  e arquivos JSON em **`var/secrets/`** (também ignorados pelo Git).
  Exemplos previstos: chaves de IA, Google Cloud (voz/STT via service account),
  OAuth Client ID/secret para login Google (somente no `.env`).
- **Ambiente institucional (alvo):** todas as chaves, tokens e credenciais de
  APIs externas devem ser **institucionais** — contratadas, emitidas ou
  gerenciadas pelo órgão adotante (secret manager, cofre ou política equivalente
  da instituição).
- **Nunca** commitar segredos no repositório; o código referencia apenas nomes de
  variáveis de ambiente (ex.: `OPENAI_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`).

### Organização local de segredos

| Tipo | Onde guardar | Exemplo de variável |
|---|---|---|
| Pares chave=valor (OAuth login, DB, SECRET_KEY) | `.env` | `GOOGLE_CLIENT_ID`, `AUTH_PROVIDER` |
| Arquivos JSON (service account Google Cloud) | `var/secrets/` | `GOOGLE_APPLICATION_CREDENTIALS=var/secrets/reportline-stt-key.json` |

A pasta `var/secrets/` é versionada apenas com `.gitkeep`; conteúdo real fica
local. **Login Google (OAuth)** usa client ID/secret no `.env`; **APIs Cloud**
(STT, voz) usam JSON de service account — credenciais distintas (ver
[ADR-0003](./0003-govbr-authentication.md)).

A mesma lógica aplica-se a credenciais OIDC do gov.br (ver ADR-0003): pessoais
não substituem client institucional em produção.

## Consequências

- Funcionalidades que dependem de API externa devem **degradar graciosamente**
  ou sinalizar indisponibilidade quando a variável de ambiente não estiver
  configurada (evita dependência silenciosa de chave pessoal em CI).
- Documentação de setup local pode citar variáveis genéricas, sem valores reais.
- Implantação institucional exige inventário de integrações, contratos vigentes,
  rotação de chaves e revisão de LGPD/conformidade para envio de dados a terceiros.
- Testes automatizados devem **mockar** chamadas externas; não depender de chaves
  pessoais no pipeline.

## TODO (implantação institucional)

- [ ] Inventariar integrações externas ativas (IA, voz Google, outras APIs).
- [ ] Substituir credenciais pessoais por credenciais/contas institucionais.
- [ ] Documentar variáveis de ambiente exigidas por ambiente (dev/homolog/prod).
- [ ] Definir política de retenção e envio de conteúdo de laudos a provedores de IA.
- [ ] Configurar rotação e auditoria de segredos no cofre da instituição.

## Referências

- [Contexto do sistema — integrações externas](../architecture/01-context.md)
- [ADR-0003: Autenticação gov.br (institucional)](./0003-govbr-authentication.md)
- `.gitignore` — exclusão de `.env` e variantes
- `reportline/settings.py` — `load_dotenv()` e leitura de configuração
