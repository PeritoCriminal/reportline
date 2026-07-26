"""Registradores do Django Admin do app institution_ic_sp."""

from institution_ic_sp.admin.forensic_nucleus_admin import ForensicNucleusAdmin
from institution_ic_sp.admin.forensic_team_admin import ForensicTeamAdmin
from institution_ic_sp.admin.institution_admin import InstitutionAdmin

__all__ = [
    "InstitutionAdmin",
    "ForensicNucleusAdmin",
    "ForensicTeamAdmin",
]
