# Demo ADK Agent — Gemini Enterprise Agent Platform

A **Travel Planner** agent built with [Google ADK](https://google.github.io/adk-docs/), deployed on the Gemini Enterprise Agent Platform (Vertex AI Agent Engine / Reasoning Engine).

## Project layout

```
gemini_agent_platform/
├── demo_agent/
│   ├── __init__.py       ← makes demo_agent a proper Python package (required)
│   ├── agent.py          ← root_agent definition + 4 tool functions
│   ├── app.py            ← GeminiApiAdkApp + session service (see Architecture Notes)
│   └── requirements.txt  ← container-side dependencies
├── deploy.py             ← deploys demo_agent to Agent Engine
├── query_agent.py        ← streams a query to a deployed agent
├── delete_agent.py       ← safely deletes a deployed agent
└── requirements.txt      ← local dev dependencies
```

---

## 1  Prerequisites

### 1.1  GCP project & APIs

Enable the APIs required by Agent Engine:

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  --project YOUR_GCP_PROJECT_ID
```

> **`gen-lang-client-*` projects** (the free "gen-lang-client" tier) only have
> `generativelanguage.googleapis.com` enabled — they do **not** have Vertex AI
> publisher model serving. See [Architecture Notes](#architecture-notes) for how
> this project works around that limitation.

### 1.2  IAM roles for your account

| Role | Why |
|------|-----|
| `roles/aiplatform.user` | Create / query Agent Engine resources |
| `roles/storage.objectAdmin` | Upload staging artefacts to GCS |
| `roles/secretmanager.admin` | Create secrets and manage IAM on them |

```bash
PROJECT=YOUR_GCP_PROJECT_ID
EMAIL=YOUR_EMAIL

for ROLE in roles/aiplatform.user roles/storage.objectAdmin roles/secretmanager.admin; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="user:$EMAIL" \
    --role="$ROLE"
done
```

### 1.3  Staging bucket

Agent Engine uploads a pickled agent and a requirements file to GCS before
spinning up the container. Create the bucket once:

```bash
gcloud storage buckets create gs://YOUR_STAGING_BUCKET \
  --project YOUR_GCP_PROJECT_ID \
  --location us-central1
```

### 1.4  Authenticate locally

```bash
gcloud auth application-default login
```

---

## 2  Gemini API key — get it and store it in Secret Manager

The agent calls the Gemini API at runtime using an API key. The key is stored in
Secret Manager and injected into the container as an environment variable at
startup.

### 2.1  Get a Gemini API key

1. Open [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Click **Create API key**.
3. Select your GCP project from the drop-down.
4. Copy the generated key — you will not be able to see it again.

### 2.2  Create the secret in Secret Manager

```bash
# Replace <YOUR_API_KEY> with the key you just copied.
echo -n "YOUR_API_KEY" | gcloud secrets create gemini-api-key \
  --project YOUR_GCP_PROJECT_ID \
  --replication-policy automatic \
  --data-file=-
```

If the secret already exists, add a new version instead:

```bash
echo -n "YOUR_API_KEY" | gcloud secrets versions add gemini-api-key \
  --project YOUR_GCP_PROJECT_ID \
  --data-file=-
```

### 2.3  Grant the Agent Engine service account access to the secret

Agent Engine runs inside a managed container using a dedicated service account.
That account must be allowed to read the secret at startup.

First find your project **number** (different from the project ID):

```bash
gcloud projects describe YOUR_GCP_PROJECT_ID --format="value(projectNumber)"
# e.g. 511354492757
```

Then grant access:

```bash
PROJECT_NUMBER=511354492757   # replace with your project number

gcloud secrets add-iam-policy-binding gemini-api-key \
  --project YOUR_GCP_PROJECT_ID \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform-re.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

> **Important:** If you delete and recreate the secret, the IAM binding is lost.
> You must re-run the command above after every recreation.

---

## 3  Local setup

```bash
# Python 3.10+ required
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

---

## 4  Test the agent locally (optional)

```bash
# Interactive browser UI — runs the agent locally without deploying
adk web demo_agent

# Or a quick CLI test
adk run demo_agent
```

Set `GOOGLE_API_KEY` in your shell before running locally:

```bash
export GOOGLE_API_KEY="your-key-here"
adk web demo_agent
```

---

## 5  Deploy to Agent Engine

Update the three constants near the top of `deploy.py`:

```python
DEFAULT_PROJECT        = "YOUR_GCP_PROJECT_ID"
DEFAULT_LOCATION       = "us-central1"          # must support Agent Engine
DEFAULT_STAGING_BUCKET = "gs://YOUR_STAGING_BUCKET"
```

Then run from the project root (the directory that contains `demo_agent/`):

```bash
python deploy.py \
  --project YOUR_GCP_PROJECT_ID \
  --location us-central1 \
  --staging-bucket gs://YOUR_STAGING_BUCKET \
  --display-name "Travel Planner Demo"
```

Deployment takes **3–8 minutes**. On success:

```
Deployment successful!
Resource name : projects/511354492757/locations/us-central1/reasoningEngines/123456789
```

**Save the resource name** — you need it to query or delete the agent.

---

## 6  Query the deployed agent

```bash
python query_agent.py \
  --project YOUR_GCP_PROJECT_ID \
  --resource-name "projects/511354492757/locations/us-central1/reasoningEngines/123456789" \
  --message "Plan a 3-day trip from New York to London in June. My hotel budget is \$200/night."
```

You can also use the **Playground** tab in the [Cloud Console](https://console.cloud.google.com/vertex-ai/agents) — open the agent, click **+ New Session**, and type a message.

> **Note:** The Playground currently shows the streaming response while it arrives,
> but may clear the display after the stream ends. This is a known limitation of
> the in-memory session service (see [Architecture Notes](#architecture-notes)).
> The agent works correctly when queried via the Python SDK.

---

## 7  What the demo agent does

The **Travel Planner** agent (`demo_agent/agent.py`) exposes four stub tools:

| Tool | Description |
|------|-------------|
| `search_flights` | Returns sample flights between two cities on a given date |
| `get_hotel_recommendations` | Filters hotels by city and nightly budget |
| `get_local_attractions` | Lists attractions filtered by category |
| `get_weather_forecast` | Returns a weather summary for a city and date |

The tools return hard-coded stub data. Replace each function body with a real API
call (Google Flights, Google Places, OpenWeatherMap, etc.) to make the agent
production-ready.

---

## 8  Customising the agent

- **Change the model** — edit `model=` in `demo_agent/agent.py`
  (e.g. `"gemini-2.5-pro-preview"`, `"gemini-3.1-pro-preview"`).
- **Add tools** — define a Python function with a descriptive docstring and add
  it to the `tools=` list in `root_agent`.
- **Add sub-agents** — use `google.adk.agents.Agent` with
  `sub_agents=[...]` for multi-agent workflows.
- **Add environment variables / secrets** — add entries to the `env_vars` dict
  in `deploy.py`. Use `SecretRef(secret="<name>", version="latest")` for secrets
  stored in Secret Manager, or plain strings for non-sensitive config.

---

## 9  Cleanup

### 9.1  Delete the deployed agent

```bash
python delete_agent.py \
  --project YOUR_GCP_PROJECT_ID \
  --resource-name "projects/511354492757/locations/us-central1/reasoningEngines/123456789"
```

The script retries automatically if another operation is still running on the
agent (up to ~10 minutes). Add `--force` to skip the confirmation prompt.

### 9.2  Delete the Secret Manager secret

```bash
gcloud secrets delete gemini-api-key \
  --project YOUR_GCP_PROJECT_ID
```

> **Note:** This permanently destroys all secret versions and their IAM bindings.
> There is no recovery after deletion.

### 9.3  Delete the staging GCS bucket

```bash
# Remove all objects first, then delete the bucket
gcloud storage rm -r gs://YOUR_STAGING_BUCKET
```

If you only want to remove the staging artefacts but keep the bucket:

```bash
gcloud storage rm "gs://YOUR_STAGING_BUCKET/**"
```

### 9.4  Revoke IAM bindings

If you granted roles specifically for this project and no longer need them:

```bash
PROJECT=YOUR_GCP_PROJECT_ID
EMAIL=YOUR_EMAIL

for ROLE in roles/aiplatform.user roles/storage.objectAdmin roles/secretmanager.admin; do
  gcloud projects remove-iam-policy-binding $PROJECT \
    --member="user:$EMAIL" \
    --role="$ROLE"
done
```

### 9.5  Disable GCP APIs (optional)

Only disable these if no other workloads in the project depend on them:

```bash
gcloud services disable \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  --project YOUR_GCP_PROJECT_ID
```

### 9.6  Automated cleanup script

`cleanup.py` runs all five steps in the correct order with a single command:

```bash
python cleanup.py \
  --project YOUR_GCP_PROJECT_ID \
  --resource-name "projects/511354492757/locations/us-central1/reasoningEngines/123456789" \
  --staging-bucket gs://YOUR_STAGING_BUCKET \
  --email YOUR_EMAIL
```

Each step prompts for confirmation before taking action. To skip all prompts:

```bash
python cleanup.py \
  --project YOUR_GCP_PROJECT_ID \
  --resource-name "projects/.../reasoningEngines/..." \
  --staging-bucket gs://YOUR_STAGING_BUCKET \
  --email YOUR_EMAIL \
  --force
```

To also disable the GCP APIs (only if no other workloads depend on them):

```bash
python cleanup.py ... --disable-apis
```

Any step can be skipped by omitting its flag:
- Omit `--resource-name` → skip agent deletion
- Omit `--email` → skip IAM binding revocation
- Omit `--disable-apis` → keep APIs enabled (default)

### 9.7  Manual cleanup order

If you prefer to run steps individually, do them in this order to avoid dependency errors:

1. Delete the deployed agent (`9.1`)
2. Delete the Secret Manager secret (`9.2`)
3. Delete the staging bucket (`9.3`)
4. Revoke IAM bindings (`9.4`)
5. Disable APIs if no longer needed (`9.5`)

---

## 10  Architecture notes

### Why `GeminiApiAdkApp` instead of the stock `AdkApp`

`gen-lang-client-*` projects (and any project that only has the Gemini API
enabled) hit two problems with the stock `AdkApp`:

| Problem | Root cause | Fix |
|---------|-----------|-----|
| **Model 404 at runtime** | `AdkApp.set_up()` hard-codes `GOOGLE_GENAI_USE_VERTEXAI=1`, so the ADK's `genai.Client` tries to reach Vertex AI publisher model serving, which is not enabled on these projects. | `GeminiApiAdkApp.set_up()` calls `super().set_up()` then immediately resets `GOOGLE_GENAI_USE_VERTEXAI=0`, forcing the client to use `generativelanguage.googleapis.com` with `GOOGLE_API_KEY`. |
| **Container crash on startup** | `AdkApp.set_up()` creates a `VertexAiSessionService`, which calls the Resource Manager API to resolve the project number. This API call fails in the container environment. | `session_service_builder=build_in_memory_session_service` is passed to `AdkApp`, bypassing `VertexAiSessionService` entirely. `GeminiApiAdkApp.project_id()` is also overridden to return the project string directly rather than calling the Resource Manager API. |

### `_AutoCreateSessionService`

The Playground reuses session IDs across deployments. When a session ID from a
previous (deleted) deployment is sent to a fresh container, the default
`InMemorySessionService` raises `SessionNotFoundError`. `_AutoCreateSessionService`
extends `InMemorySessionService` and overrides `get_session` to silently
create a new session when the requested one does not exist.

### Gemini API key injection

The key is stored in Secret Manager under the name `gemini-api-key`. The
`deploy.py` script passes it to Agent Engine as:

```python
env_vars = {
    "GOOGLE_API_KEY": SecretRef(secret="gemini-api-key", version="latest"),
}
```

Agent Engine resolves the `SecretRef` at container startup and injects the value
as the `GOOGLE_API_KEY` environment variable. The ADK's `genai.Client` picks it
up automatically (when `GOOGLE_GENAI_USE_VERTEXAI=0`).

### Telemetry

`GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true` is set in `env_vars` and
`enable_tracing=True` is passed to `GeminiApiAdkApp`. This enables Cloud Trace
integration and makes traces visible in the **Telemetry** tab of the Cloud
Console agent page.

---

## References

- [Vertex AI Agent Engine documentation](https://cloud.google.com/vertex-ai/generative-ai/docs/reasoning-engine/overview)
- [Google ADK documentation](https://google.github.io/adk-docs/)
- [Vertex AI Agent Engine Python SDK reference](https://cloud.google.com/python/docs/reference/aiplatform/latest/vertexai.agent_engines)
- [Secret Manager documentation](https://cloud.google.com/secret-manager/docs)
- [ADK error code 429](https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429)
