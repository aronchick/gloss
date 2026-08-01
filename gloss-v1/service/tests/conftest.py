from __future__ import annotations

import io
import json
import uuid
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session, sessionmaker

from gloss_service.config import Settings
from gloss_service.database import Base, create_db_engine
from gloss_service.main import create_app
from gloss_service.quarantine_handoff import encode_private_key, encode_public_key, utc_text
from gloss_service.quarantine_job import normative_profile_hashes
from gloss_service.quarantine_runner import InsecureInProcessQuarantineRunner
from gloss_service.quarantine_worker import quarantine_once
from gloss_service.runner import HostedArtifactBinding

MANIFEST_HASH = f"sha256:{'a' * 64}"
GRADER_SOURCE_HASH = f"sha256:{'b' * 64}"
ENVIRONMENT_HASH = "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"


def hosted_artifact_binding(
    submission_id: str = "00000000-0000-0000-0000-000000000001",
) -> HostedArtifactBinding:
    return HostedArtifactBinding(
        prompt_variant="canonical",
        generation_seed=None,
        schema_validation_performed=True,
        schema_valid=True,
        schema_violations=(),
        schema_bundle_sha256=f"sha256:{'5' * 64}",
        schema_root_map_sha256=f"sha256:{'6' * 64}",
        mce_profile_sha256=f"sha256:{'4' * 64}",
        canonical_package_hash_profile_sha256=f"sha256:{'7' * 64}",
        canonical_package_hash_v1=f"sha256:{'d' * 64}",
        gold_duplicate_check="clear",
        submission_sha256=f"sha256:{'e' * 64}",
        mce_resolved_package_sha256=f"sha256:{'f' * 64}",
        assistance_class="unassisted",
        generation_profile_sha256=f"sha256:{'a' * 64}",
        attested_metrics={"generation_strategy": "direct"},
        attestation={"human_intervention": False},
        submission_id=submission_id,
        campaign_id="00000000-0000-0000-0000-000000000002",
        robustness_group_id=None,
        campaign_slot=1,
        submitter_id="00000000-0000-0000-0000-000000000003",
        model_key="00000000-0000-0000-0000-000000000004",
        model_revision_key="00000000-0000-0000-0000-000000000005",
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    signing_key = Ed25519PrivateKey.generate()
    key_id = "test-quarantine-key"
    now = datetime.now(UTC)
    runtime_settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'service.db'}",
        storage_path=tmp_path / "data",
        admin_api_key="test-admin-key",
        api_key_pepper="test-pepper",
        submissions_per_hour=100,
        free_monthly_quota=100,
        trusted_hosts=["testserver"],
        active_scoring_manifest_sha256=MANIFEST_HASH,
        active_grader_source_tree_sha256=GRADER_SOURCE_HASH,
        active_environment_attestation_sha256=ENVIRONMENT_HASH,
        allow_insecure_quarantine_runner=True,
        quarantine_signing_key_id=key_id,
        quarantine_signing_private_key=encode_private_key(signing_key),
        quarantine_verification_keys_json=json.dumps(
            {
                key_id: {
                    "public_key": encode_public_key(signing_key.public_key()),
                    "not_before": utc_text(now - timedelta(days=1)),
                    "not_after": utc_text(now + timedelta(days=1)),
                    "revoked_at": None,
                }
            }
        ),
    )
    profiles = normative_profile_hashes(runtime_settings)
    runtime_settings.active_quarantine_profile_sha256 = profiles["quarantine_profile_sha256"]
    runtime_settings.active_mce_profile_sha256 = profiles["mce_profile_sha256"]
    runtime_settings.active_schema_bundle_sha256 = profiles["schema_bundle_sha256"]
    runtime_settings.active_schema_root_map_sha256 = profiles["schema_root_map_sha256"]
    runtime_settings.active_canonical_package_hash_profile_sha256 = profiles[
        "canonical_package_hash_profile_sha256"
    ]
    return runtime_settings


@pytest.fixture
def sessions(settings: Settings) -> Iterator[sessionmaker[Session]]:
    engine = create_db_engine(settings)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    yield factory
    engine.dispose()


