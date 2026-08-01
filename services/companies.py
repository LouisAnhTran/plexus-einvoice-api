"""Read/write helpers for the companies table.

Every read runs the stored statuses through services.state.project() first, so
callers always see the status the clock says they should have, and any movement
is written back.
"""

import re
import uuid

import db
from config import settings
from db import from_db_json, from_db_time, to_db_json, to_db_time, utcnow
from services.state import (
    KYC_FLOW,
    TAX_FLOW,
    project,
    seconds_until_next_change,
)

# iso6523-actorid-upis::0195:SGTST202400100A
#                            ^^^^ scheme, then the business identifier
_PARTICIPANT_RE = re.compile(r"^.*::(?P<scheme>\d{4}):(?P<identifier>.+)$")


def parse_uen(participant_id: str) -> str:
    """Pull the bare business identifier out of a Peppol participant ID.

    Falls back to the whole string when it doesn't match the expected shape —
    this is a dummy service, not a validator, and refusing to store a company
    over a formatting quibble would be unhelpful.
    """
    match = _PARTICIPANT_RE.match(participant_id.strip())
    return match.group("identifier") if match else participant_id.strip()


async def _project(row) -> dict:
    """Bring one row's KYC and tax statuses up to date, persisting any change."""
    kyc_status, kyc_changed = project(
        row["kyc_status"],
        from_db_time(row["kyc_status_changed_at"]),
        KYC_FLOW,
        settings.auto_advance_seconds,
    )

    tax_status = row["tax_status"]
    tax_changed = from_db_time(row["tax_status_changed_at"])
    if tax_status is not None:
        tax_status, tax_changed = project(
            tax_status, tax_changed, TAX_FLOW, settings.auto_advance_seconds
        )

    if kyc_status != row["kyc_status"] or tax_status != row["tax_status"]:
        await db.execute(
            """
            UPDATE companies
               SET kyc_status = ?,
                   kyc_status_changed_at = ?,
                   tax_status = ?,
                   tax_status_changed_at = ?,
                   updated_at = ?
             WHERE participant_id = ?
            """,
            kyc_status,
            to_db_time(kyc_changed),
            tax_status,
            to_db_time(tax_changed),
            to_db_time(utcnow()),
            row["participant_id"],
        )

    return {
        "participantId": row["participant_id"],
        "uen": row["uen"],
        "name": row["name"],
        "countryCode": row["country_code"],
        "solutionProviderId": row["solution_provider_id"],
        "accessPointConfigurations": from_db_json(
            row["access_point_configurations"]
        ),
        "kycStatus": kyc_status,
        "kycStatusChangedAt": kyc_changed.isoformat(),
        "kycSecondsUntilNextChange": seconds_until_next_change(
            kyc_status, kyc_changed, KYC_FLOW, settings.auto_advance_seconds
        ),
        "taxStatus": tax_status,
        "taxStatusChangedAt": tax_changed.isoformat() if tax_changed else None,
        "taxSecondsUntilNextChange": (
            seconds_until_next_change(
                tax_status, tax_changed, TAX_FLOW, settings.auto_advance_seconds
            )
            if tax_status
            else None
        ),
        "createdAt": from_db_time(row["created_at"]).isoformat(),
        "updatedAt": from_db_time(row["updated_at"]).isoformat(),
    }


async def create(payload: dict) -> dict:
    """Register a company.

    KYC is always configured and starts at PENDING. Tax submission is only
    configured when taxSubmissionEnabled is true, in which case it starts at
    PENDING_ACTIVATION; otherwise tax_status stays NULL and tax can be
    activated later through an explicit call.
    """
    participant_id = payload["participantId"].strip()
    tax_status = "PENDING_ACTIVATION" if payload.get("taxSubmissionEnabled") else None
    now = to_db_time(utcnow())

    await db.execute(
        """
        INSERT INTO companies (
            id, participant_id, uen, name, country_code, solution_provider_id,
            access_point_configurations, kyc_status, kyc_status_changed_at,
            tax_status, tax_status_changed_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?)
        """,
        str(uuid.uuid4()),
        participant_id,
        parse_uen(participant_id),
        payload["name"],
        payload["countryCode"].upper(),
        payload.get("solutionProviderId"),
        to_db_json(payload.get("accessPointConfigurations")),
        now,
        tax_status,
        now if tax_status else None,
        now,
        now,
    )
    return await get(participant_id)


async def get(participant_id: str) -> dict | None:
    """Look up by participantId, falling back to a bare UEN.

    The fallback exists so callers (and the MCP server's tools) can pass
    "202400100A" instead of reconstructing the full iso6523 string.
    """
    row = await db.fetchrow(
        "SELECT * FROM companies WHERE participant_id = ? OR uen = ?",
        participant_id.strip(),
        participant_id.strip(),
    )
    return await _project(row) if row else None


async def list_all() -> list[dict]:
    rows = await db.fetch("SELECT * FROM companies ORDER BY created_at DESC")
    return [await _project(r) for r in rows]


async def delete(participant_id: str) -> bool:
    affected = await db.execute(
        "DELETE FROM companies WHERE participant_id = ? OR uen = ?",
        participant_id.strip(),
        participant_id.strip(),
    )
    return affected > 0


async def set_tax_status(participant_id: str, status: str) -> dict:
    now = to_db_time(utcnow())
    await db.execute(
        """
        UPDATE companies
           SET tax_status = ?, tax_status_changed_at = ?, updated_at = ?
         WHERE participant_id = ? OR uen = ?
        """,
        status,
        now,
        now,
        participant_id.strip(),
        participant_id.strip(),
    )
    return await get(participant_id)
