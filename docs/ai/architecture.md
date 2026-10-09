

# Overview architecture

Client
  ↓
API Router
  ↓
Chat Service
  ↓
Context / Session
  ↓
SecurityStage
  ↓
Agent / Orchestrator
  ↓
LLM Provider
  ↓
Tools / Retrieval
  ↓
Response

## Chat Module

Path:
app/modules/chatbot/

Responsibility:
- Validate chatbot requests
- Start/continue sessions
- Invoke chatbot orchestration
- Convert internal result into API response

Does not own:
- LLM provider implementation
- Database repository implementation
- Prompt authoring

Main entry points:
- router.py
- services/*.py
- schemas/*.py
- schemas/system/*.py
- schemas/channels/*.py
- stages/*.py

Security boundary:
- Schema validation and session authorization happen before `SecurityStage`.
- `SecurityStage` runs before context, retrieval and the LLM provider.
- Blocked requests do not call the provider and are not recorded as completed.
- Detector and policy logic stays in `modules/chatbot/stages/security/`; routers
  only map the decision to transport responses.

Dependencies:
- provider layer
- session/context layer

