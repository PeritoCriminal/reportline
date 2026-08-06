"""Registrador administrativo de relatórios modulares."""

from django.contrib import admin

from reports.models import Report
from reports.services.report_deletion import delete_report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Administra relatórios e metadados de publicação."""

    list_display = (
        "title",
        "author_label_display",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "title",
        "author__username",
        "author_username",
        "author_display_name",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("author",)
    fieldsets = (
        (
            None,
            {
                "fields": ("author", "title", "status"),
            },
        ),
        (
            "Autor (snapshot)",
            {
                "description": (
                    "Preenchidos automaticamente enquanto houver autor vinculado; "
                    "preservados após exclusão da conta."
                ),
                "fields": ("author_username", "author_display_name"),
            },
        ),
        (
            "Metadados",
            {
                "fields": ("id", "created_at", "updated_at"),
            },
        ),
    )

    def delete_model(self, request, obj):
        """Remove laudo pelo serviço centralizado, incluindo pasta em MEDIA."""
        delete_report(obj)

    def delete_queryset(self, request, queryset):
        """Remove laudos em lote com limpeza de mídia por registro."""
        for report in queryset:
            delete_report(report)

    @admin.display(description="Autor")
    def author_label_display(self, obj):
        """Exibe autor ativo ou identificação preservada em snapshot."""
        return obj.author_label
