import math
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from database import get_db_connection
from services.bank_importer import MACRO_CATEGORIES, CATEGORY_SMART_TAGS

# ---------------------------------------------------------
# 1. DATABASE SCHEMA INITIALIZATION FOR FOCUS & MORTGAGE
# ---------------------------------------------------------
def init_focus_schema():
    """Ensures tables for mortgage profiles and focus preferences exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Mortgage Contract Profiles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mortgage_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            profile_id INTEGER,
            name TEXT NOT NULL DEFAULT 'Mutuo Prima Casa',
            bank_name TEXT DEFAULT 'Banca',
            original_amount REAL NOT NULL DEFAULT 200000.0,
            start_date TEXT NOT NULL DEFAULT '2021-01-01',
            duration_months INTEGER NOT NULL DEFAULT 240, -- 20 years
            interest_type TEXT NOT NULL DEFAULT 'FIXED', -- FIXED, VARIABLE, CAP
            annual_interest_rate REAL NOT NULL DEFAULT 3.20, -- TAN in %
            monthly_installment REAL NOT NULL DEFAULT 1050.00,
            is_primary_residence BOOLEAN NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE SET NULL
        )
    ''')
    
    # 2. User Focus Active Categories
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_focus_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            profile_id INTEGER,
            category_name TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(workspace_id, category_name),
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()


def get_active_focus_categories(workspace_id, profile_id=None):
    """Returns the list of active categories to display in the Focus Hub."""
    init_focus_schema()
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT category_name FROM user_focus_categories
        WHERE workspace_id = ? AND is_active = 1
        ORDER BY display_order ASC, id ASC
    """, (workspace_id,)).fetchall()
    conn.close()
    
    if rows:
        return [r['category_name'] for r in rows]
    
    # Default initial focus categories if none set yet
    default_cats = ["Casa & Immobili", "Auto & Mobilità"]
    conn = get_db_connection()
    for idx, cname in enumerate(default_cats):
        conn.execute("""
            INSERT OR IGNORE INTO user_focus_categories (workspace_id, category_name, is_active, display_order)
            VALUES (?, ?, 1, ?)
        """, (workspace_id, cname, idx))
    conn.commit()
    conn.close()
    return default_cats


def toggle_focus_category(workspace_id, category_name, is_active=True):
    """Adds or removes a category from active focus cards."""
    init_focus_schema()
    conn = get_db_connection()
    exists = conn.execute("""
        SELECT id FROM user_focus_categories WHERE workspace_id = ? AND category_name = ?
    """, (workspace_id, category_name)).fetchone()
    
    if exists:
        conn.execute("""
            UPDATE user_focus_categories SET is_active = ? WHERE id = ?
        """, (1 if is_active else 0, exists['id']))
    else:
        conn.execute("""
            INSERT INTO user_focus_categories (workspace_id, category_name, is_active, display_order)
            VALUES (?, ?, ?, 99)
        """, (workspace_id, category_name, 1 if is_active else 0))
    conn.commit()
    conn.close()


