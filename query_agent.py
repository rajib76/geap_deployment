"""Send a query to a deployed Agent Engine agent and stream the response."""

import argparse

import vertexai
from vertexai import agent_engines

DEFAULT_PROJECT = "YOUR_GCP_PROJECT_ID"
DEFAULT_LOCATION = "us-central1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Query a deployed Agent Engine agent")
    p.add_argument("--project", default=DEFAULT_PROJECT)
    p.add_argument("--location", default=DEFAULT_LOCATION)
    p.add_argument(
        "--resource-name",
        required=True,
        help="Full resource name from deploy.py output, e.g. "
             "projects/123/locations/us-central1/reasoningEngines/456",
    )
    p.add_argument("--user-id", default="demo_user")
    p.add_argument(
        "--message",
        default="Plan a 3-day trip from New York to London in June. "
                "My hotel budget is $200 per night.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    vertexai.init(project=args.project, location=args.location)

    agent = agent_engines.get(args.resource_name)

    print("Creating session …")
    session = agent.create_session(user_id=args.user_id)
    session_id = session["id"]
    print(f"Session ID: {session_id}\n")

    print(f"User: {args.message}\n")
    print("Agent: ", end="", flush=True)
    for chunk in agent.stream_query(
        user_id=args.user_id,
        session_id=session_id,
        message=args.message,
    ):
        # Each chunk may contain text or tool call info.
        if isinstance(chunk, dict):
            text = (
                chunk.get("text")
                or chunk.get("content", {}).get("parts", [{}])[0].get("text", "")
            )
            if text:
                print(text, end="", flush=True)
        elif hasattr(chunk, "text"):
            print(chunk.text, end="", flush=True)
    print()


if __name__ == "__main__":
    main()
