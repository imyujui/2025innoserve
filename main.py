# main.py
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import io, auth, database, models, schemas, crud, financial_engine, gcis_client
from parsers import excel_parser
from database import engine, get_db # 從 database 匯入 get_db 和 engine
import pandas as pd
from typing import List, Optional
import os

# --- 資料載入設定 ---
DATA_FILE_PATH = os.path.join("data", "六都公司登記資料-H金融、保險及不動產業.csv")
company_data_df: Optional[pd.DataFrame] = None # 全域變數儲存 DataFrame

def load_company_data() -> Optional[pd.DataFrame]:
    """載入 CSV 資料到 Pandas DataFrame，只載入一次"""
    global company_data_df
    if company_data_df is None:
        # 第一次呼叫 API 時才載入，避免伺服器啟動過慢
        if not os.path.exists(DATA_FILE_PATH):
             print(f"警告：找不到資料檔案 {DATA_FILE_PATH}，本地查詢功能將無法使用。")
             company_data_df = pd.DataFrame() # 標記為已嘗試載入（即使是空的）
             return company_data_df

        try:
            print(f"嘗試從 {DATA_FILE_PATH} 載入公司資料...")
            company_data_df = pd.read_csv(DATA_FILE_PATH, dtype=str) # 將所有欄位讀為字串
            company_data_df.columns = company_data_df.columns.str.strip() # 清理欄位名空格
            print("公司資料載入成功！")
            # 預處理關鍵欄位
            if '統一編號' in company_data_df.columns:
                 company_data_df['統一編號'] = company_data_df['統一編號'].str.strip()
            if '公司名稱' in company_data_df.columns:
                 company_data_df['公司名稱'] = company_data_df['公司名稱'].str.strip()
        except FileNotFoundError:
            # 這段理論上不會執行到，因為上面已經檢查過檔案是否存在
            print(f"錯誤：找不到資料檔案 {DATA_FILE_PATH}")
            company_data_df = pd.DataFrame() # 建立空 DataFrame
        except Exception as e:
            print(f"載入或處理公司資料時發生錯誤: {e}")
            company_data_df = pd.DataFrame()
    return company_data_df
# ----------------------

app = FastAPI(title="AI 智慧資金管理平台 API", version="1.0.0")

# --- 應用程式啟動事件 ---
@app.on_event("startup")
def on_startup():
    print("應用程式啟動中...")
    # 建立資料表
    try:
         models.Base.metadata.create_all(bind=engine)
         print("資料表檢查/建立完成。")
    except Exception as e:
         print(f"建立資料表時發生錯誤: {e}")
    # 預先載入一次公司資料 (可選)
    # load_company_data()
# ----------------------

# --- CORS 設定 ---
# !!! 請務必將 YOUR_WIX_SITE_URL 換成您 Wix 網站的實際網址 !!!
# 本地測試時，加入 "null"
origins = [
    "http://localhost:8000", # 允許本地 API 文件頁面
    "http://127.0.0.1:8000", # 同上
    "null",                  # 允許本地 file:/// 協議 (僅限測試)
    # "http://localhost:8081", # 如果您使用 python -m http.server
    "https://YOUR_WIX_SITE_URL", # 未來的 Wix 網址
    # "*" # 開發階段可以暫時用 "*" 允許所有，但部署前務必移除
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -----------------

# --- API Endpoints ---

@app.post("/token", response_model=schemas.Token, summary="使用者登入以獲取權杖")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="不正確的使用者名稱或密碼",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=schemas.User, summary="註冊新使用者")
def create_user_api(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="此使用者名稱已被註冊")
    return crud.create_user(db=db, user=user)

