import json
from collections.abc import AsyncIterator
from typing import Any

from app.modules.chatbot.extraction.validate_registry import display_name
from app.modules.chatbot.orchestration import collect_results
from app.modules.chatbot.prompts import SYSTEM_PROMPT
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.schemas.system import RunState


class AnswerCompositionError(RuntimeError):
    """The final answer prompt could not be built from the run state."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _pages(start: int | None, end: int | None) -> str | None:
    if start is None:
        return None
    return str(start) if end is None or end == start else f"{start}-{end}"


class AnswerComposer:
    """Turn executed task results into one streamed provider answer per turn."""

    name = "answer_composer"

    def __init__(self, provider: OpenAIProvider, source_char_limit: int = 3000) -> None:
        self._provider = provider
        # Chặn một chunk cha quá dài chiếm hết context của câu trả lời.
        self._source_char_limit = source_char_limit

    def build_messages(self, state: RunState) -> list[dict[str, str]]:
        if state.context is None or state.analysis is None or state.plan is None:
            raise AnswerCompositionError(
                "answer_state_incomplete",
                "Answer composition requires context, analysis and an executed plan.",
            )

        sub_queries = {sub_query.id: sub_query for sub_query in state.analysis.sub_queries}
        task_results = []
        sources = []
        for task, result in zip(state.plan.tasks, collect_results(state.plan)):
            item: dict[str, Any] = {
                "task_id": task.task_id,
                "kind": task.kind.value,
                "status": result.status.value,
                "queries": [
                    sub_queries[sub_query_id].standalone_query
                    for sub_query_id in task.sub_query_ids
                    if sub_query_id in sub_queries
                ],
            }
            if result.metadata:
                item["metadata"] = result.metadata
            inherited = [
                warning.split(":", 1)[1]
                for sub_query_id in task.sub_query_ids
                if sub_query_id in sub_queries
                for warning in sub_queries[sub_query_id].warnings
                if warning.startswith("inherited_model:")
            ]
            if inherited:
                item["context_model"] = display_name(inherited[0])
            if result.error is not None:
                item["error"] = result.error.code
            task_results.append(item)

            if result.retrieval is None:
                continue
            for sub_result in result.retrieval.results:
                sub_query = sub_queries.get(sub_result.sub_query_id)
                if sub_query is None:
                    continue
                answer_mode = (
                    sub_query.retrieval_scope.answer_mode
                    if sub_query.retrieval_scope is not None
                    else "full"
                )
                sources.append({
                    "query": sub_query.standalone_query,
                    "answer_mode": answer_mode,
                    "sources": [
                        {
                            "source_id": hit.source_id,
                            "section": " › ".join(hit.section_path) or hit.section_title,
                            "pages": _pages(hit.page_start, hit.page_end),
                            "content": hit.content[: self._source_char_limit],
                        }
                        for hit in sub_result.hits
                    ],
                })

        parts = [
            f"<language>{state.context.query.language}</language>",
            f"<query>{state.context.query.origin}</query>",
            f"<task_results>{_j(task_results)}</task_results>",
        ]
        if sources:
            parts.append(f"<sources>{_j(sources)}</sources>")
        clarification = state.analysis.clarification
        if clarification is not None:
            payload = clarification.model_dump(mode="json")
            payload["display_candidates"] = {
                key: [display_name(model) for model in models]
                for key, models in clarification.candidates.items()
            }
            parts.append(f"<clarification>{_j(payload)}</clarification>")

        history = [
            {"role": message.role, "content": message.content}
            for message in state.context.conversation.history[-2:]
        ]
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": "\n".join(parts)},
        ]

    async def stream(self, state: RunState) -> AsyncIterator[str]:
        async for chunk in self._provider.stream_chat(self.build_messages(state)):
            yield chunk
