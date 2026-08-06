"""Registrador administrativo do perito criminal (SP)."""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from institution_ic_sp.models import ForensicTeam
from profiles.forms.forensic_examiner_sp_admin_form import ForensicExaminerSPAdminForm
from profiles.models import ForensicExaminerSP


@admin.register(ForensicExaminerSP)
class ForensicExaminerSPAdmin(admin.ModelAdmin):
    """Administra perfis de peritos criminais de SP."""

    form = ForensicExaminerSPAdminForm
    change_form_template = "admin/profiles/forensicexaminersp/change_form.html"

    list_display = (
        "display_name",
        "user",
        "job_title",
        "can_send_images_to_external_ai",
        "assignment_display",
        "created_at",
    )
    list_filter = (
        "job_title",
        "can_send_images_to_external_ai",
        "forensic_nucleus",
        "forensic_team__nucleus",
        "forensic_team",
    )
    search_fields = (
        "display_name",
        "user__username",
        "forensic_team__name",
        "forensic_team__code",
        "forensic_nucleus__name",
        "forensic_nucleus__code",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    autocomplete_fields = ("user",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "user",
                    "display_name",
                    "job_title",
                    "calling_gender",
                    "director_display",
                ),
            },
        ),
        (
            "Lotação",
            {
                "description": (
                    "Selecione o núcleo pericial. A equipe é opcional — "
                    "deixe em branco para lotação direta no núcleo."
                ),
                "fields": ("lotacao_nucleus", "forensic_team"),
            },
        ),
        (
            "Integração com IA",
            {
                "fields": ("can_send_images_to_external_ai",),
            },
        ),
        (
            "Metadados",
            {
                "fields": ("id", "created_at", "updated_at"),
            },
        ),
    )

    def get_urls(self):
        """Expõe endpoint auxiliar para filtrar equipes por núcleo no admin."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "teams-by-nucleus/",
                self.admin_site.admin_view(self.teams_by_nucleus_view),
                name="profiles_forensicexaminersp_teams_by_nucleus",
            ),
        ]
        return custom_urls + urls

    def teams_by_nucleus_view(self, request):
        """Retorna equipes periciais filhas do núcleo informado."""
        nucleus_id = request.GET.get("nucleus_id")
        if not nucleus_id:
            return JsonResponse({"teams": []})

        teams = (
            ForensicTeam.objects.filter(nucleus_id=nucleus_id)
            .order_by("sort_order", "name")
            .only("id", "name", "code")
        )
        return JsonResponse(
            {
                "teams": [
                    {"id": str(team.pk), "label": str(team)}
                    for team in teams
                ],
            }
        )

    @admin.display(description="Lotação")
    def assignment_display(self, obj):
        """Resume a lotação administrativa do servidor."""
        if obj.forensic_team_id:
            return obj.forensic_team.name
        if obj.forensic_nucleus_id:
            return f"{obj.forensic_nucleus.name} (núcleo)"
        return "—"
