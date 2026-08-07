# reportline/reports/admin/__init__.py
"""Registradores do Django Admin do app reports."""

from reports.admin.report_admin import ReportAdmin
from reports.admin.report_block_admin import ReportBlockAdmin
from reports.admin.report_node_admin import ReportNodeAdmin

__all__ = [
    "ReportAdmin",
    "ReportBlockAdmin",
    "ReportNodeAdmin",
]
