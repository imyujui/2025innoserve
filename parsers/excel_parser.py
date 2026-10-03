# parsers/excel_parser.py
import pandas as pd
import io
from typing import Dict, Optional

# --- 設定：加入新的 Excel 欄位名稱對應 ---
COLUMN_MAPPING_AGGREGATION = {
    "稅後淨利 (期間累計)": {"internal_name": "稅後淨利", "aggregation": "last"},
    "折舊與攤銷 (期間累計)": {"internal_name": "折舊與攤銷", "aggregation": "last"},
    "應收帳款 (期末餘額)": {"internal_name": "應收帳款", "aggregation": "average"},
    "存貨 (期末餘額)": {"internal_name": "存貨", "aggregation": "average"},
    "應付帳款 (期末餘額)": {"internal_name": "應付帳款", "aggregation": "average"},
    "營業收入 (期間累計)": {"internal_name": "營業收入", "aggregation": "last"}, # <--- 新增
    "銷貨成本 (期間累計)": {"internal_name": "銷貨成本", "aggregation": "last"}, # <--- 新增
}
# ---------------------------------------------

# 核心計算需要的內部欄位名稱 (加入營收和成本)
REQUIRED_INTERNAL_ITEMS = [
    "稅後淨利",
    "折舊與攤銷",
    "應收帳款",
    "存貨",
    "應付帳款",
    "營業收入", # <--- 新增
    "銷貨成本"  # <--- 新增
]

def parse_excel_file(file: io.BytesIO) -> Dict:
    """
    修改後的解析器：讀取多日記錄的 Excel 報表，
    計算期間總額 (流量) 或期間平均餘額 (存量)。
    """
    try:
        # header=0: 指定第一行為標題行
        df = pd.read_excel(file, header=0)

        # 清理欄位名稱可能存在的首尾空格
        df.columns = df.columns.str.strip()

        # 檢查 DataFrame 是否為空 或 是否包含 '日期 (Day)' 欄位 (用於確定天數)
        if df.empty or '日期 (Day)' not in df.columns:
            return {"status": "error", "message": "Excel 檔案為空或缺少 '日期 (Day)' 欄位"}

        # 從 '日期 (Day)' 欄位獲取實際天數
        # period_days = len(df) # 直接計算行數作為天數
        # 更穩健：取 '日期 (Day)' 欄的最大值
        try:
             period_days = int(pd.to_numeric(df['日期 (Day)'], errors='coerce').max())
             if period_days <= 0:
                  raise ValueError("無法確定有效天數")
        except Exception as e:
            print(f"無法從 '日期 (Day)' 欄獲取天數: {e}")
            return {"status": "error", "message": "無法確定報告期間的天數"}


        extracted_data = {}
        found_required_count = 0

        # 遍歷我們定義的欄位對應關係
        for excel_col_name, config in COLUMN_MAPPING_AGGREGATION.items():
            internal_item_name = config["internal_name"]
            aggregation_method = config["aggregation"]

            if excel_col_name in df.columns:
                # 嘗試將整欄轉換為數字
                numeric_column = pd.to_numeric(df[excel_col_name].astype(str).str.replace(',', '', regex=False), errors='coerce')
                valid_values = numeric_column.dropna()

                if not valid_values.empty:
                    calculated_value = None
                    if aggregation_method == "last":
                        calculated_value = valid_values.iloc[-1]
                    elif aggregation_method == "average":
                        calculated_value = valid_values.mean()

                    if calculated_value is not None:
                        extracted_data[internal_item_name] = round(float(calculated_value), 2)
                        if internal_item_name in REQUIRED_INTERNAL_ITEMS:
                             found_required_count += 1
                    else:
                         print(f"警告：欄位 '{excel_col_name}' 無法計算彙總值。")
                         extracted_data[internal_item_name] = None
                else:
                    print(f"警告：欄位 '{excel_col_name}' 不包含任何有效的數值資料。")
                    extracted_data[internal_item_name] = None
            else:
                print(f"警告：Excel 檔案中缺少預期欄位 '{excel_col_name}'")
                extracted_data[internal_item_name] = None

        # 檢查是否提取到了足夠的核心數據
        if found_required_count < len(REQUIRED_INTERNAL_ITEMS):
             missing_items = [item for item in REQUIRED_INTERNAL_ITEMS if extracted_data.get(item) is None]
             print(f"警告：未能提取到所有核心計算所需數據，缺少: {missing_items}")
             # return {"status": "error", "message": f"缺少核心數據: {missing_items}"}

        # 在回傳的數據中加入實際天數
        return {"status": "success", "data": extracted_data, "days": period_days}

    except Exception as e:
        print(f"解析 Excel 時發生錯誤: {e}")
        return {"status": "error", "message": f"無法讀取或解析 Excel 檔案: {e}"}