"""Registradores administrativos dos núcleos periciais."""

from django.contrib import admin

from institution_ic_sp.models import ForensicNucleus, ForensicTeam


class ForensicTeamInline(admin.TabularInline):
    """Lista equipes vinculadas ao núcleo na tela de edição."""

    model = ForensicTeam
    extra = 0
    fields = ("code", "name", "headquarters_city", "is_embedded_unit", "sort_order")
    ordering = ("sort_order", "name")


@admin.register(ForensicNucleus)
class ForensicNucleusAdmin(admin.ModelAdmin):
    """Administra núcleos periciais do IC-SP."""

    list_display = (
        "code",
        "name",
        "nucleus_type",
        "organizational_center",
        "headquarters_city",
    )
    list_filter = ("nucleus_type", "organizational_center", "institution")
    search_fields = ("code", "name", "headquarters_city")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [ForensicTeamInline]
