#!/bin/bash
# Prism (棱镜) - 容器化一键部署与升级控制脚本
# 设计原则：
#   1. 所有默认配置文件由仓库统一管理（config/、gateway/、docker-compose.release.yml），
#      脚本只负责"释放/下载"，不再内嵌 heredoc，避免脚本与仓库分歧。
#   2. 部署后自动生成 SIDECAR_ADMIN_TOKEN，并自动登录 Memos 创建长期 PAT，
#      让 sidecar/worker 真正"零人工干预"启动。
set -e

# ---------- 字体颜色 ----------
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# ---------- 路径与仓库源 ----------
# 当通过 `bash <(curl ...)` 运行时，BASH_SOURCE[0] 形如 /dev/fd/63，realpath 会指向匿名 fd，
# 后续 [ -f "$SCRIPT_DIR/xxx" ] 自然 false，会回落到 curl 远端分支。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo /tmp)"

# 仓库原始内容 base URL，支持 file:// 用于本地测试。
# 可通过 PRISM_REPO_RAW_BASE 直接覆盖；否则按 PRISM_REF 分支名拼接。
REPO_RAW_BASE="${PRISM_REPO_RAW_BASE:-https://raw.githubusercontent.com/nabule/Prism/${PRISM_REF:-master}}"

# ---------- Docker Compose 智能检测 ----------
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
elif docker-compose --version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker-compose"
else
    echo -e "${RED}错误: 未检测到 docker compose 或 docker-compose！请先安装 Docker Compose。${NC}"
    exit 1
fi

# ---------- Python 检测（用于解析 Memos API JSON 响应） ----------
PYBIN=""
if command -v python3 >/dev/null 2>&1; then
    PYBIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYBIN="python"
fi

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}       Prism (棱镜) AI 知识库一键部署工具       ${NC}"
echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}>>> 配置源: ${REPO_RAW_BASE}${NC}"

# ---------- 通用工具：从仓库释放单个文件 ----------
# 用法：fetch_file <仓库相对路径> <本地落地路径>
# 优先级：
#   (1) 目标文件已存在 → 保留用户改动，跳过；
#   (2) 脚本同目录存在同名仓库副本（即用户在 git clone 后的仓库根直接运行）→ cp；
#   (3) 否则 → curl -fsSL "$REPO_RAW_BASE/$relpath"。
fetch_file() {
    local relpath="$1"
    local dest="$2"
    if [ -f "$dest" ]; then
        echo -e "${YELLOW}[-] $dest 已存在，跳过。${NC}"
        return 0
    fi
    mkdir -p "$(dirname "$dest")"
    local src_local="${SCRIPT_DIR}/${relpath}"
    local dest_abs
    dest_abs="$(cd "$(dirname "$dest")" && pwd)/$(basename "$dest")"
    if [ -f "$src_local" ] && [ "$(realpath "$src_local" 2>/dev/null)" != "$dest_abs" ]; then
        cp "$src_local" "$dest"
        echo -e "${GREEN}[+] 从本地仓库副本释放: $relpath -> $dest${NC}"
    else
        if ! curl -fsSL "$REPO_RAW_BASE/$relpath" -o "$dest"; then
            echo -e "${RED}!!! 下载失败: $REPO_RAW_BASE/$relpath${NC}"
            return 1
        fi
        echo -e "${GREEN}[+] 从仓库下载: $relpath -> $dest${NC}"
    fi
}

# ---------- 1. 初始化目录 ----------
echo -e "${GREEN}[1/6] 初始化目录结构...${NC}"
mkdir -p config data/memos data/sidecar data/caddy logs/caddy gateway docs

# ---------- 2. 释放默认配置文件（全部来自仓库） ----------
echo -e "${GREEN}[2/6] 释放默认配置文件...${NC}"
fetch_file gateway/Caddyfile             gateway/Caddyfile
fetch_file config/app.yaml               config/app.yaml
fetch_file config/models.yaml            config/models.yaml
fetch_file config/prompts.yaml           config/prompts.yaml
fetch_file config/taxonomy.yaml          config/taxonomy.yaml
fetch_file docker-compose.release.yml    docker-compose.release.yml

