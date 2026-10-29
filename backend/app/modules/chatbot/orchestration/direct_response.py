from app.modules.chatbot.prompts.direct_responses import has_direct_response
from app.modules.chatbot.schemas.system import ExecutionPlan, TaskKind

DIRECT_KINDS = frozenset({TaskKind.CHITCHAT, TaskKind.OUT_OF_SCOPE})


def select_direct_response_code(plan: ExecutionPlan, language: str = "vi") -> str | None:
    """Return a fixed-response code when the turn needs no answer LLM.

    Fixed replies exist only for some languages; for any other language the
    turn goes through AnswerComposer, which has the same chitchat/out_of_scope/
    handoff rules and answers in the user's language.
    """
    if not has_direct_response(language):
        return None
    kinds = {task.kind for task in plan.tasks}
    if kinds <= DIRECT_KINDS:
        return "out_of_scope" if TaskKind.OUT_OF_SCOPE in kinds else "chitchat"
    if kinds == {TaskKind.HANDOFF}:
        result = plan.tasks[0].result
        reason = result.metadata.get("handoff_reason") if result else None
        return f"handoff.{reason or 'human_request'}"
    return None
