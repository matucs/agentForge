import os

import yaml
from pydantic import ValidationError

from app.evaluation.schemas import EvalTask


class EvalTaskLoadError(RuntimeError):
    pass


def load_tasks(tasks_dir: str) -> list[EvalTask]:
    tasks: list[EvalTask] = []
    for filename in sorted(os.listdir(tasks_dir)):
        if not filename.endswith((".yaml", ".yml")):
            continue
        path = os.path.join(tasks_dir, filename)
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        try:
            tasks.append(EvalTask.model_validate(raw))
        except ValidationError as exc:
            raise EvalTaskLoadError(f"{filename} is not a valid eval task: {exc}") from exc
    return tasks
