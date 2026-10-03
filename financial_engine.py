# financial_engine.py
import math
from typing import Optional, List, Dict

def calculate_working_capital(data: dict) -> Optional[float]:
    """計算營運資金"""
    try:
        ar = float(data.get("應收帳款", 0) or 0)
        inv = float(data.get("存貨", 0) or 0)
        ap = float(data.get("應付帳款", 0) or 0)
        return round((ar + inv) - ap, 2)
    except (ValueError, TypeError) as e:
        print(f"計算營運資金時發生錯誤: {e}")
        return None

def calculate_free_cash_flow(data: dict) -> Optional[float]:
    """計算自由現金流量 (FCF) - 簡化版"""
    try:
        ni = float(data.get("稅後淨利", 0) or 0)
        da = float(data.get("折舊與攤銷", 0) or 0)
        return round(ni + da, 2)
    except (ValueError, TypeError) as e:
        print(f"計算 FCF 時發生錯誤: {e}")
        return None

# --- 修改這裡：計算真實的 CCC ---
def calculate_cash_conversion_cycle(data: dict, days: int) -> Optional[int]:
    """計算現金轉換週期 (CCC)"""
    try:
        # 從 data 字典獲取彙總後的期間數據
        revenue = float(data.get("營業收入", 0) or 0)
        cogs = float(data.get("銷貨成本", 0) or 0)
        avg_ar = float(data.get("應收帳款", 0) or 0) # 解析器已算出平均值
        avg_inv = float(data.get("存貨", 0) or 0)     # 解析器已算出平均值
        avg_ap = float(data.get("應付帳款", 0) or 0)     # 解析器已算出平均值

        # 檢查是否有足夠數據進行計算
        required_for_ccc = [revenue, cogs, avg_ar, avg_inv, avg_ap]
        if any(val is None or val == 0 for val in required_for_ccc):
             print("警告：缺少計算 CCC 所需的數據 (營收/成本/平均AR/INV/AP 可能為 0 或 None)")
             return None # 缺少數據則無法計算

        # 使用從解析器傳入的實際天數
        period_days = days

        # 計算週轉天數 (避免除以零)
        dso = (avg_ar / revenue) * period_days if revenue else 0
        dio = (avg_inv / cogs) * period_days if cogs else 0
        dpo = (avg_ap / cogs) * period_days if cogs else 0
        
        ccc = dso + dio - dpo
        return round(ccc) # 回傳整數天數

    except (ValueError, TypeError, ZeroDivisionError) as e:
        print(f"計算 CCC 時發生錯誤: {e}")
        return None
# --------------------------------

def generate_ai_summary(fcf: Optional[float], wc: Optional[float], ccc: Optional[int]) -> str: # 加入 ccc 參數
    """根據關鍵指標生成文字摘要"""
    summary_parts = []
    
    # FCF 評估
    if fcf is not None:
        if fcf > 0:
            summary_parts.append(f"公司本期自由現金流量為正 ({fcf:,.0f})，顯示在維持營運後仍有現金盈餘，財務狀況穩健。")
        elif fcf == 0:
             summary_parts.append("公司本期自由現金流量為零，收支大致平衡，但缺乏額外擴張資金。")
        else:
            summary_parts.append(f"注意！公司本期自由現金流量為負 ({fcf:,.0f})，代表營運產生的現金不足以支撐擴張，需留意潛在資金壓力。")
    else:
         summary_parts.append("自由現金流量無法計算。")

    # WC 評估
    if wc is not None:
        if wc > 0:
            summary_parts.append(f"同時，營運資金充裕 ({wc:,.0f})，短期償債能力無虞。")
        elif wc == 0:
             summary_parts.append("同時，營運資金為零，短期流動性可能較緊。")
        else:
            summary_parts.append(f"此外，營運資金為負 ({wc:,.0f})，可能面臨短期流動性風險，建議密切監控。")
    else:
         summary_parts.append("營運資金無法計算。")

    # CCC 評估 (如果成功計算出來)
    if ccc is not None:
         summary_parts.append(f"現金轉換週期為 {ccc} 天。") # 可以根據天數長短加入更多描述
    else:
         summary_parts.append("現金轉換週期因數據不足無法計算。")
        
    return "".join(summary_parts) if summary_parts else "無法生成摘要，關鍵指標計算失敗或數據不足。"


