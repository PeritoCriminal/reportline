# reportline/institution_ic_sp/tests/test_exam_category_inference.py
"""
Testes de inferência determinística da categoria de exame pericial.
"""

from django.test import TestCase

from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from institution_ic_sp.forensic_report.common.services.case_metadata_extraction import (
    resolve_exam_category,
)
from institution_ic_sp.forensic_report.common.services.exam_category import (
    EXAM_CATEGORY_PROPERTY_SCENE,
    EXAM_CATEGORY_TRAFFIC_ACCIDENT,
    EXAM_CATEGORY_UNKNOWN,
    EXAM_CATEGORY_WORK_ACCIDENT,
    infer_exam_category_from_text,
    normalize_exam_category,
)


class ExamCategoryTextInferenceTests(TestCase):
    """Testes de inferência de categoria a partir de texto do objetivo ou orientações."""

    def test_levantamento_local_furto_residencia(self):
        """Garante reconhecimento do objetivo típico de local de furto em residência."""
        objective = "LEVANTAMENTO DE LOCAL - FURTO A RESIDENCIA"
        self.assertEqual(
            infer_exam_category_from_text(objective),
            EXAM_CATEGORY_PROPERTY_SCENE,
        )

    def test_accented_furto_residencia(self):
        """Garante normalização de acentos na inferência."""
        objective = "Levantamento de local - furto à residência"
        self.assertEqual(
            infer_exam_category_from_text(objective),
            EXAM_CATEGORY_PROPERTY_SCENE,
        )

    def test_traffic_and_work_categories(self):
        """Garante inferência de acidente de trânsito e de trabalho."""
        self.assertEqual(
            infer_exam_category_from_text("Acidente de trânsito na rodovia"),
            EXAM_CATEGORY_TRAFFIC_ACCIDENT,
        )
        self.assertEqual(
            infer_exam_category_from_text("Acidente de trabalho na obra"),
            EXAM_CATEGORY_WORK_ACCIDENT,
        )

    def test_unknown_when_no_signal(self):
        """Garante fallback para unknown sem indícios no texto."""
        self.assertEqual(
            infer_exam_category_from_text("Exame papiloscópico"),
            EXAM_CATEGORY_UNKNOWN,
        )


class ExamCategoryAliasNormalizationTests(TestCase):
    """Testes de aliases comuns retornados pela IA."""

    def test_property_crime_alias(self):
        """Garante mapeamento de alias property_crime para property_scene."""
        self.assertEqual(
            normalize_exam_category("property_crime"),
            EXAM_CATEGORY_PROPERTY_SCENE,
        )


class ResolveExamCategoryTests(TestCase):
    """Testes de complemento da categoria após merge com payload da IA."""

    def test_resolves_from_exam_objective_when_ai_unknown(self):
        """Completa exam_category quando IA deixa unknown mas objetivo é explícito."""
        metadata = CaseMetadata(
            exam_objective="Objetivo da Perícia: LEVANTAMENTO DE LOCAL - FURTO A RESIDENCIA",
            exam_category=EXAM_CATEGORY_UNKNOWN,
        )
        resolved = resolve_exam_category(metadata)
        self.assertEqual(resolved.exam_category, EXAM_CATEGORY_PROPERTY_SCENE)

    def test_resolves_from_supplementary_prompt(self):
        """Completa exam_category a partir das orientações complementares do perito."""
        metadata = CaseMetadata(
            supplementary_prompt="Trata-se de levantamento de local por furto a residência.",
            exam_category=EXAM_CATEGORY_UNKNOWN,
        )
        resolved = resolve_exam_category(metadata)
        self.assertEqual(resolved.exam_category, EXAM_CATEGORY_PROPERTY_SCENE)

    def test_preserves_ai_category_when_present(self):
        """Não sobrescreve categoria já inferida pela IA."""
        metadata = CaseMetadata(
            exam_objective="LEVANTAMENTO DE LOCAL - FURTO A RESIDENCIA",
            exam_category=EXAM_CATEGORY_TRAFFIC_ACCIDENT,
        )
        resolved = resolve_exam_category(metadata)
        self.assertEqual(resolved.exam_category, EXAM_CATEGORY_TRAFFIC_ACCIDENT)

    def test_no_change_when_still_unknown(self):
        """Mantém unknown quando não há indício no texto."""
        metadata = CaseMetadata(
            exam_objective="Coleta de material biológico.",
            exam_category=EXAM_CATEGORY_UNKNOWN,
        )
        resolved = resolve_exam_category(metadata)
        self.assertEqual(resolved.exam_category, EXAM_CATEGORY_UNKNOWN)
        self.assertIs(resolved, metadata)
