"""Deploy demo_agent to Gemini Enterprise Agent Platform (Agent Engine)."""

import argparse
import sys

import vertexai
from google.cloud.aiplatform_v1.types import SecretRef
from vertexai import agent_engines

from demo_agent.agent import root_agent
from demo_agent.app import GeminiApiAdkApp, build_in_memory_session_service

# # ── Configuration ──────────────────────────────────────────────────────────────
# # Fill these in or pass them as CLI arguments.
# DEFAULT_PROJECT = "YOUR_GCP_PROJECT_ID"
# DEFAULT_LOCATION = "us-central1"   # region that supports Agent Engine
# DEFAULT_STAGING_BUCKET = "gs://YOUR_STAGING_BUCKET"  # must already exist

DEFAULT_PROJECT        = "gen-lang-client-0172427287"
DEFAULT_LOCATION       = "us-central1"           # must support Agent Engine
DEFAULT_STAGING_BUCKET = "gs://adk-install"
# ───────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Deploy travel_planner agent to Agent Engine")
    p.add_argument("--project", default=DEFAULT_PROJECT)
    p.add_argument("--location", default=DEFAULT_LOCATION)
    p.add_argument("--staging-bucket", default=DEFAULT_STAGING_BUCKET)
    p.add_argument(
        "--display-name",
        default="Travel Planner Demo",
        help="Display name shown in the Cloud Console",
    )
    p.add_argument(
        "--description",
        default="Demo ADK travel planner agent deployed via Agent Engine.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.project == "YOUR_GCP_PROJECT_ID":
        print(
            "ERROR: Set --project or update DEFAULT_PROJECT in deploy.py",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.staging_bucket == "gs://YOUR_STAGING_BUCKET":
        print(
            "ERROR: Set --staging-bucket or update DEFAULT_STAGING_BUCKET in deploy.py",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Initialising Vertex AI  project={args.project}  location={args.location}")
    vertexai.init(
        project=args.project,
        location=args.location,
        staging_bucket=args.staging_bucket,
    )

    requirements = [
        "google-cloud-aiplatform[agent_engines,adk]>=1.93.0",
        "google-adk>=1.0.0",
        # OpenTelemetry packages needed for Cloud Trace telemetry.
        "opentelemetry-sdk>=1.20.0",
        "opentelemetry-exporter-gcp-trace>=1.6.0",
        "opentelemetry-resourcedetector-gcp>=1.6.0a0",
    ]

    env_vars = {
        # GOOGLE_API_KEY is injected at runtime from Secret Manager.
        # GeminiApiAdkApp.set_up() then resets GOOGLE_GENAI_USE_VERTEXAI=0
        # so the ADK runner uses the Gemini API (not Vertex AI model serving).
        "GOOGLE_API_KEY": SecretRef(secret="gemini-api-key", version="latest"),
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
    }

    app = GeminiApiAdkApp(
        agent=root_agent,
        enable_tracing=True,
        # Bypasses VertexAiSessionService which crashes on startup trying to
        # call the Resource Manager API to resolve project numbers.
        session_service_builder=build_in_memory_session_service,
    )

    print("Deploying agent with telemetry — this may take several minutes …")
    remote_agent = agent_engines.create(
        agent_engine=app,
        requirements=requirements,
        extra_packages=["demo_agent"],
        display_name=args.display_name,
        description=args.description,
        env_vars=env_vars,
    )

    resource_name = remote_agent.resource_name
    print("\nDeployment successful!")
    print(f"Resource name : {resource_name}")
    print(f"Operations    : {remote_agent.operation_schemas()}")
    print(
        "\nTo query the agent later, use:\n"
        "  from vertexai import agent_engines\n"
        f'  agent = agent_engines.get("{resource_name}")\n'
        "  session = agent.create_session(user_id='demo_user')\n"
        "  for chunk in agent.stream_query(user_id='demo_user', "
        "session_id=session['id'], message='Plan a 3-day trip to Paris'):\n"
        "      print(chunk)"
    )


if __name__ == "__main__":
    main()
