# gcis_client.py
import requests
import os
from dotenv import load_dotenv

# 從 .env 檔案載入環境變數 (API 金鑰)
load_dotenv()

# !!! 請務必在您的專案根目錄建立一個 .env 檔案，並在其中加入您的 API 金鑰:
# GCIS_API_KEY=YOUR_ACTUAL_API_KEY
API_KEY = os.getenv("GCIS_API_KEY") 
BASE_URL = "https://data.gcis.nat.gov.tw/od/api/v1/rest/datastore"

# 各資料集的唯一識別碼 (Resource ID) - 請再次確認這些 ID 是否為最新
COMPANY_INFO_ID = "236000000G-000001" # 公司登記基本資料 (應用一)
BUSINESS_INFO_ID = "236000000G-000002" # 商業登記基本資料
SUSPENSION_LIST_ID = "236000000G-000012" # 公司解散、撤銷、廢止
# 注意：全國營業(稅籍)登記資料的 ID 可能需要重新查找，這裡先用公司登記代替部分功能

def _make_request(resource_id: str, filters: dict):
    """通用請求函式"""
    if not API_KEY:
        return {"error": "API 金鑰未設定"}

    params = {
        'resource_id': resource_id,
        'format': 'json',
        'api_key': API_KEY,
    }

    # 建立 $filter 字串
    filter_str = " and ".join([f"{key} eq '{value}'" for key, value in filters.items()])
    if filter_str:
         params['$filter'] = filter_str

    try:
        response = requests.get(BASE_URL, params=params, timeout=10) # 設定超時
        response.raise_for_status() # 檢查 HTTP 錯誤
        data = response.json()
        if data.get("success") is False:
             return {"error": data.get("result", {}).get("message", "API 請求失敗")}
        return data.get('result', {}).get('records', [])
    except requests.exceptions.RequestException as e:
        print(f"呼叫 GCIS API 時發生錯誤: {e}")
        return {"error": f"網路請求失敗: {e}"}
    except Exception as e:
        print(f"處理 GCIS API 回應時發生未知錯誤: {e}")
        return {"error": f"處理回應失敗: {e}"}

def get_company_status(unified_number: str):
    """
    功能 4.2: 查詢合作夥伴健康度
    查詢公司登記狀態，並檢查是否在停歇業名單中。
    """
    # 1. 檢查是否在停歇業 (解散/撤銷/廢止) 名單中
    suspension_records = _make_request(SUSPENSION_LIST_ID, {"President_No": unified_number}) # 注意：欄位名稱可能需確認
    if isinstance(suspension_records, dict) and "error" in suspension_records:
        return {"status": "查詢失敗", "reason": suspension_records["error"]}
    if suspension_records:
         # 從記錄中提取狀態描述，例如 "解散"
         status_desc = suspension_records[0].get("Change_Desc", "已停業/解散") 
         return {"status": "停業或已解散", "reason": status_desc}

    # 2. 如果不在停歇業名單，查詢公司登記基本資料
    company_records = _make_request(COMPANY_INFO_ID, {"Business_Accounting_NO": unified_number})
    if isinstance(company_records, dict) and "error" in company_records:
         return {"status": "查詢失敗", "reason": company_records["error"]}

    if company_records:
        status_desc = company_records[0].get("Business_Status_Desc", "狀態不明")
        if status_desc == "核准設立":
             return {"status": "正常營運", "reason": status_desc}
        else:
             # 其他狀態如 "撤銷", "廢止" 等也視為非正常
             return {"status": "非正常營運", "reason": status_desc}

    # 3. 如果公司和停歇業都查不到，可能也要查商業登記
    business_records = _make_request(BUSINESS_INFO_ID, {"Business_Accounting_NO": unified_number})
    if isinstance(business_records, dict) and "error" in business_records:
         # 如果連商業登記都查詢失敗，才回報查無資料
         if (isinstance(company_records, list) and not company_records):
              return {"status": "查無資料", "reason": business_records["error"]}
         else: # 若公司登記有查到但商業登記失敗，以公司登記為主
              return {"status": "狀態不明", "reason": "商業登記查詢失敗"}

    if business_records:
         status_desc = business_records[0].get("Business_Status_Desc", "狀態不明")
         # 商號的正常狀態通常也是 "核准設立" 或類似詞語
         if status_desc == "核准設立":
              return {"status": "正常營運", "reason": f"商號: {status_desc}"}
         else:
              return {"status": "非正常營運", "reason": f"商號: {status_desc}"}

    # 如果所有都查不到
    return {"status": "查無資料", "reason": "在公司、商業及停歇業登記中均未找到此統編"}

# --- 功能 4.1 的基礎 (待擴充) ---
# 這個功能比較複雜，因為 "全國營業(稅籍)登記資料" 非常龐大，
# 且不直接包含財務比率，我們只能做基於登記資料的比較。
# def get_industry_benchmarks(industry_code: str, region: str = None):
#     """
#     功能 4.1: 獲取行業標竿數據 (基於登記資料)
#     例如：計算同業平均資本額、公司數量等。
#     需要找到 "全國營業(稅籍)登記資料" 的 Resource ID 並實作篩選邏輯。
#     """
#     # 實作細節：
#     # 1. 找到全國營業稅籍資料的 Resource ID
#     # 2. 建立篩選條件 (行業代碼, 可能還有地區)
#     # 3. 呼叫 _make_request
#     # 4. 對回傳的大量資料進行彙總計算 (平均資本額、家數)
#     # 5. 回傳計算結果
#     pass # 暫時留空