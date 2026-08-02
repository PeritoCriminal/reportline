"""Testes do atalho de linha horizontal (___ + Enter)."""

from django.test import SimpleTestCase

from reports.services.report_horizontal_rule_shortcut import is_horizontal_rule_shortcut_line


class ReportHorizontalRuleShortcutTests(SimpleTestCase):
    """Testes de reconhecimento da linha de atalho para linha horizontal."""

    def test_three_underscores_is_shortcut(self):
        """Garante que três underscores isolados na linha acionam o atalho."""
        self.assertTrue(is_horizontal_rule_shortcut_line("___"))

    def test_more_than_three_underscores_is_shortcut(self):
        """Garante que quatro ou mais underscores isolados também acionam."""
        self.assertTrue(is_horizontal_rule_shortcut_line("____"))

    def test_leading_space_disables_shortcut(self):
        """Garante que espaço antes dos underscores mantém o texto digitado."""
        self.assertFalse(is_horizontal_rule_shortcut_line(" ___"))

    def test_prefix_character_disables_shortcut(self):
        """Garante que caractere antes dos underscores impede a linha horizontal."""
        self.assertFalse(is_horizontal_rule_shortcut_line("x___"))

    def test_suffix_character_disables_shortcut(self):
        """Garante que caractere após os underscores impede a linha horizontal."""
        self.assertFalse(is_horizontal_rule_shortcut_line("___x"))

    def test_fewer_than_three_underscores_is_not_shortcut(self):
        """Garante que menos de três underscores não acionam o atalho."""
        self.assertFalse(is_horizontal_rule_shortcut_line("__"))
