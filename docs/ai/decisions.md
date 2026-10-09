## Chat history persistence

- The persistence model is `ChatHistory`, mapped to the existing Supabase
  `public.chat_history` table.
- Database access remains behind `HistoryRepository` and
  `ChatbotService`; FastAPI routes only perform dependency wiring and SSE
  transport.
- A request without `session_id` receives a backend-generated UUID. The ID is
  returned in the existing SSE `done` event and stored by the frontend for
  subsequent requests.
- Completed streams write `status='completed'`; provider failures write
  `status='error'`.
- History read endpoint integration is deferred. When enabled, session-only
  reads are limited to local/test environments until server-issued
  visitor-token or authenticated-user ownership checks are implemented.