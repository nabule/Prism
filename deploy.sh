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
  trigger_tag: '#提醒'
  webhook_url_env: REMINDER_WEBHOOK_URL
  confidence_threshold: 0.75
  request_timeout_seconds: 10
vector_search:
  enabled: false
  api_key_env: SILICONFLOW_API_KEY
  base_url: https://api.siliconflow.cn/v1
  model: BAAI/bge-m3
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

# 3.2 释放内建 models.yaml 模型初始配置文件
if [ ! -f config/models.yaml ]; then
    echo -e "${GREEN}[3.1/5] 正在生成初始系统模型配置文件 config/models.yaml...${NC}"
    cat << 'EOF' > config/models.yaml
default_provider: deepseek
providers:
  openrouter:
    base_url: https://openrouter.ai/api/v1
    api_key_env: OPENROUTER_API_KEY
    default_model: google/gemma-3-27b-it
    temperature: 0.2
    max_tokens: null
    response_format: json_object
    extra_body: {}
  openai:
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
    default_model: gpt-4o-mini
    temperature: 0.2
    max_tokens: null
    response_format: json_object
    extra_body: {}
  deepseek:
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY
    default_model: deepseek-v4-flash
    temperature: 0.2
    max_tokens: null
    response_format: json_object
    extra_body:
      thinking:
        type: enabled
EOF
else
    echo -e "${YELLOW}[-] 检测到 config/models.yaml 已存在，跳过生成。${NC}"
fi

# 3.3 释放内建 prompts.yaml 系统初始提示词文件
if [ ! -f config/prompts.yaml ]; then
    echo -e "${GREEN}[3.2/5] 正在生成初始系统提示词文件 config/prompts.yaml...${NC}"
    cat << 'EOF' > config/prompts.yaml
organize_memo:
  system: "你是个人知识库整理助手。请只输出 JSON 对象，不要输出 Markdown 代码块。\n必须优先从已有正式标签中选择 active_tags。\n\
    只选择与正文核心主题直接相关的少量标签，active_tags 通常不超过 5 个。\n只有正文确实需要且没有合适正式标签时，才在 candidate_tags\
    \ 中提出新标签；不要把新标签放入 active_tags，candidate_tags 通常不超过 2 个。\n不同层级的业务标签必须保证最后一级名称唯一，例如已有\
    \ #项目/数管 时，不要再提出 #数管 或 #其他/数管。\n如果内容指代不明或缺少关键信息，将 needs_clarification 设为 true，并给出\
    \ clarification_question。\nJSON 字段：title, summary, key_points, todos, active_tags,\
    \ candidate_tags, needs_clarification, clarification_question。\ncandidate_tags\
    \ 每项字段：path, reason, confidence。标签 path 必须以 # 开头，不含空格。\n已有正式标签：\n{active_tags}\n\
    \n除非 memo 内容为空、无法识别任何主题，或缺少完成整理所必需的信息，否则 needs_clarification 必须为 false。\n  如果原文是问题、排障记录、测试步骤、URL、待验证事项，不要因为它包含疑问句就要求澄清；应直接整理为\
    \ summary、key_points、\n  todos。\n  clarification_question 仅在 needs_clarification=true\
    \ 时填写，否则必须为 null。"
  user: '请整理以下 memo，并遵守本地标签治理草案，对于URL连接需要获取真实内容并分析，所有内容主要语言为中文，你需要完整全面的整理原始memo内容，树形风格，有条理。


    本地标签治理草案：

    {local_plan_json}


    原始 memo：

    {content}'
tag_summary:
  system: "你是个人知识库专题整理助手。请输出 Markdown，不要输出 JSON。\n目标是把同一标签下零散 memo 整理成适合人阅读的整体展示。\n\
    请保留事实边界，不要编造未出现的信息。\n建议结构：总览、关键主题、时间线或进展、已完成、问题与风险、待办、相关 memo。\n要详实、有条理有框架，完整体系化的总结，树形风格。\n\
    除非 memo 内容为空、无法识别任何主题，或缺少完成整理所必需的信息，否则 needs_clarification 必须为 false。\n  如果原文是问题、排障记录、测试步骤、URL、待验证事项，不要因为它包含疑问句就要求澄清；应直接整理为\
    \ summary、key_points、\n  todos。\n  clarification_question 仅在 needs_clarification=true\
    \ 时填写，否则必须为 null。"
  user: '请为标签 {tag} 生成整体总结，对于URL连接需要获取真实内容并分析。


    memo 数量：{memo_count}


    memo 列表：

    {memos_markdown}'
reminder_extraction:
  system: 你是提醒时间抽取器，只返回 JSON 对象，不要输出 Markdown。只处理用户明确使用触发标签的提醒请求。把相对时间换算成带时区的 ISO
    8601 时间；无法确定具体时间时要求澄清。
  user: '触发标签：{trigger_tag}

    当前时间：{now}

    默认时区：{timezone}


    请返回 JSON：

    {"has_reminder": boolean, "items": [{"title": string, "body": string, "due_at":
    string, "timezone": string, "confidence": number, "raw_text": string}], "needs_clarification":
    boolean, "clarification_question": string|null}


    规则：

    - 只有正文包含触发标签时才提取提醒。

    - due_at 必须是可解析的 ISO 8601 时间，优先包含时区偏移。

    - 如果只有日期没有具体时刻、时间已无法确定或语义模糊，needs_clarification=true。

    - title 简短概括提醒事项，body 保留必要上下文。


    memo 内容：

    {content}'
EOF
else
    echo -e "${YELLOW}[-] 检测到 config/prompts.yaml 已存在，跳过生成。${NC}"
fi

# 3.4 释放内建 taxonomy.yaml 系统初始标签体系配置文件
if [ ! -f config/taxonomy.yaml ]; then
    echo -e "${GREEN}[3.3/5] 正在生成初始标签治理配置文件 config/taxonomy.yaml...${NC}"
    cat << 'EOF' > config/taxonomy.yaml
system_tags:
  original: "#系统/原始记录"
  ai_summary: "#系统/AI整理"
  ai_document: "#系统/AI文档"
  pending_clarification: "#系统/待澄清"
  tag_candidate: "#系统/标签待审核"
  qa: "#系统/问答"
  failed: "#系统/处理失败"
business_tags:
  - path: "#项目/个人AI知识库"
    status: active
aliases:
  - alias: "#AI知识库"
    target: "#项目/个人AI知识库"
disabled:
  - "#杂项"
EOF
else
    echo -e "${YELLOW}[-] 检测到 config/taxonomy.yaml 已存在，跳过生成。${NC}"
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
    image: caddy:2.10.2
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
    image: neosmemo/memos:stable
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
