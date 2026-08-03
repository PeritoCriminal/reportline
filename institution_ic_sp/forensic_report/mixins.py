"""
Mixin de autorização para views restritas a ForensicExaminerSP.
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404

from profiles.models import ForensicExaminerSP


class ForensicExaminerSPRequiredMixin(LoginRequiredMixin):
    """
    Restringe acesso a usuários com perfil ForensicExaminerSP vinculado.

    Disponibiliza ``examiner_profile`` na view após autenticação bem-sucedida.
    """

    examiner_profile: ForensicExaminerSP | None = None

    def dispatch(self, request, *args, **kwargs):
        """Carrega perfil pericial ou responde 404 antes de executar a view."""
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        self.examiner_profile = get_object_or_404(
            ForensicExaminerSP.objects.select_related(
                "forensic_team",
                "forensic_team__nucleus",
                "forensic_nucleus",
            ),
            user=request.user,
        )
        return super().dispatch(request, *args, **kwargs)
