# Docker 安装与项目接入

这台机器当前环境是：

- Ubuntu 24.04.4 LTS
- `systemd`
- 当前用户 `xiaobin`
- 当前没有安装 Docker
- 当前账户不能无密码 `sudo`

所以我已经把可直接执行的安装脚本放到了：

- [scripts/install_docker_ubuntu24.sh](/home/xiaobin/myproject/CodeRepair/scripts/install_docker_ubuntu24.sh)

## 1. 安装 Docker Engine

需要 root 权限执行：

```bash
cd /home/xiaobin/myproject/CodeRepair
sudo bash scripts/install_docker_ubuntu24.sh
```

这会完成：

- 配置 Docker 官方 apt 源
- 安装 `docker-ce` / `docker compose` / `buildx`
- 启动 `docker` 服务
- 尝试把当前用户加入 `docker` 组

## 2. 配置阿里云镜像加速

阿里云加速地址是账号专属的，不是固定公共地址。你需要先去阿里云 ACR 控制台拿到自己的加速器地址，然后这样执行：

```bash
cd /home/xiaobin/myproject/CodeRepair
sudo DOCKER_REGISTRY_MIRROR="https://你的专属加速地址" bash scripts/install_docker_ubuntu24.sh
```

## 2.1 使用国内 Docker CE 软件源

如果你在下载 `https://download.docker.com/linux/ubuntu/gpg` 时遇到连接重置，可以直接切到国内 apt 源。脚本现在支持通过环境变量切换：

### 方案 A：中科大 USTC

```bash
cd /home/xiaobin/myproject/CodeRepair
sudo DOCKER_APT_MIRROR="https://mirrors.ustc.edu.cn/docker-ce/linux/ubuntu" \
     DOCKER_GPG_URL="https://mirrors.ustc.edu.cn/docker-ce/linux/ubuntu/gpg" \
     bash scripts/install_docker_ubuntu24.sh
```

### 方案 B：清华 TUNA

```bash
cd /home/xiaobin/myproject/CodeRepair
sudo DOCKER_APT_MIRROR="https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/ubuntu" \
     DOCKER_GPG_URL="https://mirrors.tuna.tsinghua.edu.cn/docker-ce/linux/ubuntu/gpg" \
     bash scripts/install_docker_ubuntu24.sh
```

### 方案 C：阿里云 Docker CE 软件源

```bash
cd /home/xiaobin/myproject/CodeRepair
sudo DOCKER_APT_MIRROR="https://mirrors.aliyun.com/docker-ce/linux/ubuntu" \
     DOCKER_GPG_URL="https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg" \
     bash scripts/install_docker_ubuntu24.sh
```

推荐优先顺序：

1. `USTC`
2. `TUNA`
3. `阿里云`

如果其中一个不稳定，就直接换下一个，不要反复重试同一个源。

如果 Docker 已经装好了，也可以单独写入：

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "registry-mirrors": ["https://你的专属加速地址"]
}
EOF

sudo systemctl daemon-reload
sudo systemctl restart docker
```

## 3. 验证 Docker

安装后先重新登录 shell，或者执行：

```bash
newgrp docker
```

然后验证：

```bash
docker --version
docker compose version
docker run hello-world
docker info | grep -A 5 "Registry Mirrors"
```

## 4. 验证项目 Docker 链

先跑沙盒测试：

```bash
cd /home/xiaobin/myproject/CodeRepair
./.venv/bin/python -m pytest tests/test_sandbox.py -v
```

再强制主链只走 Docker 验证：

```bash
./.venv/bin/python app.py \
  --workspace examples/sample_go_project \
  --query "修复 main.go 中的问题，并返回完整文件代码" \
  --apply-file main.go \
  --validation-mode docker
```

如果这里能跑通，才算项目真正具备了“Docker 沙盒验证”这条链，而不是仅靠本地降级。

## 5. 当前边界说明

在 Docker 没装好之前：

- `--validation-mode auto` 仍然会自动降级到本地验证
- 这适合开发联调
- 但**不应该**把它当成“Docker 沙盒能力已完整落地”

只有下面 3 件都成立时，才建议对外写 Docker 能力：

1. `docker run hello-world` 正常
2. `tests/test_sandbox.py` 可跑
3. `app.py --validation-mode docker` 主链可跑

## 6. 参考

- Docker Ubuntu 安装文档: https://docs.docker.com/engine/install/ubuntu/
- 阿里云 ECS 安装 Docker: https://help.aliyun.com/zh/ecs/user-guide/install-and-use-docker
