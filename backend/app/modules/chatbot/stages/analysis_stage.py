

from app.modules.chatbot.schemas.system import RunContext
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.analysis.analyzer import QueryAnalyzer
from app.modules.chatbot.analysis.prompt.registry_render import _j

class AnalysisStage:
    name = "analysis_stage"

    def __init__(
        self,
        provider: OpenAIProvider,
        n_examples: int = 4
    ) -> None:
        self.analyzer = QueryAnalyzer(provider=provider, n_examples=n_examples)
    
    def build_context_analysis(self, context: RunContext) -> str:
        parts = []
        history = [
            {"role": item.role, "content": item.content}
            for item in context.conversation.history
        ]
        query = context.query.origin
        state = context.conversation.state
        if state and state.last_models:
            parts.append(f"<state>{_j({'last_models': state.last_models})}</state>")
        if history:
            parts.append(f"<history>\n{history}\n</history>")
        parts.append(f"<query>{query}</query>")
        return "\n".join(parts)

    async def execute(self, context: RunContext) -> dict:

        context_analysis = self.build_context_analysis(context)

        return await self.analyzer.analyze_raw(context_analysis)