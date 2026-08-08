# reportline/institution_ic_sp/forensic_report/workflows/initial_data/ai/prompts/metadata_extraction/user.md
Extraia metadados administrativos dos trechos abaixo e devolva JSON conforme o schema.

Identifique o tipo de cada documento (Requisição, Minuta, Boletim de Ocorrência, Inquérito Policial, Memorando/Ofício, Laudo Pericial, Laudo Necroscópico, Oitivas) antes de preencher os campos.

{{output_schema_summary}}

Documentos (texto extraído; cada bloco corresponde a um arquivo anexado):
---
{{document_excerpts}}
---

Informações complementares do perito (**prioridade máxima** — prevalecem sobre todos os documentos quando indicarem valor ou correção explícita para um campo):
{{supplementary_prompt}}

Antes de devolver o JSON, normalize nomes próprios (autoridade, distrito/delegacia,
perito, fotógrafo, escaneamento 3D, croqui) com capitalização normativa do português:
inicial maiúscula em cada palavra; preposições/artigos (*de*, *da*, *do*, *das*, *dos*,
*e*, …) em minúsculas no meio do nome (ex.: *José da Silva*, *Maria das Dores*).
