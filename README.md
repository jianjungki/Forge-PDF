# PDF Processing System

[English](./README.md) | [中文](./README-zh.md)

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