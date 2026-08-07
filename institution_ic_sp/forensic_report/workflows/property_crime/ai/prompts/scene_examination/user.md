# reportline/institution_ic_sp/forensic_report/workflows/property_crime/ai/prompts/scene_examination/user.md
Redija os trechos de exame de local com base nas informações abaixo.

## Metadados administrativos

{{metadata_json}}

## Localização informada

{{location_text}}

## Orientações do perito sobre o local

{{scene_prompt}}

## Dados estruturados do contexto de atendimento

{{attendance_context_text}}

## Trechos documentais (referência)

{{document_excerpts}}

Devolva JSON com ``characteristics_heading``, ``attendance_context_paragraph`` e ``characteristics_paragraph``.
