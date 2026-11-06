"""Dataset báo cáo đã đăng ký. Thêm dataset: khai báo DatasetSpec và thêm vào DATASETS."""

from ..catalog import DatasetSpec
from .tickets import TICKETS

DATASETS: dict[str, DatasetSpec] = {spec.name: spec for spec in (TICKETS,)}

__all__ = ["DATASETS"]
