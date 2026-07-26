"""Registrador administrativo do perito criminal (SP)."""

from django.contrib import admin

from profiles.models import ForensicExaminerSP


@admin.register(ForensicExaminerSP)
class ForensicExaminerSPAdmin(admin.ModelAdmin):
    """Administra perfis de peritos criminais de SP."""

    list_display = ("display_name", "user", "forensic_team", "created_at")
    list_filter = ("forensic_team__nucleus", "forensic_team")
    search_fields = (
        "display_name",
        "user__username",
        "forensic_team__name",
        "forensic_team__code",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("user", "forensic_team")
