from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Request
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import os
import aiofiles
import uuid
import magic
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

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("upload-service")

# 创建FastAPI应用
app = FastAPI(
    title="PDF Upload Service",
    description="PDF上传服务",
    version="1.0.0",
)

# 配置国际化
i18n.load_path.append(os.path.join(os.path.dirname(__file__), "locales"))
i18n.set("fallback", "zh_CN")

# 配置Prometheus指标
UPLOAD_COUNT = Counter("pdf_uploads_total", "Total PDF Upload Count", ["status"])
UPLOAD_SIZE = Histogram("pdf_upload_size_bytes", "PDF Upload Size in Bytes", buckets=[1024, 1024*1024, 10*1024*1024, 50*1024*1024])
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

# 允许的文件类型
ALLOWED_MIME_TYPES = [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/msword",  # doc
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # pptx
    "application/vnd.ms-powerpoint",  # ppt
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.ms-excel",  # xls
    "text/plain",
    "text/html",
    "text/markdown",
]

# 最大文件大小 (16MB)
MAX_FILE_SIZE = 16 * 1024 * 1024

# 模型
class FileMetadata(BaseModel):
    file_id: str
    original_filename: str
    mime_type: str
    size: int
    upload_time: datetime
    status: str
    bucket: str
    object_name: str
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class PDFInfo(BaseModel):
    page_count: int
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None

class UploadResponse(BaseModel):
    file_id: str
    original_filename: str
    mime_type: str
    size: int
    upload_time: datetime
    status: str
    pdf_info: Optional[PDFInfo] = None

# 中间件
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = datetime.utcnow()
    
    response = await call_next(request)
    
    # 计算请求处理时间
    process_time = (datetime.utcnow() - start_time).total_seconds()
    
    # 记录指标
    endpoint = request.url.path
    
    return response

# 辅助函数
async def get_rabbitmq_channel():
    global rabbitmq_connection, rabbitmq_channel
    
    if rabbitmq_connection is None or rabbitmq_connection.is_closed:
        rabbitmq_connection = await aio_pika.connect_robust(rabbitmq_uri)
        
    if rabbitmq_channel is None or rabbitmq_channel.is_closed:
        rabbitmq_channel = await rabbitmq_connection.channel()
        
    return rabbitmq_channel

async def publish_message(routing_key: str, message: dict):
    channel = await get_rabbitmq_channel()
    
    await channel.declare_exchange(
        "pdf_processing",
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )
    
    await channel.publish(
        aio_pika.Message(
            body=json.dumps(message).encode(),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=routing_key,
    )

async def extract_pdf_info(file_content: bytes) -> Optional[PDFInfo]:
    try:
        with io.BytesIO(file_content) as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # 获取基本信息
            info = pdf_reader.metadata if pdf_reader.metadata else {}
            
            return PDFInfo(
                page_count=len(pdf_reader.pages),
                title=info.get("/Title"),
                author=info.get("/Author"),
                subject=info.get("/Subject"),
                keywords=info.get("/Keywords"),
                creator=info.get("/Creator"),
                producer=info.get("/Producer"),
                creation_date=info.get("/CreationDate"),
                modification_date=info.get("/ModDate"),
            )
    except Exception as e:
        logger.error(f"提取PDF信息时出错: {str(e)}")
        return None

async def validate_file(file: UploadFile) -> bool:
    # 检查文件大小
    file.file.seek(0, 2)  # 移动到文件末尾
    file_size = file.file.tell()  # 获取文件大小
    file.file.seek(0)  # 重置文件指针
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件大小超过限制")
    
    # 读取文件内容
    content = await file.read(1024)  # 读取前1024字节用于检测文件类型
    mime_type = magic.from_buffer(content, mime=True)
    await file.seek(0)  # 重置文件指针
    
    # 检查MIME类型
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=415, detail=f"不支持的文件类型: {mime_type}")
    
    return True

