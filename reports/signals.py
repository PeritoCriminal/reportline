"""
Sinais do app reports.

Garante integridade referencial entre nó e bloco e preserva snapshot do
autor quando a conta vinculada for excluída.
"""

from django.conf import settings
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver

from reports.models import Report, ReportBlock, ReportNode
from reports.services.author_snapshot import snapshot_author_fields
from reports.services.report_block_image_cleanup import delete_block_images
from reports.services.report_media_cleanup import delete_report_media_folder


@receiver(post_delete, sender=ReportNode)
def remove_block_after_node_delete(sender, instance, **kwargs):
    """Remove o bloco associado após exclusão do nó, inclusive em cascata."""
    block_id = instance.block_id
    if not block_id:
        return

    block = ReportBlock.objects.filter(pk=block_id).first()
    if block:
        delete_block_images(block.block_type, block.content or {})

    ReportBlock.objects.filter(pk=block_id).delete()


@receiver(post_delete, sender=Report)
def remove_report_media_folder(sender, instance, **kwargs):
    """Remove pasta de mídia do laudo após exclusão permanente do registro."""
    delete_report_media_folder(instance.pk)


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def preserve_report_author_on_user_delete(sender, instance, **kwargs):
    """
    Grava snapshot textual do autor antes da exclusão da conta.

    O FK ``author`` é anulado via ``SET_NULL`` pelo Django; os campos string
    mantêm rastreabilidade do documento.
    """
    snapshot = snapshot_author_fields(instance)
    Report.objects.filter(author=instance).update(**snapshot)
