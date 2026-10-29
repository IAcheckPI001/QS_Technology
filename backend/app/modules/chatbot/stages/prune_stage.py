

from collections.abc import Callable

from app.util.token_counter import count_tokens
from app.modules.chatbot.schemas.system import (
    Conversation,
    RunContext
)
from app.modules.chatbot.stages.errors import ContextBudgetError, ContextConfigurationError

class Prune:
    name = "prune"

    def __init__(
        self,
        token_budget: int,
        # (context, model) -> số token; model quyết định bảng mã tiktoken.
        token_counter: Callable[[RunContext, str], int] | None = None,
    ) -> None:
        if token_budget <= 0:
            raise ContextConfigurationError("context token budget must be positive")
        self._token_budget = token_budget
        self._token_counter = token_counter or self.estimate_context_tokens
    
    def estimate_context_tokens(self, context: RunContext, model: str) -> int:
        text = context.query.origin
        if context.conversation.summary:
            text += context.conversation.summary
        text += "".join(message.content for message in context.conversation.history)
        
        return count_tokens(text, model)

    def execute(self, context: RunContext, model: str) -> RunContext:
        if self._token_counter(context, model) <= self._token_budget:
            return context
        history = list(context.conversation.history)
        while self._token_counter(context, model) > self._token_budget and len(history) > 2:
            first_id = history[0].message_id.rsplit(":", 1)[0]
            
            remove_count = 1

            if len(history) > 1 and history[1].message_id.startswith(f"{first_id}:"):
                remove_count = 2

            if len(history) - remove_count < 2:
                break
            
            history = history[remove_count:]
            
            context = context.model_copy(update={
                "conversation": context.conversation.model_copy(update={"history": history}),
            })
        if self._token_counter(context, model) > self._token_budget:
            raise ContextBudgetError("mandatory context exceeds token budget")
        return context
