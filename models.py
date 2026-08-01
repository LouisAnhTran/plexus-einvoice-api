from pydantic import BaseModel, Field


class DocumentId(BaseModel):
    scheme: str = "peppol-doctype-wildcard"
    value: str


class DocumentType(BaseModel):
    processId: str
    documentId: DocumentId


class AccessPointConfiguration(BaseModel):
    endpointId: str
    documentTypes: list[DocumentType] = []


class RegisterCompanyRequest(BaseModel):
    participantId: str = Field(
        ...,
        description="Raw form, e.g. iso6523-actorid-upis::0195:SGTST202400100A",
        examples=["iso6523-actorid-upis::0195:SGTST202400100A"],
    )
    name: str
    countryCode: str = Field(..., min_length=2, max_length=2, examples=["SG"])
    accessPointConfigurations: list[AccessPointConfiguration] = []
    solutionProviderId: str | None = None
    taxSubmissionEnabled: bool = Field(
        default=False,
        description=(
            "Enable tax submission at registration. True starts taxStatus at "
            "PENDING_ACTIVATION, which auto-advances to ACTIVATED. False leaves "
            "taxStatus null — it can still be activated later."
        ),
    )


class CompanyResponse(BaseModel):
    participantId: str
    uen: str
    name: str
    countryCode: str
    solutionProviderId: str | None
    accessPointConfigurations: list[dict]

    kycStatus: str
    kycStatusChangedAt: str
    kycSecondsUntilNextChange: int | None

    taxStatus: str | None
    taxStatusChangedAt: str | None
    taxSecondsUntilNextChange: int | None

    createdAt: str
    updatedAt: str