def run_simulation(base_data: dict, revenue_growth: float, time_scale: str, periods: int) -> List[float]:
    """執行現金流模擬"""
    try:
        last_net_income = float(base_data.get("稅後淨利", 0) or 0)
        last_d_and_a = float(base_data.get("折舊與攤銷", 0) or 0)
        base_annual_inflow = last_net_income + last_d_and_a
        base_monthly_inflow = base_annual_inflow / 12

        if time_scale == 'daily':
            base_period_inflow = base_monthly_inflow / 30.4
            scale_divisor = 365
        elif time_scale == 'weekly':
            base_period_inflow = base_monthly_inflow / 4.33
            scale_divisor = 52
        else: # monthly
            base_period_inflow = base_monthly_inflow
            scale_divisor = 12

        forecast = []
        current_cash = 0
        for period in range(periods):
            growth_factor = 1 + (revenue_growth * (period + 1) / scale_divisor)
            adjusted_inflow = base_period_inflow * growth_factor
            net_cash_flow = adjusted_inflow # 簡化模型
            current_cash += net_cash_flow
            forecast.append(round(current_cash, 2))
        return forecast
    except Exception as e:
        print(f"執行模擬時發生錯誤: {e}")
        return []

def generate_daily_simulation(end_data: dict, days: int = 30) -> List[Dict]:
    """根據期末數據，模擬生成一份每日的財務報表數據列表。"""
    simulated_days = []
    if days <= 0: return simulated_days
    try:
        ni_end = float(end_data.get("稅後淨利", 0) or 0)
        da_end = float(end_data.get("折舊與攤銷", 0) or 0)
        ar_end = float(end_data.get("應收帳款", 0) or 0)
        inv_end = float(end_data.get("存貨", 0) or 0)
        ap_end = float(end_data.get("應付帳款", 0) or 0)

        daily_ni = ni_end / days if days > 0 else 0
        daily_da = da_end / days if days > 0 else 0
        
        # 反推假設的期初值
        ar_start = ar_end * 0.75 
        inv_start = inv_end * 0.75
        ap_start = ap_end * 0.8 

        daily_ar_change = (ar_end - ar_start) / days if days > 0 else 0
        daily_inv_change = (inv_end - inv_start) / days if days > 0 else 0
        daily_ap_change = (ap_end - ap_start) / days if days > 0 else 0

        cumulative_ni = 0.0; cumulative_da = 0.0
        current_ar = ar_start; current_inv = inv_start; current_ap = ap_start

        for day in range(1, days + 1):
            cumulative_ni += daily_ni; cumulative_da += daily_da
            current_ar += daily_ar_change; current_inv += daily_inv_change
            current_ap += daily_ap_change
            
            final_ni = ni_end if day == days else cumulative_ni
            final_da = da_end if day == days else cumulative_da
            final_ar = ar_end if day == days else current_ar
            final_inv = inv_end if day == days else current_inv
            final_ap = ap_end if day == days else current_ap

            daily_data = {
                "day": day,
                "稅後淨利_累計": round(final_ni, 2), "折舊與攤銷_累計": round(final_da, 2),
                "應收帳款_餘額": round(final_ar, 2), "存貨_餘額": round(final_inv, 2),
                "應付帳款_餘額": round(final_ap, 2)
            }
            simulated_days.append(daily_data)
        return simulated_days
    except Exception as e:
        print(f"生成每日模擬報表時發生錯誤: {e}")
        return []