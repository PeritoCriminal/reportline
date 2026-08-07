# reportline/accounts/admin/user_admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Administração de CustomUser com metadados OAuth."""

    list_display = UserAdmin.list_display + ("auth_provider",)
    list_filter = UserAdmin.list_filter + ("auth_provider",)
    readonly_fields = UserAdmin.readonly_fields + ("auth_provider", "external_subject")
    fieldsets = UserAdmin.fieldsets + (
        (
            "Autenticação externa",
            {
                "fields": ("auth_provider", "external_subject"),
            },
        ),
    )
