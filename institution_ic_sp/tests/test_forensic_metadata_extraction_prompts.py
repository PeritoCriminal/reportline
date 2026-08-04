"""
Testes dos prompts e schema da extração administrativa de metadados.
"""

from django.test import TestCase

from institution_ic_sp.forensic_report.common.ai.prompt_loader import (
    load_case_metadata_schema_summary,
    load_prompt_markdown,
)
from institution_ic_sp.forensic_report.registry import GENERIC_WORKFLOW


class MetadataExtractionPromptTests(TestCase):
    """Testes dos contratos de prompt da etapa de extração administrativa."""

    def test_system_prompt_enforces_extractor_role_and_source_hierarchy(self):
        """Garante regras de extrator documental e hierarquia de fontes no system prompt."""
        system = load_prompt_markdown(
            workflow_slug=GENERIC_WORKFLOW.slug,
            task="metadata_extraction",
            name="system",
        )

        self.assertIn("metadados **administrativos**", system)
        self.assertIn("Requisição de Exame Pericial", system)
        self.assertIn("Boletim de Ocorrência", system)
        self.assertIn("Inquérito Policial", system)
        self.assertIn("Minuta", system)
        self.assertIn("Laudo Necroscópico", system)
        self.assertIn("Oitivas", system)
        self.assertIn("Informações complementares do perito", system)
        self.assertIn("prevalecem sobre todos os documentos", system.lower())
        self.assertIn("Na dúvida, deixe o campo vazio", system)

    def test_user_prompt_marks_supplementary_as_highest_priority(self):
        """Garante que informações complementares prevaleçam sobre os documentos."""
        user = load_prompt_markdown(
            workflow_slug=GENERIC_WORKFLOW.slug,
            task="metadata_extraction",
            name="user",
        )

        self.assertIn("{{supplementary_prompt}}", user)
        self.assertIn("prioridade máxima", user.lower())
        self.assertIn("prevalecem sobre todos os documentos", user.lower())

    def test_schema_summary_includes_field_priority_hints(self):
        """Garante que o resumo do schema oriente prioridade documental nos campos-chave."""
        summary = load_case_metadata_schema_summary()

        self.assertIn("occurrence_report", summary)
        self.assertIn("Prioridade: Requisição", summary)
        self.assertIn("Copiar exatamente", summary)

    def test_schema_summary_describes_requisition_at_location_and_default_time(self):
        """Garante orientação de localização e hora padrão para requisition_at."""
        summary = load_case_metadata_schema_summary()

        self.assertIn("requisition_at", summary)
        self.assertIn("assinatura da autoridade requisitante", summary.lower())
        self.assertIn("T00:00", summary)
        self.assertIn("não consta no bo", summary.lower())

    def test_system_prompt_describes_requisition_at_default_time(self):
        """Garante regra de hora padrão para requisition_at no system prompt."""
        system = load_prompt_markdown(
            workflow_slug=GENERIC_WORKFLOW.slug,
            task="metadata_extraction",
            name="system",
        )

        self.assertIn("requisition_at", system)
        self.assertIn("T00:00", system)
        self.assertIn("assinatura da autoridade requisitante", system.lower())
        self.assertIn("não consta no bo", system.lower())

    def test_system_prompt_lists_document_types_with_priorities(self):
        """Garante tipologia documental com prioridades no system prompt."""
        system = load_prompt_markdown(
            workflow_slug=GENERIC_WORKFLOW.slug,
            task="metadata_extraction",
            name="system",
        )

        self.assertIn("Tipos de documento", system)
        self.assertIn("Memorando / Ofício", system)
        self.assertIn("Laudo Pericial", system)