# ---------------------------------------------------------
# 2. DATE RANGE RESOLVER
# ---------------------------------------------------------
def resolve_timeframe(workspace_id, preset='6M', from_ym=None, to_ym=None):
    """
    Resolves the start and end date/months for querying.
    Returns: (from_date_str, to_date_str, list_of_ym_months, preset_label)
    """
    now = datetime.now()
    cur_ym = now.strftime("%Y-%m")
    
    # If custom manual range is provided
    if preset == 'CUSTOM' and from_ym and to_ym:
        try:
            fy, fm = map(int, from_ym.split('-'))
            ty, tm = map(int, to_ym.split('-'))
            start_d = date(fy, fm, 1)
            # End date is end of to_month
            end_d = date(ty, tm, 1) + relativedelta(months=1) - relativedelta(days=1)
            preset_label = f"Da {from_ym} a {to_ym}"
        except Exception:
            start_d = date(now.year, now.month, 1) - relativedelta(months=5)
            end_d = date(now.year, now.month, 1) + relativedelta(months=1) - relativedelta(days=1)
            preset_label = "Ultimi 6 Mesi"
    elif preset == '2M':
        start_d = date(now.year, now.month, 1) - relativedelta(months=1)
        end_d = date(now.year, now.month, 1) + relativedelta(months=1) - relativedelta(days=1)
        preset_label = "Ultimi 2 Mesi"
    elif preset == '6M':
        start_d = date(now.year, now.month, 1) - relativedelta(months=5)
        end_d = date(now.year, now.month, 1) + relativedelta(months=1) - relativedelta(days=1)
        preset_label = "Ultimi 6 Mesi"
    elif preset == '12M':
        start_d = date(now.year, now.month, 1) - relativedelta(months=11)
        end_d = date(now.year, now.month, 1) + relativedelta(months=1) - relativedelta(days=1)
        preset_label = "Ultimo Anno (12 Mesi)"
    elif preset == 'ALL':
        conn = get_db_connection()
        min_date_row = conn.execute("SELECT MIN(date) FROM transactions WHERE workspace_id = ?", (workspace_id,)).fetchone()
        conn.close()
        if min_date_row and min_date_row[0]:
            try:
                min_p = datetime.strptime(min_date_row[0][:10], "%Y-%m-%d").date()
                start_d = date(min_p.year, min_p.month, 1)
            except Exception:
                start_d = date(2020, 1, 1)
        else:
            start_d = date(2020, 1, 1)
        end_d = date(now.year, now.month, 1) + relativedelta(months=1) - relativedelta(days=1)
        preset_label = "Tutto lo Storico"
    else:
        # Default 6M
        start_d = date(now.year, now.month, 1) - relativedelta(months=5)
        end_d = date(now.year, now.month, 1) + relativedelta(months=1) - relativedelta(days=1)
        preset_label = "Ultimi 6 Mesi"

    from_date_str = start_d.strftime("%Y-%m-%d")
    to_date_str = end_d.strftime("%Y-%m-%d")

    # Generate sequence of YYYY-MM
    months = []
    curr = date(start_d.year, start_d.month, 1)
    end_month = date(end_d.year, end_d.month, 1)
    while curr <= end_month:
        months.append(curr.strftime("%Y-%m"))
        curr += relativedelta(months=1)

    return from_date_str, to_date_str, months, preset_label


