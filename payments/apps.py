from django.apps import AppConfig

class PaymentsConfig(AppConfig):   # ✅ plural class name
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'payments'              # ✅ plural app name

    def ready(self):
        import payments.signals    # ✅ keep signals import
