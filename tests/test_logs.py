import logging
import pytest
from fastapi.testclient import TestClient

from memosima.api.app import create_app
from memosima.db.store import Store
from helpers import app_config_text, models_config_text, write_yaml

def test_sqlite_logging_handler_and_endpoints(tmp_path, monkeypatch):
    app_path = write_yaml(tmp_path / "app.yaml", app_config_text(tmp_path / "sidecar.db"))
    models_path = write_yaml(tmp_path / "models.yaml", models_config_text())
    monkeypatch.setenv("SIDECAR_ADMIN_TOKEN", "admin-token")

    # Initialize app (this registers the handler to logging.getLogger("memosima"))
    app = create_app(str(app_path), str(models_path))
    client = TestClient(app)
    
    store = app.state.store
    workspace_id = app.state.config.workspace_id

    # Set the memosima logger level to INFO to ensure info logs are captured in test environment
    logging.getLogger("memosima").setLevel(logging.INFO)

    # Emit logs under the memosima namespace
    logger_api = logging.getLogger("memosima.api.test")
    logger_ai = logging.getLogger("memosima.llm.openai")
    logger_parser = logging.getLogger("memosima.mineru.parser")
    
    logger_api.info("API Info Log message")
    logger_ai.warning("LLM Warning Log message")
    logger_parser.error("MinerU Parser Error Log message")
    
    # 1. Query directly via Store
    logs, total = store.get_system_logs(workspace_id=workspace_id)
    assert total >= 3
    
    # 2. Query via unauthorized API call
    unauth = client.get("/admin/logs")
    assert unauth.status_code == 401
    
    # 3. Query via authorized API call
    auth = client.get("/admin/logs", headers={"Authorization": "Bearer admin-token"})
    assert auth.status_code == 200
    data = auth.json()
    assert data["total_count"] >= 3
    
    # Verify components and levels are correctly classified and present
    components = [log["component"] for log in data["logs"]]
    levels = [log["level"] for log in data["logs"]]
    messages = [log["message"] for log in data["logs"]]
    
    assert "api" in components
    assert "ai" in components
    assert "mineru" in components
    
    assert "INFO" in levels
    assert "WARNING" in levels
    assert "ERROR" in levels
    
    assert any("API Info Log" in msg for msg in messages)
    assert any("LLM Warning Log" in msg for msg in messages)
    assert any("MinerU Parser Error Log" in msg for msg in messages)
    
    # 4. Test filter by level
    res_level = client.get(
        "/admin/logs?level=ERROR",
        headers={"Authorization": "Bearer admin-token"}
    )
    assert res_level.status_code == 200
    assert res_level.json()["total_count"] == 1
    assert res_level.json()["logs"][0]["level"] == "ERROR"
    assert "MinerU" in res_level.json()["logs"][0]["message"]
    
    # 5. Test filter by component
    res_comp = client.get(
        "/admin/logs?component=ai",
        headers={"Authorization": "Bearer admin-token"}
    )
    assert res_comp.status_code == 200
    assert res_comp.json()["total_count"] == 1
    assert res_comp.json()["logs"][0]["component"] == "ai"
    
    # 6. Test full-text search query filter
    res_query = client.get(
        "/admin/logs?query=Warning",
        headers={"Authorization": "Bearer admin-token"}
    )
    assert res_query.status_code == 200
    assert res_query.json()["total_count"] == 1
    assert "Warning" in res_query.json()["logs"][0]["message"]
    
    # 7. Test clear logs
    res_clear = client.post(
        "/admin/logs/clear",
        headers={"Authorization": "Bearer admin-token"}
    )
    assert res_clear.status_code == 200
    assert res_clear.json()["status"] == "ok"
    
    # Check that database logs were cleared
    res_after_clear = client.get(
        "/admin/logs",
        headers={"Authorization": "Bearer admin-token"}
    )
    assert res_after_clear.status_code == 200
    assert res_after_clear.json()["total_count"] == 0
