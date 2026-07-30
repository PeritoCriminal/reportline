"""
Testes dos utilitários de limpeza de FileField/ImageField.
"""

from unittest.mock import MagicMock

from django.test import SimpleTestCase

from common.file_fields import (
    cleanup_replaced_file,
    cleanup_replaced_files,
    delete_model_file_fields,
    get_file_field_name,
)


class FileFieldCleanupUtilityTests(SimpleTestCase):
    """Testes das funções puras de limpeza de arquivos substituídos."""

    def test_get_file_field_name_returns_empty_for_falsy_values(self):
        """Garante retorno vazio quando não há arquivo associado."""
        self.assertEqual(get_file_field_name(None), "")
        self.assertEqual(get_file_field_name(""), "")

    def test_cleanup_replaced_file_deletes_when_path_changes(self):
        """Remove arquivo anterior quando o caminho do upload muda."""
        old_file = MagicMock()
        old_file.name = "institution_ic_sp/logos/old.png"
        new_file = MagicMock()
        new_file.name = "institution_ic_sp/logos/new.png"

        cleanup_replaced_file(old_file, new_file)

        old_file.delete.assert_called_once_with(save=False)

    def test_cleanup_replaced_file_keeps_file_when_path_is_unchanged(self):
        """Não remove arquivo quando o campo continua apontando para o mesmo path."""
        old_file = MagicMock()
        old_file.name = "institution_ic_sp/logos/same.png"
        new_file = MagicMock()
        new_file.name = "institution_ic_sp/logos/same.png"

        cleanup_replaced_file(old_file, new_file)

        old_file.delete.assert_not_called()

    def test_cleanup_replaced_file_deletes_when_field_is_cleared(self):
        """Remove arquivo anterior quando o campo de upload é limpo."""
        old_file = MagicMock()
        old_file.name = "institution_ic_sp/logos/old.png"

        cleanup_replaced_file(old_file, None)

        old_file.delete.assert_called_once_with(save=False)

    def test_cleanup_replaced_files_iterates_over_field_names(self):
        """Garante limpeza em lote para múltiplos campos de arquivo."""
        previous = MagicMock()
        previous.sp_logo.name = "institution_ic_sp/logos/sp_old.png"
        previous.sptc_logo.name = "institution_ic_sp/logos/sptc_old.png"

        current = MagicMock()
        current.sp_logo.name = "institution_ic_sp/logos/sp_new.png"
        current.sptc_logo.name = "institution_ic_sp/logos/sptc_old.png"

        cleanup_replaced_files(current, previous, ("sp_logo", "sptc_logo"))

        previous.sp_logo.delete.assert_called_once_with(save=False)
        previous.sptc_logo.delete.assert_not_called()

    def test_delete_model_file_fields_removes_all_informed_files(self):
        """Remove todos os arquivos informados na exclusão do registro."""
        instance = MagicMock()
        instance.sp_logo.name = "institution_ic_sp/logos/sp.png"
        instance.sptc_logo.name = "institution_ic_sp/logos/sptc.png"

        delete_model_file_fields(instance, ("sp_logo", "sptc_logo"))

        instance.sp_logo.delete.assert_called_once_with(save=False)
        instance.sptc_logo.delete.assert_called_once_with(save=False)
