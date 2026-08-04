Extraia metadados administrativos dos trechos abaixo e devolva JSON conforme o schema.

Identifique o tipo de cada documento (Requisição, Minuta, Boletim de Ocorrência, Inquérito Policial, Memorando/Ofício, Laudo Pericial, Laudo Necroscópico, Oitivas) antes de preencher os campos.

{{output_schema_summary}}

Documentos (texto extraído; cada bloco corresponde a um arquivo anexado):
---
{{document_excerpts}}
---

Informações complementares do perito (**prioridade máxima** — prevalecem sobre todos os documentos quando indicarem valor ou correção explícita para um campo):
{{supplementary_prompt}}
