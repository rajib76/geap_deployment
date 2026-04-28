"""Custom AdkApp that uses the Gemini API instead of Vertex AI.

Two problems with the stock AdkApp on gen-lang-client-* projects:
1. set_up() hard-codes GOOGLE_GENAI_USE_VERTEXAI=1, causing 404s because
   this project type only has generativelanguage.googleapis.com enabled.
2. set_up() creates VertexAiSessionService, which calls the Resource Manager
   API to resolve project numbers and crashes on startup.

Fixes:
- Pass build_in_memory_session_service as session_service_builder to skip
  VertexAiSessionService entirely.
- Override set_up() to reset GOOGLE_GENAI_USE_VERTEXAI=0 after super() runs,
  so the ADK's genai.Client is created with vertexai=False and picks up
  GOOGLE_API_KEY (injected at runtime from Secret Manager) instead.
"""

import os

from google.adk.sessions.in_memory_session_service import InMemorySessionService
from vertexai.agent_engines import AdkApp


class _AutoCreateSessionService(InMemorySessionService):
    """InMemorySessionService that auto-creates a session when the requested one is not found.

    This prevents SessionNotFoundError when the Playground reuses a session ID
    from a previous deployment that no longer exists in memory.
    """

    async def get_session(self, *, app_name, user_id, session_id, **kwargs):
        session = await super().get_session(
            app_name=app_name, user_id=user_id, session_id=session_id, **kwargs
        )
        if session is None:
            session = await super().create_session(
                app_name=app_name, user_id=user_id, session_id=session_id
            )
        return session


def build_in_memory_session_service():
    """Returns an _AutoCreateSessionService; module-level so it is picklable."""
    return _AutoCreateSessionService()


class GeminiApiAdkApp(AdkApp):
    """AdkApp that routes model calls through the Gemini API (not Vertex AI)."""

    def project_id(self):
        # AdkApp.project_id() calls resource_manager_utils.get_project_id()
        # which can raise exceptions beyond PermissionDenied/Unauthenticated
        # (e.g. NotFound, network errors) that crash set_up() in the container.
        # Return the project string directly — it's already a human-readable ID.
        return self._tmpl_attrs.get("project")

    def set_up(self) -> None:
        super().set_up()
        # super().set_up() forces GOOGLE_GENAI_USE_VERTEXAI=1.
        # Reset it so the ADK's genai.Client is created with vertexai=False
        # and uses GOOGLE_API_KEY (injected via SecretRef) instead.
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "0"
