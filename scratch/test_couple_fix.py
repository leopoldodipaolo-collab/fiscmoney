import sys
sys.path.insert(0, '.')
from database import get_db_connection
from services.couple_split_engine import get_couple_split_analytics

# Let's inspect workspace 2 with current logic
res = get_couple_split_analytics(2, preset='THIS_MONTH')
print("Current Total shared:", res.get("total_shared"))
print("Current P1 spent:", res.get("p1_total"))
print("Current P2 spent:", res.get("p2_total"))
print("Current categories in matrix:")
for cat, data in (res.get("category_matrix") or {}).items():
    print(f"  {cat}: total={data['total']}, p1={data['p1_amount']}, p2={data['p2_amount']}")
