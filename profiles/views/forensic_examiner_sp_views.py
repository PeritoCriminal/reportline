"""
Views de perfil profissional do servidor pericial (SP).

Concentra CBVs para edição pelo próprio usuário após vínculo
administrativo com equipe pericial.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from common.user_messages import notify_success
from profiles.forms.forensic_examiner_sp_form import ForensicExaminerSPProfileForm
from profiles.models import ForensicExaminerSP


class ForensicExaminerSPProfileView(LoginRequiredMixin, UpdateView):
    """
    Formulário de perfil profissional do servidor pericial (SP).

    Disponível apenas para usuários com vínculo ForensicExaminerSP
    criado pelo administrador. Permite informar nome de exibição e cargo;
    a lotação em equipe permanece sob gestão administrativa.
    """

    model = ForensicExaminerSP
    form_class = ForensicExaminerSPProfileForm
    template_name = "profiles/forensic_examiner_sp_form.html"
    success_url = reverse_lazy("profiles:forensic_examiner_sp")

    def get_object(self, queryset=None):
        """Retorna o perfil vinculado ao usuário autenticado ou responde 404."""
        return get_object_or_404(
            ForensicExaminerSP.objects.select_related(
                "forensic_team",
                "forensic_team__nucleus",
                "forensic_nucleus",
            ),
            user=self.request.user,
        )

    def form_valid(self, form):
        """Persiste o perfil e exibe confirmação ao usuário."""
        response = super().form_valid(form)
        notify_success(self.request, "Perfil profissional salvo com sucesso.")
        return response
