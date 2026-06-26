from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # Força o Django a carregar as amarrações do nosso pacote modular de admin
        import accounts.admin