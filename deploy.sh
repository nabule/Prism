#!/bin/bash
# Prism (棱镜) - 容器化一键部署与升级控制脚本
set -e

# 字体颜色控制
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Docker Compose 引擎智能检测
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif docker-compose --version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}错误: 未检测到 docker compose 或 docker-compose！请先安装 Docker Compose。${NC}"
    exit 1
fi

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}       Prism (棱镜) AI 知识库一键部署工具       ${NC}"
echo -e "${BLUE}===============================================${NC}"

# 1. 确保必要目录结构存在
echo -e "${GREEN}[1/5] 正在检查并初始化目录结构...${NC}"
mkdir -p config data/memos data/sidecar logs/caddy gateway

# 2. 释放内建 Caddyfile 代理配置文件
if [ ! -f gateway/Caddyfile ]; then
    echo -e "${GREEN}[2/5] 正在生成网关 Caddyfile...${NC}"
    cat << 'EOF' > gateway/Caddyfile
:80 {
	handle /admin/* {
		reverse_proxy sidecar:8080
	}

	handle /health {
		reverse_proxy sidecar:8080
	}

	handle /webhooks/* {
		reverse_proxy sidecar:8080
	}

	handle {
		reverse_proxy memos:5230
	}
}
EOF
else
    echo -e "${YELLOW}[-] 检测到 gateway/Caddyfile 已存在，跳过生成。${NC}"
fi

# 3. 释放内建 app.yaml 系统初始配置文件
if [ ! -f config/app.yaml ]; then
    echo -e "${GREEN}[3/5] 正在生成初始系统配置文件 config/app.yaml...${NC}"
    cat << 'EOF' > config/app.yaml
app:
  workspace_id: default
  public_base_url: http://localhost:8085
  timezone: Asia/Shanghai
database:
  path: data/sidecar/sidecar.db
taxonomy:
  path: config/taxonomy.yaml
prompts:
  path: config/prompts.yaml
security:
  admin_token_env: SIDECAR_ADMIN_TOKEN
memos:
  base_url_env: MEMOS_BASE_URL
  api_token_env: MEMOS_API_TOKEN
  webhook_url_env: MEMOS_WEBHOOK_URL
  request_timeout_seconds: 15
  ingestion_mode: poll
  poll_page_size: 20
  show_candidate_tags: false
  admin_entry_enabled: true
  admin_entry_title: Memosima 管理入口
  admin_entry_visibility: PRIVATE
document_parser:
  provider: mineru
  token_env: MINERU_API_TOKEN
  base_url: https://mineru.net
  timeout_seconds: 60
  poll_interval_seconds: 3
  max_polls: 60
  mineru_model_version: vlm
  language: ch
  enable_table: true
  enable_formula: true
  is_ocr: false
reminders:
  enabled: true
  trigger_tag: "#提醒"
  webhook_url_env: REMINDER_WEBHOOK_URL
  confidence_threshold: 0.75
  request_timeout_seconds: 10
worker:
  poll_interval_seconds: 2
  max_attempts: 3
  create_probe_comment: false
limits:
  max_attachment_mb: 50
  max_ai_active_tags: 5
  max_ai_candidate_tags: 2
  allowed_parse_extensions:
    - .txt
    - .md
    - .doc
    - .docx
    - .xls
    - .xlsx
    - .ppt
    - .pptx
    - .pdf
    - .drawio
    - .drawio.svg
    - .json
EOF
else
    echo -e "${YELLOW}[-] 检测到 config/app.yaml 已存在，跳过生成。${NC}"
fi

# 4. 生成安全密钥与环境变量文件
if [ ! -f .env ]; then
    echo -e "${GREEN}[4/5] 正在生成安全密钥文件 .env...${NC}"
    # 自动生成 16 字节随机密码作为管理 Token
    AUTO_ADMIN_TOKEN=$(openssl rand -hex 16 2>/dev/null || echo "token_$(date +%s)_$RANDOM")
    cat << EOF > .env
# Memosima Sidecar Admin Token
# 请在访问 http://localhost:8085/admin/ui 时输入该 Token 进行认证
SIDECAR_ADMIN_TOKEN=${AUTO_ADMIN_TOKEN}

# Memos 与大模型配置，可在 Sidecar 管理界面热更新
MEMOS_BASE_URL=http://memos:5230
MEMOS_API_TOKEN=
DEEPSEEK_API_KEY=
EOF
    echo -e "${GREEN}>>> 已为您自动生成安全的 Admin Token: ${BLUE}${AUTO_ADMIN_TOKEN}${NC}"
    echo -e "${GREEN}>>> 密钥已写入 .env 文件中，请妥善保管！${NC}"
else
    echo -e "${YELLOW}[-] 检测到 .env 文件已存在，跳过生成。${NC}"
fi

# 释放内建 docker-compose.release.yml 配置文件
if [ ! -f docker-compose.release.yml ]; then
    echo -e "${GREEN}[-] 正在释放容器编排文件 docker-compose.release.yml...${NC}"
    cat << 'EOF' > docker-compose.release.yml
services:
  gateway:
    image: xget.your-domain.com/cr/docker/library/caddy:2.10.2
    container_name: memosima-gateway
    restart: unless-stopped
    depends_on:
      - memos
      - sidecar
    ports:
      - "${GATEWAY_PORT:-8085}:80"
    volumes:
      - ./gateway/Caddyfile:/etc/caddy/Caddyfile:ro
      - ./data/caddy:/data
      - ./logs/caddy:/var/log/caddy

  memos:
    image: xget.your-domain.com/cr/docker/neosmemo/memos:stable
    container_name: memosima-memos
    restart: unless-stopped
    volumes:
      - ./data/memos:/var/opt/memos
    environment:
      MEMOS_PORT: 5230
      MEMOS_DRIVER: sqlite

  sidecar:
    image: ghcr.io/nabule/prism:${PRISM_VERSION:-latest}
    container_name: memosima-sidecar
    restart: unless-stopped
    depends_on:
      - memos
    env_file:
      - .env
    environment:
      MEMOS_BASE_URL: http://memos:5230
    volumes:
      - ./config:/app/config
      - ./data/sidecar:/app/data/sidecar
      - ./logs:/app/logs

  sidecar-worker:
    image: ghcr.io/nabule/prism:${PRISM_VERSION:-latest}
    container_name: memosima-sidecar-worker
    restart: unless-stopped
    depends_on:
      - memos
      - sidecar
    env_file:
      - .env
    environment:
      MEMOS_BASE_URL: http://memos:5230
    volumes:
      - ./config:/app/config
      - ./data/sidecar:/app/data/sidecar
      - ./logs:/app/logs
    command: memosima-worker
EOF
fi

# 5. 一键拉取与热启动
echo -e "${GREEN}[5/5] 正在拉取最新的生产容器镜像...${NC}"
$DOCKER_COMPOSE -f docker-compose.release.yml pull

echo -e "${GREEN}>>> 正在拉起全栈 Docker 容器服务...${NC}"
$DOCKER_COMPOSE -f docker-compose.release.yml up -d

echo -e "${BLUE}===============================================${NC}"
echo -e "${GREEN}        🎉 Prism (棱镜) 部署成功！             ${NC}"
echo -e "${BLUE}===============================================${NC}"
echo -e "${GREEN}网关宿主机入口: ${YELLOW}http://localhost:${GATEWAY_PORT:-8085}${NC}"
echo -e "${GREEN}AI 管理端地址:  ${YELLOW}http://localhost:${GATEWAY_PORT:-8085}/admin/ui${NC}"
if [ -f .env ]; then
    CURRENT_TOKEN=$(grep -E "^SIDECAR_ADMIN_TOKEN=" .env | cut -d'=' -f2-)
    echo -e "${GREEN}您的管理 Token:  ${BLUE}${CURRENT_TOKEN}${NC}"
fi
echo -e "${BLUE}===============================================${NC}"
echo -e "${YELLOW}提示: 如果第一次运行，请通过网关注册 Memos 账号，然后在管理端配置对应密钥即可！${NC}"
