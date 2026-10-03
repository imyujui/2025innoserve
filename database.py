# database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv() # 載入 .env 檔案中的環境變數 (僅本地開發時有效)

# --- 資料庫連線設定 ---
# 優先從環境變數讀取 DATABASE_URL (Render 等雲平台會設定這個)
# 如果環境變數不存在，則使用本地的預設值 (!!! 請務必將 YOUR_PASSWORD 替換成您自己的 PostgreSQL 密碼 !!!)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:00000000@localhost/financial_db")
# -----------------------

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Dependency (資料庫連線產生器) ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# -----------------------------------