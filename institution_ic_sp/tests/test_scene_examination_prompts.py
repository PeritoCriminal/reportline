"""
Testes dos prompts e biblioteca de estilo da inferência de exame de local.
"""

from django.test import TestCase

from institution_ic_sp.forensic_report.common.ai.prompt_loader import (
    load_prompt_markdown,
    load_writing_style_markdown,
    render_prompt_template,
)
from institution_ic_sp.forensic_report.registry import PROPERTY_CRIME_WORKFLOW


class SceneExaminationPromptTests(TestCase):
    """Testes dos contratos de prompt da inferência de exame de local patrimonial."""

    def test_system_prompt_references_attendance_context_style_placeholder(self):
        """Garante que o system prompt reserve espaço para a biblioteca de estilo."""
        system = load_prompt_markdown(
            workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
            task="scene_examination",
            name="system",
        )

        self.assertIn("{{attendance_context_style}}", system)
        self.assertIn("Contexto de atendimento", system)
        self.assertIn("Não", system)
        self.assertIn("dinâmica dos fatos", system)

    def test_attendance_context_style_library_contains_guidelines_and_examples(self):
        """Garante diretrizes de redação e exemplos fictícios na biblioteca de estilo."""
        style = load_writing_style_markdown(
            workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
            name="attendance_context",
        )

        self.assertIn("Biblioteca de Estilo", style)
        self.assertIn("fictícios", style.lower())
        self.assertIn("a equipe compareceu ao local", style.lower())
        self.assertIn("não copie trechos integralmente", style.lower())
        self.assertIn("Exemplo 01", style)
        self.assertIn("Exemplo 20", style)

    def test_system_prompt_includes_rendered_attendance_style_library(self):
        """Garante composição do system prompt com a biblioteca de contexto de atendimento."""
        system_template = load_prompt_markdown(
            workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
            task="scene_examination",
            name="system",
        )
        attendance_style = load_writing_style_markdown(
            workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
            name="attendance_context",
        )
        characteristics_style = load_writing_style_markdown(
            workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
            name="characteristics",
        )
        rendered = render_prompt_template(
            system_template,
            attendance_context_style=attendance_style,
            characteristics_style=characteristics_style,
        )

        self.assertNotIn("{{attendance_context_style}}", rendered)
        self.assertIn("Biblioteca de Estilo", rendered)
        self.assertIn("Exemplo 10", rendered)

    def test_user_prompt_includes_attendance_context_placeholder(self):
        """Garante placeholder para dados estruturados do contexto de atendimento."""
        user = load_prompt_markdown(
            workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
            task="scene_examination",
            name="user",
        )

        self.assertIn("{{attendance_context_text}}", user)
        self.assertIn("Dados estruturados do contexto de atendimento", user)

    def test_system_prompt_references_characteristics_style_placeholder(self):
        """Garante que o system prompt reserve espaço para a biblioteca de características."""
        system = load_prompt_markdown(
            workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
            task="scene_examination",
            name="system",
        )

        self.assertIn("{{characteristics_style}}", system)
        self.assertIn("Características do local", system)

    def test_characteristics_style_library_contains_examples(self):
        """Garante exemplos fictícios na biblioteca de estilo de características do local."""
        style = load_writing_style_markdown(
            workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
            name="characteristics",
        )

        self.assertIn("Biblioteca de Estilo", style)
        self.assertIn("fictícios", style.lower())
        self.assertIn("não devem ser reproduzidos literalmente", style.lower())
        self.assertIn("Exemplo 01", style)
        self.assertIn("Exemplo 15", style)
        self.assertIn("residência térrea", style.lower())

    def test_system_prompt_includes_both_style_libraries(self):
        """Garante composição do system prompt com ambas as bibliotecas de estilo."""
        system_template = load_prompt_markdown(
            workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
            task="scene_examination",
            name="system",
        )
        attendance_style = load_writing_style_markdown(
            workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
            name="attendance_context",
        )
        characteristics_style = load_writing_style_markdown(
            workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
            name="characteristics",
        )
        rendered = render_prompt_template(
            system_template,
            attendance_context_style=attendance_style,
            characteristics_style=characteristics_style,
        )

        self.assertNotIn("{{attendance_context_style}}", rendered)
        self.assertNotIn("{{characteristics_style}}", rendered)
        self.assertIn("Contexto de Atendimento", rendered)
        self.assertIn("Características do Local", rendered)
        self.assertIn("Exemplo 10", rendered)
