"""Delete a deployed Agent Engine resource."""

import argparse
import sys
import time

import vertexai
from google.api_core.exceptions import FailedPrecondition
from vertexai import agent_engines

DEFAULT_PROJECT = "gen-lang-client-0172427287"
DEFAULT_LOCATION = "us-central1"
RETRY_INTERVAL_S = 15
MAX_RETRIES = 40  # up to ~10 minutes


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Delete a deployed Agent Engine")
    p.add_argument("--project", default=DEFAULT_PROJECT)
    p.add_argument("--location", default=DEFAULT_LOCATION)
    p.add_argument(
        "--resource-name",
        required=True,
        help="Full resource name, e.g. projects/123/locations/us-central1/reasoningEngines/456",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not args.force:
        confirm = input(f"Delete agent {args.resource_name}? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            sys.exit(0)

    vertexai.init(project=args.project, location=args.location)

    print(f"Fetching {args.resource_name} …")
    agent = agent_engines.get(args.resource_name)
    print(f"Found: '{agent.display_name}'")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"Deleting (attempt {attempt}) …")
            agent.delete(force=True)
            print("Done — agent deleted.")
            return
        except FailedPrecondition as e:
            if "other operations running" in str(e):
                print(f"  Blocked by a running operation — retrying in {RETRY_INTERVAL_S} s …")
                time.sleep(RETRY_INTERVAL_S)
            else:
                raise

    print("ERROR: gave up waiting after too many retries.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
