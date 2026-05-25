import logging
from memosima.db.store import Store

class SQLiteLogHandler(logging.Handler):
    def __init__(self, store: Store, workspace_id: str):
        super().__init__()
        self.store = store
        self.workspace_id = workspace_id

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Prevent infinite logging loops by ignoring db store operations
            if "store" in record.name or "db" in record.name or "sqlite" in record.name:
                return

            name = record.name.lower()
            component = "system"
            if "api" in name:
                component = "api"
            elif "worker" in name:
                component = "worker"
            elif "llm" in name or "openai" in name or "deepseek" in name or "provider" in name:
                component = "ai"
            elif "vector" in name:
                component = "vector"
            elif "mineru" in name or "parser" in name:
                component = "mineru"

            # Format the message
            msg = self.format(record)

            # Insert into database
            self.store.insert_system_log(
                workspace_id=self.workspace_id,
                level=record.levelname,
                component=component,
                message=msg,
            )
        except Exception:
            # Avoid crashing the application if logging fails
            self.handleError(record)
