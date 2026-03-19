# DePredict 部署指南

## 架构概览

```
用户浏览器
    ↓ HTTPS (443)
┌─────────┐
│  Caddy   │  ← 自动 HTTPS 证书 (Let's Encrypt)
└────┬─────┘
     ↓ HTTP (3000)
┌─────────┐
│  Nginx   │  ← 前端静态文件 + API 反向代理
└────┬─────┘
     ↓ /api/* (5001)
┌─────────┐
│  Flask   │  ← 后端 API + AI Debate 引擎
└─────────┘
```

所有服务通过 Docker Compose 编排，一键启动。

---

## Step 1: 购买 VPS

推荐 **DigitalOcean**（最低 $6/月）。

### 1.1 注册 DigitalOcean
- 访问 https://www.digitalocean.com
- 注册账号，绑定信用卡或 PayPal

### 1.2 创建 Droplet
1. 点击 **Create → Droplets**
2. 选择配置：
   - **Region**: San Francisco 或 Singapore（选离你近的）
   - **Image**: Ubuntu 24.04 LTS
   - **Size**: Basic → Regular → **$6/mo**（1 vCPU, 1GB RAM, 25GB SSD）
   - **Authentication**: SSH Key
3. 点击底部 **Add SSH Key**，粘贴你的公钥：
   ```bash
   # 在你的 Mac 上运行，复制输出内容
   cat ~/.ssh/id_ed25519.pub
   ```
4. **Hostname** 填 `depredict`（随意）
5. 点击 **Create Droplet**
6. 等待创建完成，记下分配的 **IP 地址**（例如 `167.71.xxx.xxx`）

### 1.3 验证 SSH 连接
```bash
# 在你的 Mac 终端执行
ssh root@你的IP地址

# 如果看到 root@depredict:~# 表示成功
# 输入 exit 退出
```

---

## Step 2: 配置域名

### 方案 A: 购买新域名
- **Namecheap** (https://namecheap.com) — 便宜，`.com` 约 $9/年
- **Cloudflare Registrar** (https://dash.cloudflare.com) — 成本价，无加价

### 方案 B: 不用域名，先用 IP 测试
如果暂时不想买域名，可以跳过此步，直接用 `http://你的IP` 访问（无 HTTPS）。
需要修改 Caddyfile 为：
```
:80 {
    reverse_proxy frontend:3000
}
```

### 2.1 添加 DNS 记录
在你的域名注册商控制台：

| 类型 | 名称 | 值 | TTL |
|------|------|----|-----|
| A | `@` | `你的VPS IP` | 300 |
| A | `www` | `你的VPS IP` | 300 |

> 设置后等待 5-10 分钟让 DNS 生效。

### 2.2 验证 DNS
```bash
# 在 Mac 上执行
ping 你的域名.com
# 应该显示你的 VPS IP
```

---

## Step 3: 部署到 VPS

### 3.1 SSH 登录 VPS
```bash
ssh root@你的IP地址
```

### 3.2 安装 Docker
```bash
# 安装 Docker（官方一键脚本）
curl -fsSL https://get.docker.com | sh

# 验证安装
docker --version
# 应输出: Docker version 27.x.x

# Docker Compose 已内置，验证：
docker compose version
```

### 3.3 克隆代码
```bash
cd /opt
git clone https://github.com/Andrewyzzz/Depredict.git
cd Depredict
```

### 3.4 配置环境变量
```bash
cp .env.example .env
nano .env
```

填入以下内容（替换为你的真实值）：
```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxx
DOMAIN=你的域名.com
```

保存退出：`Ctrl+O` → `Enter` → `Ctrl+X`

### 3.5 配置域名（如有）
```bash
nano Caddyfile
```
确认内容为：
```
你的域名.com {
    reverse_proxy frontend:3000
    encode gzip zstd
}
```
> 把 `{$DOMAIN:localhost}` 替换为你的实际域名。

**如果没有域名**，改为：
```
:80 {
    reverse_proxy frontend:3000
    encode gzip zstd
}
```

### 3.6 启动服务
```bash
# 构建并启动所有容器（首次约 3-5 分钟）
docker compose up -d --build

# 查看容器状态（应该 3 个都是 Up）
docker compose ps
```

预期输出：
```
NAME                  STATUS    PORTS
depredict-backend-1   Up        5001/tcp
depredict-frontend-1  Up        3000/tcp
depredict-caddy-1     Up        0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

### 3.7 验证
- 有域名：打开 `https://你的域名.com`
- 无域名：打开 `http://你的IP地址`

---

## 常用运维命令

```bash
# 查看实时日志
docker compose logs -f

# 只看后端日志
docker compose logs -f backend

# 重启所有服务
docker compose restart

# 停止所有服务
docker compose down

# 更新代码后重新部署
cd /opt/Depredict
git pull
docker compose up -d --build

# 查看磁盘占用
docker system df
```

---

## 故障排查

### 网站打不开
```bash
# 1. 检查容器是否都在运行
docker compose ps

# 2. 检查 Caddy 日志（HTTPS 证书问题）
docker compose logs caddy

# 3. 检查防火墙
ufw status
# 如果 active，需要开放端口：
ufw allow 80
ufw allow 443
```

### API 报错
```bash
# 查看后端日志
docker compose logs backend

# 进入后端容器调试
docker compose exec backend sh
```

### 更新前端代码后不生效
```bash
# 需要重新 build 前端镜像
docker compose up -d --build frontend
```
