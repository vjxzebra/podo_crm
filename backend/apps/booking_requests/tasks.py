from celery import shared_task

from apps.booking_requests.telegram_services import (
    dispatch_due_telegram_deliveries,
    process_telegram_update,
)


@shared_task(name="apps.booking_requests.tasks.dispatch_telegram_booking_request_deliveries")
def dispatch_telegram_booking_request_deliveries() -> int:
    return dispatch_due_telegram_deliveries()


@shared_task(name="apps.booking_requests.tasks.process_telegram_update")
def process_telegram_update_task(update_id: int) -> str:
    return process_telegram_update(update_id)
