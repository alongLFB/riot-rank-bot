FROM python:3.12-slim

# 从官方镜像提取超快的 uv 安装器
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 将 apt 源替换为国内清华源，解决由于网络屏蔽导致的 apt-get exit code 100 报错
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y chromium \
    && rm -rf /var/lib/apt/lists/*

# 仅拷贝包管理文件并使用 uv 极速安装依赖
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 拷贝剩余代码
COPY . .

# 使用 uv 启动
CMD ["uv", "run", "python", "bot.py"]
