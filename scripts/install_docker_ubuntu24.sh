#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "请用 root 运行此脚本，例如：sudo bash scripts/install_docker_ubuntu24.sh"
  exit 1
fi

if [[ ! -f /etc/os-release ]]; then
  echo "未检测到 /etc/os-release，无法确认系统版本"
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release

if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "当前脚本只面向 Ubuntu，检测到: ${ID:-unknown}"
  exit 1
fi

if [[ "${VERSION_CODENAME:-}" != "noble" ]]; then
  echo "当前脚本按 Ubuntu 24.04 (noble) 编写，检测到: ${VERSION_CODENAME:-unknown}"
  exit 1
fi

DOCKER_APT_MIRROR="${DOCKER_APT_MIRROR:-https://download.docker.com/linux/ubuntu}"
DOCKER_GPG_URL="${DOCKER_GPG_URL:-${DOCKER_APT_MIRROR}/gpg}"

echo "[1/7] 安装基础依赖"
apt-get update
apt-get install -y ca-certificates curl

echo "[2/7] 写入 Docker 官方 GPG Key"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL "${DOCKER_GPG_URL}" -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo "[3/7] 配置 Docker apt 源"
cat >/etc/apt/sources.list.d/docker.sources <<'EOF'
Types: deb
URIs: __DOCKER_APT_MIRROR__
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sed -i "s|__DOCKER_APT_MIRROR__|${DOCKER_APT_MIRROR}|g" /etc/apt/sources.list.d/docker.sources

echo "[4/7] 安装 Docker Engine / Buildx / Compose"
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

if [[ -n "${DOCKER_REGISTRY_MIRROR:-}" ]]; then
  echo "[5/7] 配置 registry mirror"
  install -m 0755 -d /etc/docker
  cat >/etc/docker/daemon.json <<EOF
{
  "registry-mirrors": ["${DOCKER_REGISTRY_MIRROR}"]
}
EOF
else
  echo "[5/7] 未提供 DOCKER_REGISTRY_MIRROR，跳过镜像加速配置"
fi

echo "[6/7] 启动并设置 Docker 开机自启"
systemctl daemon-reload
systemctl enable --now docker

echo "[7/7] 配置 docker 用户组"
groupadd docker 2>/dev/null || true

TARGET_USER="${SUDO_USER:-}"
if [[ -n "${TARGET_USER}" ]]; then
  usermod -aG docker "${TARGET_USER}"
  echo "已将用户 ${TARGET_USER} 加入 docker 组"
else
  echo "未检测到 SUDO_USER，跳过自动加组"
fi

echo
echo "Docker 安装完成，当前版本："
docker --version
docker compose version
echo
echo "使用的软件源："
echo "  DOCKER_APT_MIRROR=${DOCKER_APT_MIRROR}"
echo "  DOCKER_GPG_URL=${DOCKER_GPG_URL}"
echo
echo "建议后续手动执行："
echo "  1. 重新登录 shell，或执行 newgrp docker"
echo "  2. docker run hello-world"
echo "  3. ./.venv/bin/python -m pytest tests/test_sandbox.py -v"
