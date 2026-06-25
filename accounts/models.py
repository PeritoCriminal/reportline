from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    # Deixamos em branco (pass) por enquanto. 
    # No futuro, se precisar adicionar campos como 'registro_profissional' ou 'cargo', basta colocá-los aqui.
    pass
