# reportline/reports/admin/report_block_admin.py
"""Registrador administrativo de blocos genéricos de relatório."""

from django.contrib import admin

from reports.models import ReportBlock


@admin.register(ReportBlock)
class ReportBlockAdmin(admin.ModelAdmin):
    """Administra blocos tipados de conteúdo de relatório."""

    list_display = (
        "block_type",
        "title_level",
        "line_spacing",
        "created_at",
        "updated_at",
    )
    list_filter = ("block_type", "line_spacing")
    search_fields = ("block_type",)
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": ("block_type", "content", "title_level"),
            },
        ),
        (
            "Layout e paginação",
            {
                "fields": (
                    "page_break_before",
                    "keep_with_previous",
                    "keep_with_next",
                    "indent_level",
                    "first_line_indent",
                    "line_spacing",
                    "space_before",
                    "space_after",
                ),
            },
        ),
        (
            "Metadados",
            {
                "fields": ("id", "created_at", "updated_at"),
            },
        ),
    )
