"""
Cabeçalho e rodapé institucionais para laudos periciais do IC-SP.

Copia logos da ``Institution`` para ``ReportImage`` do laudo e monta
``page_layout`` com modelos tabulares do editor de relatórios.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from institution_ic_sp.models import Institution
from profiles.models import ForensicExaminerSP
from reports.models import Report, ReportImage
from reports.services.report_image_processing import (
    content_type_from_filename,
    process_image_bytes,
)
from reports.services.report_inline_text import sanitize_header_text_html
from reports.services.report_kind import attach_institutional_page_layout_snapshot, merge_reportline_meta
from reports.services.report_page_layout import (
    FOOTER_TEMPLATE_TEXT_ONLY,
    LAYOUT_TEMPLATE_LOGO_TEXT_LOGO,
    apply_footer_template,
    apply_header_template,
    default_header_extra_rule_row,
    default_header_extra_text_row,
    initial_header_logo_display_size_by_width,
    normalize_footer_text_cell,
    normalize_text_cell,
    update_logo_cell_from_image,
)

INSTITUTION_HEADER_SECURITY_SECRETARIAT = "SECRETARIA DA SEGURANÇA PÚBLICA"
INSTITUTION_HEADER_SPTC = "SUPERINTENDÊNCIA DA POLÍCIA TÉCNICO-CIENTÍFICA (SPTC)"
INSTITUTION_HEADER_IC = "INSTITUTO DE CRIMINALÍSTICA"
INSTITUTION_HEADER_NAMESAKE = (
    '"Perito Criminal Dr. Octávio Eduardo de Brito Alvarenga"'
)
INSTITUTION_FOOTER_DISCLAIMER_LINE_1 = (
    "Esta folha é propriedade da Superintendência da Polícia Técnico-Científica "
    "e seu conteúdo não"
)
INSTITUTION_FOOTER_DISCLAIMER_LINE_2 = (
    "pode ser copiado ou revelado a terceiros sem autorização expressa."
)
INSTITUTION_HEADER_LOGO_CELL_SOURCES = (
    (0, "sp_logo"),
    (2, "sptc_logo"),
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
        return f"{cleaned_phone} | {cleaned_email}"
    if cleaned_phone:
        return cleaned_phone
    return cleaned_email


def _styled_header_line(
    text: str,
    *,
    bold: bool = False,
    font_size: str = "md",
) -> str:
    """Monta fragmento HTML de linha do cabeçalho institucional."""
    cleaned = text.strip()
    if not cleaned:
        return ""
    if font_size not in {"sm", "md", "lg"}:
        font_size = "md"
    inner = f'<span class="report-inline-font-{font_size}">{cleaned}</span>'
    if bold:
        inner = f"<strong>{inner}</strong>"
    return inner


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
        _styled_header_line(
            INSTITUTION_HEADER_SECURITY_SECRETARIAT,
            bold=True,
            font_size="md",
        ),
        _styled_header_line(
            INSTITUTION_HEADER_SPTC,
            bold=True,
            font_size="sm",
        ),
        _styled_header_line(
            INSTITUTION_HEADER_IC,
            font_size="md",
        ),
        _styled_header_line(
            INSTITUTION_HEADER_NAMESAKE,
            font_size="sm",
        ),
    ]

    unit_name = _header_unit_name(examiner)
    if unit_name:
        lines.append(_styled_header_line(unit_name, font_size="sm"))

    address, phone, email = _assignment_contact(examiner)
    cleaned_address = address.strip()
    if cleaned_address:
        lines.append(_styled_header_line(cleaned_address, font_size="sm"))
    contact_line = _format_institutional_contact_line(phone, email)
    if contact_line:
        lines.append(_styled_header_line(contact_line, font_size="sm"))

    return sanitize_header_text_html("<br>".join(line for line in lines if line))


def _styled_footer_disclaimer() -> str:
    """Monta aviso institucional do rodapé (10 pt, itálico, centralizado)."""
    inner = (
        f'<span class="report-inline-font-xs">'
        f"{INSTITUTION_FOOTER_DISCLAIMER_LINE_1}<br>"
        f"{INSTITUTION_FOOTER_DISCLAIMER_LINE_2}"
        f"</span>"
    )
    return f"<em>{inner}</em>"


def _build_footer_text(institution: Institution) -> str:
    """Monta HTML do rodapé institucional."""
    _ = institution
    return sanitize_header_text_html(_styled_footer_disclaimer())


def _build_header_extra_rows(main_title_text: str) -> list[dict[str, Any]]:
    """Monta linha horizontal e número do laudo abaixo do cabeçalho principal."""
    report_number_row = default_header_extra_text_row(align="right")
    report_number_row["text"] = sanitize_header_text_html(
        _styled_header_line(main_title_text.strip(), font_size="sm")
    )
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

    original_name = image_field.name.rsplit("/", 1)[-1]
    try:
        image_bytes, extension, width, height = process_image_bytes(
            content,
            filename=original_name,
            content_type=content_type_from_filename(original_name),
        )
    except ValidationError:
        return None

    report_image = ReportImage(
        report=report,
        width=width,
        height=height,
        original_filename=original_name,
    )
    report_image.save()
    report_image.image.save(
        f"{report_image.pk}.{extension}",
        ContentFile(image_bytes),
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


def rehydrate_institutional_header_logos(
    report: Report,
    layout: dict[str, Any],
    *,
    institution: Institution | None = None,
) -> dict[str, Any]:
    """
    Garante emblemas do cabeçalho institucional após restauração do layout.

    Reutiliza ``ReportImage`` do snapshot quando ainda existir; caso contrário,
    copia novamente os arquivos originais da ``Institution``.
    """
    institution = institution or Institution.objects.first()
    if institution is None:
        return layout

    header = layout.get("header")
    if not isinstance(header, dict) or not header.get("enabled"):
        return layout

    cells = header.get("cells", [])
    updated = layout

    for cell_index, field_name in INSTITUTION_HEADER_LOGO_CELL_SOURCES:
        if cell_index >= len(cells) or cells[cell_index].get("type") != "logo":
            continue

        image_payload = _resolve_institutional_logo_payload(
            report,
            cells[cell_index],
            logo_field=getattr(institution, field_name, None),
        )
        if image_payload is None:
            continue

        updated = update_logo_cell_from_image(
            updated,
            cell_index=cell_index,
            image_payload=image_payload,
        )

    return updated


def _resolve_institutional_logo_payload(
    report: Report,
    logo_cell: dict[str, Any],
    *,
    logo_field,
) -> dict[str, Any] | None:
    """Resolve payload de logo reutilizando imagem do laudo ou copiando da instituição."""
    image_id = logo_cell.get("image_id")
    if image_id:
        existing = ReportImage.objects.filter(pk=image_id, report=report).first()
        if existing is not None and existing.image.name:
            return _logo_payload(existing)

    report_image = _copy_institution_logo_to_report(report, logo_field)
    if report_image is None:
        return None
    return _logo_payload(report_image)


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
    footer_cells[0] = normalize_footer_text_cell(
        {
            **footer_cells[0],
            "text": _build_footer_text(institution),
            "align": "center",
            "indent_level": 0,
            "first_line_indent": False,
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

    layout = merge_reportline_meta(layout, workflow=workflow)
    return attach_institutional_page_layout_snapshot(layout)


def get_examiner_assignment_labels(examiner: ForensicExaminerSP) -> tuple[str, str]:
    """Expõe unidade e município da lotação para listas do laudo."""
    return _assignment_label(examiner)
