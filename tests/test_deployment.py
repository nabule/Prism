from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def _caddyfile() -> str:
    return (ROOT / "gateway" / "Caddyfile").read_text(encoding="utf-8")


def test_compose_exposes_only_gateway_port_by_default():
    services = _compose()["services"]

    assert "gateway" in services
    assert services["gateway"]["image"] == "caddy:2.10.2"
    assert services["gateway"]["ports"] == ["${GATEWAY_PORT:-8080}:80"]
    assert "ports" not in services["memos"]
    assert "ports" not in services["sidecar"]


def test_caddy_routes_sidecar_paths_and_memos_root():
    caddyfile = _caddyfile()

    assert "handle /admin/*" in caddyfile
    assert "handle /health" in caddyfile
    assert "handle /webhooks/*" in caddyfile
    assert caddyfile.count("reverse_proxy sidecar:8080") >= 3
    assert "reverse_proxy memos:5230" in caddyfile
