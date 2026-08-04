"""
Inferência de gênero gramatical a partir de honoríficos Dr./Dra.
"""

from __future__ import annotations

import re

from profiles.models import GenderCalling


def infer_requesting_authority_gender(raw_authority: str) -> str | None:
    """
    Infere tratamento masculino/feminino pelo prefixo Dr./Dra. na autoridade.

    Retorna ``None`` quando o prefixo estiver ausente (texto neutro no preâmbulo).
    """
    value = (raw_authority or "").strip()
    if re.match(r"^dra\.", value, re.IGNORECASE):
        return GenderCalling.FEMALE
    if re.match(r"^dr\.", value, re.IGNORECASE):
        return GenderCalling.MALE
    return None


def strip_leading_dr_prefix(name: str) -> str:
    """Remove prefixo Dr./Dra. para reaplicar honorífico coerente."""
    cleaned = (name or "").strip()
    return re.sub(r"^dra?\.\s*", "", cleaned, flags=re.IGNORECASE).strip()


def authority_with_honorific(
    raw_authority: str,
    *,
    requesting_authority_gender: str | None = None,
) -> str:
    """Formata autoridade requisitante com Dr./Dra. quando o gênero é conhecido."""
    raw = (raw_authority or "").strip()
    body = strip_leading_dr_prefix(raw)
    if not body:
        return ""

    gender = requesting_authority_gender
    if gender is None:
        gender = infer_requesting_authority_gender(raw)

    if gender == GenderCalling.FEMALE:
        return f"Dra. {body}"
    if gender == GenderCalling.MALE:
        return f"Dr. {body}"
    return body


def requisition_authority_clause(*, requesting_authority_gender: str | None) -> str:
    """Trecho delegado do preâmbulo (pelo/pela, Delegado/Delegada)."""
    if requesting_authority_gender == GenderCalling.FEMALE:
        return "pela Exma. Sra. Delegada de Polícia"
    if requesting_authority_gender == GenderCalling.MALE:
        return "pelo Exmo. Sr. Delegado de Polícia"
    return "pelo(a) Exmo(a). Sr(a). Delegado(a) de Polícia"


def examiner_designation_phrase(*, calling_gender: str | None) -> str:
    """Frase de designação do perito no preâmbulo."""
    if calling_gender == GenderCalling.FEMALE:
        return "foi designada a Perita Criminal"
    return "foi designado o Perito Criminal"
