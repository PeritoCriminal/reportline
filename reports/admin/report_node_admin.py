"""Registrador administrativo de nós na árvore de relatório."""

from django.contrib import admin

from reports.models import ReportNode


@admin.register(ReportNode)
class ReportNodeAdmin(admin.ModelAdmin):
    """Administra nós hierárquicos e posição na árvore do relatório."""

    list_display = ("report", "parent", "position", "block", "created_at")
    list_filter = ("report",)
    search_fields = ("report__title",)
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("report", "parent", "block")
    fieldsets = (
        (
            None,
            {
                "fields": ("report", "parent", "block", "position"),
            },
        ),
        (
            "Metadados",
            {
                "fields": ("id", "created_at", "updated_at"),
            },
        ),
    )
