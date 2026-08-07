# reportline/institution_ic_sp/forensic_report/workflows/property_crime/ai/prompts/trace_observation/user.md
Redija a descrição do vestígio com base nas informações abaixo.

## Metadados administrativos

{{metadata_json}}

## Orientações do perito sobre o vestígio

{{trace_prompt}}

## Imagens do vestígio

Para cada imagem, ``show_in_report`` indica se deve entrar no laudo e ``proposed_caption`` traz a sugestão do perito.

{{trace_images_json}}

Devolva JSON com ``trace_paragraph`` e, quando houver imagens marcadas para exibição, ``report_images``.
