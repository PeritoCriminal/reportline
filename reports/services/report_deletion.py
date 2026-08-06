"""
Serviço de exclusão permanente de relatório e recursos associados.
"""

from django.db import transaction

from reports.models import Report
from reports.services.report_image_upload import delete_report_image
from reports.services.report_media_cleanup import delete_report_media_folder


@transaction.atomic
def delete_report(report: Report) -> None:
    """
    Remove relatório, nós, blocos e arquivos de imagem permanentemente.

    Todas as imagens vinculadas ao laudo são apagadas do storage antes
    da remoção do registro principal, da árvore de conteúdo e da pasta
    ``media/reports/<uuid>/``.
    """
    report_id = report.pk
    for image_id in list(report.images.values_list("pk", flat=True)):
        delete_report_image(image_id)

    delete_report_media_folder(report_id)
    report.delete()
    delete_report_media_folder(report_id)
