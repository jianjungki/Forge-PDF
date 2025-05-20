from fastapi import FastAPI, HTTPException, Depends, Header, Request, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from typing import List, Optional, Dict, Any
import os
import aiofiles
import uuid
import logging
from datetime import datetime
import json
from pydantic import BaseModel
import asyncio
from minio import Minio
from minio.error import S3Error
import aio_pika
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import i18n
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import PyPDF2
import io
import fitz  # PyMuPDF
from PIL import Image
from pdf2image import convert_from_bytes
import tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("viewer-page-service")

# 创建FastAPI应用
app = FastAPI(
    title="PDF Viewer & Page Service",
    description="PDF查看与页面服务",
    version="1.0.0",
)

# 配置国际化
i18n.load_path.append(os.path.join(os.path.dirname(__file__), "locales"))
i18n.set("fallback", "zh_CN")

# 配置Prometheus指标
PAGE_OPERATIONS = Counter("pdf_page_operations_total", "Total PDF Page Operations Count", ["operation"])
PROCESSING_TIME = Histogram("pdf_processing_time_seconds", "PDF Processing Time in Seconds")

# MinIO客户端
minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "minio:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minio"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minio123"),
    secure=False,
)

# MongoDB客户端
mongo_client = AsyncIOMotorClient(os.getenv("MONGODB_URI", "mongodb://mongodb:27017/pdf-tools"))
db = mongo_client.get_database("pdf-tools")
files_collection = db.get_collection("files")

# RabbitMQ连接
rabbitmq_uri = os.getenv("RABBITMQ_URI", "amqp://guest:guest@rabbitmq:5672/")
rabbitmq_connection = None
rabbitmq_channel = None

# 模型
class PageInfo(BaseModel):
    page_number: int
    width: float
    height: float
    rotation: int

class PDFInfo(BaseModel):
    file_id: str
    total_pages: int
    pages: List[PageInfo]
    metadata: Optional[Dict[str, Any]] = None

class PageOperation(BaseModel):
    operation: str
    pages: List[int]
    parameters: Optional[Dict[str, Any]] = None

class OperationResponse(BaseModel):
    operation_id: str
    status: str
    message: str

# 辅助函数
async def get_rabbitmq_channel():
    global rabbitmq_connection, rabbitmq_channel
    
    if rabbitmq_connection is None or rabbitmq_connection.is_closed:
        rabbitmq_connection = await aio_pika.connect_robust(rabbitmq_uri)
        
    if rabbitmq_channel is None or rabbitmq_channel.is_closed:
        rabbitmq_channel = await rabbitmq_connection.channel()
        
    return rabbitmq_channel

