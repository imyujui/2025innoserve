# models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base # 從 database 匯入 Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    reports = relationship("FinancialReport", back_populates="owner")

class FinancialReport(Base):
    __tablename__ = "financial_reports"
    id = Column(Integer, primary_key=True, index=True)
    period = Column(String, index=True) # 例如: "2025-Q3"
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="reports")
    line_items = relationship("LineItem", back_populates="report", cascade="all, delete-orphan") # 加入 cascade

class LineItem(Base):
    __tablename__ = "line_items"
    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String, index=True) # 例如: "net_income"
    item_value = Column(Float)
    report_id = Column(Integer, ForeignKey("financial_reports.id"))
    report = relationship("FinancialReport", back_populates="line_items")