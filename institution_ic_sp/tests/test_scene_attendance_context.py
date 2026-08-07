"""
Testes do contexto de atendimento estruturado no exame de local patrimonial.
"""

from django.test import TestCase

from institution_ic_sp.forensic_report.common.services.scene_attendance_context import (
    normalize_scene_attendance_context,
    scene_attendance_context_from_extensions,
    scene_attendance_context_to_payload,
)
from institution_ic_sp.forensic_report.services.forensic_bootstrap import (
    attach_bootstrap_meta,
    save_bootstrap_after_analyze,
)
from institution_ic_sp.forensic_report.services.scene_attendance_context_finalize import (
    finalize_attendance_context_prompts,
)
from institution_ic_sp.forensic_report.services.scene_attendance_context_prompts import (
    compute_pending_attendance_context_prompts,
    pending_attendance_context_prompt_catalog,
)
from institution_ic_sp.forensic_report.common.services.case_metadata import CaseMetadata
from reports.models import Report


class SceneAttendanceContextTests(TestCase):
    """Testes de normalização e prompts do contexto de atendimento."""

    def test_normalize_preservation_and_yes_no_values(self):
        """Garante normalização de preservação do local e respostas sim/não."""
        context = normalize_scene_attendance_context(
            {
                "location_preserved": "parcialmente",
                "police_authority_present": "sim",
                "investigation_team_present": "não",
            }
        )

        self.assertEqual(context.location_preserved, "partially")
        self.assertEqual(context.police_authority_present, "yes")
        self.assertEqual(context.investigation_team_present, "no")

    def test_pending_prompts_include_informant_briefing_only_when_needed(self):
        """Garante prompt de informes somente quando houver resposta afirmativa."""
        without_briefing = normalize_scene_attendance_context(
            {"informant_provided_info": "yes"}
        )
        with_briefing = normalize_scene_attendance_context(
            {
                "informant_provided_info": "yes",
                "informant_briefing": "Informou que o imóvel estava fechado.",
            }
        )

        self.assertIn(
            "informant_briefing",
            compute_pending_attendance_context_prompts(without_briefing),
        )
        self.assertNotIn(
            "informant_briefing",
            compute_pending_attendance_context_prompts(with_briefing),
        )

    def test_prompt_catalog_personalizes_informant_label_with_access_name(self):
        """Garante rótulo dinâmico do prompt de informes com nome de quem franqueou acesso."""
        context = normalize_scene_attendance_context(
            {
                "access_granted_by": "proprietário do imóvel",
                "informant_provided_info": "yes",
            }
        )
        catalog = pending_attendance_context_prompt_catalog(context)
        briefing = next(item for item in catalog if item["field"] == "informant_briefing")

        self.assertIn("proprietário do imóvel", str(briefing["label"]))

    def test_extensions_seed_bootstrap_attendance_context(self):
        """Garante preenchimento inicial do contexto a partir de extensions inferidas."""
        report = Report.objects.create(title="Laudo teste")
        metadata = CaseMetadata(exam_category="property_scene")
        save_bootstrap_after_analyze(
            report,
            metadata,
            extensions={
                "scene_location_preserved": "yes",
                "scene_access_granted_by": "síndico do condomínio",
            },
        )

        report.refresh_from_db()
        from institution_ic_sp.forensic_report.services.forensic_bootstrap import get_bootstrap_meta

        bootstrap = get_bootstrap_meta(report.page_layout) or {}
        context = bootstrap.get("scene_attendance_context", {})

        self.assertEqual(context.get("location_preserved"), "yes")
        self.assertEqual(context.get("access_granted_by"), "síndico do condomínio")

    def test_finalize_attendance_context_prompts_persists_answers(self):
        """Garante persistência das respostas do perito no bootstrap."""
        report = Report.objects.create(title="Laudo teste")
        report.page_layout = attach_bootstrap_meta(
            report.page_layout,
            {
                "state": "collecting_scene_continuation",
                "scene_attendance_context": scene_attendance_context_to_payload(
                    normalize_scene_attendance_context({})
                ),
            },
        )
        report.save(update_fields=["page_layout"])

        finalize_attendance_context_prompts(
            report,
            answers={
                "location_preserved": "yes",
                "police_authority_present": "no",
                "investigation_team_present": "yes",
                "access_granted_by": "proprietário",
                "informant_provided_info": "no",
            },
            skipped=[],
        )

        report.refresh_from_db()
        from institution_ic_sp.forensic_report.common.services.scene_attendance_context import (
            scene_attendance_context_from_bootstrap,
        )

        context = scene_attendance_context_from_bootstrap(report.page_layout)
        self.assertEqual(context.location_preserved, "yes")
        self.assertEqual(context.access_granted_by, "proprietário")
        self.assertEqual(context.informant_provided_info, "no")
        self.assertEqual(context.informant_briefing, "")

    def test_scene_attendance_context_from_extensions_maps_keys(self):
        """Garante mapeamento das chaves documentais de extensions para o contexto."""
        context = scene_attendance_context_from_extensions(
            {
                "scene_police_authority_present": "yes",
                "scene_informant_briefing": "Local preservado pela GCM.",
            }
        )

        self.assertEqual(context.police_authority_present, "yes")
        self.assertEqual(context.informant_briefing, "Local preservado pela GCM.")
