"""
Testes dos models institucionais do IC-SP.

Valida regras de identificação, relacionamentos e carga inicial de dados.
"""

from django.test import TestCase

from institution_ic_sp.data.ic_sp_seed import load_ic_sp_institution_data
from institution_ic_sp.models import ForensicNucleus, ForensicTeam, Institution


class InstitutionIcSpSeedTests(TestCase):
    """Testes da carga inicial de núcleos e equipes do IC-SP."""

    def test_load_ic_sp_data_creates_institution_and_teams(self):
        """Garante que a carga inicial cria instituição, 29 núcleos e 59 equipes."""
        load_ic_sp_institution_data()

        self.assertEqual(Institution.objects.count(), 1)
        self.assertEqual(
            Institution.objects.get(acronym="IC-SP").is_provisional,
            True,
        )
        self.assertEqual(ForensicNucleus.objects.count(), 29)
        self.assertEqual(ForensicTeam.objects.count(), 59)

    def test_capital_nucleus_has_seventeen_teams(self):
        """Garante que o NPC-CAP concentra as 17 equipes da capital e Grande SP."""
        load_ic_sp_institution_data()

        capital_nucleus = ForensicNucleus.objects.get(code="NPC-CAP")
        self.assertEqual(capital_nucleus.teams.count(), 17)

    def test_interior_nuclei_have_forty_teams(self):
        """Garante que os 11 núcleos do interior somam 40 equipes periciais."""
        load_ic_sp_institution_data()

        interior_teams = ForensicTeam.objects.filter(
            nucleus__nucleus_type=ForensicNucleus.NucleusType.FIELD_INTERIOR
        )
        self.assertEqual(interior_teams.count(), 40)

    def test_team_code_is_unique(self):
        """Impede duplicidade de código de equipe na base local."""
        load_ic_sp_institution_data()

        duplicate = ForensicTeam(
            nucleus=ForensicNucleus.objects.first(),
            code="EPC-SPC",
            name="Duplicata",
            headquarters_city="São Paulo",
        )

        with self.assertRaises(Exception):
            duplicate.save()
