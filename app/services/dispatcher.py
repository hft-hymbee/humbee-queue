"""
Notification Dispatcher
=======================
Handles fanout logic: receives a notification event and dispatches
individual Celery tasks per (channel × recipient) combination.

Race-condition-safe dispatch order
-----------------------------------
The previous implementation called celery_app.send_task() inside the
per-recipient loop, BEFORE db.commit(). Workers could (and did under high
load) start executing before the NotificationHistory row was visible to
other DB sessions, producing:

    "Notification record not found for status update"

The fixed order is:

    Phase 1 — DB writes (flush only, no tasks sent):
        for each (channel × recipient):
            pre-generate celery_task_id as a UUID string
            NotificationService.create(..., celery_task_id=celery_task_id)
            → db.flush()   # visible to THIS session only

    Phase 2 — Commit:
        db.commit()        # ALL rows now visible to every session / worker

    Phase 3 — Enqueue (rows guaranteed visible):
        for each pending dispatch:
            celery_app.send_task(..., task_id=celery_task_id)

Because celery_task_id is pre-generated and passed to both create() and
send_task(), the DB record and the Celery task always share the same task
ID with zero extra DB round-trips.

Usage:
    from services.dispatcher import NotificationDispatcher

    dispatcher = NotificationDispatcher(db_session)
    results = dispatcher.dispatch(
        event_type="ORDER_PLACED",
        channels=["EMAIL", "SMS"],
        recipients=["user@example.com", "+91xxx"],
        template_id="order.create.erw_angles",
        payload={...},
    )
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from core.celery_app import celery_app
from core.logging import get_logger
from domain.enums import NotificationChannel
from services.notification_service import NotificationService

logger = get_logger("service.dispatcher")

# Channel enum → Celery task name
CHANNEL_TASK_MAP = {
    NotificationChannel.EMAIL: "notification.send_email",
    NotificationChannel.SMS: "notification.send_sms",
    NotificationChannel.WHATSAPP: "notification.send_whatsapp",
    NotificationChannel.PUSH: "notification.send_push",
}

# Channel enum → Celery queue name
CHANNEL_QUEUE_MAP = {
    NotificationChannel.EMAIL: "email_queue",
    NotificationChannel.SMS: "sms_queue",
    NotificationChannel.WHATSAPP: "whatsapp_queue",
    NotificationChannel.PUSH: "push_queue",
}

# FCM multicast hard limit per API call
PUSH_BATCH_SIZE = 500


@dataclass
class _PendingDispatch:
    """Holds everything needed to enqueue a single Celery task after commit."""
    notification_id: str
    celery_task_id: str
    task_name: str
    queue: str
    channel: str
    recipient: str
    kwargs: Dict = field(default_factory=dict)


class NotificationDispatcher:
    """
    Dispatches notification events to per-channel Celery queues.

    Creates a notification_history record per (channel × recipient) before
    dispatching. Tasks are enqueued only AFTER all DB records are committed,
    eliminating the race condition where workers start before the record is
    visible in the database.
    """

    def __init__(self, db: Optional[Session]):
        self.db = db

    def dispatch(
        self,
        event_type: str,
        channels: List[NotificationChannel],
        recipients: List[str],
        template_id: str,
        payload: dict,
        user_id: Optional[str] = None,
        subject: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> List[dict]:
        """
        Fan out notification to all (channel × recipient) combinations.

        Args:
            event_type: Event name (e.g., "ORDER_PLACED")
            channels: List of channels to send on
            recipients: List of recipient addresses
            template_id: Template identifier
            payload: Notification payload
            user_id: Optional user ID for tracking
            subject: Optional subject line (email/push)
            request_id: Optional idempotency key

        Returns:
            List of dicts with notification_id and channel for each dispatched notification
        """
        # ── Idempotency check ────────────────────────────────────────────────
        # If request_id already has records, return existing data and skip.
        if request_id and self.db:
            existing = NotificationService.get_by_request_id(self.db, request_id)
            if existing:
                logger.info(
                    f"Request {request_id} already dispatched ({len(existing)} records), skipping",
                    extra={
                        "event": "dispatch_skipped_duplicate",
                        "request_id": request_id,
                        "existing_count": len(existing),
                    },
                )
                return [
                    {
                        "notification_id": str(r.id),
                        "channel": r.channel,
                        "status": r.status,
                        "skipped": True,
                    }
                    for r in existing
                ]

        def _filter_recipients(channel: NotificationChannel, all_recipients: List[str]) -> List[str]:
            phone_regex = re.compile(r"^\+?\d{6,15}$")

            if channel == NotificationChannel.EMAIL:
                return [r for r in all_recipients if "@" in r]
            elif channel in (NotificationChannel.SMS, NotificationChannel.WHATSAPP):
                # Strict phone number matching so tokens don't leak into SMS
                return [r for r in all_recipients if phone_regex.match(r)]
            elif channel == NotificationChannel.PUSH:
                # Push tokens/user_ids shouldn't be emails or plain phone numbers
                return [r for r in all_recipients if "@" not in r and not phone_regex.match(r)]

            return all_recipients

        # ── Phase 1: DB writes (flush only — no tasks enqueued yet) ─────────
        pending_dispatches: List[_PendingDispatch] = []
        pending_push_batches: List[dict] = []  # PUSH batches flushed but not committed yet

        for channel in channels:
            valid_recipients = _filter_recipients(channel, recipients)

            # --- PUSH: batch all tokens together (≤500 per FCM multicast call) ---
            if channel == NotificationChannel.PUSH:
                push_batch_infos = self._prepare_push_batches(
                    tokens=valid_recipients,
                    event_type=event_type,
                    template_id=template_id,
                    payload=payload,
                    user_id=user_id,
                    subject=subject,
                    request_id=request_id,
                )
                pending_push_batches.extend(push_batch_infos)
                continue  # skip the per-recipient loop below

            # --- All other channels: one task per recipient ---
            for recipient in valid_recipients:
                notification_id = uuid4()
                # Pre-generate the Celery task ID so it can be stored in the DB
                # record NOW (during Phase 1) without any back-fill after commit.
                celery_task_id = str(uuid4())
                task_name = CHANNEL_TASK_MAP.get(channel)
                queue_name = CHANNEL_QUEUE_MAP.get(channel)

                if not task_name:
                    logger.error(f"Unknown channel: {channel}")
                    continue

                if self.db:
                    NotificationService.create(
                        db=self.db,
                        id=notification_id,
                        event_type=event_type,
                        channel=channel.value,
                        recipient=recipient,
                        template_id=template_id,
                        user_id=user_id,
                        subject=subject,
                        payload=payload,
                        request_id=request_id,
                        celery_task_id=celery_task_id,
                    )
                    # Logging is handled inside NotificationService.create()
                    # with event="db_record_created"

                pending_dispatches.append(
                    _PendingDispatch(
                        notification_id=str(notification_id),
                        celery_task_id=celery_task_id,
                        task_name=task_name,
                        queue=queue_name,
                        channel=channel.value,
                        recipient=recipient,
                        kwargs={
                            "notification_id": str(notification_id),
                            "recipient": recipient,
                            "template_id": template_id,
                            "payload": payload,
                            "subject": subject,
                            "request_id": request_id,
                        },
                    )
                )

        # ── Phase 2: Commit ALL records automically ───────────────────────────
        # Only after this line are the rows visible to Celery workers.
        if self.db:
            self.db.commit()
            logger.info(
                "All notification records committed to database",
                extra={
                    "event": "db_committed",
                    "count": len(pending_dispatches) + len(pending_push_batches),
                    "event_type": event_type,
                    "request_id": request_id,
                },
            )

        # ── Phase 3: Enqueue tasks (rows now visible to all DB sessions) ─────
        results = []

        # Enqueue non-PUSH tasks
        for dispatch in pending_dispatches:
            celery_app.send_task(
                dispatch.task_name,
                kwargs=dispatch.kwargs,
                queue=dispatch.queue,
                task_id=dispatch.celery_task_id,  # matches the celery_task_id stored in DB
            )

            logger.info(
                f"Dispatched {dispatch.channel} notification",
                extra={
                    "event": "task_enqueued",
                    "notification_id": dispatch.notification_id,
                    "celery_task_id": dispatch.celery_task_id,
                    "channel": dispatch.channel,
                    "recipient": dispatch.recipient,
                    "event_type": event_type,
                    "request_id": request_id,
                },
            )

            results.append({
                "notification_id": dispatch.notification_id,
                "channel": dispatch.channel,
                "status": "QUEUED",
            })

        # Enqueue PUSH batch tasks
        for batch in pending_push_batches:
            celery_app.send_task(
                CHANNEL_TASK_MAP[NotificationChannel.PUSH],
                kwargs=batch["task_kwargs"],
                queue=CHANNEL_QUEUE_MAP[NotificationChannel.PUSH],
                task_id=batch["celery_task_id"],
            )

            logger.info(
                f"Dispatched PUSH batch {batch['batch_index']}/{batch['total_batches']}",
                extra={
                    "event": "task_enqueued",
                    "notification_id": str(batch["notification_id"]),
                    "celery_task_id": batch["celery_task_id"],
                    "channel": NotificationChannel.PUSH.value,
                    "recipient": batch["recipient_label"],
                    "token_count": batch["token_count"],
                    "event_type": event_type,
                    "request_id": request_id,
                },
            )

            results.append({
                "notification_id": str(batch["notification_id"]),
                "channel": NotificationChannel.PUSH.value,
                "recipient": batch["recipient_label"],
                "batch_index": batch["batch_index"],
                "total_batches": batch["total_batches"],
                "token_count": batch["token_count"],
                "status": "QUEUED",
            })

        logger.info(
            f"Dispatch complete: {len(results)} notifications queued",
            extra={
                "event": "dispatch_complete",
                "event_type": event_type,
                "request_id": request_id,
                "total_dispatched": len(results),
            },
        )

        return results

    def _prepare_push_batches(
        self,
        tokens: list,
        event_type: str,
        template_id: str,
        payload: dict,
        user_id: str = None,
        subject: str = None,
        request_id: str = None,
    ) -> list:
        """
        Phase 1 of PUSH dispatch: flush DB records for each token batch.
        Returns a list of batch info dicts used in Phase 3 to enqueue tasks.

        Follows the same pre-generated celery_task_id pattern as all other channels:
        the task ID is generated here, stored in the DB record via NotificationService.create(),
        then passed as task_id= to send_task() in Phase 3 — no backfill needed.

        Does NOT commit — the main dispatch() Phase 2 commit covers these rows.
        """
        if not tokens:
            logger.warning(
                "PUSH dispatch called with empty token list — nothing to dispatch",
                extra={"event": "push_empty_tokens", "event_type": event_type, "request_id": request_id},
            )
            return []

        batches = [
            tokens[i:i + PUSH_BATCH_SIZE]
            for i in range(0, len(tokens), PUSH_BATCH_SIZE)
        ]
        total_batches = len(batches)
        batch_infos = []

        for batch_index, batch_tokens in enumerate(batches, start=1):
            notification_id = uuid4()
            celery_task_id = str(uuid4())
            recipient_label = f"PUSH_BATCH_{batch_index}_OF_{total_batches}"

            if self.db:
                NotificationService.create(
                    db=self.db,
                    id=notification_id,
                    event_type=event_type,
                    channel=NotificationChannel.PUSH.value,
                    recipient=recipient_label,
                    template_id=template_id,
                    user_id=user_id,
                    subject=subject,
                    payload=payload,
                    request_id=request_id,
                    celery_task_id=celery_task_id,  # stored upfront, no backfill needed
                )

            batch_infos.append({
                "notification_id": notification_id,
                "celery_task_id": celery_task_id,
                "recipient_label": recipient_label,
                "batch_index": batch_index,
                "total_batches": total_batches,
                "token_count": len(batch_tokens),
                "task_kwargs": {
                    "notification_id": str(notification_id),
                    "tokens": batch_tokens,
                    "template_id": template_id,
                    "payload": payload,
                    "subject": subject,
                    "request_id": request_id,
                    "user_id": user_id,
                },
            })

        return batch_infos
