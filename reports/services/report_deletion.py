"""
Serviço de exclusão permanente de relatório e recursos associados.
"""

from django.db import transaction

from reports.models import Report
from reports.services.report_image_upload import delete_report_image


@transaction.atomic
def delete_report(report: Report) -> None:
    """
    Remove relatório, nós, blocos e arquivos de imagem permanentemente.

    Todas as imagens vinculadas ao laudo são apagadas do storage antes
    da remoção do registro principal e da árvore de conteúdo.
    """
    for image_id in list(report.images.values_list("pk", flat=True)):
        delete_report_image(image_id)

    report.delete()
