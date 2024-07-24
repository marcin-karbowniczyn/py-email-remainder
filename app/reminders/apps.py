from django.apps import AppConfig


class RemindersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reminders'

    def ready(self):
        from . import manage_reminders
        manage_reminders.start()
