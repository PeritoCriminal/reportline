# reportline/institution_ic_sp/tests/test_scene_location_table.py
"""

Testes da montagem da tabela de localização com QR code.

"""



from django.contrib.auth import get_user_model

from django.test import TestCase



from institution_ic_sp.forensic_report.common.services.scene_location import (

    LOCATION_KIND_ADDRESS,

    LOCATION_KIND_COORDINATES,

    SceneLocationData,

)

from institution_ic_sp.forensic_report.services.forensic_report_shell import create_forensic_report_shell

from institution_ic_sp.forensic_report.services.scene_location_table import (

    LOCATION_QR_PIXEL_SIZE,

    MAPS_LINK_LABEL,

    _build_location_text_html,

    _column_widths_for_qr_image,

    build_scene_location_table_content,

)

from institution_ic_sp.forensic_report.common.services.location_maps_qr import google_maps_search_url

from institution_ic_sp.models import ForensicTeam

from profiles.models import ForensicExaminerSP, ForensicJobTitle, GenderCalling

from reports.models import ReportBlockType, ReportImage

from reports.services.report_block_content import normalize_block_content



User = get_user_model()





class SceneLocationTableTests(TestCase):

    """Testes da tabela de localização no laudo pericial."""



    @classmethod

    def setUpTestData(cls):

        cls.team = ForensicTeam.objects.get(code="EPC-SPC")

        cls.user = User.objects.create_user(username="perito_maps", password="senha-segura")

        cls.examiner = ForensicExaminerSP.objects.create(

            user=cls.user,

            forensic_team=cls.team,

            display_name="Dr. Maps",

            job_title=ForensicJobTitle.PERITO_CRIMINAL,

            calling_gender=GenderCalling.MALE,

        )



    def test_build_location_table_creates_qr_in_left_column(self):

        """Garante tabela padrão com QR persistido na coluna esquerda."""

        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)

        location = SceneLocationData(

            kind=LOCATION_KIND_ADDRESS,

            address="Rua das Flores, 100, São Paulo",

        )



        content = build_scene_location_table_content(report, location)



        self.assertIsNotNone(content)

        assert content is not None

        self.assertFalse(content["show_borders"])

        self.assertFalse(content["show_header"])

        self.assertEqual(content["display_width"], 100)

        self.assertEqual(len(content["rows"]), 1)

        self.assertEqual(len(content["rows"][0]), 2)

        qr_cell = content["rows"][0][0]

        text_cell = content["rows"][0][1]

        self.assertEqual(qr_cell["type"], "image")

        self.assertEqual(qr_cell["width"], LOCATION_QR_PIXEL_SIZE)

        self.assertEqual(text_cell["type"], "text")

        self.assertIn("Endereço:", text_cell["text"])

        self.assertIn(MAPS_LINK_LABEL, text_cell["text"])

        self.assertTrue(ReportImage.objects.filter(report=report).exists())

        self.assertEqual(sum(content["column_widths"]), 100)

        self.assertLess(content["column_widths"][0], content["column_widths"][1])



    def test_qr_pixel_size_is_twenty_percent_smaller_than_base(self):

        """Garante QR gerado com 20% a menos que a largura base de referência."""

        self.assertEqual(LOCATION_QR_PIXEL_SIZE, 102)



    def test_column_widths_include_margin_for_qr_column(self):

        """Garante coluna esquerda proporcional ao QR com folga antes do texto."""

        widths = _column_widths_for_qr_image(LOCATION_QR_PIXEL_SIZE)

        self.assertEqual(sum(widths), 100)

        self.assertLess(widths[0], 35)

        self.assertGreater(widths[1], 65)



    def test_location_text_uses_coordinates_label(self):

        """Garante rótulo Coordenadas quando o local foi informado por lat/long."""

        location = SceneLocationData(

            kind=LOCATION_KIND_COORDINATES,

            latitude="-23.5505",

            longitude="-46.6333",

        )

        maps_url = google_maps_search_url(location.maps_query)

        text_html = _build_location_text_html(location, maps_url)



        self.assertIn("Coordenadas:", text_html)

        self.assertIn("-23.5505", text_html)

        self.assertIn(MAPS_LINK_LABEL, text_html)



    def test_location_text_survives_table_cell_normalization(self):

        """Garante rótulo, valor e link em linhas distintas após sanitização."""

        location = SceneLocationData(

            kind=LOCATION_KIND_ADDRESS,

            address="Rua das Flores, 100, São Paulo",

        )

        maps_url = google_maps_search_url(location.maps_query)

        text_html = _build_location_text_html(location, maps_url)



        normalized = normalize_block_content(

            ReportBlockType.TABLE,

            {

                "headers": [],

                "rows": [

                    [

                        {"type": "text", "text": "", "align": "center"},

                        {"type": "text", "text": text_html, "align": "left"},

                    ]

                ],

                "show_borders": True,

                "show_header": False,

                "column_widths": [28, 72],

            },

        )

        sanitized_text = normalized["rows"][0][1]["text"]

        self.assertIn("<strong>Endereço:</strong>", sanitized_text)

        self.assertIn("Rua das Flores", sanitized_text)

        self.assertIn(MAPS_LINK_LABEL, sanitized_text)

        self.assertIn('target="_blank"', sanitized_text)

        self.assertIn('rel="noopener noreferrer"', sanitized_text)

        br_positions = [index for index in range(len(sanitized_text)) if sanitized_text.startswith("<br>", index)]

        self.assertGreaterEqual(len(br_positions), 2)



    def test_build_location_table_skips_empty_location(self):

        """Garante ausência de tabela quando localização não foi informada."""

        report = create_forensic_report_shell(author=self.user, examiner=self.examiner)

        content = build_scene_location_table_content(report, SceneLocationData())

        self.assertIsNone(content)


