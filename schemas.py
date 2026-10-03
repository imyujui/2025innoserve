# schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Literal # 確保匯入 List 和 Literal

# --- LineItem Schemas ---
class LineItemBase(BaseModel):
    item_name: str
    item_value: float

class LineItemCreate(LineItemBase):
    pass

class LineItem(LineItemBase):
    id: int
    report_id: int

    class Config:
        from_attributes = True

# --- FinancialReport Schemas ---
class FinancialReportBase(BaseModel):
    period: str # 例如 "2025-Q3"

class FinancialReportCreate(FinancialReportBase):
    pass

class FinancialReport(FinancialReportBase):
    id: int
    owner_id: int
    line_items: List[LineItem] = [] # 確保這裡是 List[LineItem]

    class Config:
        from_attributes = True

# --- User Schemas ---
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    class Config:
        from_attributes = True

# --- Token Schema ---
class Token(BaseModel):
    access_token: str
    token_type: str

# --- API Response Model ---
class ReportAnalysisResult(FinancialReport):
    working_capital: Optional[float] = None
    free_cash_flow: Optional[float] = None
    cash_conversion_cycle: Optional[int] = None # 注意：目前還是示意值
    ai_summary: Optional[str] = None

# --- Simulation Schemas ---
class SimulationRequest(BaseModel):
    report_id: int
    revenue_growth: float = Field(default=0.0, description="營收成長率 (例如 0.1 代表 10%)")
    time_scale: Literal['daily', 'weekly', 'monthly'] = Field(default='monthly', description="時間尺度")
    periods: int = Field(default=12, ge=1, le=365, description="模擬期數 (例如 12個月 或 52週 或 365天)") # 調整最大期數

class SimulationResponse(BaseModel):
    time_scale: str
    forecast_cash_balance: List[float] # 確保這裡是 List[float]

# --- Local Company Search Schema ---
class CompanyLocalInfo(BaseModel):
    company_name: Optional[str] = None
    unified_number: Optional[str] = None
    total_capital: Optional[float] = None # 假設資本額是數字
    paid_in_capital: Optional[float] = None # 假設資本額是數字

# --- Daily Simulation Schemas ---
class DailyFinancialSim(BaseModel):
    day: int
    稅後淨利_累計: Optional[float] = None
    折舊與攤銷_累計: Optional[float] = None
    應收帳款_餘額: Optional[float] = None
    存貨_餘額: Optional[float] = None
    應付帳款_餘額: Optional[float] = None

class DailySimulationResponse(BaseModel):
    period: str # 回傳原始報告的期間
    simulation_days: int # 回傳模擬的天數
    daily_data: List[DailyFinancialSim] # 包含每日數據的列表