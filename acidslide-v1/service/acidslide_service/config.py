"""Runtime configuration with production safety gates."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, cast

import rfc8785
from cryptography.fernet import Fernet
from jsonschema import Draft202012Validator
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_DEV_FERNET_KEY = base64.urlsafe_b64encode(bytes(32)).decode()
_DEV_COHORT_HASHES = {
    f"sha256:{'0' * 64}",
    f"sha256:{'1' * 64}",
    f"sha256:{'2' * 64}",
}
_DEV_QUARANTINE_HASHES = {
    f"sha256:{'3' * 64}",
    f"sha256:{'4' * 64}",
    f"sha256:{'5' * 64}",
    f"sha256:{'6' * 64}",
    f"sha256:{'7' * 64}",
    f"sha256:{'8' * 64}",
    f"sha256:{'9' * 64}",
}
_DEV_RELEASE_HASHES = {f"sha256:{character * 64}" for character in "abcdef"}


class Settings(BaseSettings):
    """Environment-backed service settings."""

    model_config = SettingsConfigDict(
        env_prefix="ACIDSLIDE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = "sqlite:///./acidslide-service.db"
    storage_path: Path = Path("./.data")
    public_base_url: str = "http://localhost:8000"
    admin_api_key: str = "development-admin-key-change-me"
    api_key_pepper: str = "development-api-key-pepper-change-me"
    encryption_key: str = _DEV_FERNET_KEY
    trusted_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1", "testserver"]
    cors_origins: Annotated[list[str], NoDecode] = []

    active_benchmark_versions: Annotated[list[str], NoDecode] = ["acidslide-v1.0.0"]
    frozen_benchmark_versions: Annotated[list[str], NoDecode] = []
    required_prompt_variants: Annotated[list[str], NoDecode] = [
        "canonical",
        "paraphrase-a",
        "paraphrase-b",
    ]
    active_scoring_manifest_sha256: str = f"sha256:{'0' * 64}"
    active_grader_source_tree_sha256: str = f"sha256:{'1' * 64}"
    active_environment_attestation_sha256: str = f"sha256:{'2' * 64}"
    environment_attestation_json: str = "{}"
    active_grader_package_sha256: str = f"sha256:{'a' * 64}"
    active_prompt_bundle_sha256: str = f"sha256:{'b' * 64}"
    active_scored_assertion_inventory_sha256: str = f"sha256:{'c' * 64}"
    active_checklist_bundle_sha256: str = f"sha256:{'d' * 64}"

    active_quarantine_profile_sha256: str = f"sha256:{'3' * 64}"
    active_mce_profile_sha256: str = f"sha256:{'4' * 64}"
    active_schema_bundle_sha256: str = f"sha256:{'5' * 64}"
    active_schema_root_map_sha256: str = f"sha256:{'6' * 64}"
    active_canonical_package_hash_profile_sha256: str = f"sha256:{'7' * 64}"
    active_gold_byte_sha256: str = f"sha256:{'8' * 64}"
    active_gold_mce_resolved_package_sha256: str = f"sha256:{'e' * 64}"
    active_gold_canonical_package_sha256: str = f"sha256:{'9' * 64}"
    generation_profile_schema_path: Path = Path("../schemas/generation-profile.schema.json")
    environment_attestation_schema_path: Path = Path(
        "../schemas/environment-attestation.schema.json"
    )
    scoring_manifest_path: Path = Path("../benchmark/scoring-manifest.json")
    gold_evidence_path: Path = Path("../benchmark/gold-evidence.json")
    gold_resolved_path: Path = Path("../benchmark/deck/gold/acidslide-v1-gold.mce-resolved.pptx")
    control_handoff_schema_path: Path = Path("../schemas/control-handoff.schema.json")
    control_verification_keys_json: str = "{}"
    drift_canary_max_age_seconds: int = 8 * 24 * 60 * 60
    quarantine_verification_keys_json: str = "{}"
    quarantine_signing_key_id: str = ""
    quarantine_signing_private_key: str = ""
    quarantine_verdict_ttl_seconds: int = 300
    quarantine_image: str = "acidslide/quarantine:1.0.0"
    quarantine_image_digest: str = ""
    quarantine_timeout_seconds: int = 180
    quarantine_memory: str = "1g"
    quarantine_cpus: str = "1"
    quarantine_pids_limit: int = 128
    quarantine_uid: int = 10001
    allow_insecure_quarantine_runner: bool = False

    grader_image: str = "acidslide/grader:1.0.0"
    grader_image_digest: str = ""
    grader_timeout_seconds: int = 600
    grader_memory: str = "2g"
    grader_cpus: str = "2"
    grader_pids_limit: int = 256
    grader_uid: int = 10001
    allow_insecure_test_runner: bool = False

    libreoffice_version: str = "unknown"
    font_bundle_hash: str = f"sha256:{'f' * 64}"
    asset_manifest_hash: str = f"sha256:{'a' * 64}"

    max_upload_bytes: int = 100 * 1024 * 1024
    upload_timeout_seconds: int = 120
    max_uncompressed_bytes: int = 500 * 1024 * 1024
    max_zip_entries: int = 10_000
    max_decompression_ratio: float = 20.0
    upload_chunk_bytes: int = 1024 * 1024
    artifact_retention_days: int = 90
    worker_poll_seconds: float = 1.0
    worker_heartbeat_seconds: int = 30
    worker_metrics_port: int = 9001
    stale_job_seconds: int = 900

    submissions_per_hour: int = 10
    submissions_per_tuple_window: int = 3
    tuple_window_days: int = 7
    concurrent_jobs_per_key: int = 5
    free_monthly_quota: int = 30
    malicious_rejection_suspend_threshold: int = 5

    log_level: str = "INFO"
    metrics_bearer_token: str = ""

    @field_validator("trusted_hosts", "cors_origins", mode="before")
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator(
        "active_benchmark_versions",
        "frozen_benchmark_versions",
        "required_prompt_variants",
        mode="before",
    )
    @classmethod
    def split_value_csv(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("drift_canary_max_age_seconds")
    @classmethod
    def validate_canary_max_age(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("DRIFT_CANARY_MAX_AGE_SECONDS must be positive")
        return value

    @field_validator(
        "active_scoring_manifest_sha256",
        "active_grader_source_tree_sha256",
        "active_environment_attestation_sha256",
        "active_grader_package_sha256",
        "active_prompt_bundle_sha256",
        "active_scored_assertion_inventory_sha256",
        "active_checklist_bundle_sha256",
        "active_quarantine_profile_sha256",
        "active_mce_profile_sha256",
        "active_schema_bundle_sha256",
        "active_schema_root_map_sha256",
        "active_canonical_package_hash_profile_sha256",
        "active_gold_byte_sha256",
        "active_gold_mce_resolved_package_sha256",
        "active_gold_canonical_package_sha256",
        "font_bundle_hash",
        "asset_manifest_hash",
    )
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None:
            raise ValueError("active cohort fields must be lowercase sha256 digests")
        return value

    @model_validator(mode="after")
    def enforce_production_safety(self) -> Settings:
        try:
            Fernet(self.encryption_key.encode())
        except (ValueError, TypeError) as exc:
            raise ValueError("ACIDSLIDE_ENCRYPTION_KEY must be a valid Fernet key") from exc

        try:
            environment_attestation = self.environment_attestation
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(
                "ACIDSLIDE_ENVIRONMENT_ATTESTATION_JSON must contain a JSON object"
            ) from exc

        if self.app_env == "production":
            problems: list[str] = []
            if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                problems.append("production DATABASE_URL must use PostgreSQL")
            if len(self.admin_api_key) < 32 or "change-me" in self.admin_api_key:
                problems.append("ADMIN_API_KEY must be a unique secret of at least 32 characters")
            if len(self.api_key_pepper) < 32 or "change-me" in self.api_key_pepper:
                problems.append("API_KEY_PEPPER must be a unique secret of at least 32 characters")
            if self.encryption_key == _DEV_FERNET_KEY:
                problems.append("ENCRYPTION_KEY must not use the development key")
            if not self.public_base_url.startswith("https://"):
                problems.append("PUBLIC_BASE_URL must use HTTPS")
            if not self.grader_image_digest.startswith("sha256:"):
                problems.append("GRADER_IMAGE_DIGEST must pin the canonical image")
            if not self.quarantine_image_digest.startswith("sha256:"):
                problems.append("QUARANTINE_IMAGE_DIGEST must pin the quarantine image")
            for setting_name, value in (
                ("ACTIVE_SCORING_MANIFEST_SHA256", self.active_scoring_manifest_sha256),
                ("ACTIVE_GRADER_SOURCE_TREE_SHA256", self.active_grader_source_tree_sha256),
                (
                    "ACTIVE_ENVIRONMENT_ATTESTATION_SHA256",
                    self.active_environment_attestation_sha256,
                ),
            ):
                if (
                    not value.startswith("sha256:")
                    or "replace" in value
                    or value in _DEV_COHORT_HASHES
                ):
                    problems.append(f"{setting_name} must pin the active scoring cohort")
            actual_attestation_sha256 = (
                "sha256:" + hashlib.sha256(rfc8785.dumps(environment_attestation)).hexdigest()
            )
            if actual_attestation_sha256 != self.active_environment_attestation_sha256:
                problems.append(
                    "ENVIRONMENT_ATTESTATION_JSON must hash to "
                    "ACTIVE_ENVIRONMENT_ATTESTATION_SHA256"
                )
            schema_candidates = (
                self.environment_attestation_schema_path,
                Path.cwd() / self.environment_attestation_schema_path,
                Path(__file__).resolve().parents[2]
                / "schemas"
                / "environment-attestation.schema.json",
                Path("/opt/acidslide/schemas/environment-attestation.schema.json"),
            )
            schema_path = next((path for path in schema_candidates if path.is_file()), None)
            if schema_path is None:
                problems.append("environment attestation schema is unavailable")
            else:
                try:
                    schema_document = json.loads(schema_path.read_text(encoding="utf-8"))
                    validator = Draft202012Validator(schema_document)
                    validation_errors = sorted(
                        validator.iter_errors(environment_attestation),
                        key=lambda error: list(error.absolute_path),
                    )
                except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    problems.append(f"environment attestation schema is invalid: {exc}")
                else:
                    if validation_errors:
                        problems.append(
                            "ENVIRONMENT_ATTESTATION_JSON is not schema-valid: "
                            f"{validation_errors[0].message}"
                        )
            if environment_attestation.get("oci_image_digest") != self.grader_image_digest:
                problems.append(
                    "environment attestation oci_image_digest must match GRADER_IMAGE_DIGEST"
                )
            if (
                environment_attestation.get("grader_source_tree_sha256")
                != self.active_grader_source_tree_sha256
            ):
                problems.append(
                    "environment attestation grader_source_tree_sha256 must match "
                    "the active release"
                )
            font_environment = environment_attestation.get("font_environment")
            if not isinstance(font_environment, dict) or (
                font_environment.get("font_manifest_sha256") != self.font_bundle_hash
            ):
                problems.append(
                    "environment attestation font_manifest_sha256 must match FONT_BUNDLE_HASH"
                )
            profile_hashes = environment_attestation.get("profile_hashes")
            if not isinstance(profile_hashes, dict) or any(
                profile_hashes.get(name) != expected
                for name, expected in (
                    ("xsd_bundle_sha256", self.active_schema_bundle_sha256),
                    ("schema_root_map_sha256", self.active_schema_root_map_sha256),
                    ("mce_profile_sha256", self.active_mce_profile_sha256),
                    (
                        "canonical_package_hash_profile_sha256",
                        self.active_canonical_package_hash_profile_sha256,
                    ),
                )
            ):
                problems.append(
                    "environment attestation profile hashes must match the active release"
                )
            if self.allow_insecure_test_runner:
                problems.append("ALLOW_INSECURE_TEST_RUNNER must be false")
            if self.allow_insecure_quarantine_runner:
                problems.append("ALLOW_INSECURE_QUARANTINE_RUNNER must be false")
            for setting_name, value in (
                ("ACTIVE_QUARANTINE_PROFILE_SHA256", self.active_quarantine_profile_sha256),
                ("ACTIVE_MCE_PROFILE_SHA256", self.active_mce_profile_sha256),
                ("ACTIVE_SCHEMA_BUNDLE_SHA256", self.active_schema_bundle_sha256),
                ("ACTIVE_SCHEMA_ROOT_MAP_SHA256", self.active_schema_root_map_sha256),
                (
                    "ACTIVE_CANONICAL_PACKAGE_HASH_PROFILE_SHA256",
                    self.active_canonical_package_hash_profile_sha256,
                ),
                ("ACTIVE_GOLD_BYTE_SHA256", self.active_gold_byte_sha256),
                (
                    "ACTIVE_GOLD_MCE_RESOLVED_PACKAGE_SHA256",
                    self.active_gold_mce_resolved_package_sha256,
                ),
                (
                    "ACTIVE_GOLD_CANONICAL_PACKAGE_SHA256",
                    self.active_gold_canonical_package_sha256,
                ),
            ):
                if value in _DEV_QUARANTINE_HASHES:
                    problems.append(f"{setting_name} must pin the active quarantine cohort")
            for setting_name, value in (
                ("ACTIVE_GRADER_PACKAGE_SHA256", self.active_grader_package_sha256),
                ("ACTIVE_PROMPT_BUNDLE_SHA256", self.active_prompt_bundle_sha256),
                (
                    "ACTIVE_SCORED_ASSERTION_INVENTORY_SHA256",
                    self.active_scored_assertion_inventory_sha256,
                ),
                ("ACTIVE_CHECKLIST_BUNDLE_SHA256", self.active_checklist_bundle_sha256),
                ("FONT_BUNDLE_HASH", self.font_bundle_hash),
                ("ASSET_MANIFEST_HASH", self.asset_manifest_hash),
            ):
                if value in _DEV_RELEASE_HASHES:
                    problems.append(f"{setting_name} must pin the active release artifact")
            try:
                from acidslide_service.quarantine_handoff import load_verification_keys

                load_verification_keys(self.quarantine_verification_keys_json)
            except ValueError as exc:
                problems.append(str(exc))
            if "*" in self.trusted_hosts:
                problems.append("TRUSTED_HOSTS must not contain a wildcard")
            if problems:
                raise ValueError("; ".join(problems))
        return self

    @property
    def fernet(self) -> Fernet:
        return Fernet(self.encryption_key.encode())

    @property
    def environment_attestation(self) -> dict[str, Any]:
        value = json.loads(self.environment_attestation_json)
        if not isinstance(value, dict):
            raise TypeError("environment attestation must be an object")
        return cast(dict[str, Any], value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
