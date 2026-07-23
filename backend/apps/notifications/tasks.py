from celery import shared_task

from apps.notifications.services import dispatch_due_reminders


@shared_task(name="apps.notifications.tasks.dispatch_due_notification_reminders")
def dispatch_due_notification_reminders() -> int:
    return dispatch_due_reminders()
