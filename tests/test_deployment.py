from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def _caddyfile() -> str:
    return (ROOT / "gateway" / "Caddyfile").read_text(encoding="utf-8")


def _deploy_script() -> str:
    return (ROOT / "deploy.sh").read_text(encoding="utf-8")


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


def test_deploy_writes_public_base_url_env_and_recreates_sidecar_services():
    script = _deploy_script()

    assert 'REQUESTED_PUBLIC_BASE_URL="${PRISM_PUBLIC_BASE_URL:-}"' in script
    assert 'if [ -n "$REQUESTED_PUBLIC_BASE_URL" ]; then' in script
    assert 'PUBLIC_BASE_URL="${REQUESTED_PUBLIC_BASE_URL%/}"' in script
    assert 'PUBLIC_BASE_URL="http://${PUBLIC_HOST}:${GATEWAY_PORT}"' in script
    assert "^PRISM_PUBLIC_BASE_URL=" in script
    assert "PRISM_PUBLIC_BASE_URL=${PUBLIC_BASE_URL}" in script
    assert "已写入公开访问地址" in script
    assert "$DOCKER_COMPOSE -f docker-compose.release.yml up -d sidecar sidecar-worker" in script


def test_deploy_writes_public_base_url_before_starting_containers():
    script = _deploy_script()

    write_call = script.index("write_public_base_url_env")
    pull_step = script.index("[4/6] 拉取生产镜像")
    up_step = script.index("[5/6] 拉起全栈容器")

    assert write_call < pull_step < up_step
