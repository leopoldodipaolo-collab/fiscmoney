import math
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from database import get_db_connection
from services.cashflow_engine import MONTH_NAMES_IT, MONTH_NAMES_IT_SHORT
from services.bank_importer import MACRO_CATEGORIES

COMMON_DEFAULT_CATEGORIES = [
    "Spesa & Alimentari",
    "Alimentari e Spesa",
    "Bollette & Utenze",
    "Casa e Utenze",
    "Salute & Benessere",
    "Salute e Farmacia",
    "Casa & Immobili",
    "Ristoranti & Bar",
    "Auto & Mobilità",
    "Viaggi & Tempo Libero"
]

def get_couple_split_analytics(workspace_id, preset='THIS_MONTH', from_ym=None, to_ym=None, split_ratio=0.5):
    """
    Computes shared couple expenses breakdown, who paid what, category matrix and settlement balance.
    split_ratio: portion assigned to primary profile (default 0.5 = 50/50 split).
    """
    conn = get_db_connection()
    
    # 1. Fetch workspace profiles (expecting at least 2 for a couple)
    profiles = conn.execute(
        "SELECT id, name, is_primary, role_title, assistant_persona FROM profiles WHERE workspace_id = ? ORDER BY is_primary DESC, id ASC",
        (workspace_id,)
    ).fetchall()
    
    if len(profiles) < 2:
        conn.close()
        return {
            "has_couple": False,
            "profiles": [dict(p) for p in profiles],
            "message": "Aggiungi almeno 2 membri al nucleo per sbloccare il Bilancio di Coppia."
        }
        
    p1 = dict(profiles[0]) # e.g. Leopoldo (Primary)
    p2 = dict(profiles[1]) # e.g. Nunzia (Partner)
    
    # 2. Determine Date Range based on Preset
    today = date.today()
    current_ym = today.strftime("%Y-%m")
    last_month_ym = (today.replace(day=1) - relativedelta(months=1)).strftime("%Y-%m")
    
    start_date = None
    end_date = None
    period_label = "Questo Mese"
    
    if preset == 'THIS_MONTH':
        start_date = f"{current_ym}-01"
        end_date = f"{current_ym}-31"
        period_label = f"{MONTH_NAMES_IT.get(today.month, '')} {today.year}"
    elif preset == 'LAST_MONTH':
        last_m_dt = today.replace(day=1) - relativedelta(months=1)
        start_date = f"{last_month_ym}-01"
        end_date = f"{last_month_ym}-31"
        period_label = f"{MONTH_NAMES_IT.get(last_m_dt.month, '')} {last_m_dt.year}"
    elif preset == 'LAST_3_MONTHS':
        three_m_ago = (today.replace(day=1) - relativedelta(months=2)).strftime("%Y-%m")
        start_date = f"{three_m_ago}-01"
        end_date = f"{current_ym}-31"
        period_label = "Ultimi 3 Mesi"
    elif preset == 'YEAR':
        start_date = f"{today.year}-01-01"
        end_date = f"{today.year}-12-31"
        period_label = f"Anno {today.year}"
    elif preset == 'CUSTOM' and from_ym and to_ym:
        start_date = f"{from_ym}-01"
        end_date = f"{to_ym}-31"
        period_label = f"Da {from_ym} a {to_ym}"
    else: # ALL
        period_label = "Tutto lo storico"
        
    # 3. Query Transactions: Shared expenses (amount < 0, expense)
    # A transaction is counted as shared if is_shared = 1 (or tagged #comune / #condivisa when not explicitly 0)
    where_clauses = ["t.workspace_id = ?", "t.amount < 0", "t.is_transfer = 0"]
    params = [workspace_id]
    
    if start_date and end_date:
        where_clauses.append("t.date >= ? AND t.date <= ?")
        params.extend([start_date, end_date])
        
    where_clauses.append("""(
        t.is_shared = 1 
        OR (
            (t.is_shared IS NULL OR t.is_shared != 0) 
            AND (
                t.tags LIKE '%#comune%' 
                OR t.tags LIKE '%#condivisa%'
                OR t.tags LIKE '%#famiglia%'
                OR t.tags LIKE '%#figlio%'
                OR t.tags LIKE '%#figli%'
                OR t.tags LIKE '%#asilo%'
                OR t.tags LIKE '%#scuola%'
            )
        )
    )""")
    
    query = f"""
        SELECT t.*, p.name as profile_name, a.name as account_name, a.bank_name
        FROM transactions t
        LEFT JOIN profiles p ON t.profile_id = p.id
        LEFT JOIN accounts a ON t.account_id = a.id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY t.date DESC, t.id DESC
    """
    
    rows = conn.execute(query, params).fetchall()
    
    # 4. Aggregations by Member, Category, and Child/Kids Sub-Focus
    total_shared = 0.0
    p1_total = 0.0
    p2_total = 0.0
    other_total = 0.0

    # Child Expenses Tracking
    child_expenses = {
        "total": 0.0,
        "p1_amount": 0.0,
        "p2_amount": 0.0,
        "count": 0,
        "transactions": []
    }
    
    cat_breakdown = {}
    shared_transactions = []
    
    for r in rows:
        amt = abs(float(r['amount']))
        total_shared += amt
        prof_id = r['profile_id']
        cat = r['category'] or 'Altro'
        tx_tags = (r['tags'] or '').lower()
        desc_lower = (r['description'] or '').lower()
        
        # Attribute to Profile
        if prof_id == p1['id']:
            p1_total += amt
        elif prof_id == p2['id']:
            p2_total += amt
        else:
            other_total += amt

        # Check if it's a child-dedicated expense
        is_child_tx = (
            '#figlio' in tx_tags or 
            '#figli' in tx_tags or 
            '#asilo' in tx_tags or 
            '#scuola' in tx_tags or
            'asilo nido' in desc_lower or
            'asilo' in desc_lower or
            'pediatra' in desc_lower
        )
        if is_child_tx:
            child_expenses["total"] += amt
            child_expenses["count"] += 1
            if prof_id == p1['id']:
                child_expenses["p1_amount"] += amt
            elif prof_id == p2['id']:
                child_expenses["p2_amount"] += amt
            child_expenses["transactions"].append({
                "id": r['id'],
                "date": r['date'],
                "description": r['description'],
                "amount": amt,
                "profile_name": r['profile_name'] or 'Membro',
                "category": cat
            })
            
        # Category aggregation
        if cat not in cat_breakdown:
            icon = "📦"
            if "Alimentar" in cat or "Spesa" in cat:
                icon = "🛒"
            elif "Casa" in cat or "Utenz" in cat or "Bollett" in cat:
                icon = "⚡"
            elif "Salute" in cat or "Farmac" in cat:
                icon = "💊"
            elif "Mutuo" in cat or "Prestit" in cat:
                icon = "🏠"
            elif "Figli" in cat or "Famiglia" in cat:
                icon = "👶"
            elif "Ristorant" in cat or "Svago" in cat or "Bar" in cat:
                icon = "🍽️"
            elif "Trasport" in cat or "Auto" in cat:
                icon = "🚗"
                
            cat_breakdown[cat] = {
                "name": cat,
                "icon": icon,
                "total": 0.0,
                "p1_amount": 0.0,
                "p2_amount": 0.0,
                "count": 0
            }
            
        cat_breakdown[cat]["total"] += amt
        cat_breakdown[cat]["count"] += 1
        if prof_id == p1['id']:
            cat_breakdown[cat]["p1_amount"] += amt
        elif prof_id == p2['id']:
            cat_breakdown[cat]["p2_amount"] += amt
            
        # Format transaction row
        shared_transactions.append({
            "id": r['id'],
            "date": r['date'],
            "amount": amt,
            "description": r['description'] or 'Spesa Condivisa',
            "category": cat,
            "profile_id": prof_id,
            "profile_name": r['profile_name'] or ('Cointestato' if not prof_id else 'Membro'),
            "is_shared": 1,
            "is_child": is_child_tx,
            "account_name": r['account_name'] or r['bank_name'] or 'Conto'
        })
        
    conn.close()
    
    # 5. Settlement & Fairness Math
    # Ideal split targets:
    p1_target = total_shared * split_ratio
    p2_target = total_shared * (1.0 - split_ratio)
    
    # Net Difference: p1_paid - p1_target
    diff = p1_total - p1_target
    
    # Settlement verdict:
    settlement = {}
    if abs(diff) < 0.50:
        settlement = {
            "status": "EQUAL",
            "badge_color": "var(--accent-success)",
            "message": "🎉 Siete in perfetto pareggio! Nessun debito tra voi.",
            "debtor_name": None,
            "creditor_name": None,
            "amount": 0.0
        }
    elif diff > 0:
        # P1 has paid more than their target -> P2 owes P1 the difference
        settlement = {
            "status": "P2_OWES_P1",
            "badge_color": "#eab308",
            "message": f"👉 {p2['name']} deve rimborsare a {p1['name']}",
            "debtor_name": p2['name'],
            "creditor_name": p1['name'],
            "amount": round(diff, 2),
            "formatted_amount": f"{round(diff, 2):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
        }
    else:
        # P2 has paid more than their target -> P1 owes P2 the difference
        settlement = {
            "status": "P1_OWES_P2",
            "badge_color": "#eab308",
            "message": f"👉 {p1['name']} deve rimborsare a {p2['name']}",
            "debtor_name": p1['name'],
            "creditor_name": p2['name'],
            "amount": round(abs(diff), 2),
            "formatted_amount": f"{round(abs(diff), 2):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
        }
        
    # Format category list sorted by total
    sorted_categories = sorted(list(cat_breakdown.values()), key=lambda x: x['total'], reverse=True)
    for c in sorted_categories:
        c["p1_percent"] = round((c["p1_amount"] / c["total"] * 100), 1) if c["total"] > 0 else 50.0
        c["p2_percent"] = round((c["p2_amount"] / c["total"] * 100), 1) if c["total"] > 0 else 50.0
        
    p1_pct = round((p1_total / total_shared * 100), 1) if total_shared > 0 else 50.0
    p2_pct = round((p2_total / total_shared * 100), 1) if total_shared > 0 else 50.0
    
    return {
        "has_couple": True,
        "period_label": period_label,
        "preset": preset,
        "split_ratio": split_ratio,
        "p1": p1,
        "p2": p2,
        "total_shared": total_shared,
        "p1_total": p1_total,
        "p2_total": p2_total,
        "p1_pct": p1_pct,
        "p2_pct": p2_pct,
        "p1_target": p1_target,
        "p2_target": p2_target,
        "settlement": settlement,
        "categories": sorted_categories,
        "child_expenses": child_expenses,
        "transactions_count": len(shared_transactions),
        "recent_transactions": shared_transactions[:15]
    }


