"""
Testes dos models institucionais do IC-SP.

Valida regras de identificação, relacionamentos e carga inicial de dados.
"""

from io import BytesIO
import shutil
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from institution_ic_sp.data.ic_sp_seed import load_ic_sp_institution_data
from institution_ic_sp.models import ForensicNucleus, ForensicTeam, Institution


def _make_test_png(name="logo.png"):
    """Gera um PNG mínimo em memória para testes de upload."""
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color="white").save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


@override_settings(MEDIA_ROOT="test_media")
class InstitutionLogoFieldTests(TestCase):
    """Testes dos campos de logo da instituição para cabeçalho de laudo."""

    def setUp(self):
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.exists():
            shutil.rmtree(media_root)

    def _create_institution(self, **kwargs):
        defaults = {
            "name": "Instituto de Criminalística",
            "acronym": "IC-TEST",
            "parent_organization": "SPTC",
            "headquarters_city": "São Paulo",
        }
        defaults.update(kwargs)
        return Institution.objects.create(**defaults)

    def test_logos_are_optional_on_create(self):
        """Garante que a instituição possa existir sem logos cadastrados."""
        institution = self._create_institution(acronym="IC-TEST")

        self.assertFalse(institution.sp_logo)
        self.assertFalse(institution.sptc_logo)

    def test_logo_upload_uses_institution_logos_path(self):
        """Garante que uploads de logo sejam gravados em institution_ic_sp/logos/."""
        institution = self._create_institution(
            acronym="IC-LOGO",
            sp_logo=_make_test_png("sp_logo.png"),
            sptc_logo=_make_test_png("sptc_logo.png"),
        )

        self.assertTrue(institution.sp_logo.name.startswith("institution_ic_sp/logos/"))
        self.assertTrue(institution.sptc_logo.name.startswith("institution_ic_sp/logos/"))

    def test_replacing_sp_logo_deletes_previous_file(self):
        """Remove do storage o logo anterior quando sp_logo é substituído."""
        institution = self._create_institution(
            acronym="IC-REPLACE",
            sp_logo=_make_test_png("sp_v1.png"),
        )
        previous_logo_name = institution.sp_logo.name

        institution.sp_logo = _make_test_png("sp_v2.png")
        institution.save()
        institution.refresh_from_db()

        self.assertFalse(default_storage.exists(previous_logo_name))
        self.assertTrue(default_storage.exists(institution.sp_logo.name))
        self.assertNotEqual(previous_logo_name, institution.sp_logo.name)

    def test_replacing_sptc_logo_deletes_previous_file(self):
        """Remove do storage o logo anterior quando sptc_logo é substituído."""
        institution = self._create_institution(
            acronym="IC-SPTC",
            sptc_logo=_make_test_png("sptc_v1.png"),
        )
        previous_logo_name = institution.sptc_logo.name

        institution.sptc_logo = _make_test_png("sptc_v2.png")
        institution.save()
        institution.refresh_from_db()

        self.assertFalse(default_storage.exists(previous_logo_name))
        self.assertTrue(default_storage.exists(institution.sptc_logo.name))

    def test_clearing_logo_deletes_previous_file(self):
        """Remove do storage o arquivo quando o campo de logo é limpo."""
        institution = self._create_institution(
            acronym="IC-CLEAR",
            sp_logo=_make_test_png("sp_clear.png"),
        )
        previous_logo_name = institution.sp_logo.name

        institution.sp_logo = ""
        institution.save()
        institution.refresh_from_db()

        self.assertFalse(institution.sp_logo)
        self.assertFalse(default_storage.exists(previous_logo_name))

    def test_saving_without_logo_change_keeps_existing_file(self):
        """Mantém o arquivo quando o save não altera os campos de logo."""
        institution = self._create_institution(
            acronym="IC-KEEP",
            sp_logo=_make_test_png("sp_keep.png"),
        )
        logo_name = institution.sp_logo.name

        institution.name = "Instituto Atualizado"
        institution.save()
        institution.refresh_from_db()

        self.assertEqual(institution.sp_logo.name, logo_name)
        self.assertTrue(default_storage.exists(logo_name))

    def test_deleting_institution_removes_logo_files(self):
        """Remove logos do storage quando a instituição é excluída."""
        institution = self._create_institution(
            acronym="IC-DELETE",
            sp_logo=_make_test_png("sp_delete.png"),
            sptc_logo=_make_test_png("sptc_delete.png"),
        )
        sp_logo_name = institution.sp_logo.name
        sptc_logo_name = institution.sptc_logo.name

        institution.delete()

        self.assertFalse(default_storage.exists(sp_logo_name))
        self.assertFalse(default_storage.exists(sptc_logo_name))


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


@override_settings(MEDIA_ROOT="test_media")
class ForensicTeamContactFieldTests(TestCase):
    """Testes dos campos de contato opcionais da equipe pericial."""

    @classmethod
    def setUpTestData(cls):
        load_ic_sp_institution_data()

    def test_contact_fields_are_optional(self):
        """Garante que telefone, e-mail e endereço possam ficar em branco."""
        team = ForensicTeam.objects.create(
            nucleus=ForensicNucleus.objects.first(),
            code="EPC-TEST",
            name="Equipe de Teste",
            headquarters_city="São Paulo",
        )

        self.assertEqual(team.phone, "")
        self.assertEqual(team.institutional_email, "")
        self.assertEqual(team.address, "")

    def test_contact_fields_persist_when_informed(self):
        """Garante persistência de telefone, e-mail institucional e endereço."""
        team = ForensicTeam.objects.create(
            nucleus=ForensicNucleus.objects.first(),
            code="EPC-CONT",
            name="Equipe com Contato",
            headquarters_city="Campinas",
            phone="(19) 3733-1000",
            institutional_email="epc-cps@policiacientifica.sp.gov.br",
            address="Rua Exemplo, 100 — Campinas/SP",
        )

        team.refresh_from_db()
        self.assertEqual(team.phone, "(19) 3733-1000")
        self.assertEqual(team.institutional_email, "epc-cps@policiacientifica.sp.gov.br")
        self.assertEqual(team.address, "Rua Exemplo, 100 — Campinas/SP")