# ---------- 3. 生成 .env（含随机 SIDECAR_ADMIN_TOKEN） ----------
if [ ! -f .env ]; then
    echo -e "${GREEN}[3/6] 生成 .env（注入随机 admin token）...${NC}"
    AUTO_ADMIN_TOKEN=$(openssl rand -hex 16 2>/dev/null || echo "token_$(date +%s)_$RANDOM")
    cat > .env <<EOF
# Prism Sidecar 管理 Token（访问 http://localhost:\${GATEWAY_PORT}/admin/ui 时使用）
SIDECAR_ADMIN_TOKEN=${AUTO_ADMIN_TOKEN}

# Memos / 大模型 / 附件解析 / 推送 配置（可在 Sidecar 管理界面热更新）
MEMOS_API_TOKEN=
MEMOS_WEBHOOK_URL=
DEEPSEEK_API_KEY=
OPENROUTER_API_KEY=
OPENAI_API_KEY=
MINERU_API_TOKEN=
SILICONFLOW_API_KEY=
REMINDER_WEBHOOK_URL=

# 网关对外端口（多租户隔离时按用户递增）
GATEWAY_PORT=${GATEWAY_PORT:-8085}

# 锁定 GHCR 镜像版本，留空或 latest 表示跟随最新发布
PRISM_VERSION=${PRISM_VERSION:-latest}
EOF
    chmod 600 .env
    echo -e "${GREEN}>>> 已生成 .env，SIDECAR_ADMIN_TOKEN=${BLUE}${AUTO_ADMIN_TOKEN}${NC}"
else
    echo -e "${YELLOW}[3/6] 检测到 .env 已存在，跳过生成。${NC}"
fi

# 加载 .env 供后续逻辑使用（GATEWAY_PORT、PRISM_VERSION）
set -o allexport
# shellcheck disable=SC1091
source .env
set +o allexport
GATEWAY_PORT="${GATEWAY_PORT:-8085}"

# ---------- 4. 拉取镜像 & 启动容器 ----------
echo -e "${GREEN}[4/6] 拉取生产镜像...${NC}"
$DOCKER_COMPOSE -f docker-compose.release.yml pull

echo -e "${GREEN}[5/6] 拉起全栈容器...${NC}"
$DOCKER_COMPOSE -f docker-compose.release.yml up -d

