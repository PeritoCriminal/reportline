import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    """
    Modelo de usuário personalizado do ecossistema ReportLine.

    Substitui a chave primária sequencial padrão (AutoIncrement ID) por um 
    identificador global único (UUIDv4). Esta abordagem mitiga vulnerabilidades 
    de IDOR (Insecure Direct Object Reference) em endpoints públicos e previne 
    a exposição de métricas de volumetria do banco de dados na camada de apresentação.
    """
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False
    )

    class Meta:
        app_label = 'accounts'
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    def __str__(self):
        return self.username