@app.get("/users/me/", response_model=schemas.User, summary="獲取當前登入者資訊")
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@app.post("/users/me/reports/", response_model=schemas.ReportAnalysisResult, summary="為當前登入者上傳財報並分析")
async def create_report_for_current_user(
    period: str, # 改回查詢參數
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    contents = await file.read()
    file_stream = io.BytesIO(contents)

    if file.content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        result = excel_parser.parse_excel_file(file_stream)
    else:
        raise HTTPException(status_code=400, detail="不支援的檔案格式，目前僅支援 Excel (.xlsx)")

    extracted_data = result.get("data")
    period_days = result.get("days") # 從解析結果獲取天數

    if result["status"] == "error" or not extracted_data or period_days is None:
        raise HTTPException(status_code=400, detail=f"檔案解析失敗: {result.get('message', '無法確定天數或提取數據')}")

    working_capital = financial_engine.calculate_working_capital(extracted_data)
    free_cash_flow = financial_engine.calculate_free_cash_flow(extracted_data)
    cash_conversion_cycle = financial_engine.calculate_cash_conversion_cycle(extracted_data, days=period_days) # 傳遞天數
    ai_summary = financial_engine.generate_ai_summary(fcf=free_cash_flow, wc=working_capital, ccc=cash_conversion_cycle) # 傳遞 CCC 結果

    report_create = schemas.FinancialReportCreate(period=period)
    db_report = crud.create_financial_report(db=db, report=report_create, user_id=current_user.id)

    items_to_commit = []
    for item_name, item_value in extracted_data.items():
        if item_value is not None:
            item_create = schemas.LineItemCreate(item_name=item_name, item_value=item_value)
            db_item = models.LineItem(**item_create.model_dump(), report_id=db_report.id)
            items_to_commit.append(db_item)

    if items_to_commit:
        db.add_all(items_to_commit)
        db.commit()

    db.refresh(db_report) # 重新整理報告以載入關聯的 line_items

    # 直接從 db_report 轉換 Pydantic 模型 (會包含 line_items)
    analysis_result = schemas.ReportAnalysisResult.model_validate(db_report)
    # 手動附加計算結果
    analysis_result.working_capital = working_capital
    analysis_result.free_cash_flow = free_cash_flow
    analysis_result.cash_conversion_cycle = cash_conversion_cycle
    analysis_result.ai_summary = ai_summary

    return analysis_result

@app.get("/users/me/reports/", response_model=List[schemas.FinancialReport], summary="獲取當前登入者的歷史報告列表")
async def read_reports_for_current_user(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    reports = crud.get_reports_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return reports

@app.get("/users/me/reports/{report_id}", response_model=schemas.ReportAnalysisResult, summary="獲取當前登入者指定報告的詳細分析結果")
async def read_report_details_for_current_user(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    db_report = crud.get_report_by_id_and_user(db, report_id=report_id, user_id=current_user.id)
    if db_report is None:
        raise HTTPException(status_code=404, detail="找不到報告或報告不屬於您")

    base_data = {item.item_name: item.item_value for item in db_report.line_items}
    # 獲取實際天數 (假設 period 格式固定，或從其他地方獲取)
    # 這裡需要一個更穩健的方式來獲取天數，暫時先假設 30
    period_days = 30 # 假設為 30，或者需要從 db_report.period 解析
    if db_report.line_items: # 如果有 line_items，嘗試從模擬數據獲取天數
         try:
              daily_sim_data = financial_engine.generate_daily_simulation(end_data=base_data, days=period_days) # 生成模擬數據
              if daily_sim_data: period_days = len(daily_sim_data) # 更新為模擬的天數
         except: pass # 忽略生成錯誤

    working_capital = financial_engine.calculate_working_capital(base_data)
    free_cash_flow = financial_engine.calculate_free_cash_flow(base_data)
    cash_conversion_cycle = financial_engine.calculate_cash_conversion_cycle(base_data, days=period_days)
    ai_summary = financial_engine.generate_ai_summary(fcf=free_cash_flow, wc=working_capital, ccc=cash_conversion_cycle)

    analysis_result = schemas.ReportAnalysisResult.model_validate(db_report)
    analysis_result.working_capital = working_capital
    analysis_result.free_cash_flow = free_cash_flow
    analysis_result.cash_conversion_cycle = cash_conversion_cycle
    analysis_result.ai_summary = ai_summary

    return analysis_result

@app.get("/users/me/reports/{report_id}/daily_simulation",
         response_model=schemas.DailySimulationResponse,
         summary="獲取指定報告的每日模擬財務數據")
async def get_daily_simulation_for_report(
    report_id: int,
    days: int = Query(30, ge=1, le=365, description="要模擬的天數"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    db_report = crud.get_report_by_id_and_user(db, report_id=report_id, user_id=current_user.id)
    if db_report is None:
        raise HTTPException(status_code=404, detail="找不到報告或報告不屬於您")

    base_data = {item.item_name: item.item_value for item in db_report.line_items}

    daily_simulation_data = financial_engine.generate_daily_simulation(end_data=base_data, days=days)

    if not daily_simulation_data:
         raise HTTPException(status_code=500, detail="生成每日模擬數據時發生錯誤")

    return schemas.DailySimulationResponse(
        period=db_report.period,
        simulation_days=days,
        daily_data=daily_simulation_data
    )

@app.post("/api/v1/simulate", response_model=schemas.SimulationResponse, summary="執行互動式現金流模擬")
def run_simulation_api(request: schemas.SimulationRequest, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_report = crud.get_report_with_line_items(db, report_id=request.report_id)
    if not db_report or db_report.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="基礎報告不存在或不屬於您")

    base_data = {item.item_name: item.item_value for item in db_report.line_items}

    forecast_data = financial_engine.run_simulation(
        base_data=base_data,
        revenue_growth=request.revenue_growth,
        time_scale=request.time_scale,
        periods=request.periods
    )

    if not forecast_data:
         raise HTTPException(status_code=500, detail="模擬計算時發生錯誤")

    return schemas.SimulationResponse(
        time_scale=request.time_scale,
        forecast_cash_balance=forecast_data
    )

@app.get("/api/v1/partner-check/{unified_number}",
         summary="查詢合作夥伴營運狀態 (暫停服務)",
         status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
         response_model=dict)
async def check_partner_status(
    unified_number: str,
    current_user: models.User = Depends(auth.get_current_user)
):
    return {"status": "維護中", "reason": "此功能目前正在進行更新，請稍後再試。"}

@app.get("/api/v1/local-company-search/",
         response_model=List[schemas.CompanyLocalInfo],
         summary="從本地檔案查詢公司資料")
async def search_local_company_data(
    query: str = Query(..., min_length=2, description="輸入統一編號 (8位數字) 或部分公司名稱 (至少2字) 進行查詢"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    df = load_company_data() # 確保資料已載入
    if df is None or df.empty:
         # 第一次載入失敗時，load_company_data 會印出錯誤，這裡直接回傳錯誤給前端
         raise HTTPException(status_code=503, detail=f"本地公司資料無法載入，請檢查伺服器日誌與檔案: {DATA_FILE_PATH}")

    results = []
    unified_number_col = '統一編號'
    company_name_col = '公司名稱'
    total_capital_col = '資本總額'
    paid_in_capital_col = '實收資本額' # 可選

    # 檢查必要欄位是否存在，如果不存在則直接回傳錯誤
    required_cols = [unified_number_col, company_name_col, total_capital_col]
    if not all(col in df.columns for col in required_cols):
         missing = [col for col in required_cols if col not in df.columns]
         print(f"錯誤：CSV 檔案缺少必要欄位: {', '.join(missing)}")
         raise HTTPException(status_code=500, detail=f"伺服器錯誤：本地資料檔案格式不符，缺少欄位: {', '.join(missing)}")

    query = query.strip()
    matched_df = pd.DataFrame()

    if query.isdigit() and len(query) == 8:
        matched_df = df[df[unified_number_col] == query]
    elif len(query) >= 2:
        try:
             # 確保查詢前欄位是字串且無 NA 值
             search_series = df[company_name_col].astype(str).fillna('')
             matched_df = df[search_series.str.contains(query, case=False, na=False)]
        except AttributeError:
             print("錯誤：公司名稱欄位無法進行字串包含查詢。")
             matched_df = pd.DataFrame() # 設為空
             raise HTTPException(status_code=500, detail="伺服器錯誤：本地資料檔案格式不符，無法查詢公司名稱。")


    if matched_df.empty:
        return []

    for index, row in matched_df.iterrows():
        # 安全地讀取欄位值
        company_name = row.get(company_name_col)
        unified_number = row.get(unified_number_col)
        total_cap_str = row.get(total_capital_col)
        paid_cap_str = row.get(paid_in_capital_col)

        try: total_cap = float(str(total_cap_str).replace(',','')) if pd.notna(total_cap_str) else None
        except (ValueError, AttributeError): total_cap = None

        paid_cap = None
        if paid_cap_str is not None:
             try: paid_cap = float(str(paid_cap_str).replace(',','')) if pd.notna(paid_cap_str) else None
             except (ValueError, AttributeError): paid_cap = None

        results.append(schemas.CompanyLocalInfo(
            company_name=company_name,
            unified_number=unified_number,
            total_capital=total_cap,
            paid_in_capital=paid_cap
        ))
        if len(results) >= 10: break # 限制最多回傳 10 筆

    return results

# --- 提供 HTML 頁面的路由 (修正後版本) ---
@app.get("/", response_class=FileResponse, include_in_schema=False)
async def read_index():
    file_path = "static/index.html"
    if not os.path.exists(file_path): return HTTPException(status_code=404, detail="Index page not found")
    return file_path

@app.get("/login", response_class=FileResponse, include_in_schema=False)
async def read_login():
    file_path = "static/login.html"
    if not os.path.exists(file_path): return HTTPException(status_code=404)
    return file_path

@app.get("/register", response_class=FileResponse, include_in_schema=False)
async def read_register():
    file_path = "static/register.html"
    if not os.path.exists(file_path): return HTTPException(status_code=404)
    return file_path

@app.get("/dashboard", response_class=FileResponse, include_in_schema=False)
async def read_dashboard():
    file_path = "static/dashboard.html"
    if not os.path.exists(file_path): return HTTPException(status_code=404)
    return file_path

@app.get("/upload", response_class=FileResponse, include_in_schema=False)
async def read_upload():
    file_path = "static/upload.html"
    if not os.path.exists(file_path): return HTTPException(status_code=404)
    return file_path

@app.get("/analysis", response_class=FileResponse, include_in_schema=False)
async def read_analysis():
    file_path = "static/analysis.html"
    if not os.path.exists(file_path): return HTTPException(status_code=404)
    return file_path

@app.get("/future", response_class=FileResponse, include_in_schema=False)
async def read_future():
    file_path = "static/future.html"
    if not os.path.exists(file_path): return HTTPException(status_code=404)
    return file_path

@app.get("/history", response_class=FileResponse, include_in_schema=False)
async def read_history():
    file_path = "static/history.html"
    if not os.path.exists(file_path): return HTTPException(status_code=404)
    return file_path

@app.get("/query", response_class=FileResponse, include_in_schema=False)
async def read_query():
    file_path = "static/query.html"
    if not os.path.exists(file_path): return HTTPException(status_code=404)
    return file_path

# --- 提供靜態檔案 (CSS, JS, 圖片等) ---
# 將 /static 路徑掛載到 static 資料夾
# 確保這行在所有 @app.get HTML 路由之後
app.mount("/static", StaticFiles(directory="static"), name="static")