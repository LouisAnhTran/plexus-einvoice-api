"""Time-based status progression.

The real InvoiceNow network takes minutes-to-hours to move a company through
KYC registration and tax-submission activation. We fake that with elapsed time
rather than a background scheduler: every read *projects* the stored status
forward based on how long it has sat in its current state, and persists the
result if it moved.

Projecting on read rather than ticking on a timer means:
  - no scheduler to run, and no drift between it and the request path
  - correct behaviour across restarts (elapsed time lives in the database)
  - a company registered 20 minutes ago already reads as REGISTERED the first
    time anyone looks, instead of waiting for a worker to catch up
"""

from datetime import datetime, timedelta, timezone

# KYC registration — always configured at register time.
KYC_FLOW = {
    "PENDING": "REGISTERED",
}

# Tax submission — opt-in, and togglable at any time regardless of KYC status.
TAX_FLOW = {
    "PENDING_ACTIVATION": "ACTIVATED",
    "PENDING_DEACTIVATION": "DEACTIVATED",
}

# Statuses that only an explicit call can leave. Anything not in a *_FLOW map
# above is terminal until acted on.
TAX_SETTLED = {"ACTIVATED", "DEACTIVATED"}


def project(
    status: str,
    changed_at: datetime,
    flow: dict[str, str],
    delay_seconds: int,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    """Advance `status` through `flow` for as many steps as elapsed time allows.

    `changed_at` is advanced to the moment each transition became *due* — not to
    `now` — so a company left alone for an hour ends up with the same status and
    timestamp it would have had if someone polled it every second.
    """
    now = now or datetime.now(timezone.utc)
    step = timedelta(seconds=delay_seconds)

    while status in flow:
        due_at = changed_at + step
        if now < due_at:
            break
        status = flow[status]
        changed_at = due_at

    return status, changed_at


def seconds_until_next_change(
    status: str,
    changed_at: datetime,
    flow: dict[str, str],
    delay_seconds: int,
    now: datetime | None = None,
) -> int | None:
    """Seconds until `status` moves on, or None if nothing is pending.

    Returned in API responses so a caller polling for completion can report
    "about 4 more minutes" and pick a sane retry interval instead of hammering.
    """
    if status not in flow:
        return None
    now = now or datetime.now(timezone.utc)
    remaining = (changed_at + timedelta(seconds=delay_seconds)) - now
    return max(0, int(remaining.total_seconds()))
