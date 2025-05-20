FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    ghostscript \
    imagemagick \
    pdftk \
    qpdf \
    poppler-utils \
    libmagickwand-dev \
    && rm -rf /var/lib/apt/lists/*

# 配置ImageMagick策略以允许PDF操作
RUN sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8006

# 启动应用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006", "--reload"]