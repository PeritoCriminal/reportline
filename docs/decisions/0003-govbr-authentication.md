# ADR-0003: Autenticação via gov.br em ambiente institucional

**Status:** 🟡 Proposto  
**Data:** 2026-07-26

## Contexto

O ReportLine trata laudos e relatórios periciais/forenses — dados sensíveis que,
em uso **institucional** (órgãos públicos, instituições oficiais de perícia ou
integração com processos governamentais), exigem identidade digital confiável e
alinhada às políticas do governo federal.

Hoje o app `accounts` usa autenticação Django nativa com `CustomUser` e uma
`LoginView` provisória, adequada à fase de desenvolvimento e aprendizado do
projeto.

## Recomendação

Quando o ReportLine for implantado em **ambiente institucional**, a autenticação
de usuários finais (peritos/examinadores) **deve** ser feita pelo **Login
gov.br** (Login Único / identidade digital federal), e não por credenciais
locais username/senha.

Isso garante:

- Identidade verificada pelo ecossistema gov.br (incluindo níveis de confiança
  da conta gov.br, quando aplicável).
- Conformidade com práticas usuais em sistemas públicos brasileiros.
- Redução de gestão de senhas locais para usuários finais.

A autenticação local via Django Admin pode permanecer restrita a **operadores
internos** (superusuários/staff), se necessário para suporte — fora do fluxo
principal do perito.

## Opções consideradas

### 1. Manter autenticação Django username/senha em produção institucional

- **Prós:** implementação simples, já parcialmente presente no projeto.
- **Contras:** gestão de senhas, recuperação de acesso e nível de confiança da
  identidade ficam a cargo do ReportLine; desalinhado com expectativa institucional.

### 2. Login gov.br (OpenID Connect / OAuth 2.0) ✅ recomendado para institucional

- **Prós:** padrão federal, identidade centralizada, integração com CPF/conta
  gov.br, alinhamento com e-CPF/e-Notariado quando exigido pelo órgão.
- **Contras:** credenciamento junto ao Login Único, configuração de redirect URIs,
  ambientes de homologação/produção e mapeamento de claims para `CustomUser`.

### 3. Provedor OIDC genérico (Keycloak, Azure AD, etc.)

- **Prós:** flexível para ambientes privados ou híbridos.
- **Contras:** não atende diretamente a recomendação gov.br para uso público
  institucional no Brasil.

## Decisão

- **Fase atual (desenvolvimento):** manter autenticação Django local e
  `LoginView` placeholder até existir fluxo de login completo.
- **Fase institucional (alvo):** adotar **Login gov.br** como mecanismo principal
  de autenticação dos peritos/examinadores, integrando via OIDC ao `CustomUser`
  existente (vinculação por CPF ou identificador estável retornado pelo provedor).

Nenhuma integração gov.br deve ser implementada antes do credenciamento formal
do sistema junto ao Login Único; a decisão registra o **alvo arquitetural** para
não acumular dívida de desenho.

## Consequências

- Será necessário pacote ou backend OIDC compatível com Django (ex.: integração
  manual com `mozilla-django-oidc` ou solução equivalente avaliada na época).
- `CustomUser` provavelmente precisará de campo para CPF ou `sub` OIDC e flag de
  origem da conta (local vs gov.br).
- Fluxos de primeiro acesso (provisionamento de `Profile`) devem ocorrer após
  callback OIDC bem-sucedido.
- Testes de integração dependerão de ambiente de homologação gov.br.

## TODO (implementação futura — ambiente institucional)

- [ ] Solicitar credenciamento do ReportLine no [Login Único gov.br](https://www.gov.br/governodigital/pt-br/identidade/conta-gov-br/conta-gov-br).
- [ ] Configurar client OIDC (client_id, client_secret, redirect URIs) por ambiente
  (homologação e produção).
- [ ] Implementar backend/view de callback OIDC no app `accounts`, substituindo a
  autenticação username/senha do fluxo principal do perito.
- [ ] Mapear claims gov.br (CPF, nome, e-mail verificado) para `CustomUser` e
  criar/atualizar usuário no primeiro login.
- [ ] Definir política para contas staff/admin (local vs gov.br) e documentar no
  ADR ou ADR filho.
- [ ] Adicionar testes que mockem o provedor OIDC (caso feliz + falha de callback
  + usuário inativo).

## Referências

- [Login Único — gov.br](https://www.gov.br/governodigital/pt-br/identidade/conta-gov-br/conta-gov-br)
- [Documentação técnica Login Único (API/OIDC)](https://acesso.gov.br/roteiro-tecnico/)
- [Contexto do sistema — accounts](../architecture/01-context.md)
- [Mapa de apps — accounts](../architecture/03-apps-map.md)
- [ADR-0001: CustomUser com UUID](./0001-custom-user-uuid.md)
- [ADR-0005: Credenciais de APIs externas](./0005-external-api-credentials.md)