async def get_pdf_content(file_id: str) -> bytes:
    try:
        file_info = await files_collection.find_one({"file_id": file_id})
        if not file_info:
            raise HTTPException(status_code=404, detail=f"文件 {file_id} 不存在")
            
        content = minio_client.get_object(
            file_info["bucket"],
            file_info["object_name"],
        ).read()
        
        return content
    except Exception as e:
        logger.error(f"获取PDF内容时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def save_pdf_content(content: bytes, file_id: str) -> str:
    try:
        object_name = f"{file_id}/processed.pdf"
        minio_client.put_object(
            "pdf-uploads",
            object_name,
            io.BytesIO(content),
            length=len(content),
            content_type="application/pdf",
        )
        return object_name
    except Exception as e:
        logger.error(f"保存PDF内容时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 路由：健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# 路由：指标
@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# 路由：获取PDF信息
@app.get("/files/{file_id}/info", response_model=PDFInfo)
async def get_pdf_info(file_id: str):
    try:
        content = await get_pdf_content(file_id)
        
        with io.BytesIO(content) as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            doc = fitz.open(stream=content, filetype="pdf")
            
            pages = []
            for page_num in range(len(pdf_reader.pages)):
                page = doc[page_num]
                pages.append(PageInfo(
                    page_number=page_num + 1,
                    width=page.rect.width,
                    height=page.rect.height,
                    rotation=page.rotation,
                ))
            
            return PDFInfo(
                file_id=file_id,
                total_pages=len(pdf_reader.pages),
                pages=pages,
                metadata=pdf_reader.metadata if pdf_reader.metadata else None,
            )
            
    except Exception as e:
        logger.error(f"获取PDF信息时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 路由：获取页面预览图
@app.get("/files/{file_id}/pages/{page_number}/preview")
async def get_page_preview(
    file_id: str,
    page_number: int,
    width: Optional[int] = None,
    height: Optional[int] = None,
):
    try:
        content = await get_pdf_content(file_id)
        
        with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp_pdf:
            tmp_pdf.write(content)
            tmp_pdf.seek(0)
            
            images = convert_from_bytes(
                content,
                first_page=page_number,
                last_page=page_number,
            )
            
            if not images:
                raise HTTPException(status_code=404, detail="页面不存在")
            
            image = images[0]
            
            if width and height:
                image = image.resize((width, height), Image.LANCZOS)
            
            img_byte_array = io.BytesIO()
            image.save(img_byte_array, format='PNG')
            img_byte_array.seek(0)
            
            return StreamingResponse(img_byte_array, media_type="image/png")
            
    except Exception as e:
        logger.error(f"获取页面预览图时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 路由：页面操作
@app.post("/files/{file_id}/operations", response_model=OperationResponse)
async def perform_page_operation(
    file_id: str,
    operation: PageOperation,
):
    try:
        content = await get_pdf_content(file_id)
        operation_id = str(uuid.uuid4())
        
        # 记录操作指标
        PAGE_OPERATIONS.labels(operation=operation.operation).inc()
        
        with io.BytesIO(content) as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            pdf_writer = PyPDF2.PdfWriter()
            
            if operation.operation == "rotate":
                angle = operation.parameters.get("angle", 90)
                for i in range(len(pdf_reader.pages)):
                    if i + 1 in operation.pages:
                        page = pdf_reader.pages[i]
                        page.rotate(angle)
                    pdf_writer.add_page(pdf_reader.pages[i])
                    
            elif operation.operation == "delete":
                for i in range(len(pdf_reader.pages)):
                    if i + 1 not in operation.pages:
                        pdf_writer.add_page(pdf_reader.pages[i])
                        
            elif operation.operation == "extract":
                for page_num in operation.pages:
                    if 0 < page_num <= len(pdf_reader.pages):
                        pdf_writer.add_page(pdf_reader.pages[page_num - 1])
                        
            else:
                raise HTTPException(status_code=400, detail=f"不支持的操作: {operation.operation}")
            
            # 保存处理后的PDF
            output = io.BytesIO()
            pdf_writer.write(output)
            output.seek(0)
            
            # 保存到MinIO
            object_name = await save_pdf_content(output.getvalue(), operation_id)
            
            # 更新MongoDB
            await files_collection.insert_one({
                "file_id": operation_id,
                "original_file_id": file_id,
                "operation": operation.operation,
                "status": "completed",
                "bucket": "pdf-uploads",
                "object_name": object_name,
                "created_at": datetime.utcnow(),
            })
            
            return OperationResponse(
                operation_id=operation_id,
                status="completed",
                message="操作成功完成",
            )
            
    except Exception as e:
        logger.error(f"执行页面操作时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 路由：合并PDF
@app.post("/merge", response_model=OperationResponse)
async def merge_pdfs(
    file_ids: List[str],
    x_user: Optional[str] = Header(None),
):
    try:
        operation_id = str(uuid.uuid4())
        merger = PyPDF2.PdfMerger()
        
        for file_id in file_ids:
            content = await get_pdf_content(file_id)
            merger.append(io.BytesIO(content))
        
        output = io.BytesIO()
        merger.write(output)
        output.seek(0)
        
        # 保存到MinIO
        object_name = await save_pdf_content(output.getvalue(), operation_id)
        
        # 更新MongoDB
        await files_collection.insert_one({
            "file_id": operation_id,
            "original_file_ids": file_ids,
            "operation": "merge",
            "status": "completed",
            "bucket": "pdf-uploads",
            "object_name": object_name,
            "created_at": datetime.utcnow(),
            "user_id": x_user,
        })
        
        return OperationResponse(
            operation_id=operation_id,
            status="completed",
            message="PDF合并成功",
        )
        
    except Exception as e:
        logger.error(f"合并PDF时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 路由：添加水印
@app.post("/files/{file_id}/watermark", response_model=OperationResponse)
async def add_watermark(
    file_id: str,
    text: str,
    x_user: Optional[str] = Header(None),
):
    try:
        operation_id = str(uuid.uuid4())
        content = await get_pdf_content(file_id)
        
        with io.BytesIO(content) as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            pdf_writer = PyPDF2.PdfWriter()
            
            # 创建水印页面
            watermark = io.BytesIO()
            c = canvas.Canvas(watermark, pagesize=letter)
            c.setFont("Helvetica", 60)
            c.setFillColorRGB(0.5, 0.5, 0.5, 0.3)  # 灰色，30%透明度
            c.rotate(45)
            c.drawString(100, 100, text)
            c.save()
            watermark.seek(0)
            
            watermark_pdf = PyPDF2.PdfReader(watermark)
            watermark_page = watermark_pdf.pages[0]
            
            # 为每一页添加水印
            for page in pdf_reader.pages:
                page.merge_page(watermark_page)
                pdf_writer.add_page(page)
            
            output = io.BytesIO()
            pdf_writer.write(output)
            output.seek(0)
            
            # 保存到MinIO
            object_name = await save_pdf_content(output.getvalue(), operation_id)
            
            # 更新MongoDB
            await files_collection.insert_one({
                "file_id": operation_id,
                "original_file_id": file_id,
                "operation": "watermark",
                "status": "completed",
                "bucket": "pdf-uploads",
                "object_name": object_name,
                "created_at": datetime.utcnow(),
                "user_id": x_user,
                "watermark_text": text,
            })
            
            return OperationResponse(
                operation_id=operation_id,
                status="completed",
                message="水印添加成功",
            )
            
    except Exception as e:
        logger.error(f"添加水印时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 路由：下载处理后的文件
@app.get("/files/{file_id}/download")
async def download_file(file_id: str):
    try:
        file_info = await files_collection.find_one({"file_id": file_id})
        if not file_info:
            raise HTTPException(status_code=404, detail=f"文件 {file_id} 不存在")
            
        content = minio_client.get_object(
            file_info["bucket"],
            file_info["object_name"],
        ).read()
        
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{file_id}.pdf"',
            },
        )
        
    except Exception as e:
        logger.error(f"下载文件时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 启动事件
@app.on_event("startup")
async def startup_event():
    logger.info("查看与页面服务启动")
    
    # 确保MinIO bucket存在
    try:
        found = minio_client.bucket_exists("pdf-uploads")
        if not found:
            minio_client.make_bucket("pdf-uploads")
            logger.info("创建了'pdf-uploads' bucket")
    except Exception as e:
        logger.error(f"MinIO初始化错误: {str(e)}")
    
    # 初始化RabbitMQ连接
    try:
        await get_rabbitmq_channel()
        logger.info("RabbitMQ连接已建立")
    except Exception as e:
        logger.error(f"RabbitMQ连接错误: {str(e)}")

# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("查看与页面服务关闭")
    
    # 关闭RabbitMQ连接
    global rabbitmq_connection
    if rabbitmq_connection:
        await rabbitmq_connection.close()

# 主入口
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)