# ---------------------------------------------------------
# 3. VERTICAL CATEGORY ANALYTICS ENGINE
# ---------------------------------------------------------
def get_vertical_category_data(workspace_id, category_name, preset='6M', from_ym=None, to_ym=None, profile_id=None):
    """
    Computes in-depth analytics, tag distribution, direct answers, and Chart.js datasets
    for a specific macro category over the specified timeframe.
    """
    from_date_str, to_date_str, months_list, preset_label = resolve_timeframe(workspace_id, preset, from_ym, to_ym)
    
    cat_meta = MACRO_CATEGORIES.get(category_name, {
        "icon": "📦",
        "color": "#3b82f6",
        "subcategories": []
    })

    conn = get_db_connection()
    
    # Query transactions in this category within date range
    query = """
        SELECT id, date, amount, description, raw_description, category, sub_category, tags
        FROM transactions
        WHERE workspace_id = ? 
          AND (category = ? OR category LIKE ?)
          AND amount < 0
          AND is_transfer = 0
          AND date >= ? AND date <= ?
    """
    params = [workspace_id, category_name, f"{category_name}%", from_date_str, to_date_str]
    if profile_id:
        query += " AND profile_id = ?"
        params.append(profile_id)
    query += " ORDER BY date DESC"

    tx_rows = conn.execute(query, params).fetchall()
    conn.close()

    total_spent = sum(abs(r['amount']) for r in tx_rows)
    tx_count = len(tx_rows)
    num_months = max(len(months_list), 1)
    monthly_avg = round(total_spent / num_months, 2)

    # 1. Breakdown by Subcategory & Tags
    tag_totals = {}
    tag_counts = {}
    tag_tx_map = {}
    subcat_totals = {}
    monthly_tag_matrix = {m: {} for m in months_list}
    monthly_cat_totals = {m: 0.0 for m in months_list}

    parsed_txs = []
    for r in tx_rows:
        amt = abs(r['amount'])
        t_date = r['date'][:10]
        t_ym = t_date[:7]
        
        # Primary tag or subcategory extraction
        raw_tags = r['tags'] or ''
        tag_list = [t.strip() for t in raw_tags.split(',') if t.strip()]
        subcat = r['sub_category'] or (tag_list[0].replace('#', '').replace('_', ' ').title() if tag_list else 'Altre Spese')
        
        # Aggregate Subcategories
        subcat_totals[subcat] = subcat_totals.get(subcat, 0.0) + amt

        # Aggregate Tags
        if tag_list:
            for tg in tag_list:
                clean_tg = tg if tg.startswith('#') else f"#{tg}"
                tag_totals[clean_tg] = tag_totals.get(clean_tg, 0.0) + amt
                tag_counts[clean_tg] = tag_counts.get(clean_tg, 0) + 1
                if clean_tg not in tag_tx_map:
                    tag_tx_map[clean_tg] = []
                tag_tx_map[clean_tg].append(r['id'])
        else:
            tag_totals['#generico'] = tag_totals.get('#generico', 0.0) + amt
            tag_counts['#generico'] = tag_counts.get('#generico', 0) + 1

        # Time series matrix
        if t_ym in monthly_tag_matrix:
            monthly_tag_matrix[t_ym][subcat] = monthly_tag_matrix[t_ym].get(subcat, 0.0) + amt
            monthly_cat_totals[t_ym] += amt

        parsed_txs.append({
            'id': r['id'],
            'date': t_date,
            'amount': amt,
            'description': r['description'] or 'Spesa',
            'raw_description': r['raw_description'] or '',
            'subcategory': subcat,
            'tags': raw_tags
        })

    # 1.1 Complete Tag Analysis for ALL category tags (curated + discovered)
    official_tags = CATEGORY_SMART_TAGS.get(category_name, [])
    all_tags_dict = {}
    for ot in official_tags:
        code = ot['code']
        all_tags_dict[code] = {
            "code": code,
            "label": ot['label'],
            "icon": ot.get('icon', '🏷️'),
            "subcat": ot.get('subcat', ''),
            "total_amount": 0.0,
            "tx_count": 0,
            "monthly_avg": 0.0,
            "percent": 0.0,
            "has_activity": False
        }

    # Add any extra tags found in transactions
    for tg, t_amt in tag_totals.items():
        if tg not in all_tags_dict:
            all_tags_dict[tg] = {
                "code": tg,
                "label": tg.replace('#', '').replace('_', ' ').title(),
                "icon": "🏷️",
                "subcat": "",
                "total_amount": 0.0,
                "tx_count": 0,
                "monthly_avg": 0.0,
                "percent": 0.0,
                "has_activity": False
            }

    # Populate amounts and percentages
    for code, info in all_tags_dict.items():
        tot = tag_totals.get(code, 0.0)
        cnt = tag_counts.get(code, 0)
        info["total_amount"] = round(tot, 2)
        info["tx_count"] = cnt
        info["monthly_avg"] = round(tot / num_months, 2)
        info["percent"] = round((tot / total_spent * 100), 1) if total_spent > 0 else 0.0
        info["has_activity"] = (cnt > 0)

    # Sort tags: active tags with highest spend first, then inactive
    all_tags_analysis = sorted(all_tags_dict.values(), key=lambda x: (x["has_activity"], x["total_amount"]), reverse=True)

    # Sort subcategories and tags by spend descending
    sorted_subcats = sorted(subcat_totals.items(), key=lambda x: x[1], reverse=True)
    sorted_tags = sorted(tag_totals.items(), key=lambda x: x[1], reverse=True)

    subcat_breakdown = []
    for s_name, s_amt in sorted_subcats:
        pct = round((s_amt / total_spent * 100), 1) if total_spent > 0 else 0.0
        subcat_breakdown.append({
            "name": s_name,
            "amount": s_amt,
            "percent": pct,
            "avg_monthly": round(s_amt / num_months, 2)
        })

    # 2. Smart Direct Answers (Q&A Generator)
    answers = []
    if category_name == "Auto & Mobilità":
        fuel_amt = tag_totals.get('#carburante', 0.0) + subcat_totals.get('Carburante & Ricarica', 0.0)
        telepass_amt = tag_totals.get('#telepass', 0.0) + subcat_totals.get('Telepass & Pedaggi', 0.0)
        maint_amt = tag_totals.get('#tagliando', 0.0) + tag_totals.get('#tagliando_meccanico', 0.0) + tag_totals.get('#manutenzione_auto', 0.0) + subcat_totals.get('Tagliando & Manutenzione', 0.0)
        ins_amt = tag_totals.get('#assicurazione', 0.0) + subcat_totals.get('Assicurazione', 0.0)
        
        answers.append({
            "question": f"⛽ Quanta spesa per carburante/ricarica nel periodo ({preset_label})?",
            "answer": f"€ {fuel_amt:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
            "detail": f"Circa € {fuel_amt / num_months:,.2f}/mese ({((fuel_amt / total_spent) * 100) if total_spent else 0:.1f}% del totale mobilità)."
        })
        if telepass_amt > 0:
            answers.append({
                "question": "🛣️ Pedaggi & Telepass sostenuti:",
                "answer": f"€ {telepass_amt:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                "detail": f"Media di € {telepass_amt / num_months:,.2f}/mese di autostrada/spostamenti."
            })
        if maint_amt > 0:
            answers.append({
                "question": "🔧 Manutenzione & Tagliandi:",
                "answer": f"€ {maint_amt:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                "detail": f"Costi straordinari o revisione veicoli registrati."
            })

    elif category_name == "Casa & Immobili":
        mutuo_amt = tag_totals.get('#mutuo', 0.0) + subcat_totals.get('Mutuo', 0.0)
        arredo_amt = tag_totals.get('#brico_arredo', 0.0) + tag_totals.get('#arredo', 0.0) + tag_totals.get('#brico', 0.0) + subcat_totals.get('Arredo & Brico', 0.0)
        condo_amt = tag_totals.get('#condominio', 0.0) + subcat_totals.get('Condominio', 0.0)
        maint_home = tag_totals.get('#manutenzione_casa', 0.0) + tag_totals.get('#ristrutturazione', 0.0) + subcat_totals.get('Manutenzione Casa', 0.0)

        if arredo_amt > 0:
            answers.append({
                "question": f"🛋️ Spese per arredamento & brico nel periodo ({preset_label}):",
                "answer": f"€ {arredo_amt:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                "detail": f"Pari al {((arredo_amt / total_spent) * 100) if total_spent else 0:.1f}% del budget totale casa."
            })
        if mutuo_amt > 0:
            answers.append({
                "question": "🏠 Rate Mutuo contabilizzate:",
                "answer": f"€ {mutuo_amt:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                "detail": f"Spesa fissa rateale ({len([t for t in parsed_txs if '#mutuo' in t['tags'] or 'mutuo' in t['description'].lower()])} rate nel periodo)."
            })
        if condo_amt > 0:
            answers.append({
                "question": "🏢 Spese Condominiali:",
                "answer": f"€ {condo_amt:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                "detail": f"Quote ordinarie e straordinarie di gestione stabile."
            })
    else:
        # Generic top answers for any other category
        if sorted_subcats:
            top_sub = sorted_subcats[0]
            answers.append({
                "question": f"🎯 Voce di spesa principale ({top_sub[0]}):",
                "answer": f"€ {top_sub[1]:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                "detail": f"Costituisce il {((top_sub[1] / total_spent) * 100) if total_spent else 0:.1f}% della categoria nel periodo."
            })

    # 3. Chart.js Data Preparation
    # Monthly Bar Chart Labels (Clean format, without modifying X-axis labels)
    MESI_IT_SHORT = {1: "Gen", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mag", 6: "Giu", 7: "Lug", 8: "Ago", 9: "Set", 10: "Ott", 11: "Nov", 12: "Dic"}
    chart_months_labels = []
    current_ym = date.today().strftime('%Y-%m')
    current_month_index = -1

    for idx, ym in enumerate(months_list):
        try:
            cy, cm = map(int, ym.split('-'))
            chart_months_labels.append(f"{MESI_IT_SHORT.get(cm, ym)} '{str(cy)[2:]}")
        except Exception:
            chart_months_labels.append(ym)
        if ym == current_ym:
            current_month_index = idx

    # Prepare Top 4 Subcategories for Stacked Bar Datasets, plus 'Altro'
    top_subcat_names = [s[0] for s in sorted_subcats[:4]]
    chart_datasets = []
    palette = ["#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4"]
    
    for idx, s_name in enumerate(top_subcat_names):
        col = palette[idx % len(palette)]
        data_points = []
        for ym in months_list:
            data_points.append(round(monthly_tag_matrix[ym].get(s_name, 0.0), 2))
        chart_datasets.append({
            "label": s_name,
            "backgroundColor": col,
            "data": data_points
        })

    # Donut Chart for Subcategories
    donut_labels = [s["name"] for s in subcat_breakdown]
    donut_values = [s["amount"] for s in subcat_breakdown]
    donut_colors = [palette[i % len(palette)] for i in range(len(donut_labels))]

    return {
        "category_name": category_name,
        "icon": cat_meta.get("icon", "📦"),
        "color": cat_meta.get("color", "#3b82f6"),
        "preset": preset,
        "preset_label": preset_label,
        "from_date": from_date_str,
        "to_date": to_date_str,
        "from_ym": from_ym if from_ym else months_list[0],
        "to_ym": to_ym if to_ym else months_list[-1],
        "months_list": months_list,
        "current_ym": current_ym,
        "current_month_index": current_month_index,
        "total_spent": total_spent,
        "tx_count": tx_count,
        "monthly_avg": monthly_avg,
        "all_tags_analysis": all_tags_analysis,
        "subcat_breakdown": subcat_breakdown,
        "answers": answers,
        "transactions": parsed_txs[:50], # Top 50 recent
        "chart_months_labels": chart_months_labels,
        "chart_datasets": chart_datasets,
        "donut_labels": donut_labels,
        "donut_values": donut_values,
        "donut_colors": donut_colors
    }


# ---------------------------------------------------------
# 4. SPECIAL MORTGAGE & CREDIT HUB ENGINE
# ---------------------------------------------------------
def get_mortgage_profile(workspace_id, profile_id=None):
    """Retrieves the active mortgage profile or seeds a default one for workspace 1."""
    init_focus_schema()
    conn = get_db_connection()
    row = conn.execute("""
        SELECT * FROM mortgage_profiles WHERE workspace_id = ? ORDER BY id DESC LIMIT 1
    """, (workspace_id,)).fetchone()
    
    if row:
        profile_data = dict(row)
        conn.close()
        return profile_data
        
    # Only seed default demo profile for workspace 1 (demo/admin environment)
    if workspace_id == 1:
        # Check if there are existing mortgage transactions (e.g. BCC 1050 €)
        mutuo_tx = conn.execute("""
            SELECT amount, date, description FROM transactions 
            WHERE workspace_id = ? AND (tags LIKE '%#mutuo%' OR description LIKE '%mutuo%')
            ORDER BY date DESC LIMIT 1
        """, (workspace_id,)).fetchone()
        
        inst_amt = 1050.00
        if mutuo_tx:
            inst_amt = abs(mutuo_tx['amount'])

        # Create default realistic profile
        conn.execute("""
            INSERT INTO mortgage_profiles (
                workspace_id, profile_id, name, bank_name, original_amount, start_date, 
                duration_months, interest_type, annual_interest_rate, monthly_installment, is_primary_residence
            ) VALUES (?, ?, 'Mutuo Prima Casa (BCC)', 'BCC Credito Cooperativo', 210000.0, '2023-01-01', 240, 'FIXED', 3.45, ?, 1)
        """, (workspace_id, profile_id, inst_amt))
        conn.commit()
        
        new_row = conn.execute("SELECT * FROM mortgage_profiles WHERE workspace_id = ? ORDER BY id DESC LIMIT 1", (workspace_id,)).fetchone()
        conn.close()
        return dict(new_row) if new_row else None
        
    conn.close()
    return None


def calculate_french_amortization(original_amount, annual_rate_pct, duration_months, start_date_str, monthly_installment=None):
    """
    Simulates full French Amortization schedule (Ammortamento alla Francese a Rata Costante).
    Returns detailed schedule, current status, and tax interest breakdown.
    """
    try:
        start_d = datetime.strptime(start_date_str[:10], "%Y-%m-%d").date()
    except Exception:
        start_d = date(2023, 1, 1)

    r_monthly = (annual_rate_pct / 100.0) / 12.0
    
    # Calculate exact monthly payment if not specified or recalculate
    if r_monthly > 0:
        theoretical_installment = original_amount * (r_monthly * ((1 + r_monthly) ** duration_months)) / (((1 + r_monthly) ** duration_months) - 1)
    else:
        theoretical_installment = original_amount / duration_months

    installment = theoretical_installment

    today = date.today()
    schedule = []
    residual_principal = original_amount
    total_interest_paid_to_date = 0.0
    total_capital_paid_to_date = 0.0
    paid_installments_count = 0
    
    cur_year = today.year
    current_year_interest = 0.0

    for m_idx in range(1, duration_months + 1):
        due_date = start_d + relativedelta(months=m_idx - 1)
        is_past = due_date <= today
        
        interest_quota = residual_principal * r_monthly
        capital_quota = installment - interest_quota
        
        if capital_quota > residual_principal:
            capital_quota = residual_principal
            installment = capital_quota + interest_quota
            
        residual_principal = max(0.0, residual_principal - capital_quota)

        if is_past:
            paid_installments_count += 1
            total_interest_paid_to_date += interest_quota
            total_capital_paid_to_date += capital_quota
            if due_date.year == cur_year:
                current_year_interest += interest_quota

        schedule.append({
            "installment_number": m_idx,
            "date": due_date.strftime("%Y-%m-%d"),
            "year": due_date.year,
            "month": due_date.month,
            "installment": round(installment, 2),
            "capital_quota": round(capital_quota, 2),
            "interest_quota": round(interest_quota, 2),
            "residual_principal": round(residual_principal, 2),
            "is_past": is_past
        })
        
        if residual_principal <= 0:
            break

    remaining_installments = max(0, duration_months - paid_installments_count)
    repaid_capital_pct = round((total_capital_paid_to_date / original_amount * 100), 1) if original_amount > 0 else 0.0
    end_date = start_d + relativedelta(months=duration_months)

    # Aggregate by Year for Amortization Chart
    yearly_dict = {}
    for item in schedule:
        yr = item["year"]
        if yr not in yearly_dict:
            yearly_dict[yr] = {
                "year": yr,
                "capital_paid": 0.0,
                "interest_paid": 0.0,
                "end_residual": item["residual_principal"],
                "is_current": (yr == cur_year),
                "is_past": item["is_past"]
            }
        yearly_dict[yr]["capital_paid"] += item["capital_quota"]
        yearly_dict[yr]["interest_paid"] += item["interest_quota"]
        yearly_dict[yr]["end_residual"] = item["residual_principal"]

    yearly_timeline = []
    chart_years = []
    chart_residual = []
    chart_capital = []
    chart_interest = []

    for yr in sorted(yearly_dict.keys()):
        y_info = yearly_dict[yr]
        y_info["capital_paid"] = round(y_info["capital_paid"], 2)
        y_info["interest_paid"] = round(y_info["interest_paid"], 2)
        y_info["end_residual"] = round(y_info["end_residual"], 2)
        yearly_timeline.append(y_info)

        chart_years.append(str(yr))
        chart_residual.append(y_info["end_residual"])
        chart_capital.append(y_info["capital_paid"])
        chart_interest.append(y_info["interest_paid"])

    current_res_debt = round(schedule[min(paid_installments_count, len(schedule)-1)]["residual_principal"], 2) if schedule else 0.0

    return {
        "schedule": schedule,
        "theoretical_installment": round(theoretical_installment, 2),
        "actual_installment": round(installment, 2),
        "paid_installments_count": paid_installments_count,
        "remaining_installments": remaining_installments,
        "total_installments": duration_months,
        "total_capital_paid": round(total_capital_paid_to_date, 2),
        "total_interest_paid": round(total_interest_paid_to_date, 2),
        "current_residual_debt": current_res_debt,
        "repaid_capital_pct": min(100.0, repaid_capital_pct),
        "end_date": end_date.strftime("%d/%m/%Y"),
        "end_year": end_date.year,
        "current_year_interest": round(current_year_interest, 2),
        "yearly_timeline": yearly_timeline,
        "chart_years": chart_years,
        "chart_residual": chart_residual,
        "chart_capital": chart_capital,
        "chart_interest": chart_interest
    }


def get_mortgage_deep_dive(workspace_id, profile_id=None):
    """
    Assembles full Mortgage Deep Dive Hub data: Contract params, Amortization,
    Bank transaction reconciliation, 730 Tax Deduction, and Bersani Surrogacy Advisor.
    """
    mortgage = get_mortgage_profile(workspace_id, profile_id)
    if not mortgage:
        return None
    
    # 1. Amortization Math
    sim = calculate_french_amortization(
        original_amount=mortgage['original_amount'],
        annual_rate_pct=mortgage['annual_interest_rate'],
        duration_months=mortgage['duration_months'],
        start_date_str=mortgage['start_date'],
        monthly_installment=mortgage['monthly_installment']
    )

    # 2. Reconcile with actual bank transactions
    conn = get_db_connection()
    tx_rows = conn.execute("""
        SELECT id, date, amount, description, raw_description 
        FROM transactions 
        WHERE workspace_id = ? AND (tags LIKE '%#mutuo%' OR description LIKE '%mutuo%')
        ORDER BY date DESC
    """, (workspace_id,)).fetchall()
    conn.close()

    actual_txs = []
    actual_paid_sum = 0.0
    for r in tx_rows:
        amt = abs(r['amount'])
        actual_paid_sum += amt
        actual_txs.append({
            "id": r['id'],
            "date": r['date'][:10],
            "amount": amt,
            "description": r['description'] or 'Rata Mutuo'
        })

    # 3. Tax 730 Deduction on Mortgage Interest (19% up to 4.000 €/year)
    # Rigo E7 del Modello 730: Interessi passivi mutuo prima casa
    max_deductible_interest = 4000.00
    eligible_interest = min(sim['current_year_interest'], max_deductible_interest)
    tax_refund_estimated = round(eligible_interest * 0.19, 2) if mortgage['is_primary_residence'] else 0.0

    # 4. AI Advisor Insights (Decreto Bersani L. 40/2007 & Optimization)
    advisor_tips = []
    
    # Tax Benefit Insight
    if mortgage['is_primary_residence']:
        advisor_tips.append({
            "type": "success",
            "icon": "🏛️",
            "title": "Detrazione Fiscale 730 (Rigo E7)",
            "text": f"Per l'anno fiscale in corso hai maturato una quota interessi stimata di <strong>€ {sim['current_year_interest']:,.2f}</strong>. "
                    f"Grazie alla detrazione IRPEF del 19% sulla Prima Casa (tetto max € 4.000/anno), riceverai un <strong>rimborso fiscale stimato di € {tax_refund_estimated:,.2f}</strong> nel tuo 730."
        })

    # Surrogacy Bersani Insight
    curr_rate = mortgage['annual_interest_rate']
    if curr_rate >= 3.0:
        market_benchmark_fixed = 2.80 # Reference competitive market rate
        spread_diff = curr_rate - market_benchmark_fixed
        if spread_diff > 0.3:
            potential_saving_month = (sim['current_residual_debt'] * (spread_diff / 100.0)) / 12.0
            total_potential_saving = potential_saving_month * sim['remaining_installments']
            advisor_tips.append({
                "type": "purple",
                "icon": "⚡",
                "title": "Opportunità Surroga a Costo Zero (Legge Bersani n. 40/2007)",
                "text": f"Il tuo tasso contrattuale è del <strong>{curr_rate:.2f}%</strong>. Con la <em>Portabilità del Mutuo (Surroga Bersani)</em> puoi trasferire il finanziamento verso un altro istituto a <strong>zero spese notarili, zero penali e zero commissioni bancarie</strong>. "
                        f"Ottenere un tasso di mercato al ~{market_benchmark_fixed:.2f}% ti farebbe risparmiare circa <strong>€ {potential_saving_month:,.0f}/mese</strong> (oltre <strong>€ {total_potential_saving:,.0f}</strong> complessivi fino a scadenza!)."
            })
    
    # Prepayment Strategy vs PAC
    advisor_tips.append({
        "type": "amber",
        "icon": "💡",
        "title": "Estinzione Anticipata vs Investimento",
        "text": f"Rimborsare una quota straordinaria di <strong>€ 5.000</strong> oggi ridurrebbe il debito residuo a <strong>€ {sim['current_residual_debt'] - 5000:,.0f}</strong>, facendoti risparmiare circa <strong>€ {5000 * (curr_rate / 100) * (sim['remaining_installments']/12):,.0f}</strong> di interessi futuri. "
                f"Valuta se la resa netta dei tuoi investimenti liquidi supera il {curr_rate:.2f}% annuo prima di estinguere anticipatamente."
    })

    return {
        "mortgage": mortgage,
        "simulation": sim,
        "actual_txs": actual_txs,
        "actual_paid_sum": round(actual_paid_sum, 2),
        "tax_refund_estimated": tax_refund_estimated,
        "eligible_interest": eligible_interest,
        "advisor_tips": advisor_tips
    }
