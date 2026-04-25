from contextvars import ContextVar

request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx_var: ContextVar[int | None] = ContextVar("user_id", default=None)
