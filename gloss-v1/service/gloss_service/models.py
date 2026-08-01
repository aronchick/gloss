"""Persistent hosted-service records."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gloss_service.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> str:
    return str(uuid.uuid4())


class SubmissionStatus(enum.StrEnum):
    QUARANTINING = "quarantining"
    QUEUED = "queued"
    GRADING = "grading"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class OwnerAttribution(enum.StrEnum):
    OWNER_VERIFIED = "owner-verified"
    SUBMITTER_ATTESTED = "submitter-attested"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    monthly_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    malicious_rejections: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    submissions: Mapped[list[Submission]] = relationship(back_populates="organization")
    models: Mapped[list[ModelIdentity]] = relationship(back_populates="organization")
    generation_profiles: Mapped[list[GenerationProfile]] = relationship(
        back_populates="organization"
    )
    campaigns: Mapped[list[Campaign]] = relationship(back_populates="organization")
    robustness_groups: Mapped[list[RobustnessGroup]] = relationship(back_populates="organization")


class ModelIdentity(Base):
    """Server-issued model identity; display text never acts as a grouping key."""

    __tablename__ = "model_identities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    owner_attribution: Mapped[str] = mapped_column(
        String(24), nullable=False, default=OwnerAttribution.SUBMITTER_ATTESTED.value
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="models")
    revisions: Mapped[list[ModelRevision]] = relationship(back_populates="model")


class ModelRevision(Base):
    """Immutable server-issued revision identity with a public revision note."""

    __tablename__ = "model_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    model_id: Mapped[str] = mapped_column(
        ForeignKey("model_identities.id"), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    revision_note: Mapped[str] = mapped_column(Text, nullable=False)
    provider_revision: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    first_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    model: Mapped[ModelIdentity] = relationship(back_populates="revisions")
    campaigns: Mapped[list[Campaign]] = relationship(back_populates="model_revision")
    generation_profiles: Mapped[list[GenerationProfile]] = relationship(
        back_populates="model_revision"
    )


class GenerationProfile(Base):
    """Immutable tenant/revision-scoped RFC 8785 generation configuration."""

    __tablename__ = "generation_profiles"

    generation_profile_sha256: Mapped[str] = mapped_column(String(71), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    model_revision_id: Mapped[str] = mapped_column(
        ForeignKey("model_revisions.id"), nullable=False, index=True
    )
    canonical_profile_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="generation_profiles")
    model_revision: Mapped[ModelRevision] = relationship(back_populates="generation_profiles")


class RobustnessGroup(Base):
    """Parent precommit that atomically owns one campaign for each standard variant."""

    __tablename__ = "robustness_groups"
    __table_args__ = (
        CheckConstraint(
            "assistance_class IN ('unassisted', 'human-assisted')",
            name="ck_robustness_group_assistance_class",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    model_id: Mapped[str] = mapped_column(
        ForeignKey("model_identities.id"), nullable=False, index=True
    )
    model_revision_id: Mapped[str] = mapped_column(
        ForeignKey("model_revisions.id"), nullable=False, index=True
    )
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    benchmark_version: Mapped[str] = mapped_column(String(80), nullable=False)
    scoring_cohort_id: Mapped[str] = mapped_column(String(71), nullable=False, index=True)
    scoring_manifest_sha256: Mapped[str] = mapped_column(String(160), nullable=False)
    grader_source_tree_sha256: Mapped[str] = mapped_column(String(160), nullable=False)
    environment_attestation_sha256: Mapped[str] = mapped_column(String(160), nullable=False)
    assistance_class: Mapped[str] = mapped_column(String(24), nullable=False)
    generation_profile_sha256: Mapped[str] = mapped_column(
        ForeignKey("generation_profiles.generation_profile_sha256"), nullable=False, index=True
    )
    window_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="robustness_groups")
    campaigns: Mapped[list[Campaign]] = relationship(back_populates="robustness_group")


class Campaign(Base):
    """Immutable seven-day, single-tier, single-variant reliability precommit."""

    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint("tier IN (1, 2, 3)", name="ck_campaign_tier"),
        CheckConstraint(
            "assistance_class IN ('unassisted', 'human-assisted')",
            name="ck_campaign_assistance_class",
        ),
        UniqueConstraint("robustness_group_id", "prompt_variant", name="uq_group_prompt_variant"),
        Index(
            "ix_campaign_identity_window",
            "organization_id",
            "model_revision_id",
            "scoring_cohort_id",
            "tier",
            "prompt_variant",
            "assistance_class",
            "generation_profile_sha256",
            "opens_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    model_id: Mapped[str] = mapped_column(
        ForeignKey("model_identities.id"), nullable=False, index=True
    )
    model_revision_id: Mapped[str] = mapped_column(
        ForeignKey("model_revisions.id"), nullable=False, index=True
    )
    robustness_group_id: Mapped[str | None] = mapped_column(
        ForeignKey("robustness_groups.id"), index=True
    )
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    benchmark_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    prompt_variant: Mapped[str] = mapped_column(String(40), nullable=False)
    scoring_cohort_id: Mapped[str] = mapped_column(String(71), nullable=False, index=True)
    scoring_manifest_sha256: Mapped[str] = mapped_column(String(160), nullable=False)
    grader_source_tree_sha256: Mapped[str] = mapped_column(String(160), nullable=False)
    environment_attestation_sha256: Mapped[str] = mapped_column(String(160), nullable=False)
    assistance_class: Mapped[str] = mapped_column(String(24), nullable=False)
    generation_profile_sha256: Mapped[str] = mapped_column(
        ForeignKey("generation_profiles.generation_profile_sha256"), nullable=False, index=True
    )
    window_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="campaigns")
    model: Mapped[ModelIdentity] = relationship()
    model_revision: Mapped[ModelRevision] = relationship(back_populates="campaigns")
    robustness_group: Mapped[RobustnessGroup | None] = relationship(back_populates="campaigns")
    submissions: Mapped[list[Submission]] = relationship(back_populates="campaign")


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        Index("ix_submissions_queue", "status", "created_at"),
        Index("ix_submissions_campaign_state", "campaign_id", "status", "created_at"),
        UniqueConstraint("campaign_id", "campaign_slot", name="uq_campaign_slot"),
        CheckConstraint(
            "campaign_slot IS NULL OR campaign_slot IN (1, 2, 3)",
            name="ck_submission_campaign_slot",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    model_id: Mapped[str] = mapped_column(
        ForeignKey("model_identities.id"), nullable=False, index=True
    )
    model_revision_id: Mapped[str] = mapped_column(
        ForeignKey("model_revisions.id"), nullable=False, index=True
    )
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False, index=True)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    benchmark_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    prompt_variant: Mapped[str] = mapped_column(String(40), nullable=False, default="canonical")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=SubmissionStatus.QUEUED)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_object_version: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    resolved_file_path: Mapped[str | None] = mapped_column(Text)
    resolved_file_sha256: Mapped[str | None] = mapped_column(String(64))
    resolved_file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    resolved_object_version: Mapped[str | None] = mapped_column(String(80), unique=True)
    run_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="submission")
    control_authorization_sha256: Mapped[str | None] = mapped_column(String(71))
    control_authorization_object_version: Mapped[str | None] = mapped_column(String(80))
    canonical_package_hash_profile_sha256: Mapped[str | None] = mapped_column(String(71))
    canonical_package_hash_v1: Mapped[str | None] = mapped_column(String(71))
    gold_duplicate_check_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    schema_validation_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    quarantine_envelope_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    quarantine_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quarantine_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quarantine_worker_id: Mapped[str | None] = mapped_column(String(160))
    quarantine_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    efficiency_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    attestation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    generation_seed: Mapped[str | None] = mapped_column(String(256))
    webhook_url: Mapped[str | None] = mapped_column(Text)
    webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    report_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    error_retryable: Mapped[bool | None] = mapped_column(Boolean)
    fidelity_score: Mapped[float | None] = mapped_column(Float)
    campaign_score: Mapped[float | None] = mapped_column(Float)
    campaign_slot: Mapped[int | None] = mapped_column(Integer)
    eligible: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    grading_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grading_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(160))
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    organization: Mapped[Organization] = relationship(back_populates="submissions")
    campaign: Mapped[Campaign] = relationship(back_populates="submissions")
    model: Mapped[ModelIdentity] = relationship()
    model_revision: Mapped[ModelRevision] = relationship()
    run: Mapped[RunRecord | None] = relationship(back_populates="submission", uselist=False)
    verdict_uses: Mapped[list[QuarantineVerdictUse]] = relationship(back_populates="submission")


class QuarantineVerdictUse(Base):
    """CAS lifecycle for one signed quarantine verdict."""

    __tablename__ = "quarantine_verdict_uses"
    verdict_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("submissions.id"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="issued")
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_id: Mapped[str | None] = mapped_column(String(160))
    lease_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    submission: Mapped[Submission] = relationship(back_populates="verdict_uses")


class RunRecord(Base):
    """Immutable grading provenance written exactly once by a worker."""

    __tablename__ = "run_records"
    __table_args__ = (UniqueConstraint("submission_id", name="uq_run_submission"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), nullable=False)
    benchmark_version: Mapped[str] = mapped_column(String(80), nullable=False)
    grader_version: Mapped[str] = mapped_column(String(80), nullable=False)
    libreoffice_version: Mapped[str] = mapped_column(String(160), nullable=False)
    docker_image_hash: Mapped[str] = mapped_column(String(160), nullable=False)
    font_bundle_hash: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_manifest_hash: Mapped[str] = mapped_column(String(160), nullable=False)
    environment_hash: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    scoring_cohort_id: Mapped[str] = mapped_column(String(71), nullable=False, index=True)
    scoring_manifest_sha256: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    grader_source_tree_sha256: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    environment_attestation_sha256: Mapped[str] = mapped_column(
        String(160), nullable=False, index=True
    )
    verification_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    verification_label: Mapped[str] = mapped_column(String(80), nullable=False)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    report_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    report_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    grading_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    grading_completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    submission: Mapped[Submission] = relationship(back_populates="run")
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="run")


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("run_id", "name", name="uq_artifact_run_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("run_records.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    run: Mapped[RunRecord] = relationship(back_populates="artifacts")


class LeaderboardSnapshot(Base):
    __tablename__ = "leaderboard_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    benchmark_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"))
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(160), nullable=False)
    process_id: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class DriftCanaryAuthorizationUse(Base):
    """Single-use maintainer authorization consumed before a canary executes."""

    __tablename__ = "drift_canary_authorization_uses"

    authorization_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nonce_sha256: Mapped[str] = mapped_column(String(71), nullable=False, unique=True)
    canary_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    targeted_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    authorization_sha256: Mapped[str] = mapped_column(String(71), nullable=False, unique=True)
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DriftCanaryRun(Base):
    """Immutable, self-hashed evidence from one three-tier drift-canary batch."""

    __tablename__ = "drift_canary_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pass', 'drift', 'error')",
            name="ck_drift_canary_status",
        ),
        Index(
            "ix_drift_canary_cohort_completed",
            "scoring_cohort_id",
            "completed_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    benchmark_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    scoring_cohort_id: Mapped[str] = mapped_column(String(71), nullable=False, index=True)
    scoring_manifest_sha256: Mapped[str] = mapped_column(String(71), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(71), nullable=False, unique=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


def _reject_immutable_record_mutation(_mapper: object, _connection: object, target: object) -> None:
    raise RuntimeError(f"{type(target).__name__} records are immutable")


for immutable_record in (
    Campaign,
    DriftCanaryAuthorizationUse,
    DriftCanaryRun,
    GenerationProfile,
    RobustnessGroup,
    RunRecord,
):
    event.listen(immutable_record, "before_update", _reject_immutable_record_mutation)
    event.listen(immutable_record, "before_delete", _reject_immutable_record_mutation)
