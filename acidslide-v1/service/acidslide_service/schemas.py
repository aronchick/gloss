"""Public API request and response models."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

ShortText = Annotated[str, Field(min_length=1, max_length=160, pattern=r"^[^\x00-\x1f]+$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EfficiencyMetrics(StrictModel):
    generation_strategy: Literal["direct", "code", "hybrid", "template-edit"]
    generation_wall_clock_seconds: float | None = Field(default=None, ge=0, le=604800)
    generation_token_count: int | None = Field(default=None, ge=0)
    generation_cost_usd: float | None = Field(default=None, ge=0)
    retry_count: int | None = Field(default=None, ge=0, le=10000)
    code_language: str | None = Field(default=None, max_length=120)
    code_line_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_code_fields(self) -> EfficiencyMetrics:
        if self.generation_strategy not in {"code", "hybrid"} and (
            self.code_language is not None or self.code_line_count is not None
        ):
            raise ValueError("code fields are only valid for code or hybrid strategies")
        return self


class Attestation(StrictModel):
    method: str = Field(min_length=3, max_length=2000)
    human_intervention: bool
    post_processing: bool
    external_resources_used: bool
    external_resources_description: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_external_resources(self) -> Attestation:
        if self.external_resources_used and not self.external_resources_description:
            raise ValueError(
                "external_resources_description is required when external resources were used"
            )
        if not self.external_resources_used and self.external_resources_description:
            raise ValueError(
                "external_resources_description must be omitted when external resources "
                "were not used"
            )
        return self


class SubmissionMetadata(StrictModel):
    campaign_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    generation_seed: str | None
    efficiency_metrics: EfficiencyMetrics
    attestation: Attestation
    webhook_url: HttpUrl | None = None
    webhook_secret: str | None = Field(default=None, min_length=16, max_length=512)

    @model_validator(mode="after")
    def validate_webhook(self) -> SubmissionMetadata:
        if self.generation_seed is not None and len(self.generation_seed.encode("utf-8")) > 256:
            raise ValueError("generation_seed must be at most 256 UTF-8 bytes")
        if bool(self.webhook_url) != bool(self.webhook_secret):
            raise ValueError("webhook_url and webhook_secret must be provided together")
        return self


class SubmissionAccepted(BaseModel):
    submission_id: str
    campaign_id: str
    campaign_slot: Literal[1, 2, 3]
    status: Literal["quarantining"]
    estimated_wait_seconds: int
    status_url: str


class SubmissionError(BaseModel):
    code: str
    message: str
    retryable: bool
    active_benchmark_versions: list[str] | None = None


class SubmissionResult(BaseModel):
    fidelity_score: float | None
    passed_items: int
    total_items: int
    deck_passed: bool
    eligible: bool
    anti_cheat_flags: list[Any]
    repair_triggered: bool
    tier_scores: dict[str, Any]
    report_url: str
    environment_hash: str
    campaign_id: str
    campaign_slot: int
    campaign_score: float
    verification_label: Literal["grading-verified artifact score; generation-attested"]
    verification_scope: Literal["artifact_conformance"]
    scoring_cohort_id: str
    scoring_manifest_sha256: str
    grader_source_tree_sha256: str
    environment_attestation_sha256: str


class SubmissionStatusResponse(BaseModel):
    submission_id: str
    campaign_id: str
    campaign_slot: int | None
    status: Literal["quarantining", "queued", "grading", "completed", "failed", "rejected"]
    result: SubmissionResult | None = None
    error: SubmissionError | None = None
    created_at: datetime
    grading_started_at: datetime | None = None
    grading_completed_at: datetime | None = None


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    monthly_quota: int = Field(default=30, ge=1, le=1_000_000)
    is_paid: bool = False


class OrganizationCreated(BaseModel):
    organization_id: str
    name: str
    api_key: str
    monthly_quota: int
    warning: str = "This API key is shown once. Store it securely."


class OrganizationUpdate(BaseModel):
    is_suspended: bool | None = None
    monthly_quota: int | None = Field(default=None, ge=1, le=1_000_000)


class PublishReportResponse(BaseModel):
    submission_id: str
    report_public: Literal[True]
    report_url: str


class ModelCreate(StrictModel):
    display_name: ShortText
    owner_attribution: Literal["owner-verified", "submitter-attested"] = "submitter-attested"


class ModelCreated(BaseModel):
    model_key: str
    submitter_id: str
    display_name: str
    owner_attribution: Literal["owner-verified", "submitter-attested"]
    created_at: datetime


class ModelRevisionCreate(StrictModel):
    display_version: ShortText
    revision_note: str = Field(min_length=1, max_length=4000)
    provider_revision: str | None = Field(default=None, min_length=1, max_length=320)


class ModelRevisionCreated(BaseModel):
    model_key: str
    model_revision_key: str
    display_version: str
    revision_note: str
    created_at: datetime


class GenerationProfileCreate(StrictModel):
    model_revision_key: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    profile: dict[str, Any]


class GenerationProfileCreated(BaseModel):
    generation_profile_sha256: str
    submitter_id: str
    model_revision_key: str
    profile: dict[str, Any]
    created_at: datetime


class CampaignCreate(StrictModel):
    model_revision_key: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    scoring_cohort_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    tier: Literal[1, 2, 3]
    prompt_variant: Literal["canonical", "paraphrase-a", "paraphrase-b"]
    assistance_class: Literal["unassisted", "human-assisted"]
    generation_profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class RobustnessGroupCreate(StrictModel):
    model_revision_key: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    scoring_cohort_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    tier: Literal[1, 2, 3]
    assistance_class: Literal["unassisted", "human-assisted"]
    generation_profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class CampaignCreated(BaseModel):
    campaign_id: str
    robustness_group_id: str | None
    submitter_id: str
    model_key: str
    model_revision_key: str
    tier: Literal[1, 2, 3]
    benchmark_version: str
    prompt_variant: Literal["canonical", "paraphrase-a", "paraphrase-b"]
    assistance_class: Literal["unassisted", "human-assisted"]
    generation_profile_sha256: str
    scoring_cohort_id: str
    scoring_manifest_sha256: str
    grader_source_tree_sha256: str
    environment_attestation_sha256: str
    window_id: str
    opens_at: datetime
    closes_at: datetime
    slot_count: Literal[3] = 3
    occupied_slots: int = 0
    status: Literal["open", "provisional", "closed-incomplete", "completed"]
    slots: list[dict[str, Any]] = Field(default_factory=list)
    public_run_ids: list[str] = Field(default_factory=list)
    official_score: float | None = None
    best_score: float | None = None
    worst_score: float | None = None
    standard_deviation: float | None = None
    verification_scope: Literal["artifact_conformance"] | None = None
    verification_label: Literal["grading-verified artifact score; generation-attested"] | None = (
        None
    )


class RobustnessGroupCreated(BaseModel):
    robustness_group_id: str
    submitter_id: str
    model_key: str
    model_revision_key: str
    tier: Literal[1, 2, 3]
    assistance_class: Literal["unassisted", "human-assisted"]
    generation_profile_sha256: str
    benchmark_version: str
    scoring_cohort_id: str
    scoring_manifest_sha256: str
    grader_source_tree_sha256: str
    environment_attestation_sha256: str
    window_id: str
    opens_at: datetime
    closes_at: datetime
    campaigns: dict[str, str]
    campaign_statuses: dict[str, str]
    status: Literal["open", "provisional", "closed-incomplete", "completed"]
    robustness_score: float | None = None
    cross_variant_mean: float | None = None
    cross_variant_standard_deviation: float | None = None
    verification_scope: Literal["artifact_conformance"] | None = None
    verification_label: Literal["grading-verified artifact score; generation-attested"] | None = (
        None
    )
