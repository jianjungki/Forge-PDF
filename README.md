# PDF Processing System

[English](#pdf-processing-system) | [中文](#pdf处理系统)

A comprehensive PDF processing backend system offering various PDF manipulation features, supporting Docker deployment.

## Features

### Page Operations
- View and Edit PDFs - Support for custom viewing, sorting, and searching of multi-page PDFs, along with page editing features like annotations, drawings, text, and image additions
- Complete interactive GUI for merging/splitting/rotating/moving PDFs and their pages
- Merge multiple PDFs into a single result file
- Split PDF into multiple files at specified page numbers or extract all pages as separate files
- Reorder PDF pages
- Rotate PDF by 90 degrees
- Delete pages
- Multi-page layout (format PDF into multiple pages per page)
- Scale page content size by percentage
- Adjust contrast
- Crop PDF
- Auto-split PDF (using physical scan page separators)
- Extract pages
- Convert PDF to single pages
- Overlay PDFs
- Split PDF by sections

### Conversion Operations
- Convert PDF to images or images to PDF
- Convert any common file to PDF using LibreOffice
- Convert PDF to Word/PowerPoint etc. using LibreOffice
- Convert HTML to PDF
- Convert PDF to XML
- Convert PDF to CSV
- URL to PDF
- Markdown to PDF

### Security and Permissions
- Add and remove passwords
- Change/set PDF permissions
- Add watermarks
- Certify/sign PDFs
- Sanitize PDFs
- Auto-redact text

### Other Operations
- Add/generate/write signatures
- Split by size or PDF
- Fix PDFs
- Detect and remove blank pages
- Compare two PDFs and show text differences
- Add images to PDF
- Compress PDF to reduce file size
- Extract images from PDF
- Remove images from PDF
- Extract images from scans
- Remove annotations
- Add page numbers
- Auto-rename files by detecting PDF title text
- OCR on PDFs (using Tesseract OCR)
- PDF/A conversion
- Edit metadata
- Flatten PDFs
- Get all PDF info to view or export as JSON
- Show/detect embedded JavaScript

## System Architecture

The system uses a microservices architecture with the following components:

### Core Services
- **API Gateway** - Handles all external requests, routing to appropriate services
- **Upload Service** - Handles file uploads and storage
- **Viewer & Page Service** - Provides PDF preview and page operation features
- **Security Service** - Handles PDF security-related features
- **Conversion Service** - Handles file format conversions

### Processing Services
- **OCR Service** - Provides text recognition capabilities
- **Processing Service** - Provides PDF processing features
- **Transform Service** - Provides format conversion and document beautification features

### Infrastructure
- **MongoDB** - Stores metadata
- **MinIO** - Object storage for files
- **RabbitMQ** - Message queue for inter-service communication
- **Redis** - Caching

### Monitoring
- **Prometheus** - Monitoring metrics collection
- **Grafana** - Monitoring dashboard

## Deployment Guide

### Prerequisites
- Docker
- Docker Compose

### Deployment Steps

1. Clone the repository
```bash
git clone https://github.com/yourusername/pdf-tools.git
cd pdf-tools
```

2. Start services
```bash
cd docker
docker-compose up -d
```

3. Access services
- API Gateway: http://localhost:8000
- MinIO Console: http://localhost:9001
- RabbitMQ Management: http://localhost:15672
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

## Internationalization

The system supports multiple languages, currently including:
- English
- Chinese

## Development Guide

### Environment Setup
1. Install dependencies
```bash
pip install -r requirements.txt
```

2. Set environment variables
```bash
cp .env.example .env
```

3. Start development server
```bash
uvicorn app:app --reload
```

## API Documentation

After starting the service, API documentation can be accessed at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Contributing Guide

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add some amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Create a Pull Request

## License

MIT License

<!-- Chinese -->

# PDF处理系统

一个完整的PDF处理后台系统，提供多种PDF处理功能，支持Docker部署。

## 功能特点

### 页面操作
- 查看和修改PDF - 支持多页PDF的自定义查看、排序和搜索，以及页面编辑功能，如注释、绘图、添加文本和图像
- 合并/分割/旋转/移动PDF及其页面的完整交互式GUI
- 将多个PDF合并为单个结果文件
- 在指定页码处将PDF拆分为多个文件，或将所有页面提取为单独的文件
- 将PDF页面重新排序
- 90度旋转PDF
- 删除页面
- 多页面布局（将PDF格式化为多页页面）
- 按设定百分比缩放页面内容大小
- 调整对比度
- 裁剪PDF
- 自动拆分PDF（使用物理扫描的页面分隔符）
- 提取页面
- 将PDF转换为单页
- 将PDF叠加在一起
- 按部分拆分PDF

### 转换操作
- 将PDF转换为图像，或将图像转换为PDF
- 使用LibreOffice将任何常见文件转换为PDF
- 使用LibreOffice将PDF转换为Word/PowerPoint等格式
- 将HTML转换为PDF
- 将PDF转换为XML
- 将PDF转换为CSV
- URL转PDF
- Markdown转PDF

### 安全和权限
- 添加和删除密码
- 更改/设置PDF权限
- 添加水印
- 认证/签名PDF
- 净化PDF
- 自动编辑文本

### 其他操作
- 添加/生成/写入签名
- 按大小或PDF拆分
- 修复PDF
- 检测并删除空白页
- 比较两个PDF并显示文本差异
- 向PDF添加图像
- 压缩PDF以减小文件大小
- 从PDF中提取图像
- 从PDF中删除图像
- 从扫描件中提取图像
- 删除注释
- 添加页码
- 通过检测PDF标题文本自动重命名文件
- PDF上的OCR（使用Tesseract OCR）
- PDF/A转换
- 编辑元数据
- 扁平化PDF
- 获取PDF的所有信息以查看或导出为JSON
- 显示/检测嵌入式JavaScript

## 系统架构

系统采用微服务架构，包含以下组件：

### 核心服务
- **API Gateway** - 处理所有外部请求，路由到相应的服务
- **Upload Service** - 处理文件上传和存储
- **Viewer & Page Service** - 提供PDF预览和页面操作功能
- **Security Service** - 处理PDF安全相关功能
- **Conversion Service** - 处理文件格式转换

### 处理服务
- **OCR Service** - 提供文字识别功能
- **Processing Service** - 提供PDF处理功能
- **Transform Service** - 提供格式转换和文档美化功能

### 基础设施
- **MongoDB** - 存储元数据
- **MinIO** - 对象存储，用于存储文件
- **RabbitMQ** - 消息队列，用于服务间通信
- **Redis** - 缓存

### 监控
- **Prometheus** - 监控指标收集
- **Grafana** - 监控面板

## 部署指南

### 前置条件
- Docker
- Docker Compose

### 部署步骤

1. 克隆仓库
```bash
git clone https://github.com/yourusername/pdf-tools.git
cd pdf-tools
```

2. 启动服务
```bash
cd docker
docker-compose up -d
```

3. 访问服务
- API Gateway: http://localhost:8000
- MinIO控制台: http://localhost:9001
- RabbitMQ管理界面: http://localhost:15672
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

## 国际化支持

系统支持多语言，目前包括：
- 中文
- 英文

## 开发指南

### 环境设置
1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 设置环境变量
```bash
cp .env.example .env
```

3. 启动开发服务器
```bash
uvicorn app:app --reload
```

## API文档

启动服务后，可以通过以下URL访问API文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 贡献指南

1. Fork仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

## 许可证

MIT License