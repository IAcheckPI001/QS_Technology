import json
from collections.abc import AsyncIterator
from typing import Any

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


class AnswerComposer:
    """Turn executed task results into one streamed provider answer per turn."""

    name = "answer_composer"

    def __init__(self, provider: OpenAIProvider) -> None:
        self._provider = provider

    def build_messages(self, state: RunState) -> list[dict[str, str]]:
        if state.context is None or state.analysis is None or state.plan is None:
            raise AnswerCompositionError(
                "answer_state_incomplete",
                "Answer composition requires context, analysis and an executed plan.",
            )

        sub_queries = {sub_query.id: sub_query for sub_query in state.analysis.sub_queries}
        task_results = []
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
            if result.error is not None:
                item["error"] = result.error.code
            task_results.append(item)

        parts = [
            f"<query>{state.context.query.origin}</query>",
            f"<task_results>{_j(task_results)}</task_results>",
        ]
        clarification = state.analysis.clarification
        if clarification is not None:
            parts.append(
                f"<clarification>{_j(clarification.model_dump(mode='json'))}</clarification>"
            )

        history = [
            {"role": message.role, "content": message.content}
            for message in state.context.conversation.history
        ]
        print([
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": "\n".join(parts)},
        ])
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": "\n".join(parts)},
        ]

    async def stream(self, state: RunState) -> AsyncIterator[str]:
        async for chunk in self._provider.stream_chat(self.build_messages(state)):
            yield chunk
