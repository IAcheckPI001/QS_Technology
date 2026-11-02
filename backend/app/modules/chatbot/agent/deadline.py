import time
from collections.abc import Callable


class Deadline:
    """Hạn chót chung của một lượt agent.

    Mọi lời gọi LLM/tool lấy timeout từ đây, nên tổng thời gian không vượt
    timeout của lượt dù mỗi lời gọi có giới hạn riêng. `reserve_s` giữ lại thời
    gian cho bước trả lời cuối.
    """

    def __init__(self, timeout_s: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._end = clock() + timeout_s

    def remaining(self) -> float:
        return max(0.0, self._end - self._clock())

    def budget(self, limit_s: float, reserve_s: float = 0.0) -> float:
        """Timeout cho một lời gọi: không quá giới hạn riêng, chừa reserve_s cho bước cuối."""
        return min(limit_s, self.remaining() - reserve_s)
