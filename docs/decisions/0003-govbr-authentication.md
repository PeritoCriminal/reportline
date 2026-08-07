# reportline/docs/decisions/0003-govbr-authentication.md
# ADR-0003: Estratégia de autenticação em fases (local → Google → gov.br)

**Status:** 🟡 Proposto (fases 0 e 1 implementadas)  
**Data:** 2026-07-26  
**Atualizado:** 2026-07-29

## Contexto

O ReportLine trata laudos e relatórios periciais/forenses — dados sensíveis que,
em uso **institucional** (órgãos públicos, instituições oficiais de perícia ou
integração com processos governamentais), exigem identidade digital confiável e
alinhada às políticas do governo federal.

O app `accounts` usa `CustomUser` (UUID) como identidade central. Todos os fluxos
pós-login (`ForensicExaminerSP`, laudos, permissões) devem depender apenas de
`CustomUser`, nunca de um provedor OAuth específico.

## Estratégia em fases

| Fase | Ambiente | Provedor | Objetivo |
|---|---|---|---|
| **0 — imediata** | Desenvolvimento local | Django username/senha | Destravar login, sessão e telas sem credenciais externas |
| **1 — dev/pessoal** | Dev local e deploy em servidor pessoal | Google OAuth (OIDC) | Login social sem gestão de senhas para peritos em ambiente não institucional |
| **2 — institucional** | Órgão público / IC oficial | Login gov.br (OIDC) | Identidade digital federal; substitui Google no fluxo principal |

A troca entre fases deve ocorrer por **configuração de ambiente** (`AUTH_PROVIDER`)
e backends OIDC distintos, reutilizando um **serviço único de provisionamento**
de `CustomUser` após callback OAuth bem-sucedido.

```
[Google OAuth]  ──┐
                  ├──► provisionar/atualizar CustomUser + sessão Django
[gov.br OIDC]   ──┘
                              │
                              ▼
                    ForensicExaminerSP, laudos, permissões…
```

## Recomendação por ambiente

### Fase 0: login local Django ✅

- **Prós:** zero dependências externas, funciona com `createsuperuser` e Admin.
- **Contras:** gestão manual de senhas; inadequado como fluxo principal em produção.
- **Escopo:** fallback para staff; permanece disponível sob link discreto quando Google está ativo.

### Fase 1: Google OAuth (dev e servidor pessoal) ✅

- **Prós:** login rápido, credenciais via Google Cloud Console (sem credenciamento
  gov.br), adequado a deploy pessoal e demonstrações.
- **Contras:** identidade não institucional; exige política de migração ao adotar gov.br.
- **Implementação:** `django-allauth` + `CustomSocialAccountAdapter` que delega ao
  serviço `accounts/services/oauth_user_service.py`.

### Fase 2: Login gov.br (institucional)

- **Prós:** padrão federal, identidade centralizada (CPF/conta gov.br), conformidade
  com expectativa de sistemas públicos brasileiros.
- **Contras:** credenciamento junto ao Login Único, redirect URIs por ambiente,
  mapeamento de claims e testes em homologação gov.br.
- **Implementação prevista:** backend OIDC (`mozilla-django-oidc` ou equivalente)
  reutilizando o mesmo serviço de provisionamento da fase 1.

Em todas as fases, a autenticação local via Django Admin permanece restrita a
**operadores internos** (superusuários/staff), fora do fluxo principal do perito.

## Opções consideradas (fase institucional)

### 1. Manter username/senha ou Google em produção institucional

- **Contras:** desalinhado com políticas gov.br; Google não atende identidade oficial.

### 2. Login gov.br (OpenID Connect / OAuth 2.0) ✅ recomendado para institucional

- Ver fase 2 acima.

### 3. Provedor OIDC genérico (Keycloak, Azure AD, etc.)

- **Prós:** flexível para ambientes privados ou híbridos.
- **Contras:** não substitui gov.br para uso público institucional no Brasil.

## Decisão

- **Fase 0 (implementada):** login local Django (`LoginView` / `LogoutView`) com
  template em português; `LOGIN_URL` e redirecionamentos configurados.
- **Fase 1 (implementada):** Google OAuth via `django-allauth` como provedor
  principal do perito em dev e deploy pessoal; variáveis `AUTH_PROVIDER=google`,
  `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` no `.env`.
- **Fase 2 (alvo institucional):** Login gov.br substitui Google; contas existentes
  migradas por e-mail verificado ou CPF conforme política a definir.

Nenhuma integração gov.br antes do credenciamento formal no Login Único.

## Consequências

