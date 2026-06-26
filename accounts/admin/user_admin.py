from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from accounts.models import CustomUser

# Registra o CustomUser usando o comportamento padrão do UserAdmin do Django
admin.site.register(CustomUser, UserAdmin)