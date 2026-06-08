import asyncio
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

EMPTY_STATE: dict[str, Any] = {"tickets": {}, "runs": {}, "traces": {}, "approvals": {}, "audit_events": {}, "metrics": {"node_metrics": {}, "cost_usd": 0.0}}


class JsonStateStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = asyncio.Lock()

    async def load(self) -> dict[str, Any]:
        async with self._lock:
            return self._read()

    async def update(self, mutator: Callable[[dict[str, Any]], Any]) -> Any:
        async with self._lock:
            state = self._read()
            result = mutator(state)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
            tmp.replace(self.path)
            return result

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return deepcopy(EMPTY_STATE)
        loaded = json.loads(self.path.read_text(encoding="utf-8"))
        state = deepcopy(EMPTY_STATE)
        for key, value in loaded.items():
            if isinstance(value, dict) and isinstance(state.get(key), dict):
                state[key].update(value)
            else:
                state[key] = value
        return state

