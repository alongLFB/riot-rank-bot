FROM python:3.12-slim

# 从官方镜像提取超快的 uv 安装器
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 安装 html2image 依赖的 Chromium 浏览器
RUN apt-get update && apt-get install -y chromium && rm -rf /var/lib/apt/lists/*

# 仅拷贝包管理文件并使用 uv 极速安装依赖
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 拷贝剩余代码
COPY . .

# 使用 uv 启动
CMD ["uv", "run", "python", "bot.py"]
