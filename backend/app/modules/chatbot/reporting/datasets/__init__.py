"""Dataset báo cáo đã đăng ký. Thêm dataset: khai báo DatasetSpec và thêm vào DATASETS."""

from ..catalog import DatasetSpec
from .assignments import ASSIGNMENTS
from .customers import CUSTOMERS
from .deliveries import DELIVERIES
from .tickets import TICKETS

DATASETS: dict[str, DatasetSpec] = {
    spec.name: spec for spec in (TICKETS, CUSTOMERS, ASSIGNMENTS, DELIVERIES)
}

__all__ = ["DATASETS"]
