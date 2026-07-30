"""
Utilitários para limpeza de arquivos substituídos em FileField/ImageField.

Evita acúmulo de imagens obsoletas em MEDIA_ROOT quando usuários ou
administradores trocam uploads ou limpam campos de arquivo.
"""


def get_file_field_name(file_field):
    """
    Retorna o caminho relativo armazenado no campo de arquivo.

    Args:
        file_field: Instância de FieldFile ou valor equivalente.

    Returns:
        str: Nome relativo no storage ou string vazia quando ausente.
    """
    if not file_field:
        return ""

    name = getattr(file_field, "name", None)
    return name or ""


def cleanup_replaced_file(old_file, new_file):
    """
    Remove do storage o arquivo anterior quando um upload é substituído ou limpo.

    A remoção ocorre somente se havia arquivo anterior e o caminho mudou.
    Atualizações que não alteram o arquivo referenciado são ignoradas.

    Args:
        old_file: FieldFile anterior ao save.
        new_file: FieldFile após o save.
    """
    old_name = get_file_field_name(old_file)
    new_name = get_file_field_name(new_file)

    if old_name and old_name != new_name:
        old_file.delete(save=False)


def cleanup_replaced_files(instance, previous_instance, field_names):
    """
    Compara dois registros e remove arquivos obsoletos dos campos informados.

    Args:
        instance: Registro persistido com os valores atuais.
        previous_instance: Registro anterior ao save.
        field_names: Iterable com nomes dos campos FileField/ImageField.
    """
    for field_name in field_names:
        cleanup_replaced_file(
            getattr(previous_instance, field_name, None),
            getattr(instance, field_name, None),
        )


def delete_model_file_fields(instance, field_names):
    """
    Remove do storage os arquivos associados aos campos informados.

    Usado na exclusão do registro para evitar órfãos em MEDIA_ROOT.

    Args:
        instance: Registro cujos arquivos serão removidos.
        field_names: Iterable com nomes dos campos FileField/ImageField.
    """
    for field_name in field_names:
        file_field = getattr(instance, field_name, None)
        if get_file_field_name(file_field):
            file_field.delete(save=False)