- Serviço de provisionamento OAuth em `accounts/services/oauth_user_service.py`,
  compartilhado com gov.br na fase 2.
- `CustomUser` possui `auth_provider` e `external_subject` para rastrear origem OAuth.
- Fluxos de primeiro acesso (`ForensicExaminerSP`) ocorrem após login bem-sucedido,
  independentemente do provedor.
- Rotas django-allauth ficam em `reportline/urls.py` (`/accounts/social/`), **fora**
  do namespace `accounts:`, pois o allauth resolve callbacks sem prefixo de app.
- Testes de integração gov.br dependerão de ambiente de homologação gov.br.

## Implementação atual (fases 0 e 1)

### Variáveis de ambiente (`.env`)

| Variável | Fase | Descrição |
|---|---|---|
| `AUTH_PROVIDER` | 0 / 1 | `local` (só username/senha) ou `google` (botão Google + staff oculto) |
| `GOOGLE_CLIENT_ID` | 1 | Client ID OAuth (*Web application*) do Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | 1 | Client secret do OAuth Client |

Redirect URI cadastrado no Google Cloud Console:

`http://127.0.0.1:8000/accounts/social/google/login/callback/`

> **Nota:** credenciais OAuth (login) são distintas de service account JSON usada
> em APIs Cloud (STT/voz) — ver [ADR-0005](./0005-external-api-credentials.md).

### Rotas

| Rota | Descrição |
|---|---|
| `/accounts/login/` | Tela de login (`accounts:login`) |
| `/accounts/logout/` | Encerramento de sessão (`accounts:logout`) |
| `/accounts/social/google/login/` | Início do fluxo Google (`google_login`) |
| `/accounts/social/google/login/callback/` | Callback OAuth (`google_callback`) |

### Interface de login

- **Perito (fase 1):** botão principal **Entrar com Google**.
- **Staff/admin:** link discreto **Entrar com administrador** → formulário local
  em collapse Bootstrap (oculto por padrão; expande automaticamente se houver erro).
- Templates allauth sobrescritos em `accounts/templates/socialaccount/` com
  layout do projeto (`base.html`).
- `SOCIALACCOUNT_LOGIN_ON_GET = True` — clique no botão Google redireciona
  direto ao provedor, sem tela intermediária de confirmação.

### Arquivos principais

```
accounts/
  models/custom_user.py          # auth_provider, external_subject
  services/oauth_user_service.py # provision_oauth_user()
  adapters/custom_social_account_adapter.py
  views/auth_views.py            # LoginView, LogoutView
  templates/accounts/login.html
  templates/socialaccount/       # overrides allauth
reportline/urls.py               # include allauth em accounts/social/
```

## TODO

### Fase 0 ✅

- [x] Implementar `LoginView` e `LogoutView` com auth Django nativa.
- [x] Template de login em português e rotas em `accounts/urls.py`.
- [x] Configurar `LOGIN_URL`, `LOGIN_REDIRECT_URL` e `LOGOUT_REDIRECT_URL`.

### Fase 1 — dev / deploy pessoal ✅

- [x] Adicionar `django-allauth` e provider Google.
- [x] Criar serviço de provisionamento de `CustomUser` a partir de claims OAuth.
- [x] Adicionar `auth_provider` e identificador externo em `CustomUser`.
- [x] Botão "Entrar com Google" na tela de login; `AUTH_PROVIDER=google` no `.env`.
- [x] Testes com mock do callback OAuth (sucesso, falha, usuário inativo).

### Fase 2 — ambiente institucional

- [ ] Solicitar credenciamento no [Login Único gov.br](https://www.gov.br/governodigital/pt-br/identidade/conta-gov-br/conta-gov-br).
- [ ] Configurar client OIDC (client_id, client_secret, redirect URIs) por ambiente.
- [ ] Implementar backend gov.br reutilizando serviço de provisionamento.
- [ ] Mapear claims gov.br (CPF, nome, e-mail) para `CustomUser`.
- [ ] Definir política de migração contas Google → gov.br e contas staff/admin.
- [ ] Testes com mock do provedor gov.br.

## Referências

- [Login Único — gov.br](https://www.gov.br/governodigital/pt-br/identidade/conta-gov-br/conta-gov-br)
- [Documentação técnica Login Único (API/OIDC)](https://acesso.gov.br/roteiro-tecnico/)
- [Contexto do sistema — accounts](../architecture/01-context.md)
- [Mapa de apps — accounts](../architecture/03-apps-map.md)
- [ADR-0001: CustomUser com UUID](./0001-custom-user-uuid.md)
- [ADR-0005: Credenciais de APIs externas](./0005-external-api-credentials.md)
