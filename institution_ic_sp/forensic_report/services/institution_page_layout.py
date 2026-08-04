"""
Cabeçalho e rodapé institucionais para laudos periciais do IC-SP.

Copia logos da ``Institution`` para ``ReportImage`` do laudo e monta
``page_layout`` com modelos tabulares do editor de relatórios.
"""

from __future__ import annotations

import io
from typing import Any

from django.core.files.base import ContentFile

from institution_ic_sp.models import Institution
from profiles.models import ForensicExaminerSP
from reports.models import Report, ReportImage
from reports.services.report_inline_text import sanitize_header_text_html
from reports.services.report_kind import merge_reportline_meta
from reports.services.report_page_layout import (
    FOOTER_TEMPLATE_TEXT_ONLY,
    LAYOUT_TEMPLATE_LOGO_TEXT_LOGO,
    apply_footer_template,
    apply_header_template,
    default_header_extra_rule_row,
    default_header_extra_text_row,
    initial_header_logo_display_size_by_width,
    normalize_text_cell,
    update_logo_cell_from_image,
)

INSTITUTION_HEADER_SECURITY_SECRETARIAT = "SECRETARIA DA SEGURANÇA PÚBLICA"
INSTITUTION_HEADER_SPTC = "SUPERINTENDÊNCIA DA POLÍCIA TÉCNICO-CIENTÍFICA (SPTC)"
INSTITUTION_HEADER_IC = "INSTITUTO DE CRIMINALÍSTICA"
INSTITUTION_HEADER_NAMESAKE = (
    '"PERITO CRIMINAL DR. OCTÁVIO EDUARDO DE BRITO ALVARENGA"'
)


def _assignment_label(examiner: ForensicExaminerSP) -> tuple[str, str]:
    """Retorna rótulo de unidade pericial e município da lotação."""
    if examiner.forensic_team_id is not None:
        team = examiner.forensic_team
        return team.name, team.headquarters_city
    if examiner.forensic_nucleus_id is not None:
        nucleus = examiner.forensic_nucleus
        return nucleus.name, nucleus.headquarters_city
    return "", ""


def _header_unit_name(examiner: ForensicExaminerSP) -> str:
    """Retorna o nome da unidade pericial exibido no cabeçalho institucional."""
    nucleus = examiner.assigned_nucleus
    if nucleus is not None:
        return nucleus.name.strip()
    _unit_label, _city = _assignment_label(examiner)
    return _unit_label.strip()


def _format_institutional_contact_line(phone: str, email: str) -> str:
    """Monta linha de telefone e e-mail institucional da lotação pericial."""
    cleaned_phone = phone.strip()
    cleaned_email = email.strip()
    if cleaned_phone and cleaned_email:
        return f"Telefone: {cleaned_phone} - {cleaned_email}"
    if cleaned_phone:
        return f"Telefone: {cleaned_phone}"
    return cleaned_email


def _assignment_contact(examiner: ForensicExaminerSP) -> tuple[str, str, str]:
    """Retorna endereço, telefone e e-mail da lotação do perito."""
    if examiner.forensic_team_id is not None:
        team = examiner.forensic_team
        return team.address, team.phone, team.institutional_email
    if examiner.forensic_nucleus_id is not None:
        nucleus = examiner.forensic_nucleus
        return nucleus.address, nucleus.phone, nucleus.institutional_email
    return "", "", ""


def _build_header_text(institution: Institution, examiner: ForensicExaminerSP) -> str:
    """Monta HTML do texto central do cabeçalho institucional."""
    _ = institution
    lines = [
        INSTITUTION_HEADER_SECURITY_SECRETARIAT,
        INSTITUTION_HEADER_SPTC,
        INSTITUTION_HEADER_IC,
        INSTITUTION_HEADER_NAMESAKE,
    ]

    unit_name = _header_unit_name(examiner)
    if unit_name:
        lines.append(unit_name)

    address, phone, email = _assignment_contact(examiner)
    cleaned_address = address.strip()
    if cleaned_address:
        lines.append(cleaned_address)
    contact_line = _format_institutional_contact_line(phone, email)
    if contact_line:
        lines.append(contact_line)

    return sanitize_header_text_html("<br>".join(lines))


