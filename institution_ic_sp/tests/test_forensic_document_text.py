# reportline/institution_ic_sp/tests/test_forensic_document_text.py
"""
Testes da extração de texto de documentos do intake pericial.
"""

from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from institution_ic_sp.forensic_report.common.ai.document_text import extract_text_from_uploads


class DocumentTextExtractionTests(TestCase):
    """Testes da leitura em memória de PDFs e demais formatos."""

    @patch(
        "institution_ic_sp.forensic_report.common.ai.document_text._extract_pdf_text",
        return_value="BO-123456 Delegacia Central",
    )
    def test_extract_text_from_pdf_upload(self, _mock_extract):
        """Garante inclusão do texto extraído de PDF no consolidado enviado à IA."""
        upload = SimpleUploadedFile(
            "requisicao.pdf",
            b"%PDF-1.4 stub",
            content_type="application/pdf",
        )
        excerpts = extract_text_from_uploads([upload])
        self.assertIn("BO-123456 Delegacia Central", excerpts)
        self.assertIn("requisicao.pdf", excerpts)

    def test_image_upload_returns_placeholder_without_ocr(self):
        """Garante marcador descritivo para imagens sem OCR local."""
        upload = SimpleUploadedFile(
            "foto.jpg",
            b"fake-image-bytes",
            content_type="image/jpeg",
        )
        excerpts = extract_text_from_uploads([upload])
        self.assertIn("Imagem anexada sem OCR local", excerpts)