async def save_to_minio(file_content: bytes, object_name: str, mime_type: str) -> bool:
    bucket_name = "pdf-uploads"
    
    try:
        # 确保bucket存在
        found = minio_client.bucket_exists(bucket_name)
        if not found:
            minio_client.make_bucket(bucket_name)
        
        # 上传文件
        minio_client.put_object(
            bucket_name,
            object_name,
            io.BytesIO(file_content),
            length=len(file_content),
            content_type=mime_type,
        )
        
        return True
    except S3Error as err:
        logger.error(f"MinIO错误: {err}")
        raise HTTPException(status_code=500, detail=f"存储文件时出错: {str(err)}")

# 路由：健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# 路由：指标
@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# 路由：上传单个文件
@app.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    x_user: Optional[str] = Header(None),
):
    try:
        # 验证文件
        await validate_file(file)
        
        # 读取文件内容
        file_content = await file.read()
        file_size = len(file_content)
        
        # 记录上传大小指标
        UPLOAD_SIZE.observe(file_size)
        
        # 生成唯一文件ID和对象名
        file_id = str(uuid.uuid4())
        object_name = f"{file_id}/{file.filename}"
        
        # 检测MIME类型
        mime_type = magic.from_buffer(file_content, mime=True)
        
        # 保存到MinIO
        await save_to_minio(file_content, object_name, mime_type)
        
        # 提取PDF信息（如果是PDF文件）
        pdf_info = None
        if mime_type == "application/pdf":
            pdf_info = await extract_pdf_info(file_content)
        
        # 创建元数据
        metadata = FileMetadata(
            file_id=file_id,
            original_filename=file.filename,
            mime_type=mime_type,
            size=file_size,
            upload_time=datetime.utcnow(),
            status="uploaded",
            bucket="pdf-uploads",
            object_name=object_name,
            user_id=x_user,
            metadata={
                "pdf_info": pdf_info.dict() if pdf_info else None,
            },
        )
        
        # 保存元数据到MongoDB
        await files_collection.insert_one(metadata.dict())
        
        # 发布消息到RabbitMQ
        await publish_message(
            routing_key="file.uploaded",
            message={
                "file_id": file_id,
                "mime_type": mime_type,
                "original_filename": file.filename,
                "user_id": x_user,
            },
        )
        
        # 记录上传成功指标
        UPLOAD_COUNT.labels(status="success").inc()
        
        # 返回响应
        return UploadResponse(
            file_id=file_id,
            original_filename=file.filename,
            mime_type=mime_type,
            size=file_size,
            upload_time=metadata.upload_time,
            status="uploaded",
            pdf_info=pdf_info,
        )
    
    except HTTPException as e:
        # 记录上传失败指标
        UPLOAD_COUNT.labels(status="error").inc()
        raise e
    
    except Exception as e:
        # 记录上传失败指标
        UPLOAD_COUNT.labels(status="error").inc()
        logger.error(f"上传文件时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传文件时出错: {str(e)}")

# 路由：上传多个文件
@app.post("/upload/batch", response_model=List[UploadResponse])
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    x_user: Optional[str] = Header(None),
):
    responses = []
    
    for file in files:
        try:
            # 调用单文件上传处理
            response = await upload_file(file, x_user)
            responses.append(response)
        except HTTPException as e:
            # 添加失败信息
            responses.append({
                "original_filename": file.filename,
                "status": "error",
                "error": e.detail,
            })
    
    return responses

# 路由：获取文件信息
@app.get("/files/{file_id}", response_model=FileMetadata)
async def get_file_info(file_id: str):
    file_info = await files_collection.find_one({"file_id": file_id})
    
    if not file_info:
        raise HTTPException(status_code=404, detail=f"文件 {file_id} 不存在")
    
    return file_info

# 路由：获取用户的所有文件
@app.get("/files", response_model=List[FileMetadata])
async def get_user_files(
    x_user: Optional[str] = Header(None),
    skip: int = 0,
    limit: int = 100,
):
    if not x_user:
        raise HTTPException(status_code=401, detail="未授权")
    
    cursor = files_collection.find({"user_id": x_user}).skip(skip).limit(limit)
    files = await cursor.to_list(length=limit)
    
    return files

# 启动事件
@app.on_event("startup")
async def startup_event():
    logger.info("上传服务启动")
    
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
    logger.info("上传服务关闭")
    
    # 关闭RabbitMQ连接
    global rabbitmq_connection
    if rabbitmq_connection:
        await rabbitmq_connection.close()

# 主入口
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)