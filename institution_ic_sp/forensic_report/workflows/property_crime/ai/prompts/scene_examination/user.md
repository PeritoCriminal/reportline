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

## Imagens do local (Características do Local)

Para cada imagem abaixo, ``show_in_report`` indica se deve entrar no laudo e
``proposed_caption`` traz a sugestão do perito.

**Contexto:** estas imagens documentam características **estruturais e construtivas**
do imóvel — **não** vestígios ou evidências do evento. Ao compor ``report_images``,
use **presente do indicativo** nas legendas e evite termos de análise de vestígios
(*vestígio*, *evidência*, *ponto de impacto*, *marca de…*). Generalize logradouros
e identificadores visíveis quando aparecerem na proposta ou na cena.

{{scene_images_json}}

Devolva JSON com ``characteristics_heading``, ``attendance_context_paragraph``,
``characteristics_paragraph`` e, quando houver imagens marcadas para exibição,
``report_images`` com legendas no padrão institucional desta seção.
