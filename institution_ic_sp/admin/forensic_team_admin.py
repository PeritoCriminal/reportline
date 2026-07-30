"""Registradores administrativos das equipes periciais."""

from django.contrib import admin

from institution_ic_sp.models import ForensicTeam


@admin.register(ForensicTeam)
class ForensicTeamAdmin(admin.ModelAdmin):
    """Administra equipes de perícias criminalísticas do IC-SP."""

    list_display = (
        "code",
        "name",
        "nucleus",
        "headquarters_city",
        "is_embedded_unit",
    )
    list_filter = ("is_embedded_unit", "nucleus__nucleus_type")
    search_fields = (
        "code",
        "name",
        "headquarters_city",
        "phone",
        "institutional_email",
        "address",
        "nucleus__name",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("nucleus",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "nucleus",
                    "code",
                    "name",
                    "headquarters_city",
                    "is_embedded_unit",
                    "sort_order",
                ),
            },
        ),
        (
            "Contato",
            {
                "fields": ("phone", "institutional_email", "address"),
            },
        ),
        (
            "Auditoria",
            {
                "fields": ("id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
