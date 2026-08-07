# reportline/institution_ic_sp/tests/test_traces_writing_style.py
"""
Testes da biblioteca de estilo da seção Vestígios (crime patrimonial).
"""

from django.test import TestCase

from institution_ic_sp.forensic_report.common.ai.prompt_loader import load_writing_style_markdown
from institution_ic_sp.forensic_report.registry import PROPERTY_CRIME_WORKFLOW


class TracesWritingStyleTests(TestCase):
    """Testes do contrato da biblioteca de estilo de vestígios."""

    def test_traces_style_library_loads_with_guidelines_and_examples(self):
        """Garante diretrizes de redação pericial e dez exemplos fictícios."""
        style = load_writing_style_markdown(
            workflow_slug=PROPERTY_CRIME_WORKFLOW.slug,
            name="traces",
        )

        self.assertIn("Biblioteca de Estilo", style)
        self.assertIn("Vestígios", style)
        self.assertIn("ambiente → elemento → posição → vestígio", style)
        self.assertIn("Características do Local", style)
        self.assertIn("compatível com", style.lower())
        self.assertIn("fictícios", style.lower())
        self.assertIn("Exemplo 01", style)
        self.assertIn("Exemplo 10", style)
        self.assertIn("impressão digital latente", style.lower())
