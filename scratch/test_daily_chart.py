import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from services.cashflow_engine import get_monthly_cashflow_data

def test_daily_data():
    workspace_id = 1
    # Test for September 2026
    data = get_monthly_cashflow_data(workspace_id, profile_id=None, year_month="2026-09")
    
    print("=== Monthly Cashflow Data (2026-09) ===")
    print(f"Month: {data['month_name_it']}")
    print(f"Total expenses: {data['actual_month_expenses']}")
    print(f"Days in month: {data['days_in_month']}")
    print(f"Daily breakdown count: {len(data['daily_breakdown'])}")
    print(f"Daily labels count: {len(data['daily_labels'])}")
    print(f"Daily series full sum: {sum(data['daily_series_full']):.2f}")
    print(f"Daily series no mortgage sum: {sum(data['daily_series_no_mortgage']):.2f}")
    print(f"Total mortgage month: {data['total_mortgage_month']}")
    print(f"Has mortgage in month: {data['has_mortgage_in_month']}")
    print(f"Peak day full: {data['peak_label_full']} -> € {data['peak_amount_full']:.2f}")
    print(f"Peak day no mortgage: {data['peak_label_no_mortgage']} -> € {data['peak_amount_no_mortgage']:.2f}")
    print(f"Today formatted: {data['today_formatted_it']}")
    
    # Assertions
    assert len(data['daily_breakdown']) == 30, f"Expected 30 days for September, got {len(data['daily_breakdown'])}"
    assert len(data['daily_labels']) == 30
    assert len(data['daily_series_full']) == 30
    assert len(data['daily_series_no_mortgage']) == 30
    assert len(data['daily_is_weekend']) == 30
    assert len(data['daily_is_today']) == 30
    
    # Check that August 2026 also works (31 days)
    data_aug = get_monthly_cashflow_data(workspace_id, profile_id=None, year_month="2026-08")
    assert len(data_aug['daily_breakdown']) == 31, f"Expected 31 days for August, got {len(data_aug['daily_breakdown'])}"
    print("\n=== Monthly Cashflow Data (2026-08) ===")
    print(f"Month: {data_aug['month_name_it']}")
    print(f"Days count: {len(data_aug['daily_breakdown'])}")
    print(f"Peak day full: {data_aug['peak_label_full']} -> € {data_aug['peak_amount_full']:.2f}")
    print(f"Peak day no mortgage: {data_aug['peak_label_no_mortgage']} -> € {data_aug['peak_amount_no_mortgage']:.2f}")
    
    print("\n✅ All assertions passed successfully!")

if __name__ == '__main__':
    test_daily_data()