@pytest.fixture
def client(
    settings: Settings,
    sessions: sessionmaker[Session],
) -> Iterator[TestClient]:
    app = create_app(settings, sessions)
    app.state.test_settings = settings
    app.state.test_sessions = sessions
    with TestClient(app) as test_client:
        yield test_client


def make_pptx(
    slide_count: int = 5,
    *,
    external_relationship: bool = False,
    embedded_spreadsheet: bool = False,
    nested_archive: bool = False,
    ole: bool = False,
    traversal: bool = False,
) -> bytes:
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            + (
                '<Default Extension="xlsx" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"/>'
                if embedded_spreadsheet
                else ""
            )
            + '<Override PartName="/ppt/presentation.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
            + "".join(
                f'<Override PartName="/ppt/slides/slide{slide}.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
                for slide in range(1, slide_count + 1)
            )
            + "</Types>",
        )
        archive.writestr(
            "ppt/presentation.xml",
            """<?xml version="1.0"?>
            <p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
              xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <p:sldIdLst>"""
            + "".join(
                f'<p:sldId id="{255 + slide}" r:id="rId{slide}"/>'
                for slide in range(1, slide_count + 1)
            )
            + """</p:sldIdLst>
              <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>
              <p:notesSz cx="6858000" cy="9144000"/>
            </p:presentation>""",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" '
            'Target="ppt/presentation.xml"/></Relationships>',
        )
        for slide in range(1, slide_count + 1):
            archive.writestr(
                f"ppt/slides/slide{slide}.xml",
                """<?xml version="1.0"?>
                <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld><p:spTree>
                    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
                    <p:grpSpPr/>
                  </p:spTree></p:cSld>
                </p:sld>""",
            )
        slide_relationships = "".join(
            f'<Relationship Id="rId{slide}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
            f'Target="slides/slide{slide}.xml"/>'
            for slide in range(1, slide_count + 1)
        )
        external = (
            '<Relationship Id="rId999" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
            'Target="https://example.com/payload" TargetMode="External"/>'
            if external_relationship
            else ""
        )
        archive.writestr(
            "ppt/_rels/presentation.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + slide_relationships
            + external
            + "</Relationships>",
        )
        if nested_archive:
            archive.writestr("ppt/media/payload.zip", b"PK\x03\x04payload")
        if embedded_spreadsheet:
            workbook_bytes = io.BytesIO()
            with zipfile.ZipFile(workbook_bytes, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
                workbook.writestr(
                    "[Content_Types].xml",
                    '<?xml version="1.0"?>'
                    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    '<Default Extension="rels" '
                    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Override PartName="/xl/workbook.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                    "</Types>",
                )
                workbook.writestr(
                    "xl/workbook.xml",
                    '<?xml version="1.0"?>'
                    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>',
                )
                workbook.writestr(
                    "_rels/.rels",
                    '<?xml version="1.0"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
                )
            archive.writestr("ppt/embeddings/chart-data.xlsx", workbook_bytes.getvalue())
        if ole:
            archive.writestr(
                "ppt/media/picture.png", bytes.fromhex("D0CF11E0A1B11AE1") + b"payload"
            )
        if traversal:
            archive.writestr("../escape.xml", "unsafe")
    return result.getvalue()


def metadata(campaign_id: str = "auto", **overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "campaign_id": campaign_id,
        "generation_seed": None,
        "efficiency_metrics": {"generation_strategy": "direct"},
        "attestation": {
            "method": "Single API generation pass",
            "human_intervention": False,
            "post_processing": False,
            "external_resources_used": False,
        },
    }
    value.update(overrides)
    return value


def create_org(client: TestClient, name: str = "Test Lab", quota: int = 100) -> tuple[str, str]:
    response = client.post(
        "/v1/admin/organizations",
        headers={"X-Admin-Key": "test-admin-key"},
        json={"name": name, "monthly_quota": quota},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return payload["organization_id"], payload["api_key"]


def create_model_revision(
    client: TestClient,
    api_key: str,
    *,
    display_name: str = "Model Alpha",
    display_version: str | None = None,
    owner_attribution: str = "submitter-attested",
) -> tuple[str, str]:
    headers = {"X-API-Key": api_key}
    model = client.post(
        "/v1/models",
        headers=headers,
        json={"display_name": display_name, "owner_attribution": owner_attribution},
    )
    assert model.status_code == 201, model.text
    model_key = model.json()["model_key"]
    revision = client.post(
        f"/v1/models/{model_key}/revisions",
        headers=headers,
        json={
            "display_version": display_version or f"test-{uuid.uuid4()}",
            "revision_note": "Test fixture revision",
        },
    )
    assert revision.status_code == 201, revision.text
    return model_key, revision.json()["model_revision_key"]


def generation_profile(
    revision_key: str,
    *,
    human_intervention_permitted: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "profile_id": "gloss-generation-profile-v1",
        "canonicalization": "RFC8785-JCS",
        "generator": {
            "provider": "test-provider",
            "model_identifier": "test-model",
            "immutable_revision": revision_key,
            "api_surface": "test-api",
        },
        "generation_strategy": "direct",
        "toolchain": [],
        "sampling": {
            "temperature": 0,
            "top_p": 1,
            "top_k": None,
            "max_output_tokens": 4096,
            "other_parameters": [],
        },
        "permissions": {
            "human_intervention_permitted": human_intervention_permitted,
            "post_processing_permitted": False,
        },
    }


def register_generation_profile(
    client: TestClient,
    api_key: str,
    revision_key: str,
    *,
    human_intervention_permitted: bool = False,
) -> str:
    response = client.post(
        "/v1/generation-profiles",
        headers={"X-API-Key": api_key},
        json={
            "model_revision_key": revision_key,
            "profile": generation_profile(
                revision_key,
                human_intervention_permitted=human_intervention_permitted,
            ),
        },
    )
    assert response.status_code == 201, response.text
    digest = response.json()["generation_profile_sha256"]
    assert isinstance(digest, str)
    return digest


def create_campaign(
    client: TestClient,
    api_key: str,
    *,
    tier: int = 1,
    prompt_variant: str = "canonical",
    revision_key: str | None = None,
    assistance_class: str = "unassisted",
) -> str:
    if revision_key is None:
        _, revision_key = create_model_revision(client, api_key)
    cohort = client.get("/v1/versions").json()["active_scoring_cohort_id"]
    profile_sha256 = register_generation_profile(
        client,
        api_key,
        revision_key,
        human_intervention_permitted=assistance_class == "human-assisted",
    )
    response = client.post(
        "/v1/campaigns",
        headers={"X-API-Key": api_key},
        json={
            "model_revision_key": revision_key,
            "scoring_cohort_id": cohort,
            "tier": tier,
            "prompt_variant": prompt_variant,
            "assistance_class": assistance_class,
            "generation_profile_sha256": profile_sha256,
        },
    )
    assert response.status_code == 201, response.text
    campaign_id = response.json()["campaign_id"]
    assert isinstance(campaign_id, str)
    return campaign_id


def submit(
    client: TestClient,
    api_key: str,
    *,
    deck: bytes | None = None,
    submission_metadata: dict[str, Any] | None = None,
) -> Response:
    outgoing = dict(submission_metadata or metadata())
    if outgoing.get("campaign_id") == "auto":
        outgoing["campaign_id"] = create_campaign(client, api_key)
    response = cast(
        Response,
        client.post(
            "/v1/submissions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={
                "metadata": (
                    None,
                    json.dumps(outgoing),
                    "application/json",
                ),
                "file": (
                    "submission.pptx",
                    deck or make_pptx(),
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ),
            },
        ),
    )
    if response.status_code == 202:
        app_state = cast(Any, client.app).state
        test_settings = cast(Settings, app_state.test_settings)
        test_sessions = cast(sessionmaker[Session], app_state.test_sessions)
        quarantine_once(
            test_settings,
            test_sessions,
            InsecureInProcessQuarantineRunner(test_settings),
            "test-quarantine-worker",
        )
    return response
