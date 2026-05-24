#!/bin/bash
set -e

# ==============================================================================
# Prism (棱镜) - 全局数据一键恢复工具
# ==============================================================================

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}🌈 Prism (棱镜) - 全局数据一键恢复与迁移工具${NC}"
echo -e "${BLUE}====================================================${NC}"

# 确认参数
BACKUP_FILE=$1
AUTO_CONFIRM=$2

if [ -z "$BACKUP_FILE" ]; then
    echo -e "${RED}❌ 错误: 未指定备份文件！${NC}"
    echo -e "${YELLOW}使用方法: ./restore.sh <备份文件路径.tar.gz> [-y]${NC}"
    echo -e "示例: ./restore.sh backups/prism_backup_20260524_120000.tar.gz"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}❌ 错误: 找不到指定的备份文件: $BACKUP_FILE${NC}"
    exit 1
fi

# 提示可能需要 sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}💡 提示: 如果在恢复时遇到 'Permission denied' 错误（如部分文件属于 root 权限），请尝试使用 sudo ./restore.sh ... 运行本脚本。${NC}"
    echo -e "${BLUE}----------------------------------------------------${NC}"
fi

# 检查是否传入 -y 自动确认参数
if [ "$AUTO_CONFIRM" = "-y" ] || [ "$AUTO_CONFIRM" = "--yes" ]; then
    CONFIRMED="y"
else
    echo -e "${YELLOW}⚠️ 警告: 恢复操作将完全覆盖当前目录下可能已有的所有 Memos 笔记、附件、Sidecar 配置及 SQLite 数据库！${NC}"
    read -p "您确定要继续吗？(y/N): " CONFIRMED
fi

if [ "$CONFIRMED" != "y" ] && [ "$CONFIRMED" != "Y" ]; then
    echo -e "${RED}❌ 操作已取消。${NC}"
    exit 0
fi

# 如果当前正在运行容器，先将其完全停止并卸载，以防止 SQLite 文件在被替换时发生读写冲突
if [ -f "docker-compose.yml" ]; then
    CONTAINERS_RUNNING=$(docker compose ps --format '{{.State}}' | grep -c "running" || true)
    if [ "$CONTAINERS_RUNNING" -gt 0 ]; then
        echo -e "${YELLOW}⏱️ 1. 检测到当前项目正在运行，正在安全下线当前容器群以避免写冲突...${NC}"
        docker compose down
    fi
fi

echo -e "${GREEN}📦 2. 正在提取备份文件，执行全局数据覆盖恢复...${NC}"
tar -xzf "$BACKUP_FILE"

# 确保必要的本地文件夹权限正确
mkdir -p data/memos data/sidecar logs config
chmod -R 777 data/memos 2>/dev/null || true
chmod -R 777 data/sidecar 2>/dev/null || true

echo -e "${GREEN}🚀 3. 正在基于新恢复的数据和配置重新拉起容器实例并开始运行...${NC}"
if command -v npx &> /dev/null && [ -f "package.json" ]; then
    # 优先使用项目统一任务入口（符合 Rule 4）
    npx nx run sidecar:up
else
    # 备用直接使用 docker compose
    docker compose up -d
fi

echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}✅ 一键恢复与完美搬家圆满成功！${NC}"
echo -e "${GREEN}🌐 请访问网关入口进行验证: ${YELLOW}http://localhost:8080/${NC}"
echo -e "${GREEN}🖥️ 管理控制台 UI: ${YELLOW}http://localhost:8080/admin/ui${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "${YELLOW}💡 提示: 涉及管理页面变更时，请访问 http://localhost:8080/admin/ui 确认恢复后的标签和配置无误。${NC}"