# ---------- 5. 自动创建 Memos host 账号并签发 PAT，写回 .env ----------
bootstrap_memos_pat() {
    # 已有 PAT 直接跳过
    local existing
    existing="$(grep -E '^MEMOS_API_TOKEN=' .env | head -n1 | cut -d= -f2-)"
    if [ -n "$existing" ]; then
        echo -e "${YELLOW}[-] .env 中已存在 MEMOS_API_TOKEN，跳过自动获取。${NC}"
        return 0
    fi
    if [ -z "$PYBIN" ]; then
        echo -e "${RED}!!! 未检测到 python/python3，无法自动获取 Memos PAT。请手动登录 Memos 创建 PAT 后回填 .env。${NC}"
        return 1
    fi

    local base="http://127.0.0.1:${GATEWAY_PORT}"
    local user="admin"
    local pass
    pass="$(openssl rand -hex 12)"

    # 等 Memos 起来（/healthz 在所有 Memos 版本上都可用；最多 90s）
    echo -e "${GREEN}>>> 等待 Memos 启动 (${base}/healthz) ...${NC}"
    local ready=0
    for _ in $(seq 1 45); do
        if curl -fsS "${base}/healthz" >/dev/null 2>&1; then
            ready=1; break
        fi
        sleep 2
    done
    if [ "$ready" != "1" ]; then
        echo -e "${RED}!!! Memos 在 90s 内未就绪，跳过自动 PAT 获取。${NC}"
        return 1
    fi

    # 创建 host 用户（已存在会返回非 2xx，吞掉即可）
    curl -sS -o /dev/null -X POST "${base}/api/v1/users" \
         -H 'Content-Type: application/json' \
         -d "{\"username\":\"${user}\",\"password\":\"${pass}\",\"email\":\"\"}" || true

    # 登录拿 accessToken
    local signin
    signin="$(curl -sS -X POST "${base}/api/v1/auth/signin" \
                   -H 'Content-Type: application/json' \
                   -d "{\"passwordCredentials\":{\"username\":\"${user}\",\"password\":\"${pass}\"}}")"
    local access_token user_name
    access_token="$(printf '%s' "$signin" | "$PYBIN" -c 'import json,sys
try:
    print(json.load(sys.stdin).get("accessToken",""))
except Exception:
    print("")')"
    user_name="$(printf '%s' "$signin" | "$PYBIN" -c 'import json,sys
try:
    u=json.load(sys.stdin).get("user",{})
    print(u.get("name",""))
except Exception:
    print("")')"

    if [ -z "$access_token" ] || [ -z "$user_name" ]; then
        echo -e "${RED}!!! Memos 登录失败，跳过自动 PAT 获取。响应：${signin}${NC}"
        echo -e "${YELLOW}    （通常是 host 用户已存在但密码不一致，请在管理界面手动创建 PAT 后回填）${NC}"
        return 1
    fi

    # 创建长期 PAT（expiresInDays=0 = 不过期）
    local pat_resp pat
    pat_resp="$(curl -sS -X POST "${base}/api/v1/${user_name}/personalAccessTokens" \
                     -H "Authorization: Bearer ${access_token}" \
                     -H 'Content-Type: application/json' \
                     -d '{"description":"prism-deploy-auto","expiresInDays":0}')"
    pat="$(printf '%s' "$pat_resp" | "$PYBIN" -c 'import json,sys
try:
    print(json.load(sys.stdin).get("token",""))
except Exception:
    print("")')"

    if [ -z "$pat" ]; then
        echo -e "${RED}!!! PAT 创建失败，响应：${pat_resp}${NC}"
        return 1
    fi

    # 写回 .env
    if grep -q '^MEMOS_API_TOKEN=' .env; then
        # 使用 # 作为分隔，避免 token 中可能的 / 干扰
        sed -i "s#^MEMOS_API_TOKEN=.*#MEMOS_API_TOKEN=${pat}#" .env
    else
        printf 'MEMOS_API_TOKEN=%s\n' "$pat" >>.env
    fi
    # 记录初始 host 账号信息，便于用户后续登录 Memos 前端
    if ! grep -q '^# MEMOS_HOST_USER=' .env; then
        printf '# MEMOS_HOST_USER=%s\n# MEMOS_HOST_PASSWORD=%s\n' "$user" "$pass" >>.env
    fi

    # 让 sidecar / worker 重新载入新 PAT
    # 注意：`docker compose restart` 不会重读 env_file，必须 `up -d` 才会用新的 .env 重建容器。
    $DOCKER_COMPOSE -f docker-compose.release.yml up -d sidecar sidecar-worker >/dev/null

    echo -e "${GREEN}>>> 已自动创建 Memos host 账号 ${BLUE}${user_name}${GREEN}，PAT 已写入 .env。${NC}"
    echo -e "${GREEN}>>> 初始 Memos 登录账号: ${BLUE}${user}${GREEN} / 密码: ${BLUE}${pass}${NC}"
    return 0
}

echo -e "${GREEN}[6/6] 自动配置 Memos host 账号与 PAT...${NC}"
bootstrap_memos_pat || true

# ---------- 结束 banner ----------
CURRENT_TOKEN="$(grep -E '^SIDECAR_ADMIN_TOKEN=' .env | head -n1 | cut -d= -f2-)"
CURRENT_PAT="$(grep -E '^MEMOS_API_TOKEN=' .env | head -n1 | cut -d= -f2-)"
# 探测一个可被局域网/公网用户实际访问到的主机 IP。优先级：
#   1. PRISM_PUBLIC_HOST 环境变量（运维显式覆盖，比如域名 prism.example.com）；
#   2. hostname -I 第一个非 127/172 的 IPv4（典型 LAN IP，例如 192.168.x.x）；
#   3. ip route 默认网关接口的 src IP；
#   4. 兜底回到 localhost（与历史行为一致）。
detect_public_host() {
    if [ -n "${PRISM_PUBLIC_HOST:-}" ]; then
        echo "$PRISM_PUBLIC_HOST"
        return
    fi
    local ip
    ip="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^(10|192\.168|172\.(1[6-9]|2[0-9]|3[0-1]))\.' | head -n1)"
    if [ -z "$ip" ]; then
        ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '/src/ {for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')"
    fi
    if [ -z "$ip" ]; then
        ip="localhost"
    fi
    echo "$ip"
}
PUBLIC_HOST="$(detect_public_host)"

