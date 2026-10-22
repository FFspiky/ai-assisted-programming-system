# 部署文档

## 运行环境

- Python 3.11+；提交代码支持 Python 3.11 / C++17
- Docker Engine/Desktop 与 `codelab-runner:local` 镜像（代码执行必需，见 [演示说明](EVIDENCE_DEMO.md)）
- Redis（推荐，用于跨进程限流）
- 生产数据库（建议 PostgreSQL；本机演示可用 SQLite）
- 反向代理（Nginx、Caddy 或云厂商网关）
- HTTPS 证书

当前实现面向本机与参赛演示；生产部署前需完成下文执行服务隔离与全局并发治理。

## 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 生产环境变量

至少配置：

```bash
FLASK_SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=sqlite:////absolute/path/app.db
DEEPSEEK_API_KEY=replace-with-your-api-key
RATE_LIMIT_REDIS_URL=redis://127.0.0.1:6379/0
CORS_ORIGINS=https://your-domain.example
AUTO_CREATE_DATABASE=0
FLASK_DEBUG=0
```

可选配置：

```bash
# 接口固定为 https://api.deepseek.com/chat/completions，仅支持 DeepSeek 官方 API
DEEPSEEK_MODEL_NAME=deepseek-flash
DEEPSEEK_AUTOCOMPLETE_MODEL_NAME=deepseek-flash
SUPPORTED_LANGUAGES=python,cpp
MAX_CODE_CHARS=20000
MAX_STDIN_CHARS=10000
MAX_AI_PROMPT_CHARS=8000
CODE_RUN_TIMEOUT_SECONDS=10
CODE_RUN_CPU_SECONDS=3
CODE_RUN_MEMORY_MB=256
CODE_RUN_FILE_SIZE_MB=1
CODE_RUN_MAX_PROCESSES=32
CODE_RUN_MAX_OUTPUT_CHARS=20000
```

首次部署如需自动创建管理员，可临时设置：

```bash
ADMIN_USERNAME=admin
ADMIN_PASSWORD=replace-with-a-strong-password
ADMIN_EMAIL=admin@example.com
```

管理员创建后应删除这些变量，改用 CLI 管理账号。

## 数据库迁移

生产环境不要依赖启动时自动建表。部署和升级时执行：

```bash
flask --app app db upgrade
```

可以显式关闭演示自动建表：

```bash
AUTO_CREATE_DATABASE=0 flask --app app db upgrade
```

## 管理员创建

推荐使用 CLI：

```bash
flask --app app create-admin
```

## 启动应用

开发或小规模演示：

```bash
FLASK_HOST=127.0.0.1 FLASK_PORT=5001 python app.py
```

生产建议使用 WSGI 服务器，例如 Gunicorn：

```bash
gunicorn -w 2 -b 127.0.0.1:5001 app:app
```

## 反向代理示例

Nginx 示例：

```nginx
server {
    listen 80;
    server_name your-domain.example;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.example;

    ssl_certificate /etc/letsencrypt/live/your-domain.example/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.example/privkey.pem;

    client_max_body_size 5m;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

部署后将 `CORS_ORIGINS` 设置为真实 HTTPS 域名。

## HTTPS

必须使用 HTTPS 承载登录 Cookie 和 CSRF token。可使用：

- Let's Encrypt + Certbot
- Caddy 自动证书
- 云厂商负载均衡 HTTPS 证书

## 代码执行沙箱

当前使用独立 Docker 容器执行 Python/C++，默认禁网、只读根文件系统、低权限用户、无宿主挂载；CPU、内存、进程、文件、输出与总时长均有限制。Docker 或镜像不可用时拒绝执行，不回退到宿主进程。

Redis 连接或请求失败时限流会回退到进程内存；多进程部署须监控该降级并恢复 Redis，不能把回退视为全局共享限流。

应用运行用户需要调用 Docker 的权限，该权限应只在专用执行主机上授予。当前并发限制为每个 Flask 进程 2 个任务，面向本机演示；多进程公网部署应把执行服务与业务主机分离，统一限制全局任务数，并维护容器运行时与镜像安全更新。不要向提交代码的容器挂载 Docker socket。

## 部署后检查

```bash
make check
flask --app app db upgrade
```

页面冒烟检查：

- `/index.html`
- `/login.html`
- `/register.html`
- `/problem_selector.html`
- `/practice.html`
- `/learn-analytics.html`
