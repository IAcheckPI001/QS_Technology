
from __future__ import annotations

from typing import Any, Iterable

HISTORY_TURNS = 6            # số message gần nhất đưa cho bộ phân tích
ASSISTANT_MAX_CHARS = 300    # câu trả lời của bot chỉ cần phần đầu để hiểu ngữ cảnh


def _msg(m: Any) -> tuple[str, str]:
    """Nhận dict {'role','content'} hoặc object có .role/.content (ConversationMessage)."""
    if isinstance(m, dict):
        return m["role"], m["content"]
    return m.role, m.content

def build_context_analysis(query: str, history: Iterable[Any] | None = None,
                       state: dict | None = None) -> str:
    parts = []
    for m in list(history or []):
        role, content = _msg(m)
        content = " ".join(str(content).split())
        if role == "assistant" and len(content) > ASSISTANT_MAX_CHARS:
            content = content[:ASSISTANT_MAX_CHARS] + "…"
        turns.append(f"{role}: {content}")
    if state and state.last_models:
        parts.append(f"<state>{_j({'last_models': state.last_models})}</state>")
    if turns:
        parts.append("<history>\n" + "\n".join(turns) + "\n</history>")
    parts.append(f"<query>{query}</query>")
    return "\n".join(parts)