# 一次性自动登录链接：把 Admin Token 放在 URL hash 里（hash 不发到服务端 access log）。
# 前端 admin_ui 检测到 #admin_token=xxx 后会写入 localStorage 并 history.replaceState
# 清掉 hash，避免长期留在地址栏/书签里。这样用户从终端直接 Ctrl+点击即登录，
# 不再需要手动复制 token 到右上角输入框。
MAGIC_LINK_LOCAL="http://localhost:${GATEWAY_PORT}/admin/ui#admin_token=${CURRENT_TOKEN}"
MAGIC_LINK_LAN="http://${PUBLIC_HOST}:${GATEWAY_PORT}/admin/ui#admin_token=${CURRENT_TOKEN}"
echo -e "${BLUE}===============================================${NC}"
echo -e "${GREEN}        🎉 Prism (棱镜) 部署完成！             ${NC}"
echo -e "${BLUE}===============================================${NC}"
if [ "$PUBLIC_HOST" != "localhost" ]; then
    echo -e "${GREEN}网关入口（本机）:    ${YELLOW}http://localhost:${GATEWAY_PORT}${NC}"
    echo -e "${GREEN}网关入口（局域网）:  ${YELLOW}http://${PUBLIC_HOST}:${GATEWAY_PORT}${NC}"
    echo -e "${GREEN}Sidecar 管理端:      ${YELLOW}http://${PUBLIC_HOST}:${GATEWAY_PORT}/admin/ui${NC}"
    echo -e "${GREEN}一次性登录链接（本机）:    ${YELLOW}${MAGIC_LINK_LOCAL}${NC}"
    echo -e "${GREEN}一次性登录链接（局域网）:  ${YELLOW}${MAGIC_LINK_LAN}${NC}"
    echo -e "${YELLOW}提示:${NC} ${GREEN}localhost / 127.0.0.1 仅在 Prism 所在主机访问有效；${NC}"
    echo -e "       ${GREEN}从其它电脑 / 手机访问，请使用上面的局域网链接（${PUBLIC_HOST}）。${NC}"
    echo -e "       ${GREEN}如需对外暴露公网域名，请用 PRISM_PUBLIC_HOST=your.domain bash deploy.sh。${NC}"
else
    echo -e "${GREEN}网关入口:            ${YELLOW}http://localhost:${GATEWAY_PORT}${NC}"
    echo -e "${GREEN}Sidecar 管理端:      ${YELLOW}http://localhost:${GATEWAY_PORT}/admin/ui${NC}"
    echo -e "${GREEN}一次性登录链接:      ${YELLOW}${MAGIC_LINK_LOCAL}${NC}"
    echo -e "${YELLOW}提示:${NC} ${GREEN}未探测到 LAN IP，仅生成 localhost 入口；${NC}"
    echo -e "       ${GREEN}如需远程访问，请通过 PRISM_PUBLIC_HOST=<IP或域名> bash deploy.sh 显式指定。${NC}"
fi
echo -e "${GREEN}                     ${NC}(点击 magic link 即自动写入 Admin Token，浏览器侧 hash 自动清空)"
echo -e "${GREEN}Admin Token:         ${BLUE}${CURRENT_TOKEN}${NC}"
if [ -n "$CURRENT_PAT" ]; then
    echo -e "${GREEN}Memos PAT:           ${BLUE}${CURRENT_PAT}${NC}"
else
    echo -e "${YELLOW}Memos PAT:           (未自动获取，请手动在管理界面创建并回填 .env)${NC}"
fi
echo -e "${BLUE}===============================================${NC}"
