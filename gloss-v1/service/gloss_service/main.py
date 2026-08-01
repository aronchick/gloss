"""FastAPI application for submissions and the public Gloss leaderboard."""

from __future__ import annotations

import hashlib
import html
import json
import logging
import statistics
import time
import uuid
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

import rfc8785
import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jsonschema import Draft202012Validator
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, joinedload, sessionmaker
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.trustedhost import TrustedHostMiddleware

from gloss_service.canary import drift_canary_health
from gloss_service.config import Settings, get_settings
from gloss_service.database import Base, SessionLocal, engine, get_session
from gloss_service.leaderboard import build_leaderboard, build_run_ledger
from gloss_service.models import (
    Artifact,
    Campaign,
    GenerationProfile,
    LeaderboardSnapshot,
    ModelIdentity,
    ModelRevision,
    Organization,
    RobustnessGroup,
    Submission,
    SubmissionStatus,
    WorkerHeartbeat,
)
from gloss_service.schemas import (
    CampaignCreate,
    CampaignCreated,
    GenerationProfileCreate,
    GenerationProfileCreated,
    ModelCreate,
    ModelCreated,
    ModelRevisionCreate,
    ModelRevisionCreated,
    OrganizationCreate,
    OrganizationCreated,
    OrganizationUpdate,
    PublishReportResponse,
    RobustnessGroupCreate,
    RobustnessGroupCreated,
    SubmissionAccepted,
    SubmissionMetadata,
    SubmissionStatusResponse,
)
from gloss_service.security import (
    authenticate_api_key,
    encrypt_secret,
    issue_api_key,
    require_admin,
    require_organization,
)
from gloss_service.service import (
    VERIFICATION_LABEL,
    VERIFICATION_SCOPE,
    check_submission_limits,
    estimated_wait_seconds,
    scoring_cohort_id,
    status_payload,
)
from gloss_service.storage import (
    InvalidUploadError,
    UploadTimeoutError,
    UploadTooLargeError,
    delete_upload,
    ensure_storage,
    store_upload,
)
from gloss_service.webhooks import UnsafeWebhookURLError, validate_webhook_url

logger = logging.getLogger("gloss.service")
REQUESTS = Counter(
    "gloss_http_requests_total",
    "HTTP requests",
    ("method", "route", "status"),
)
REQUEST_SECONDS = Histogram(
    "gloss_http_request_duration_seconds",
    "HTTP request duration",
    ("method", "route"),
)
SUBMISSIONS = Counter(
    "gloss_submissions_total",
    "Submission ingestion outcomes",
    ("outcome",),
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            },
            separators=(",", ":"),
        )


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.handlers = [handler]
    logger.setLevel(settings.log_level.upper())
    logger.propagate = False


def _report_html(submission: Submission) -> str:
    assert submission.run is not None
    report = submission.run.report_json
    reported_score = report["fidelity_score"]
    score_text = "No score" if reported_score is None else f"{float(reported_score):.4f}"
    report_json = html.escape(json.dumps(report, indent=2, sort_keys=True))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Gloss report · {html.escape(submission.id)}</title>
