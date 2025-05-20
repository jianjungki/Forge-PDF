from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import os
import httpx
import logging
from pydantic import BaseModel
import json
from dotenv import load_dotenv
import i18n
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("api-gateway")

# 创建FastAPI应用
app = FastAPI(
    title="PDF Tools API Gateway",
    description="PDF处理系统API网关",
    version="1.0.0",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置国际化
i18n.load_path.append(os.path.join(os.path.dirname(__file__), "locales"))
i18n.set("fallback", "zh_CN")

# 配置JWT
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 配置密码哈希
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 配置Prometheus指标
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP Requests Count", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "HTTP Request Latency", ["method", "endpoint"])

# 服务注册表
SERVICES = {
    "upload": os.getenv("UPLOAD_SERVICE_URL", "http://upload-service:8001"),
    "viewer": os.getenv("VIEWER_SERVICE_URL", "http://viewer-page-service:8002"),
    "conversion": os.getenv("CONVERSION_SERVICE_URL", "http://conversion-service:8003"),
    "security": os.getenv("SECURITY_SERVICE_URL", "http://security-service:8004"),
    "ocr": os.getenv("OCR_SERVICE_URL", "http://ocr-service:8005"),
    "processing": os.getenv("PROCESSING_SERVICE_URL", "http://processing-service:8006"),
}

# 用户模型
class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# 中间件：请求计数和延迟测量
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = datetime.utcnow()
    
    response = await call_next(request)
    
    # 计算请求处理时间
    process_time = (datetime.utcnow() - start_time).total_seconds()
    
    # 记录指标
    endpoint = request.url.path
    REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, endpoint).observe(process_time)
    
    return response

# 验证用户
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    # 这里应该从数据库获取用户，这是一个示例
    fake_users_db = {
        "admin": {
            "username": "admin",
            "full_name": "Administrator",
            "email": "admin@example.com",
            "hashed_password": get_password_hash("admin"),
            "disabled": False,
        }
    }
    if username in fake_users_db:
        user_dict = fake_users_db[username]
        return UserInDB(**user_dict)

def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(None, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="用户已禁用")
    return current_user

# 路由：健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# 路由：指标
@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# 路由：登录获取令牌
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(None, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# 路由：获取当前用户
@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

# 路由：API代理
@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def api_proxy(
    service: str,
    path: str,
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    if service not in SERVICES:
        raise HTTPException(status_code=404, detail=f"服务 {service} 不存在")
    
    # 获取目标服务URL
    target_url = f"{SERVICES[service]}/{path}"
    
    # 获取请求体
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        body = await request.body()
    
    # 获取请求头
    headers = dict(request.headers)
    headers.pop("host", None)  # 移除host头，避免冲突
    
    # 添加用户信息到请求头
    headers["X-User"] = current_user.username
    
    # 获取查询参数
    params = dict(request.query_params)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                params=params,
                headers=headers,
                content=body,
                timeout=30.0,
            )
            
            # 返回响应
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
            )
    except httpx.RequestError as exc:
        logger.error(f"请求错误: {exc}")
        raise HTTPException(status_code=503, detail=f"服务 {service} 不可用")

# 路由：根路径
@app.get("/")
async def root():
    return {
        "message": "欢迎使用PDF处理系统API",
        "docs_url": "/docs",
        "services": list(SERVICES.keys()),
    }

# 启动事件
@app.on_event("startup")
async def startup_event():
    logger.info("API网关启动")

# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API网关关闭")

# 主入口
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)