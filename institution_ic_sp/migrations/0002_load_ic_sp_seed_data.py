# reportline/institution_ic_sp/migrations/0002_load_ic_sp_seed_data.py
"""
Data migration: popula núcleos e equipes periciais do IC-SP.

Carga inicial baseada no Decreto 42.847/1998 e organograma SPTC.
"""

from django.db import migrations


def load_ic_sp_data(apps, schema_editor):
    """Executa seed institucional após criação das tabelas."""
    from institution_ic_sp.data.ic_sp_seed import load_ic_sp_institution_data

    load_ic_sp_institution_data(apps=apps)


def unload_ic_sp_data(apps, schema_editor):
    """Remove dados institucionais provisórios em rollback."""
    Institution = apps.get_model("institution_ic_sp", "Institution")
    Institution.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("institution_ic_sp", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(load_ic_sp_data, unload_ic_sp_data),
    ]
