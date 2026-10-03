# crud.py
from sqlalchemy.orm import Session, joinedload # 匯入 joinedload
from passlib.context import CryptContext

import models
import schemas

# 建立一個密碼雜湊的實例 (只需要建立一次)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- User CRUD ---
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = pwd_context.hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- Financial Report CRUD ---
def create_financial_report(db: Session, report: schemas.FinancialReportCreate, user_id: int):
    """為特定使用者建立一份新的財務報告主體"""
    db_report = models.FinancialReport(period=report.period, owner_id=user_id)
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

def create_line_item(db: Session, item: schemas.LineItemCreate, report_id: int):
    """為特定報告建立一筆會計科目"""
    # 使用 **item.model_dump()** (Pydantic V2 的寫法)
    db_item = models.LineItem(**item.model_dump(), report_id=report_id)
    # db.add(db_item) # 改為在 main.py 中 add_all
    # db.commit() # 改為在 main.py 中 commit
    # db.refresh(db_item) # 改為在 main.py 中 refresh
    return db_item # 回傳物件，由呼叫者決定何時 commit/refresh

def get_report_with_line_items(db: Session, report_id: int):
    """根據 ID 查詢報告，並預先載入其所有的 line_items (給 simulate API 使用)"""
    # 使用 joinedload 進行預載入，提高效率
    return db.query(models.FinancialReport).options(joinedload(models.FinancialReport.line_items)).filter(models.FinancialReport.id == report_id).first()

def get_reports_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    """根據使用者 ID 查詢報告列表 (不含 line_items，分頁查詢)"""
    return db.query(models.FinancialReport)\
             .filter(models.FinancialReport.owner_id == user_id)\
             .order_by(models.FinancialReport.id.desc())\
             .offset(skip)\
             .limit(limit)\
             .all()

def get_report_by_id_and_user(db: Session, report_id: int, user_id: int):
    """根據報告 ID 和使用者 ID 查詢單一報告 (包含 line_items) (給讀取單一報告 API 使用)"""
    # 使用 joinedload 預先載入 line_items
    return db.query(models.FinancialReport)\
             .options(joinedload(models.FinancialReport.line_items))\
             .filter(models.FinancialReport.id == report_id, models.FinancialReport.owner_id == user_id)\
             .first()