def get_couple_category_transactions(workspace_id: int, category: str, preset: str = 'THIS_MONTH', from_ym: str = None, to_ym: str = None):
    today = date.today()
    current_ym = today.strftime("%Y-%m")
    last_month_ym = (today.replace(day=1) - relativedelta(months=1)).strftime("%Y-%m")
    
    start_date = None
    end_date = None
    period_label = "Questo Mese"
    
    if preset == 'THIS_MONTH':
        start_date = f"{current_ym}-01"
        end_date = f"{current_ym}-31"
        period_label = f"{MONTH_NAMES_IT.get(today.month, '')} {today.year}"
    elif preset == 'LAST_MONTH':
        last_m_dt = today.replace(day=1) - relativedelta(months=1)
        start_date = f"{last_month_ym}-01"
        end_date = f"{last_month_ym}-31"
        period_label = f"{MONTH_NAMES_IT.get(last_m_dt.month, '')} {last_m_dt.year}"
    elif preset == 'LAST_3_MONTHS':
        three_m_ago = (today.replace(day=1) - relativedelta(months=2)).strftime("%Y-%m")
        start_date = f"{three_m_ago}-01"
        end_date = f"{current_ym}-31"
        period_label = "Ultimi 3 Mesi"
    elif preset == 'YEAR':
        start_date = f"{today.year}-01-01"
        end_date = f"{today.year}-12-31"
        period_label = f"Anno {today.year}"
    elif preset == 'CUSTOM' and from_ym and to_ym:
        start_date = f"{from_ym}-01"
        end_date = f"{to_ym}-31"
        period_label = f"Da {from_ym} a {to_ym}"
    else: # ALL
        period_label = "Tutto lo storico"

    conn = get_db_connection()
    profiles = conn.execute("SELECT id, name, is_primary FROM profiles WHERE workspace_id = ? ORDER BY is_primary DESC, id ASC", (workspace_id,)).fetchall()
    p1 = dict(profiles[0]) if len(profiles) > 0 else {"id": None, "name": "Partner 1"}
    p2 = dict(profiles[1]) if len(profiles) > 1 else {"id": None, "name": "Partner 2"}
    
    is_child_category = (category in ['__CHILDREN__', 'Figli & Infanzia', 'Spese per Figli & Infanzia'])
    where_clauses = ["t.workspace_id = ?", "t.amount < 0", "t.is_transfer = 0"]
    params = [workspace_id]
    
    if is_child_category:
        where_clauses.append("""(
            t.tags LIKE '%#figlio%' 
            OR t.tags LIKE '%#figli%' 
            OR t.tags LIKE '%#asilo%' 
            OR t.tags LIKE '%#scuola%' 
            OR LOWER(t.description) LIKE '%asilo%' 
            OR LOWER(t.description) LIKE '%pediatra%'
        )""")
    else:
        where_clauses.append("t.category = ?")
        params.append(category)
    
    if start_date and end_date:
        where_clauses.append("t.date >= ? AND t.date <= ?")
        params.extend([start_date, end_date])
        
    query = f"""
        SELECT t.*, p.name as profile_name, a.name as account_name, a.bank_name
        FROM transactions t
        LEFT JOIN profiles p ON t.profile_id = p.id
        LEFT JOIN accounts a ON t.account_id = a.id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY t.date DESC, t.id DESC
    """
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    tx_list = []
    total_amount = 0.0
    shared_amount = 0.0
    personal_amount = 0.0
    p1_shared = 0.0
    p2_shared = 0.0
    
    for r in rows:
        amt = abs(float(r['amount'] or 0.0))
        total_amount += amt
        
        is_sh = 1 if (r['is_shared'] == 1 or (r['is_shared'] != 0 and ('#comune' in (r['tags'] or '') or '#condivisa' in (r['tags'] or '') or '#famiglia' in (r['tags'] or '')))) else 0
        
        if is_sh:
            shared_amount += amt
            if r['profile_id'] == p1['id']:
                p1_shared += amt
            elif r['profile_id'] == p2['id']:
                p2_shared += amt
            else:
                p1_shared += amt / 2
                p2_shared += amt / 2
        else:
            personal_amount += amt
            
        tx_list.append({
            "id": r['id'],
            "date": r['date'],
            "description": r['description'] or 'Spesa',
            "amount": amt,
            "formatted_amount": f"{amt:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €",
            "is_shared": is_sh,
            "profile_id": r['profile_id'],
            "profile_name": r['profile_name'] or 'Comune/Cointestato',
            "account_name": r['account_name'] or r['bank_name'] or 'Conto'
        })
        
    return {
        "category": category,
        "period_label": period_label,
        "p1": p1,
        "p2": p2,
        "total_amount": round(total_amount, 2),
        "shared_amount": round(shared_amount, 2),
        "personal_amount": round(personal_amount, 2),
        "p1_shared": round(p1_shared, 2),
        "p2_shared": round(p2_shared, 2),
        "count": len(tx_list),
        "transactions": tx_list
    }


