import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from models import CompanyResponse, RegisterCompanyRequest
from routers.deps import require_api_key
from services import companies as svc

router = APIRouter(
    prefix="/ap/v1",
    tags=["companies"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/participant", status_code=201, response_model=CompanyResponse)
async def register_company(payload: RegisterCompanyRequest):
    """Register a company on the InvoiceNow network.

    KYC registration is always configured: kycStatus starts at PENDING and
    becomes REGISTERED automatically.

    Tax submission depends on `taxSubmissionEnabled`. When true, taxStatus
    starts at PENDING_ACTIVATION and auto-advances to ACTIVATED. When false or
    omitted, taxStatus stays null and tax can be activated later via
    tax/activate — at any time, independently of KYC.
    """
    try:
        return await svc.create(payload.model_dump())
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"Company {payload.participantId} is already registered",
        )


@router.get("/participant", response_model=list[CompanyResponse])
async def list_companies():
    """List every company registered through this Access Point."""
    return await svc.list_all()


@router.get("/participant/{participant_id:path}", response_model=CompanyResponse)
async def get_company(participant_id: str):
    """Fetch one company by participantId or bare UEN."""
    company = await svc.get(participant_id)
    if not company:
        raise HTTPException(status_code=404, detail=f"No company {participant_id}")
    return company


@router.delete("/participant/{participant_id:path}", status_code=204)
async def delete_company(participant_id: str):
    """Deregister a company entirely."""
    if not await svc.delete(participant_id):
        raise HTTPException(status_code=404, detail=f"No company {participant_id}")


@router.post("/participants/{participant_id:path}/tax/activate",
             response_model=CompanyResponse)
async def activate_tax(participant_id: str):
    """Start tax-submission activation. Allowed whatever the KYC status is."""
    company = await svc.get(participant_id)
    if not company:
        raise HTTPException(status_code=404, detail=f"No company {participant_id}")

    if company["taxStatus"] in ("ACTIVATED", "PENDING_ACTIVATION"):
        raise HTTPException(
            status_code=409,
            detail=f"Tax submission is already {company['taxStatus']}",
        )

    return await svc.set_tax_status(participant_id, "PENDING_ACTIVATION")


@router.post("/participants/{participant_id:path}/tax/deactivate",
             response_model=CompanyResponse)
async def deactivate_tax(participant_id: str):
    """Start tax-submission deactivation. Allowed whatever the KYC status is."""
    company = await svc.get(participant_id)
    if not company:
        raise HTTPException(status_code=404, detail=f"No company {participant_id}")

    if company["taxStatus"] is None:
        raise HTTPException(
            status_code=409,
            detail="Tax submission was never enabled for this company",
        )
    if company["taxStatus"] in ("DEACTIVATED", "PENDING_DEACTIVATION"):
        raise HTTPException(
            status_code=409,
            detail=f"Tax submission is already {company['taxStatus']}",
        )

    return await svc.set_tax_status(participant_id, "PENDING_DEACTIVATION")
