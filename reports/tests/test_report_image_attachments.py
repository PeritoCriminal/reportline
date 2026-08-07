# reportline/reports/tests/test_report_image_attachments.py
"""
Testes da normalização de anexos de imagem com legenda e exibição no laudo.
"""

from django.test import TestCase

from reports.services.report_image_attachments import (
    ReportImageAttachment,
    normalize_report_image_attachments,
    report_image_attachment_ids,
    report_image_attachments_to_payload,
)


class ReportImageAttachmentsTests(TestCase):
    """Testes do padrão de anexos de imagem do laudo."""

    def test_normalize_from_images_payload(self):
        """Garante leitura de image_id, show_in_report e proposed_caption."""
        attachments = normalize_report_image_attachments(
            [
                {
                    "image_id": "abc-1",
                    "show_in_report": False,
                    "proposed_caption": " Fachada ",
                },
                {
                    "image_id": "abc-2",
                    "show_in_report": True,
                    "proposed_caption": "Sala de estar",
                },
            ]
        )

        self.assertEqual(len(attachments), 2)
        self.assertFalse(attachments[0].show_in_report)
        self.assertEqual(attachments[0].proposed_caption, "Fachada")
        self.assertTrue(attachments[1].show_in_report)

    def test_legacy_image_ids_default_to_show_in_report(self):
        """Garante compatibilidade com payload legado baseado em image_ids."""
        attachments = normalize_report_image_attachments(
            None,
            legacy_image_ids=["img-1", "img-2"],
        )

        self.assertEqual(report_image_attachment_ids(attachments), ["img-1", "img-2"])
        self.assertTrue(all(item.show_in_report for item in attachments))
        self.assertTrue(all(item.proposed_caption == "" for item in attachments))

    def test_images_payload_takes_precedence_over_legacy_ids(self):
        """Garante que lista images prevalece quando informada."""
        attachments = normalize_report_image_attachments(
            [{"image_id": "new-id", "show_in_report": True, "proposed_caption": "Portão"}],
            legacy_image_ids=["old-id"],
        )

        self.assertEqual(report_image_attachment_ids(attachments), ["new-id"])

    def test_attachments_to_payload_roundtrip(self):
        """Garante serialização estável para persistência no bootstrap."""
        source = [
            ReportImageAttachment(
                image_id="uuid-1",
                show_in_report=True,
                proposed_caption="Entrada lateral",
            )
        ]
        payload = report_image_attachments_to_payload(source)
        restored = normalize_report_image_attachments(payload)

        self.assertEqual(restored[0].image_id, "uuid-1")
        self.assertEqual(restored[0].proposed_caption, "Entrada lateral")

    def test_normalize_strips_figure_prefix_from_proposed_caption(self):
        """Garante remoção de prefixo Figura N em legenda proposta no upload."""
        attachments = normalize_report_image_attachments(
            [{"image_id": "abc", "show_in_report": True, "proposed_caption": "Figura 2 - Portão."}]
        )

        self.assertEqual(attachments[0].proposed_caption, "Portão.")
