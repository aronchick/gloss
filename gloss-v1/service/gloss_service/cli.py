"""Small operator CLI for migrations and API-key bootstrap."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from gloss_service.canary import DriftCanaryError, run_drift_canary
from gloss_service.config import get_settings
from gloss_service.database import SessionLocal, initialize_database
from gloss_service.models import Organization
from gloss_service.runner import DockerGradingRunner
from gloss_service.security import issue_api_key


def main() -> None:
    parser = argparse.ArgumentParser(prog="gloss-admin")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="Create missing database tables")
    create = subparsers.add_parser("create-org", help="Issue an API key to an organization")
    create.add_argument("name")
    create.add_argument("--monthly-quota", type=int, default=30)
    canary = subparsers.add_parser(
        "run-drift-canary",
        help="Run the three signed gold reference controls for the active cohort",
    )
    canary.add_argument(
        "--authorization",
        action="append",
        type=Path,
        required=True,
        help="Signed control-authorization JSON; provide exactly one for each tier",
    )
    args = parser.parse_args()
    initialize_database()
    if args.command == "init-db":
        print("Database initialized")
        return
    settings = get_settings()
    if args.command == "run-drift-canary":
        try:
            documents = [
                json.loads(path.read_text(encoding="utf-8")) for path in args.authorization
            ]
            if not all(isinstance(document, dict) for document in documents):
                raise DriftCanaryError("Control authorizations must be JSON objects")
            with SessionLocal() as session:
                record = run_drift_canary(
                    session,
                    settings,
                    DockerGradingRunner(settings),
                    documents,
                )
        except (OSError, json.JSONDecodeError, DriftCanaryError) as exc:
            parser.exit(2, f"drift canary failed closed: {exc}\n")
        print(
            json.dumps(
                {
                    "canary_run_id": record.id,
                    "evidence_sha256": record.evidence_sha256,
                    "status": record.status,
                },
                sort_keys=True,
            )
        )
        if record.status != "pass":
            parser.exit(2)
        return
    with SessionLocal() as session:
        if session.scalar(select(Organization).where(Organization.name == args.name)):
            parser.error("organization already exists")
        issued = issue_api_key(settings)
        organization = Organization(
            name=args.name,
            key_prefix=issued.prefix,
            api_key_hash=issued.digest,
            monthly_quota=args.monthly_quota,
        )
        session.add(organization)
        session.commit()
        print(json.dumps({"organization_id": organization.id, "api_key": issued.value}))


if __name__ == "__main__":
    main()
