import logging
import sys
from contextvars import ContextVar
from uuid import uuid4

trace_id_context: ContextVar[str] = ContextVar("trace_id", default="")


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_context.get() or "no-trace"
        return True


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s trace_id=%(trace_id)s %(message)s"))
    handler.addFilter(TraceIdFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def new_trace_id() -> str:
    return str(uuid4())


def set_trace_id(trace_id: str) -> None:
    trace_id_context.set(trace_id)

