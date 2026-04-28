"""Full cleanup of all GCP resources created by this project.

Steps (in order):
  1. Delete the deployed Agent Engine resource
  2. Delete the Secret Manager secret (all versions)
  3. Delete the staging GCS bucket and all its contents
  4. Revoke the three IAM roles granted during setup
  5. Disable GCP APIs (optional — skipped unless --disable-apis is passed)
"""

import argparse
import subprocess
import sys
import time

import vertexai
from google.api_core.exceptions import FailedPrecondition, NotFound
from vertexai import agent_engines

DEFAULT_PROJECT  = "gen-lang-client-0172427287"
DEFAULT_LOCATION = "us-central1"
DEFAULT_STAGING_BUCKET = "gs://adk-install"
DEFAULT_SECRET   = "gemini-api-key"

SETUP_ROLES = [
    "roles/aiplatform.user",
    "roles/storage.objectAdmin",
    "roles/secretmanager.admin",
]

RETRY_INTERVAL_S = 15
MAX_RETRIES      = 40  # up to ~10 minutes


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Clean up all GCP resources created by this project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--project",         default=DEFAULT_PROJECT)
    p.add_argument("--location",        default=DEFAULT_LOCATION)
    p.add_argument("--staging-bucket",  default=DEFAULT_STAGING_BUCKET,
                   help="GCS staging bucket URI, e.g. gs://my-bucket")
    p.add_argument("--resource-name",
                   help="Full Agent Engine resource name to delete "
                        "(e.g. projects/123/locations/us-central1/reasoningEngines/456). "
                        "Omit to skip agent deletion.")
    p.add_argument("--secret",          default=DEFAULT_SECRET,
                   help="Secret Manager secret name (default: gemini-api-key)")
    p.add_argument("--email",
                   help="User email whose IAM bindings should be revoked. "
                        "Omit to skip IAM cleanup.")
    p.add_argument("--disable-apis",    action="store_true",
                   help="Also disable aiplatform, storage, and secretmanager APIs")
    p.add_argument("--force",           action="store_true",
                   help="Skip all confirmation prompts")
    return p.parse_args()


# ── helpers ────────────────────────────────────────────────────────────────────

def confirm(prompt: str, force: bool) -> bool:
    if force:
        return True
    answer = input(f"{prompt} [y/N] ").strip().lower()
    return answer == "y"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ── step functions ─────────────────────────────────────────────────────────────

def delete_agent(resource_name: str, project: str, location: str, force: bool) -> None:
    section("Step 1 — Delete deployed Agent Engine resource")

    if not confirm(f"Delete agent '{resource_name}'?", force):
        print("  Skipped.")
        return

    vertexai.init(project=project, location=location)

    try:
        agent = agent_engines.get(resource_name)
        print(f"  Found: '{agent.display_name}'")
    except NotFound:
        print("  Agent not found — already deleted or invalid resource name.")
        return

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  Deleting (attempt {attempt}) …")
            agent.delete(force=True)
            print("  Done — agent deleted.")
            return
        except FailedPrecondition as e:
            if "other operations running" in str(e):
                print(f"  Blocked by a running operation — retrying in {RETRY_INTERVAL_S} s …")
                time.sleep(RETRY_INTERVAL_S)
            else:
                raise

    print("  ERROR: gave up waiting for agent deletion.", file=sys.stderr)
    sys.exit(1)


def delete_secret(secret: str, project: str, force: bool) -> None:
    section("Step 2 — Delete Secret Manager secret")

    if not confirm(f"Permanently delete secret '{secret}' and all its versions?", force):
        print("  Skipped.")
        return

    result = run(
        ["gcloud", "secrets", "delete", secret, "--project", project, "--quiet"],
        check=False,
    )
    if result.returncode == 0:
        print("  Done — secret deleted.")
    elif "NOT_FOUND" in result.stderr or "not found" in result.stderr.lower():
        print("  Secret not found — already deleted.")
    else:
        print(f"  ERROR: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)


def delete_bucket(bucket_uri: str, force: bool) -> None:
    section("Step 3 — Delete staging GCS bucket")

    if not confirm(f"Delete bucket '{bucket_uri}' and ALL its contents?", force):
        print("  Skipped.")
        return

    result = run(["gcloud", "storage", "rm", "-r", bucket_uri], check=False)
    if result.returncode == 0:
        print("  Done — bucket deleted.")
    elif "not found" in result.stderr.lower() or "does not exist" in result.stderr.lower():
        print("  Bucket not found — already deleted.")
    else:
        print(f"  ERROR: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)


def revoke_iam(email: str, project: str, force: bool) -> None:
    section("Step 4 — Revoke IAM bindings")

    roles_str = "\n    ".join(SETUP_ROLES)
    if not confirm(
        f"Revoke the following roles from {email}?\n    {roles_str}", force
    ):
        print("  Skipped.")
        return

    member = f"user:{email}"
    for role in SETUP_ROLES:
        result = run(
            [
                "gcloud", "projects", "remove-iam-policy-binding", project,
                "--member", member,
                "--role", role,
                "--quiet",
            ],
            check=False,
        )
        if result.returncode == 0:
            print(f"  Revoked {role}")
        elif "not found" in result.stderr.lower():
            print(f"  Binding not found for {role} — already removed.")
        else:
            print(f"  WARNING: could not revoke {role}: {result.stderr.strip()}")


def disable_apis(project: str, force: bool) -> None:
    section("Step 5 — Disable GCP APIs")

    apis = [
        "aiplatform.googleapis.com",
        "storage.googleapis.com",
        "secretmanager.googleapis.com",
    ]
    apis_str = "\n    ".join(apis)
    if not confirm(
        f"Disable the following APIs?\n    {apis_str}\n"
        "  (Only do this if no other workloads in the project rely on them.)",
        force,
    ):
        print("  Skipped.")
        return

    result = run(
        ["gcloud", "services", "disable"] + apis + ["--project", project, "--quiet"],
        check=False,
    )
    if result.returncode == 0:
        print("  Done — APIs disabled.")
    else:
        print(f"  WARNING: {result.stderr.strip()}")


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("  Gemini Agent Platform — Full Cleanup")
    print("=" * 60)
    print(f"  Project : {args.project}")
    print(f"  Location: {args.location}")

    if args.resource_name:
        delete_agent(args.resource_name, args.project, args.location, args.force)
    else:
        section("Step 1 — Delete deployed Agent Engine resource")
        print("  --resource-name not provided — skipping agent deletion.")

    delete_secret(args.secret, args.project, args.force)
    delete_bucket(args.staging_bucket, args.force)

    if args.email:
        revoke_iam(args.email, args.project, args.force)
    else:
        section("Step 4 — Revoke IAM bindings")
        print("  --email not provided — skipping IAM cleanup.")

    if args.disable_apis:
        disable_apis(args.project, args.force)
    else:
        section("Step 5 — Disable GCP APIs")
        print("  Pass --disable-apis to disable APIs (skipped by default).")

    print("\n" + "=" * 60)
    print("  Cleanup complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