def _build_footer_text(institution: Institution) -> str:
    """Monta HTML do rodapé institucional."""
    lines = [institution.acronym]
    if institution.headquarters_city:
        lines.append(institution.headquarters_city)
    return sanitize_header_text_html(" — ".join(lines))


def _build_header_extra_rows(main_title_text: str) -> list[dict[str, Any]]:
    """Monta linha horizontal e número do laudo abaixo do cabeçalho principal."""
    report_number_row = default_header_extra_text_row(align="right")
    report_number_row["text"] = sanitize_header_text_html(main_title_text.strip())
    return [
        default_header_extra_rule_row(),
        report_number_row,
    ]


def _copy_institution_logo_to_report(
    report: Report,
    image_field,
    *,
    alt: str = "",
) -> ReportImage | None:
    """Copia arquivo de logo institucional para imagens do laudo."""
    _ = alt
    if not image_field or not getattr(image_field, "name", ""):
        return None

    image_field.open("rb")
    try:
        content = image_field.read()
    finally:
        image_field.close()

    if not content:
        return None

    try:
        from PIL import Image

        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
    except Exception:
        width, height = 1, 1

    original_name = image_field.name.rsplit("/", 1)[-1]
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "png"

    report_image = ReportImage(
        report=report,
        width=max(1, width),
        height=max(1, height),
        original_filename=original_name,
    )
    report_image.save()
    report_image.image.save(
        f"{report_image.pk}.{extension}",
        ContentFile(content),
        save=True,
    )
    return report_image


def _logo_payload(report_image: ReportImage) -> dict[str, Any]:
    """Monta payload de célula de logo a partir de ``ReportImage``."""
    display_width, display_height = initial_header_logo_display_size_by_width(
        report_image.width,
        report_image.height,
    )
    return {
        "file": report_image.image.name,
        "image_id": str(report_image.pk),
        "width": report_image.width,
        "height": report_image.height,
        "display_width": display_width,
        "display_height": display_height,
        "alt": report_image.original_filename,
    }


def build_institution_page_layout(
    report: Report,
    *,
    institution: Institution,
    examiner: ForensicExaminerSP,
    workflow: str,
    main_title_text: str = "",
) -> dict[str, Any]:
    """
    Monta layout de página com cabeçalho e rodapé institucionais.

    Inclui metadados de laudo pericial em ``reportline_meta`` para
    identificação na listagem de relatórios.
    """
    layout = apply_header_template({}, LAYOUT_TEMPLATE_LOGO_TEXT_LOGO)
    layout = apply_footer_template(layout, FOOTER_TEMPLATE_TEXT_ONLY)

    header = layout["header"]
    header_cells = header["cells"]
    header_cells[1] = normalize_text_cell(
        {
            **header_cells[1],
            "text": _build_header_text(institution, examiner),
            "align": "center",
        }
    )
    header["extra_rows"] = _build_header_extra_rows(main_title_text)

    footer_cells = layout["footer"]["cells"]
    footer_cells[0] = normalize_text_cell(
        {
            **footer_cells[0],
            "text": _build_footer_text(institution),
            "align": "center",
            "show_page_number": True,
        }
    )

    sp_logo = _copy_institution_logo_to_report(
        report,
        institution.sp_logo,
        alt="Logo do Governo de São Paulo",
    )
    if sp_logo is not None:
        layout = update_logo_cell_from_image(
            layout,
            cell_index=0,
            image_payload=_logo_payload(sp_logo),
        )

    sptc_logo = _copy_institution_logo_to_report(
        report,
        institution.sptc_logo,
        alt="Logo da SPTC",
    )
    if sptc_logo is not None:
        layout = update_logo_cell_from_image(
            layout,
            cell_index=2,
            image_payload=_logo_payload(sptc_logo),
        )

    return merge_reportline_meta(layout, workflow=workflow)


def get_examiner_assignment_labels(examiner: ForensicExaminerSP) -> tuple[str, str]:
    """Expõe unidade e município da lotação para listas do laudo."""
    return _assignment_label(examiner)
