# auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import crud, models, schemas, database
from database import get_db # 直接從 database 匯入 get_db
import os # 匯入 os

# --- 設定 ---
# !!! 非常重要：請務必將 SECRET_KEY 移到 .env 檔案中管理 !!!
# 在 .env 加入: SECRET_KEY=YOUR_RANDOM_SECRET_STRING
# load_dotenv() 已經在 database.py 中執行過
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key_if_not_set_in_env") # 從環境變數讀取
if SECRET_KEY == "fallback_secret_key_if_not_set_in_env":
     print("警告：未在 .env 中設定 SECRET_KEY，請立即設定！")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # Token 有效期 30 分鐘

# --- 工具 ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- 核心函式 ---
def verify_password(plain_password, hashed_password):
    # 使用 crud.py 中的 pwd_context 進行驗證
    return crud.pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 使用 async def 並依賴 get_db
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無法驗證憑證",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user # 直接回傳 SQLAlchemy User 物件