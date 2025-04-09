FROM python:3.10-slim as base

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=sec_extractor.settings \
    PYTHONPATH=/app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 开发环境
FROM base as development
RUN pip install --no-cache-dir pytest pytest-django pytest-cov
COPY . .

# 创建日志目录
RUN mkdir -p logs
RUN mkdir -p media/uploads

# 暴露端口
EXPOSE 8000

# 启动开发服务器
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# 生产环境
FROM base as production
COPY . .

# 创建日志和媒体目录
RUN mkdir -p logs
RUN mkdir -p media/uploads
RUN mkdir -p staticfiles

# 确保目录权限正确
RUN chown -R 1000:1000 /app/logs /app/media /app/staticfiles

# 收集静态文件
RUN python manage.py collectstatic --noinput

# 暴露端口
EXPOSE 8000

# 启动生产服务器
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "sec_extractor.wsgi:application"]