def bulk_set_category_shared(workspace_id: int, category: str, target_state: int, preset: str = 'THIS_MONTH', from_ym: str = None, to_ym: str = None):
    today = date.today()
    current_ym = today.strftime("%Y-%m")
    last_month_ym = (today.replace(day=1) - relativedelta(months=1)).strftime("%Y-%m")
    
    start_date = None
    end_date = None
    
    if preset == 'THIS_MONTH':
        start_date = f"{current_ym}-01"
        end_date = f"{current_ym}-31"
    elif preset == 'LAST_MONTH':
        start_date = f"{last_month_ym}-01"
        end_date = f"{last_month_ym}-31"
    elif preset == 'LAST_3_MONTHS':
        three_m_ago = (today.replace(day=1) - relativedelta(months=2)).strftime("%Y-%m")
        start_date = f"{three_m_ago}-01"
        end_date = f"{current_ym}-31"
    elif preset == 'YEAR':
        start_date = f"{today.year}-01-01"
        end_date = f"{today.year}-12-31"
    elif preset == 'CUSTOM' and from_ym and to_ym:
        start_date = f"{from_ym}-01"
        end_date = f"{to_ym}-31"
        
    conn = get_db_connection()
    where_clauses = ["workspace_id = ?", "category = ?", "amount < 0", "is_transfer = 0"]
    params = [workspace_id, category]
    
    if start_date and end_date:
        where_clauses.append("date >= ? AND date <= ?")
        params.extend([start_date, end_date])
        
    query = f"UPDATE transactions SET is_shared = {1 if target_state == 1 else 0} WHERE {' AND '.join(where_clauses)}"
    cur = conn.execute(query, params)
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return {"success": True, "affected": affected}
