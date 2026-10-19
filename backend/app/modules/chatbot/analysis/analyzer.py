
import json
import asyncio
import logging
from typing import Any

from app.modules.chatbot.schemas.system import Analysis
from app.modules.chatbot.extraction.validate_registry import resolve, plan_turn
from app.modules.chatbot.extraction.schema_builder import build_output_schema
from app.modules.chatbot.providers.openai import OpenAIProvider
from app.modules.chatbot.analysis.prompt.prompt_builder import build_analysis_prompt

log = logging.getLogger(__name__)


class AnalysisError(RuntimeError):
    """Analysis could not produce a valid typed plan."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class QueryAnalyzer:
    def __init__(
        self,
        provider: OpenAIProvider,
        n_examples: int = 4,
        timeout_s: float = 8.0
    ) -> None:
        self._provider = provider
        self._prompt = build_analysis_prompt(n_examples=n_examples)
        self._timeout = timeout_s

    def _coerce(self, resp: Any) -> dict | None:
        """Provider có thể trả dict, chuỗi JSON, hoặc chuỗi bị cắt do max_tokens."""
        if isinstance(resp, str):
            try:
                resp = json.loads(resp)
            except json.JSONDecodeError:
                return None
        if isinstance(resp, dict) and isinstance(resp.get("sub_queries"), list):
            return resp
        return None
    
    async def analyze(self, context_analysis: str) -> Analysis:
        RESPONSE_FORMAT = {
            "type": "json_schema",
            "json_schema": {"name": "query_analysis", "strict": True, "schema": build_output_schema()},
        }
        messages=[
            {"role": "system", "content": self._prompt},
            {"role": "user", "content": context_analysis},
        ]
        try:
            resp = await asyncio.wait_for(
                self._provider.chat_complete_json(messages=messages,
                                                  response_format=RESPONSE_FORMAT),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            log.warning("query_analysis timeout")
            raise AnalysisError("analysis_timeout", "Query analysis timed out.")
        except Exception as exc:
            log.exception("query_analysis provider error")
            raise AnalysisError("analysis_provider_error", "Query analysis failed.") from exc
 
        data = self._coerce(resp)
        if data is None:
            log.warning("query_analysis invalid output")
            raise AnalysisError("analysis_invalid_output", "Query analysis returned invalid output.")

        try:
            return Analysis.from_plan(plan_turn(resolve(data)))
        except (TypeError, ValueError, KeyError) as exc:
            log.warning("query_analysis plan validation failed")
            raise AnalysisError("analysis_invalid_plan", "Query analysis plan is invalid.") from exc


    

    