<style>
body{{font:16px/1.55 system-ui;max-width:72rem;margin:4rem auto;padding:0 1.5rem;
color:#10262d}}
header{{border-bottom:3px solid #ef6045;padding-bottom:2rem}}.score{{font:700 4rem/1 monospace}}
pre{{overflow:auto;background:#edf3f3;padding:1.25rem;border-left:4px solid #1d697d}}</style></head>
    <body><header><p>{html.escape(submission.run.verification_label)} ·
    {html.escape(submission.benchmark_version)}</p>
    <h1>{html.escape(submission.model.display_name)}
    <small>{html.escape(submission.model_revision.display_name)}</small></h1>
<p class="score">{score_text}</p>
<p>Environment {html.escape(submission.run.environment_hash)}</p></header>
<main><h2>Machine-readable report</h2><pre>{report_json}</pre></main></body></html>"""


def _request_api_key(request: Request) -> str | None:
    value = request.headers.get("X-API-Key")
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        value = authorization[7:].strip()
    return value


def _cohort_id(settings: Settings) -> str:
    return scoring_cohort_id(
        settings.active_scoring_manifest_sha256,
        settings.active_grader_source_tree_sha256,
        settings.active_environment_attestation_sha256,
    )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def create_app(
    settings_override: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    runtime_settings = settings_override or get_settings()
    runtime_sessions = session_factory or SessionLocal
    configure_logging(runtime_settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        bind = runtime_sessions.kw.get("bind", engine)
        if runtime_settings.app_env != "production":
            Base.metadata.create_all(bind=bind)
        ensure_storage(runtime_settings)
        yield

    app = FastAPI(
        title="Gloss hosted service",
        version="1.0.0",
        description=(
            "Supporting measurement service for Gloss — the Generative Layout & "
            "Object Structure Standard presentation challenge. Provides controlled "
            "grading and a public grading-verified leaderboard."
        ),
        docs_url="/v1/docs",
        redoc_url="/v1/redoc",
        openapi_url="/v1/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings

    def runtime_get_settings() -> Settings:
        return runtime_settings

    def runtime_get_session() -> Generator[Session, None, None]:
        with runtime_sessions() as session:
            yield session

    app.dependency_overrides[get_settings] = runtime_get_settings
    app.dependency_overrides[get_session] = runtime_get_session

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=runtime_settings.trusted_hosts)
    if runtime_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=runtime_settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Admin-Key"],
        )

    @app.middleware("http")
    async def observe_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:64]
        request.state.request_id = request_id
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled request error request_id=%s path=%s", request_id, request.url.path
            )
            raise
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        duration = time.monotonic() - started
        REQUESTS.labels(request.method, route_path, str(response.status_code)).inc()
        REQUEST_SECONDS.labels(request.method, route_path).observe(duration)
        response.headers.update(
            {
                "X-Request-ID": request_id,
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
                    "base-uri 'none'; form-action 'self'"
                ),
            }
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": exc.errors(),
                }
            },
        )

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def homepage() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/health/live", tags=["operations"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    def require_current_canary(session: Session) -> None:
        if runtime_settings.app_env != "production":
            return
        canary = drift_canary_health(session, runtime_settings)
        if not canary.ready:
            raise HTTPException(status_code=503, detail=canary.detail())

    @app.get("/health/ready", tags=["operations"])
    def ready(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
        session.execute(text("SELECT 1"))
        if runtime_settings.app_env == "production":
            cutoff = datetime.now(UTC) - timedelta(
                seconds=runtime_settings.worker_heartbeat_seconds * 2
            )
            missing = [
                role
                for role in ("grading", "quarantine")
                if session.scalar(
                    select(func.count(WorkerHeartbeat.worker_id)).where(
                        WorkerHeartbeat.worker_id.like(f"{role}:%"),
                        WorkerHeartbeat.last_seen_at >= cutoff,
                    )
                )
                == 0
            ]
            if missing:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "worker_unavailable",
                        "message": "Required worker heartbeat is missing: " + ", ".join(missing),
                    },
                )
            require_current_canary(session)
        return {"status": "ready"}

    @app.get("/metrics", include_in_schema=False)
    def metrics(
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        token = runtime_settings.metrics_bearer_token
        if token and authorization != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="Metrics token required")
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/v1/versions", tags=["benchmark"])
    def versions() -> dict[str, Any]:
        return {
            "active": runtime_settings.active_benchmark_versions,
            "frozen": runtime_settings.frozen_benchmark_versions,
            "active_scoring_cohort_id": _cohort_id(runtime_settings),
            "scoring_manifest_sha256": runtime_settings.active_scoring_manifest_sha256,
            "grader_source_tree_sha256": runtime_settings.active_grader_source_tree_sha256,
            "environment_attestation_sha256": (
                runtime_settings.active_environment_attestation_sha256
            ),
        }

    def owned_revision(
        revision_key: str, organization: Organization, session: Session
    ) -> ModelRevision:
        revision = session.scalar(
            select(ModelRevision)
            .join(ModelIdentity)
            .where(
                ModelRevision.id == revision_key,
                ModelIdentity.organization_id == organization.id,
            )
        )
        if revision is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "Model revision not found."},
            )
        return revision

    def ensure_campaign_available(
        revision: ModelRevision,
        organization: Organization,
        session: Session,
        *,
        tier: int,
        benchmark_version: str,
        prompt_variants: list[str],
        assistance_class: str,
        generation_profile_sha256: str,
        now: datetime,
    ) -> None:
        if session.bind and session.bind.dialect.name == "postgresql":
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:campaign_identity))"),
                {"campaign_identity": f"{revision.id}:{benchmark_version}:{tier}"},
            )
        cohort = _cohort_id(runtime_settings)
        conflict = session.scalar(
            select(Campaign.id)
            .where(
                Campaign.organization_id == organization.id,
                Campaign.model_revision_id == revision.id,
                Campaign.scoring_cohort_id == cohort,
                Campaign.tier == tier,
                Campaign.prompt_variant.in_(prompt_variants),
                Campaign.assistance_class == assistance_class,
                Campaign.generation_profile_sha256 == generation_profile_sha256,
                Campaign.closes_at > now,
            )
            .limit(1)
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "campaign_window_exists",
                    "message": (
                        "An active seven-day campaign already exists for this immutable "
                        "revision, cohort, tier, and prompt variant."
                    ),
                },
            )

    def new_campaign(
        revision: ModelRevision,
        organization: Organization,
        *,
        tier: int,
        benchmark_version: str,
        prompt_variant: str,
        opens_at: datetime,
        closes_at: datetime,
        window_id: str,
        assistance_class: str,
        generation_profile_sha256: str,
        robustness_group_id: str | None = None,
    ) -> Campaign:
        return Campaign(
            organization_id=organization.id,
            model_id=revision.model_id,
            model_revision_id=revision.id,
            robustness_group_id=robustness_group_id,
            tier=tier,
            benchmark_version=benchmark_version,
            prompt_variant=prompt_variant,
            scoring_cohort_id=_cohort_id(runtime_settings),
            scoring_manifest_sha256=runtime_settings.active_scoring_manifest_sha256,
            grader_source_tree_sha256=runtime_settings.active_grader_source_tree_sha256,
            environment_attestation_sha256=(runtime_settings.active_environment_attestation_sha256),
            assistance_class=assistance_class,
            generation_profile_sha256=generation_profile_sha256,
            window_id=window_id,
            opens_at=opens_at,
            closes_at=closes_at,
        )

    def campaign_response(
        campaign: Campaign, *, include_private_slots: bool = True
    ) -> CampaignCreated:
        completed = sorted(
            (
                submission
                for submission in campaign.submissions
                if submission.run is not None and submission.campaign_slot is not None
            ),
            key=lambda submission: submission.campaign_slot or 0,
        )
        reserved = sorted(
            (
                submission
                for submission in campaign.submissions
                if submission.campaign_slot is not None
            ),
            key=lambda submission: submission.campaign_slot or 0,
        )
        scores = [float(submission.campaign_score or 0.0) for submission in completed]
        now = datetime.now(UTC)
        complete = len(completed) == 3
        if complete:
            campaign_status = "completed"
        elif _as_utc(campaign.closes_at) <= now:
            campaign_status = "closed-incomplete"
        elif completed:
            campaign_status = "provisional"
        else:
            campaign_status = "open"
        visible_slots = reserved if include_private_slots else completed
        return CampaignCreated(
            campaign_id=campaign.id,
            robustness_group_id=campaign.robustness_group_id,
            submitter_id=campaign.organization_id,
            model_key=campaign.model_id,
            model_revision_key=campaign.model_revision_id,
            tier=campaign.tier,
            benchmark_version=campaign.benchmark_version,
            prompt_variant=campaign.prompt_variant,
            assistance_class=campaign.assistance_class,
            generation_profile_sha256=campaign.generation_profile_sha256,
            scoring_cohort_id=campaign.scoring_cohort_id,
            scoring_manifest_sha256=campaign.scoring_manifest_sha256,
            grader_source_tree_sha256=campaign.grader_source_tree_sha256,
            environment_attestation_sha256=campaign.environment_attestation_sha256,
            window_id=campaign.window_id,
            opens_at=campaign.opens_at,
            closes_at=campaign.closes_at,
            occupied_slots=len(completed),
            status=campaign_status,
            slots=[
                {
                    "campaign_slot": submission.campaign_slot,
                    "submission_id": submission.id,
                    "status": submission.status,
                    "run_id": submission.run.id if submission.run else None,
                    "campaign_score": submission.campaign_score,
                }
                for submission in visible_slots
            ],
            public_run_ids=[submission.run.id for submission in completed if submission.run],
            official_score=statistics.fmean(scores) if complete else None,
            best_score=max(scores) if complete else None,
            worst_score=min(scores) if complete else None,
            standard_deviation=statistics.pstdev(scores) if complete else None,
            verification_scope=VERIFICATION_SCOPE if complete else None,
            verification_label=VERIFICATION_LABEL if complete else None,
        )

    @app.post(
        "/v1/models",
        response_model=ModelCreated,
        status_code=201,
        tags=["identity"],
    )
    def create_model_identity(
        body: ModelCreate,
        organization: Annotated[Organization, Depends(require_organization)],
        session: Annotated[Session, Depends(get_session)],
    ) -> ModelCreated:
        model = ModelIdentity(
            organization_id=organization.id,
            display_name=body.display_name,
            owner_attribution=body.owner_attribution,
        )
        session.add(model)
        session.commit()
        return ModelCreated(
            model_key=model.id,
            submitter_id=organization.id,
            display_name=model.display_name,
            owner_attribution=model.owner_attribution,
            created_at=model.created_at,
        )

    @app.post(
        "/v1/models/{model_key}/revisions",
        response_model=ModelRevisionCreated,
        status_code=201,
        tags=["identity"],
    )
    def create_model_revision(
        model_key: str,
        body: ModelRevisionCreate,
        organization: Annotated[Organization, Depends(require_organization)],
        session: Annotated[Session, Depends(get_session)],
    ) -> ModelRevisionCreated:
        model = session.scalar(
            select(ModelIdentity).where(
                ModelIdentity.id == model_key,
                ModelIdentity.organization_id == organization.id,
            )
        )
        if model is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "Model identity not found."},
            )
        revision = ModelRevision(
            model_id=model.id,
            display_name=body.display_version,
            revision_note=body.revision_note,
            provider_revision=body.provider_revision,
        )
        session.add(revision)
        session.commit()
        return ModelRevisionCreated(
            model_key=model.id,
            model_revision_key=revision.id,
            display_version=revision.display_name,
            revision_note=revision.revision_note,
            created_at=revision.created_at,
        )

    def load_generation_profile_schema() -> dict[str, Any]:
        configured = runtime_settings.generation_profile_schema_path
        candidates = [
            configured,
            Path.cwd() / configured,
            Path(__file__).resolve().parents[2] / "schemas" / "generation-profile.schema.json",
            Path("/opt/gloss/schemas/generation-profile.schema.json"),
        ]
        for candidate in candidates:
            if candidate.is_file():
                value = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    return value
        raise HTTPException(
            status_code=503,
            detail={
                "code": "generation_profile_schema_unavailable",
                "message": "The immutable generation-profile schema is unavailable.",
            },
        )

    def require_generation_profile(
        digest: str,
        revision: ModelRevision,
        organization: Organization,
        session: Session,
    ) -> GenerationProfile:
        profile = session.scalar(
            select(GenerationProfile).where(
                GenerationProfile.generation_profile_sha256 == digest,
                GenerationProfile.organization_id == organization.id,
                GenerationProfile.model_revision_id == revision.id,
            )
        )
        if profile is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_generation_profile",
                    "message": (
                        "Generation profile is unknown or not registered for this "
                        "submitter and model revision."
                    ),
                },
            )
        return profile

    @app.post(
        "/v1/generation-profiles",
        response_model=GenerationProfileCreated,
        status_code=201,
        tags=["identity"],
    )
    def create_generation_profile(
        body: GenerationProfileCreate,
        organization: Annotated[Organization, Depends(require_organization)],
        session: Annotated[Session, Depends(get_session)],
    ) -> GenerationProfileCreated:
        revision = owned_revision(body.model_revision_key, organization, session)
        validator = Draft202012Validator(load_generation_profile_schema())
        errors = sorted(validator.iter_errors(body.profile), key=lambda error: list(error.path))
        if errors:
            first = errors[0]
            location = ".".join(str(part) for part in first.absolute_path) or "profile"
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_generation_profile",
                    "message": f"Generation profile {location}: {first.message}",
                },
            )
        try:
            canonical_bytes = rfc8785.dumps(body.profile)
        except (rfc8785.CanonicalizationError, rfc8785.FloatDomainError) as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_generation_profile",
                    "message": "Generation profile is not RFC 8785 canonicalizable.",
                },
            ) from exc
        digest = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
        canonical_profile = json.loads(canonical_bytes)
        existing = session.get(GenerationProfile, digest)
        if existing is not None:
            if (
                existing.organization_id != organization.id
                or existing.model_revision_id != revision.id
                or existing.canonical_profile_json != canonical_profile
            ):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "generation_profile_scope_conflict",
                        "message": "Generation-profile digest is already bound to another scope.",
                    },
                )
            profile = existing
        else:
            profile = GenerationProfile(
                generation_profile_sha256=digest,
                organization_id=organization.id,
                model_revision_id=revision.id,
                canonical_profile_json=canonical_profile,
            )
            session.add(profile)
            session.commit()
        return GenerationProfileCreated(
            generation_profile_sha256=profile.generation_profile_sha256,
            submitter_id=profile.organization_id,
            model_revision_key=profile.model_revision_id,
            profile=profile.canonical_profile_json,
            created_at=_as_utc(profile.created_at),
        )

    @app.post(
        "/v1/campaigns",
        response_model=CampaignCreated,
        status_code=201,
        tags=["campaigns"],
    )
    def create_campaign(
        body: CampaignCreate,
        organization: Annotated[Organization, Depends(require_organization)],
        session: Annotated[Session, Depends(get_session)],
    ) -> CampaignCreated:
        active_cohort = _cohort_id(runtime_settings)
        if body.scoring_cohort_id != active_cohort:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_scoring_cohort",
                    "message": "The requested scoring cohort is not active.",
                    "active_scoring_cohort_id": active_cohort,
                },
            )
        if body.prompt_variant not in runtime_settings.required_prompt_variants:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_prompt_variant", "message": "Unknown prompt variant."},
            )
        revision = owned_revision(body.model_revision_key, organization, session)
        profile = require_generation_profile(
            body.generation_profile_sha256, revision, organization, session
        )
        permissions = profile.canonical_profile_json.get("permissions", {})
        if body.assistance_class == "unassisted" and permissions.get(
            "human_intervention_permitted"
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_assistance_class",
                    "message": "Unassisted campaigns require a profile that forbids intervention.",
                },
            )
        now = datetime.now(UTC)
        benchmark_version = runtime_settings.active_benchmark_versions[0]
        window_id = str(uuid.uuid4())
        ensure_campaign_available(
            revision,
            organization,
            session,
            tier=body.tier,
            benchmark_version=benchmark_version,
            prompt_variants=[body.prompt_variant],
            assistance_class=body.assistance_class,
            generation_profile_sha256=body.generation_profile_sha256,
            now=now,
        )
        campaign = new_campaign(
            revision,
            organization,
            tier=body.tier,
            benchmark_version=benchmark_version,
            prompt_variant=body.prompt_variant,
            opens_at=now,
            closes_at=now + timedelta(days=runtime_settings.tuple_window_days),
            window_id=window_id,
            assistance_class=body.assistance_class,
            generation_profile_sha256=body.generation_profile_sha256,
        )
        session.add(campaign)
        session.commit()
        return campaign_response(campaign)

    @app.get(
        "/v1/campaigns/{campaign_id}",
        response_model=CampaignCreated,
        tags=["campaigns"],
    )
    def get_campaign(
        campaign_id: str,
        request: Request,
        session: Annotated[Session, Depends(get_session)],
    ) -> CampaignCreated:
        campaign = (
            session.execute(
                select(Campaign)
                .options(joinedload(Campaign.submissions).joinedload(Submission.run))
                .where(
                    Campaign.id == campaign_id,
                )
            )
            .unique()
            .scalar_one_or_none()
        )
        if campaign is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "Campaign not found."},
            )
        key = _request_api_key(request)
        organization = authenticate_api_key(key, session, runtime_settings) if key else None
        return campaign_response(
            campaign,
            include_private_slots=(
                organization is not None and organization.id == campaign.organization_id
            ),
        )

    @app.post(
        "/v1/robustness-groups",
        response_model=RobustnessGroupCreated,
        status_code=201,
        tags=["campaigns"],
    )
    def create_robustness_group(
        body: RobustnessGroupCreate,
        organization: Annotated[Organization, Depends(require_organization)],
        session: Annotated[Session, Depends(get_session)],
    ) -> RobustnessGroupCreated:
        active_cohort = _cohort_id(runtime_settings)
        if body.scoring_cohort_id != active_cohort:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_scoring_cohort",
                    "message": "The requested scoring cohort is not active.",
                    "active_scoring_cohort_id": active_cohort,
                },
            )
        variants = runtime_settings.required_prompt_variants
        if len(variants) != 3 or len(set(variants)) != 3:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "invalid_robustness_profile",
                    "message": "The active release must define exactly three unique variants.",
                },
            )
        revision = owned_revision(body.model_revision_key, organization, session)
        profile = require_generation_profile(
            body.generation_profile_sha256, revision, organization, session
        )
        permissions = profile.canonical_profile_json.get("permissions", {})
        if body.assistance_class == "unassisted" and permissions.get(
            "human_intervention_permitted"
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_assistance_class",
                    "message": "Unassisted campaigns require a profile that forbids intervention.",
                },
            )
        now = datetime.now(UTC)
        closes_at = now + timedelta(days=runtime_settings.tuple_window_days)
        benchmark_version = runtime_settings.active_benchmark_versions[0]
        window_id = str(uuid.uuid4())
        ensure_campaign_available(
            revision,
            organization,
            session,
            tier=body.tier,
            benchmark_version=benchmark_version,
            prompt_variants=variants,
            assistance_class=body.assistance_class,
            generation_profile_sha256=body.generation_profile_sha256,
            now=now,
        )
        group = RobustnessGroup(
            organization_id=organization.id,
            model_id=revision.model_id,
            model_revision_id=revision.id,
            tier=body.tier,
            benchmark_version=benchmark_version,
            scoring_cohort_id=active_cohort,
            scoring_manifest_sha256=runtime_settings.active_scoring_manifest_sha256,
            grader_source_tree_sha256=runtime_settings.active_grader_source_tree_sha256,
            environment_attestation_sha256=(runtime_settings.active_environment_attestation_sha256),
            assistance_class=body.assistance_class,
            generation_profile_sha256=body.generation_profile_sha256,
            window_id=window_id,
            opens_at=now,
            closes_at=closes_at,
        )
        session.add(group)
        session.flush()
        campaigns = [
            new_campaign(
                revision,
                organization,
                tier=body.tier,
                benchmark_version=benchmark_version,
                prompt_variant=variant,
                opens_at=now,
                closes_at=closes_at,
                window_id=window_id,
                assistance_class=body.assistance_class,
                generation_profile_sha256=body.generation_profile_sha256,
                robustness_group_id=group.id,
            )
            for variant in variants
        ]
        session.add_all(campaigns)
        session.commit()
        return RobustnessGroupCreated(
            robustness_group_id=group.id,
            submitter_id=organization.id,
            model_key=revision.model_id,
            model_revision_key=revision.id,
            tier=body.tier,
            assistance_class=group.assistance_class,
            generation_profile_sha256=group.generation_profile_sha256,
            benchmark_version=benchmark_version,
            scoring_cohort_id=group.scoring_cohort_id,
            scoring_manifest_sha256=group.scoring_manifest_sha256,
            grader_source_tree_sha256=group.grader_source_tree_sha256,
            environment_attestation_sha256=group.environment_attestation_sha256,
            window_id=group.window_id,
            opens_at=group.opens_at,
            closes_at=group.closes_at,
            campaigns={campaign.prompt_variant: campaign.id for campaign in campaigns},
            campaign_statuses={campaign.prompt_variant: "open" for campaign in campaigns},
            status="open",
        )

    @app.get(
        "/v1/robustness-groups/{robustness_group_id}",
        response_model=RobustnessGroupCreated,
        tags=["campaigns"],
    )
    def get_robustness_group(
        robustness_group_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> RobustnessGroupCreated:
        group = (
            session.execute(
                select(RobustnessGroup)
                .options(
                    joinedload(RobustnessGroup.campaigns)
                    .joinedload(Campaign.submissions)
                    .joinedload(Submission.run)
                )
                .where(
                    RobustnessGroup.id == robustness_group_id,
                )
            )
            .unique()
            .scalar_one_or_none()
        )
        if group is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "Robustness group not found."},
            )
        child_responses = [campaign_response(campaign) for campaign in group.campaigns]
        means = [
            child.official_score for child in child_responses if child.official_score is not None
        ]
        complete = len(child_responses) == 3 and len(means) == 3
        if complete:
            group_status = "completed"
        elif _as_utc(group.closes_at) <= datetime.now(UTC):
            group_status = "closed-incomplete"
        elif any(child.occupied_slots for child in child_responses):
            group_status = "provisional"
        else:
            group_status = "open"
        return RobustnessGroupCreated(
            robustness_group_id=group.id,
            submitter_id=group.organization_id,
            model_key=group.model_id,
            model_revision_key=group.model_revision_id,
            tier=group.tier,
            assistance_class=group.assistance_class,
            generation_profile_sha256=group.generation_profile_sha256,
            benchmark_version=group.benchmark_version,
            scoring_cohort_id=group.scoring_cohort_id,
            scoring_manifest_sha256=group.scoring_manifest_sha256,
            grader_source_tree_sha256=group.grader_source_tree_sha256,
            environment_attestation_sha256=group.environment_attestation_sha256,
            window_id=group.window_id,
            opens_at=group.opens_at,
            closes_at=group.closes_at,
            campaigns={campaign.prompt_variant: campaign.id for campaign in group.campaigns},
            campaign_statuses={child.prompt_variant: child.status for child in child_responses},
            status=group_status,
            robustness_score=min(means) if complete else None,
            cross_variant_mean=statistics.fmean(means) if complete else None,
            cross_variant_standard_deviation=(statistics.pstdev(means) if complete else None),
            verification_scope=VERIFICATION_SCOPE if complete else None,
            verification_label=VERIFICATION_LABEL if complete else None,
        )

    @app.post(
        "/v1/submissions",
        response_model=SubmissionAccepted,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["submissions"],
    )
    async def create_submission(
        request: Request,
        organization: Annotated[Organization, Depends(require_organization)],
        session: Annotated[Session, Depends(get_session)],
        metadata: Annotated[str, Form(description="JSON matching SubmissionMetadata")],
        file: Annotated[UploadFile, File(description="A .pptx deck, at most 100 MB")],
    ) -> SubmissionAccepted:
        require_current_canary(session)
        content_length = request.headers.get("content-length")
        if (
            content_length
            and content_length.isdigit()
            and int(content_length) > runtime_settings.max_upload_bytes + 1_000_000
        ):
            raise HTTPException(
                status_code=413,
                detail={"code": "file_too_large", "message": "Upload exceeds 100 MB."},
            )
        try:
            submission_metadata = SubmissionMetadata.model_validate_json(metadata)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_metadata",
                    "message": "Submission metadata is invalid.",
                    "details": exc.errors(include_context=False),
                },
            ) from exc
        campaign = session.scalar(
            select(Campaign)
            .options(joinedload(Campaign.model_revision))
            .where(
                Campaign.id == submission_metadata.campaign_id,
                Campaign.organization_id == organization.id,
            )
            .with_for_update()
        )
        if campaign is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "campaign_not_found",
                    "message": "Campaign not found for this submitter.",
                },
            )
        if campaign.benchmark_version not in runtime_settings.active_benchmark_versions:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_benchmark_version",
                    "message": "The campaign benchmark version is no longer active.",
                    "active_benchmark_versions": runtime_settings.active_benchmark_versions,
                },
            )
        if submission_metadata.webhook_url:
            try:
                validate_webhook_url(str(submission_metadata.webhook_url))
            except UnsafeWebhookURLError as exc:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "invalid_webhook_url", "message": str(exc)},
                ) from exc

        violation = check_submission_limits(
            session,
            organization,
            campaign=campaign,
            settings=runtime_settings,
        )
        if violation:
            SUBMISSIONS.labels("rate_limited").inc()
            raise HTTPException(
                status_code=429,
                detail={"code": "rate_limited", "message": violation.message, "retryable": True},
                headers={"Retry-After": str(violation.retry_after)},
            )

        reserved_slots = set(
            session.scalars(
                select(Submission.campaign_slot).where(
                    Submission.campaign_id == campaign.id,
                    Submission.campaign_slot.is_not(None),
                )
            )
        )
        campaign_slot = next((slot for slot in (1, 2, 3) if slot not in reserved_slots), None)
        if campaign_slot is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "campaign_full",
                    "message": "All three campaign slots are already reserved or occupied.",
                },
            )

        submission_id = str(uuid.uuid4())
        try:
            stored = await store_upload(file, submission_id, runtime_settings)
        except UploadTooLargeError as exc:
            SUBMISSIONS.labels("too_large").inc()
            raise HTTPException(
                status_code=413,
                detail={"code": "file_too_large", "message": str(exc)},
            ) from exc
        except UploadTimeoutError as exc:
            raise HTTPException(
                status_code=408,
                detail={"code": "upload_timeout", "message": str(exc), "retryable": True},
            ) from exc
        except InvalidUploadError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_upload", "message": str(exc), "retryable": False},
            ) from exc

        row = Submission(
            id=submission_id,
            organization_id=organization.id,
            model_id=campaign.model_id,
            model_revision_id=campaign.model_revision_id,
            campaign_id=campaign.id,
            campaign_slot=campaign_slot,
            tier=campaign.tier,
            benchmark_version=campaign.benchmark_version,
            prompt_variant=campaign.prompt_variant,
            status=SubmissionStatus.QUARANTINING.value,
            file_name=(file.filename or "submission.pptx")[:255],
            file_path=str(stored.path),
            file_sha256=stored.sha256,
            file_size_bytes=stored.size,
            original_object_version=stored.object_version,
            generation_seed=submission_metadata.generation_seed,
            efficiency_metrics=submission_metadata.efficiency_metrics.model_dump(
                mode="json", exclude_none=True
            ),
            attestation=submission_metadata.attestation.model_dump(mode="json", exclude_none=True),
            webhook_url=str(submission_metadata.webhook_url)
            if submission_metadata.webhook_url
            else None,
            webhook_secret_encrypted=(
                encrypt_secret(submission_metadata.webhook_secret, runtime_settings)
                if submission_metadata.webhook_secret
                else None
            ),
        )
        if campaign.model_revision.first_submitted_at is None:
            campaign.model_revision.first_submitted_at = datetime.now(UTC)
        session.add(row)
        try:
            session.commit()
        except Exception:
            session.rollback()
            delete_upload(stored.path)
            raise
        wait = estimated_wait_seconds(session, runtime_settings)
        SUBMISSIONS.labels("quarantining").inc()
        return SubmissionAccepted(
            submission_id=submission_id,
            campaign_id=campaign.id,
            campaign_slot=campaign_slot,
            status="quarantining",
            estimated_wait_seconds=wait,
            status_url=f"/v1/submissions/{submission_id}",
        )

    @app.get(
        "/v1/submissions/{submission_id}",
        response_model=SubmissionStatusResponse,
        tags=["submissions"],
    )
    def get_submission_status(
        submission_id: str,
        organization: Annotated[Organization, Depends(require_organization)],
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, Any]:
        submission = session.scalar(
            select(Submission)
            .options(joinedload(Submission.run))
            .where(Submission.id == submission_id, Submission.organization_id == organization.id)
        )
        if submission is None:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": "Submission not found."}
            )
        return status_payload(submission)

    @app.get("/v1/submissions/{submission_id}/report", tags=["submissions"])
    def get_submission_report(
        submission_id: str,
        request: Request,
        session: Annotated[Session, Depends(get_session)],
        format: Literal["json", "html"] = "json",
    ) -> Response:
        submission = session.scalar(
            select(Submission)
            .options(joinedload(Submission.run))
            .where(Submission.id == submission_id)
        )
        if submission is None or submission.run is None:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": "Report not found."}
            )
        if not submission.report_public:
            key = _request_api_key(request)
            organization = authenticate_api_key(key, session, runtime_settings) if key else None
            if organization is None or organization.id != submission.organization_id:
                raise HTTPException(
                    status_code=404, detail={"code": "not_found", "message": "Report not found."}
                )
        if format == "html" or "text/html" in request.headers.get("accept", ""):
            return HTMLResponse(_report_html(submission))
        return JSONResponse(submission.run.report_json)

    @app.post(
        "/v1/submissions/{submission_id}/publish-report",
        response_model=PublishReportResponse,
        tags=["submissions"],
    )
    def publish_submission_report(
        submission_id: str,
        organization: Annotated[Organization, Depends(require_organization)],
        session: Annotated[Session, Depends(get_session)],
    ) -> PublishReportResponse:
        submission = session.scalar(
            select(Submission).where(
                Submission.id == submission_id,
                Submission.organization_id == organization.id,
                Submission.status == SubmissionStatus.COMPLETED.value,
            )
        )
        if submission is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "Completed submission not found."},
            )
        submission.report_public = True
        session.commit()
        return PublishReportResponse(
            submission_id=submission.id,
            report_public=True,
            report_url=f"/v1/submissions/{submission.id}/report",
        )

    def owned_artifact(
        submission_id: str,
        artifact_name: str,
        organization: Organization,
        session: Session,
    ) -> Artifact:
        artifact = session.scalar(
            select(Artifact)
            .join(Artifact.run)
            .join(Submission)
            .where(
                Submission.id == submission_id,
                Submission.organization_id == organization.id,
                Artifact.name == artifact_name,
            )
        )
        if artifact is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "Artifact not found."},
            )
        expires_at = artifact.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "Artifact not found."},
            )
        return artifact

    @app.get("/v1/submissions/{submission_id}/artifacts", tags=["submissions"])
    def list_submission_artifacts(
        submission_id: str,
        organization: Annotated[Organization, Depends(require_organization)],
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, Any]:
        artifacts = list(
            session.scalars(
                select(Artifact)
                .join(Artifact.run)
                .join(Submission)
                .where(
                    Submission.id == submission_id,
                    Submission.organization_id == organization.id,
                )
                .order_by(Artifact.name)
            )
        )
        return {
            "submission_id": submission_id,
            "retention_days": runtime_settings.artifact_retention_days,
            "artifacts": [
                {
                    "name": artifact.name,
                    "sha256": artifact.sha256,
                    "size_bytes": artifact.size_bytes,
                    "content_type": artifact.content_type,
                    "expires_at": artifact.expires_at,
                    "url": f"/v1/submissions/{submission_id}/artifacts/{artifact.name}",
                }
                for artifact in artifacts
            ],
        }

    @app.get(
        "/v1/submissions/{submission_id}/artifacts/{artifact_name}",
        tags=["submissions"],
    )
    def get_submission_artifact(
        submission_id: str,
        artifact_name: str,
        organization: Annotated[Organization, Depends(require_organization)],
        session: Annotated[Session, Depends(get_session)],
    ) -> FileResponse:
        artifact = owned_artifact(submission_id, artifact_name, organization, session)
        path = Path(artifact.storage_path).resolve()
        artifact_root = (runtime_settings.storage_path / "artifacts").resolve()
        if not path.is_relative_to(artifact_root) or not path.is_file():
            raise HTTPException(
                status_code=404,
                detail={"code": "not_found", "message": "Artifact not found."},
            )
        return FileResponse(
            path,
            media_type=artifact.content_type,
            headers={
                "Cache-Control": "private, no-store",
                "ETag": f'"sha256:{artifact.sha256}"',
            },
        )

    @app.get("/v1/leaderboard", tags=["leaderboard"])
    def leaderboard(
        session: Annotated[Session, Depends(get_session)],
        view: Literal["summary", "detail"] = "summary",
        benchmark_version: str | None = None,
    ) -> dict[str, Any]:
        selected = benchmark_version or runtime_settings.active_benchmark_versions[0]
        allowed = (
            runtime_settings.active_benchmark_versions + runtime_settings.frozen_benchmark_versions
        )
        if selected not in allowed:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "unknown_benchmark_version",
                    "message": "Benchmark version not found.",
                },
            )
        return build_leaderboard(
            session,
            runtime_settings,
            benchmark_version=selected,
            view=view,
        )

    @app.get("/v1/leaderboard/history", tags=["leaderboard"])
    def leaderboard_history(
        session: Annotated[Session, Depends(get_session)],
        benchmark_version: str | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 30,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, Any]:
        selected = benchmark_version or runtime_settings.active_benchmark_versions[0]
        rows = list(
            session.scalars(
                select(LeaderboardSnapshot)
                .where(LeaderboardSnapshot.benchmark_version == selected)
                .order_by(LeaderboardSnapshot.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        return {
            "benchmark_version": selected,
            "snapshots": [
                {"created_at": row.created_at, "leaderboard": row.payload} for row in rows
            ],
        }

    @app.get("/v1/leaderboard/runs", tags=["leaderboard"])
    def leaderboard_runs(
        session: Annotated[Session, Depends(get_session)],
        benchmark_version: str | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, Any]:
        selected = benchmark_version or runtime_settings.active_benchmark_versions[0]
        allowed = (
            runtime_settings.active_benchmark_versions + runtime_settings.frozen_benchmark_versions
        )
        if selected not in allowed:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "unknown_benchmark_version",
                    "message": "Benchmark version not found.",
                },
            )
        return build_run_ledger(
            session,
            benchmark_version=selected,
            limit=limit,
            offset=offset,
        )

    @app.post(
        "/v1/admin/organizations",
        response_model=OrganizationCreated,
        status_code=201,
        dependencies=[Depends(require_admin)],
        tags=["admin"],
    )
    def create_organization(
        body: OrganizationCreate,
        session: Annotated[Session, Depends(get_session)],
    ) -> OrganizationCreated:
        if session.scalar(
            select(Organization).where(func.lower(Organization.name) == body.name.lower())
        ):
            raise HTTPException(
                status_code=409,
                detail={"code": "organization_exists", "message": "Organization already exists."},
            )
        for _ in range(5):
            issued = issue_api_key(runtime_settings)
            if not session.scalar(
                select(Organization).where(Organization.key_prefix == issued.prefix)
            ):
                break
        else:
            raise HTTPException(
                status_code=503,
                detail={"code": "key_issuance_failed", "message": "Could not issue a unique key."},
            )
        organization = Organization(
            name=body.name,
            key_prefix=issued.prefix,
            api_key_hash=issued.digest,
            monthly_quota=body.monthly_quota,
            is_paid=body.is_paid,
        )
        session.add(organization)
        session.commit()
        return OrganizationCreated(
            organization_id=organization.id,
            name=organization.name,
            api_key=issued.value,
            monthly_quota=organization.monthly_quota,
        )

    @app.get(
        "/v1/admin/organizations",
        dependencies=[Depends(require_admin)],
        tags=["admin"],
    )
    def list_organizations(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[dict[str, Any]]:
        organizations = list(session.scalars(select(Organization).order_by(Organization.name)))
        return [
            {
                "organization_id": item.id,
                "name": item.name,
                "monthly_quota": item.monthly_quota,
                "is_paid": item.is_paid,
                "is_suspended": item.is_suspended,
                "malicious_rejections": item.malicious_rejections,
                "created_at": item.created_at,
            }
            for item in organizations
        ]

    @app.patch(
        "/v1/admin/organizations/{organization_id}",
        dependencies=[Depends(require_admin)],
        tags=["admin"],
    )
    def update_organization(
        organization_id: str,
        body: OrganizationUpdate,
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, Any]:
        organization = session.get(Organization, organization_id)
        if organization is None:
            raise HTTPException(
                status_code=404, detail={"code": "not_found", "message": "Organization not found."}
            )
        if body.is_suspended is not None:
            organization.is_suspended = body.is_suspended
        if body.monthly_quota is not None:
            organization.monthly_quota = body.monthly_quota
        session.commit()
        return {
            "organization_id": organization.id,
            "is_suspended": organization.is_suspended,
            "monthly_quota": organization.monthly_quota,
        }

    @app.get(
        "/v1/admin/jobs",
        dependencies=[Depends(require_admin)],
        tags=["admin"],
    )
    def job_counts(session: Annotated[Session, Depends(get_session)]) -> dict[str, int]:
        rows = session.execute(
            select(Submission.status, func.count()).group_by(Submission.status)
        ).all()
        return {str(status): int(count) for status, count in rows}

    return app


app = create_app()


def run() -> None:
    uvicorn.run(
        "gloss_service.main:app",
        host="0.0.0.0",
        port=8000,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )
