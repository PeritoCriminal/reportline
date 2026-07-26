"""
Testes do BaseModel e regras de identificação e auditoria temporal.
"""

import uuid

from django.db import connection, models
from django.test import TestCase
from django.test.utils import isolate_apps

from common.models import BaseModel


@isolate_apps("common")
class BaseModelTests(TestCase):
    """Testes do model abstrato BaseModel."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        class SampleRecord(BaseModel):
            label = models.CharField(max_length=50, verbose_name="Rótulo")

            class Meta:
                app_label = "common"
                verbose_name = "Registro de teste"
                verbose_name_plural = "Registros de teste"

        cls.SampleRecord = SampleRecord

        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(SampleRecord)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(cls.SampleRecord)
        super().tearDownClass()

    def test_meta_is_abstract(self):
        """Garante que BaseModel não gera tabela própria no banco."""
        self.assertTrue(BaseModel._meta.abstract)

    def test_primary_key_is_uuid(self):
        """Garante que a chave primária seja UUID, não inteiro sequencial."""
        record = self.SampleRecord.objects.create(label="exemplo")
        self.assertIsInstance(record.pk, uuid.UUID)

    def test_created_at_is_set_on_create(self):
        """Garante preenchimento automático de created_at na criação."""
        record = self.SampleRecord.objects.create(label="exemplo")
        self.assertIsNotNone(record.created_at)
        self.assertIsNotNone(record.updated_at)

    def test_updated_at_changes_on_save(self):
        """Garante que updated_at avance após persistência de alteração."""
        record = self.SampleRecord.objects.create(label="original")
        previous_updated_at = record.updated_at

        record.label = "alterado"
        record.save()
        record.refresh_from_db()

        self.assertGreaterEqual(record.updated_at, previous_updated_at)

    def test_timestamp_verbose_names_in_portuguese(self):
        """Garante metadados de exibição dos timestamps em português."""
        created_field = BaseModel._meta.get_field("created_at")
        updated_field = BaseModel._meta.get_field("updated_at")

        self.assertEqual(created_field.verbose_name, "Criado em")
        self.assertEqual(updated_field.verbose_name, "Atualizado em")
