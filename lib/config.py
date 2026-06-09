from pathlib import Path
from typing import Any, Dict, Union

import yaml

from .paths import resolve_path


def load_yaml(path: Union[str, Path]) -> Dict[str, Any]:
    with resolve_path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return {} if data is None else data
