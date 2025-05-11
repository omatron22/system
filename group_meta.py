# group_meta.py  — central place for units / scales
UNITS = {
    "vision": "score_0_10",
    "market_assessment": "0_100",
    "strategic_assessment": "0_100",
    "risk_assessment": {"prob": "1_5", "impact": "1_9", "derived": "risk_index"},
    "competitive_assessment": "0_10",
    "portfolio_assessment": {"position": "0_100", "revenue_share": "%"},
    "strengths_assessment": "%",
    "weaknesses_assessment": "%",
    "opportunities_assessment": {"value": "USD_M", "score": "%"},
    "threats_assessment": "%",
    "revenue_growth": "USD_M",
    "operating_income": "%",
    "cash_flow": "%",
    "gross_margin": "%",
    # ↓↓↓ changes start here
    "finance_metrics":     {"value": "num"},     # ‘Value’ column numeric
    "time_to_hire": "days",
    "employee_turnover": "%",
    "employee_engagement": "%",
    "management_team_quality": "score_0_10",
    "hr_metrics": "mixed",
    "inventory_turnover": "turns",
    "on_time_delivery": "%",
    "first_pass_yield": "%",
    "total_cycle_time": "days",
    "operations_metrics":  {"value": "num"},     # ‘Value’ column numeric
    "annual_recurring_revenue": "USD_M",
    "customer_acquisition_cost": "USD_k",
    "design_win": "USD_M",
    "sales_opportunities": "USD_M",
    "sales_marketing_metrics": "mixed",
}
