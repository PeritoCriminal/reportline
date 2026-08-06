# ADR-0008: Sanitização local de PII antes de APIs externas de IA

**Status:** ✅ Aceito  
**Data:** 2026-08-06

## Contexto

O ReportLine integra a **OpenAI** para extração administrativa de metadados e
redação assistida de trechos do laudo pericial ([ADR-0005](./0005-external-api-credentials.md)).
Documentos de requisição, BO e minutas contêm **dados pessoais e sigilosos**
(nomes, CPF, endereços, números de BO/IP/laudo).

Enviar esse conteúdo em bruto a provedores externos viola requisitos de
compliance (sigilo funcional, LGPD, cadeia de custódia). O perito deve revisar
toda sugestão da IA antes de persistir dados no laudo.

## Opções consideradas

### 1. Enviar documentos integrais à OpenAI

- **Prós:** extração mais fácil para a IA.
- **Contras:** inaceitável sob compliance institucional.

### 2. Sanitização local obrigatória + gateway único ✅

- **Prós:** controle no servidor; auditoria; bloqueio quando PII residual
  permanece; allowlist de termos institucionais; degradar graciosamente sem chave.
- **Contras:** extração 100% pela IA fica limitada; manutenção de padrões regex
  e modelo spaCy no servidor.

### 3. IA on-premises para extração completa

- **Prós:** dados não saem da instituição.
- **Contras:** custo e operação elevados; fora do escopo atual.

## Decisão

Adotar **pipeline local de sanitização** em Python, aplicado **obrigatoriamente**
antes de qualquer chamada à OpenAI:

1. **Extração local** do PDF (`pypdf`) — texto permanece no servidor.
2. **Sanitização** — regex genéricos + regex forenses (BO, IP, placa…) +
   Presidio/spaCy (`pt_core_news_lg`) para `PERSON`/`LOCATION`, quando disponível.
3. **Allowlist** — termos institucionais preservados (ex.: *Autoridade Requisitante*,
   *croqui*, *fotógrafo*); extensível via settings.
4. **Gateway único** (`institution_ic_sp/.../ai/gateway.py`) — único ponto de saída
   para OpenAI; proíbe bypass acidental.
5. **Auditoria** — model `AiSanitizationAudit` (`common`): hash SHA-256, contadores,
   operação; **sem** texto bruto em log ou banco.
6. **Imagens** — envio multimodal **somente** se `ForensicExaminerSP.can_send_images_to_external_ai`
   estiver habilitado no admin (default `False`).
7. **Human-in-the-loop** — retorno da IA é minuta/sugestão; merge manual > IA;
   confirmação do perito antes de gravar no dossiê/laudo.

Variáveis de ambiente documentadas em `.env.example` e
[09-forensic-ai-privacy.md](../architecture/09-forensic-ai-privacy.md).

## Consequências

- **Servidor** exige Python, deps (`presidio-analyzer`, `spacy`) e modelo
  `pt_core_news_lg`; **usuários finais** acessam só pelo navegador.
- Sem spaCy instalado, o pipeline opera **apenas com regex** (log de aviso).
- Texto com PII residual após sanitização retorna **HTTP 422** com mensagem em
  português; imagens sem permissão retornam **HTTP 403**.
- Fase futura: extração local híbrida de campos estruturados (regex) reduzindo
  dependência da IA para metadados sensíveis.
- Testes mockam OpenAI; regras críticas têm testes unitários dedicados.

## Referências

- [ADR-0005: Credenciais de APIs externas](./0005-external-api-credentials.md)
- [09-forensic-ai-privacy.md](../architecture/09-forensic-ai-privacy.md)
- [05-profiles.md](../architecture/05-profiles.md) — permissão de imagens
- `common/privacy/` — pipeline base
- `institution_ic_sp/forensic_report/common/ai/` — gateway e padrões forenses
