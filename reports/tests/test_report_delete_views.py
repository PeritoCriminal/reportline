"""
Testes da view de exclusão de relatório.
"""

from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from reports.models import Report, ReportBlock, ReportBlockType, ReportImage, ReportNode
from reports.services.report_image_upload import build_image_block_content, store_report_image
from reports.services.report_media_cleanup import report_media_folder_relative_path

User = get_user_model()


class ReportDeleteViewTests(TestCase):
    """Testes da exclusão permanente de laudos pelo autor autenticado."""

    @classmethod
    def setUpTestData(cls):
        """Prepara usuários e relatório para os cenários."""
        cls.author = User.objects.create_user(
            username="delete_autor",
            password="senha-segura",
        )
        cls.other_user = User.objects.create_user(
            username="delete_outro",
            password="senha-segura",
        )
        cls.report = Report.objects.create(
            author=cls.author,
            title="Laudo para exclusão",
        )

    def test_anonymous_user_is_redirected_to_login_on_get(self):
        """Garante redirecionamento ao login na tela de confirmação."""
        url = reverse("reports:delete", kwargs={"pk": self.report.pk})
        response = self.client.get(url)
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
        )

    def test_anonymous_user_is_redirected_to_login_on_post(self):
        """Garante redirecionamento ao login ao tentar excluir sem autenticação."""
        url = reverse("reports:delete", kwargs={"pk": self.report.pk})
        response = self.client.post(url)
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={url}",
        )

    def test_author_sees_delete_confirmation_page(self):
        """Garante avisos de exclusão irreversível na página de confirmação."""
        self.client.login(username="delete_autor", password="senha-segura")
        response = self.client.get(
            reverse("reports:delete", kwargs={"pk": self.report.pk}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Excluir relatório")
        self.assertContains(response, "Será impossível recuperar o relatório após essa ação.")
        self.assertContains(response, "Todo o conteúdo do relatório será excluído permanentemente.")
        self.assertContains(response, "Todas as imagens armazenadas no servidor serão apagadas definitivamente.")
        self.assertContains(response, "Laudo para exclusão")

    def test_non_author_receives_404_on_get(self):
        """Garante bloqueio da tela de exclusão para usuário que não é autor."""
        self.client.login(username="delete_outro", password="senha-segura")
        response = self.client.get(
            reverse("reports:delete", kwargs={"pk": self.report.pk}),
        )
        self.assertEqual(response.status_code, 404)

    def test_non_author_receives_404_on_post(self):
        """Garante bloqueio da exclusão para usuário que não é autor."""
        self.client.login(username="delete_outro", password="senha-segura")
        response = self.client.post(
            reverse("reports:delete", kwargs={"pk": self.report.pk}),
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Report.objects.filter(pk=self.report.pk).exists())

    def test_author_can_delete_report_and_returns_to_list(self):
        """Garante exclusão do laudo, mensagem de sucesso e retorno à listagem."""
        self.client.login(username="delete_autor", password="senha-segura")
        report_id = self.report.pk
        response = self.client.post(
            reverse("reports:delete", kwargs={"pk": report_id}),
            follow=True,
        )

        self.assertRedirects(response, reverse("reports:list"))
        self.assertFalse(Report.objects.filter(pk=report_id).exists())
        stored = list(get_messages(response.wsgi_request))
        self.assertEqual(len(stored), 1)
        self.assertEqual(str(stored[0]), "Relatório excluído com sucesso.")

    def test_delete_report_removes_nodes_and_blocks(self):
        """Garante remoção permanente de nós e blocos ao excluir o laudo."""
        block = ReportBlock.objects.create(
            block_type=ReportBlockType.PARAGRAPH,
            content={"text": "Conteúdo de teste"},
        )
        node = ReportNode.objects.create(
            report=self.report,
            block=block,
            position=Decimal("1"),
        )
        node_id = node.pk
        block_id = block.pk
        report_id = self.report.pk

        self.client.login(username="delete_autor", password="senha-segura")
        self.client.post(reverse("reports:delete", kwargs={"pk": report_id}))

        self.assertFalse(Report.objects.filter(pk=report_id).exists())
        self.assertFalse(ReportNode.objects.filter(pk=node_id).exists())
        self.assertFalse(ReportBlock.objects.filter(pk=block_id).exists())

    def test_delete_report_removes_images_from_storage(self):
        """Garante remoção dos arquivos de imagem do media ao excluir o laudo."""
        buffer = BytesIO()
        Image.new("RGB", (400, 300), color="green").save(buffer, format="JPEG")
        buffer.seek(0)
        upload = SimpleUploadedFile("sample.jpg", buffer.read(), content_type="image/jpeg")

        report_image = store_report_image(self.report, upload)
        image_path = report_image.image.name
        image_id = report_image.pk
        folder_path = report_media_folder_relative_path(self.report.pk)

        block = ReportBlock.objects.create(
            block_type=ReportBlockType.IMAGE,
            content=build_image_block_content(report_image),
        )
        ReportNode.objects.create(
            report=self.report,
            block=block,
            position=Decimal("1"),
        )

        self.assertTrue(default_storage.exists(image_path))
        self.assertTrue(default_storage.exists(folder_path))

        self.client.login(username="delete_autor", password="senha-segura")
        self.client.post(
            reverse("reports:delete", kwargs={"pk": self.report.pk}),
        )

        self.assertFalse(ReportImage.objects.filter(pk=image_id).exists())
        self.assertFalse(default_storage.exists(image_path))
        self.assertFalse(default_storage.exists(folder_path))
