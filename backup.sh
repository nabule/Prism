#!/bin/bash
set -e

# ==============================================================================
# Prism (棱镜) - 全局数据一键备份工具
# ==============================================================================

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

# 获取当前时间戳
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="backups"
BACKUP_FILE="${BACKUP_DIR}/prism_backup_${TIMESTAMP}.tar.gz"

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}🌈 Prism (棱镜) - 全局数据一键打包备份工具${NC}"
echo -e "${BLUE}====================================================${NC}"

# 确保在项目根目录运行
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ 错误: 未在项目根目录下找到 docker-compose.yml 文件！${NC}"
    echo -e "${YELLOW}请切换到 Prism 项目主目录后再运行此脚本。${NC}"
    exit 1
fi

# 创建备份目录
mkdir -p "${BACKUP_DIR}"

# 提示可能需要 sudo
CONTAINERS_STOPPED_BY_US=false
cleanup() {
    if [ "$CONTAINERS_STOPPED_BY_US" = true ]; then
        echo -e "${YELLOW}🔄 正在安全重新拉起 Docker 容器以恢复服务...${NC}"
        docker compose start
    fi
}
trap cleanup EXIT

if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}💡 提示: 如果在打包时遇到 'Permission denied' 错误（如部分文件属于 root 权限），请尝试使用 sudo ./backup.sh 运行本脚本。${NC}"
    echo -e "${BLUE}----------------------------------------------------${NC}"
fi

# 判断容器是否正在运行
CONTAINERS_RUNNING=$(docker compose ps --format '{{.State}}' | grep -c "running" || true)

if [ "$CONTAINERS_RUNNING" -gt 0 ]; then
    echo -e "${YELLOW}⏱️ 1. 正在安全停止运行中的 Docker 容器以确保 SQLite 数据库完全落盘且无 WAL 锁...${NC}"
    docker compose stop
    CONTAINERS_STOPPED_BY_US=true
else
    echo -e "${GREEN}⏱️ 1. 容器当前未运行，无需停止，正在准备直接打包...${NC}"
    CONTAINERS_STOPPED_BY_US=false
fi

echo -e "${GREEN}📦 2. 正在打包全局数据、配置文件与部署依赖环境...${NC}"

# 定义需要打包的文件与目录
PACK_LIST=""

# 核心数据与密钥 (排除 caddy 生成的证书和运行时缓存，只备份 memos 和 sidecar 的数据卷)
[ -f ".env" ] && PACK_LIST="${PACK_LIST} .env"
[ -d "config" ] && PACK_LIST="${PACK_LIST} config"
[ -d "data/memos" ] && PACK_LIST="${PACK_LIST} data/memos"
[ -d "data/sidecar" ] && PACK_LIST="${PACK_LIST} data/sidecar"

# 部署依赖及网关
[ -f "docker-compose.yml" ] && PACK_LIST="${PACK_LIST} docker-compose.yml"
[ -d "gateway" ] && PACK_LIST="${PACK_LIST} gateway"
[ -f "Dockerfile" ] && PACK_LIST="${PACK_LIST} Dockerfile"
[ -f "package.json" ] && PACK_LIST="${PACK_LIST} package.json"
[ -f "nx.json" ] && PACK_LIST="${PACK_LIST} nx.json"
[ -d "sidecar" ] && PACK_LIST="${PACK_LIST} sidecar"
[ -d "src" ] && PACK_LIST="${PACK_LIST} src"
[ -f "pyproject.toml" ] && PACK_LIST="${PACK_LIST} pyproject.toml"
[ -f "uv.lock" ] && PACK_LIST="${PACK_LIST} uv.lock"

# 排除巨型或动态产生的垃圾文件
EXCLUDE_ARGS="--exclude=node_modules --exclude=.venv --exclude=.nx --exclude=.git --exclude=.pytest_cache --exclude=logs --exclude=backups"

if [ -z "${PACK_LIST}" ]; then
    echo -e "${RED}❌ 错误: 未在当前目录找到任何可备份的数据！${NC}"
    exit 1
fi

# 执行打包
tar -czf "${BACKUP_FILE}" ${EXCLUDE_ARGS} ${PACK_LIST}

echo -e "${GREEN}🚀 3. 打包完成！正在为您恢复/启动 Docker 容器...${NC}"

# 获取备份包大小
FILE_SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}✅ 备份圆满成功！${NC}"
echo -e "${GREEN}💾 备份包位置: ${YELLOW}${BACKUP_FILE}${NC}"
echo -e "${GREEN}📊 备份包大小: ${YELLOW}${FILE_SIZE}${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "${YELLOW}💡 迁移提示: 只要将此 tar.gz 备份包传到新服务器，然后使用 restore.sh 恢复，即可一键完美搬家！${NC}"
