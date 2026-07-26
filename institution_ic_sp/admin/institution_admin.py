"""Registradores administrativos da instituição IC-SP."""

from django.contrib import admin

from institution_ic_sp.models import Institution


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    """Administra cadastro da instituição pericial de referência."""

    list_display = ("acronym", "name", "headquarters_city", "is_provisional")
    list_filter = ("is_provisional",)
    search_fields = ("name", "acronym", "parent_organization")
    readonly_fields = ("id", "created_at", "updated_at")
