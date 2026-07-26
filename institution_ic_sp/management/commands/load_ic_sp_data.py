"""
Comando de gestão para carregar dados institucionais do IC-SP.

Permite repovoar núcleos e equipes a partir do módulo de seed local,
útil em desenvolvimento ou após substituição parcial dos dados.
"""

from django.core.management.base import BaseCommand

from institution_ic_sp.data.ic_sp_seed import load_ic_sp_institution_data


class Command(BaseCommand):
    """Carrega ou recarrega núcleos e equipes periciais do IC-SP."""

    help = "Popula núcleos e equipes de perícias criminalísticas do IC-SP."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove registros existentes antes de repovoar.",
        )

    def handle(self, *args, **options):
        """Executa a carga de dados institucionais."""
        result = load_ic_sp_institution_data(clear_existing=options["clear"])
        self.stdout.write(
            self.style.SUCCESS(
                "Dados do IC-SP carregados: "
                f"{result['nuclei_created']} núcleo(s) novo(s), "
                f"{result['teams_created']} equipe(s) nova(s)."
            )
        )
