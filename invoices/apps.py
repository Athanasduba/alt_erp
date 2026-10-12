from django.apps import AppConfig

class InvoicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'invoices'

    def ready(self):
        # Import signals when the app is ready
        import invoices.signals
