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


@receiver(post_delete, sender=ReportNode)
def remove_block_after_node_delete(sender, instance, **kwargs):
    """Remove o bloco associado após exclusão do nó, inclusive em cascata."""
    if instance.block_id:
        ReportBlock.objects.filter(pk=instance.block_id).delete()


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def preserve_report_author_on_user_delete(sender, instance, **kwargs):
    """
    Grava snapshot textual do autor antes da exclusão da conta.

    O FK ``author`` é anulado via ``SET_NULL`` pelo Django; os campos string
    mantêm rastreabilidade do documento.
    """
    snapshot = snapshot_author_fields(instance)
    Report.objects.filter(author=instance).update(**snapshot)
