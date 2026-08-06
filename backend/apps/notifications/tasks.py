from celery import shared_task

from apps.notifications.services import dispatch_due_reminders
from apps.notifications.telegram_services import dispatch_due_notification_telegram_deliveries


@shared_task(name="apps.notifications.tasks.dispatch_due_notification_reminders")
def dispatch_due_notification_reminders() -> int:
    return dispatch_due_reminders()


@shared_task(name="apps.notifications.tasks.dispatch_notification_telegram_deliveries")
def dispatch_notification_telegram_deliveries() -> int:
    return dispatch_due_notification_telegram_deliveries()
