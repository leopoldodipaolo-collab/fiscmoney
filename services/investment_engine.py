"""
Services for Investments & PAC tracking (ETFs, Stocks, Funds).
Computes portfolio summary, Average Load Price (PMC), accumulated shares,
and detects recent broker transfers from bank statements.
"""

from database import get_db_connection
from datetime import datetime

# Default catalog of popular ETFs for Italian investors with prefilled info
POPULAR_INSTRUMENTS = {
    "IE00BK5BQT80": {
        "isin": "IE00BK5BQT80",
        "ticker": "VWCE",
        "name": "Vanguard FTSE All-World UCITS ETF (Acc)",
        "asset_class": "Azionario Globale",
        "currency": "EUR"
    },
    "IE00B4L5Y983": {
        "isin": "IE00B4L5Y983",
        "ticker": "SWDA",
        "name": "iShares Core MSCI World UCITS ETF (Acc)",
        "asset_class": "Azionario Paesi Sviluppati",
        "currency": "EUR"
    },
    "IE00B5BMR087": {
        "isin": "IE00B5BMR087",
        "ticker": "CSSPX",
        "name": "iShares Core S&P 500 UCITS ETF (Acc)",
        "asset_class": "Azionario USA",
        "currency": "EUR"
    },
    "LU1681045370": {
        "isin": "LU1681045370",
        "ticker": "LCWD",
        "name": "Amundi MSCI World UCITS ETF",
        "asset_class": "Azionario Globale",
        "currency": "EUR"
    }
}

def get_portfolio_summary(workspace_id, profile_id=None):
    """
    Retrieves all investment purchases in workspace and aggregates:
    - Per ISIN / Instrument: total shares, average purchase price (PMC), total invested, last purchase date.
    - Global: total invested capital, total orders count, distinct instruments.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT i.*, p.name as profile_name
        FROM investments i
        LEFT JOIN profiles p ON i.profile_id = p.id
        WHERE i.workspace_id = ?
    """
    params = [workspace_id]
    if profile_id and str(profile_id).lower() != 'all':
        try:
            p_val = int(profile_id)
            query += " AND (i.profile_id = ? OR i.profile_id IS NULL)"
            params.append(p_val)
        except (ValueError, TypeError):
            pass

    query += " ORDER BY i.date DESC, i.id DESC"
    rows = cursor.execute(query, params).fetchall()

    instruments_map = {}
    total_capital_invested = 0.0
    total_fees_paid = 0.0

    for r in rows:
        row_dict = dict(r)
        isin = (row_dict.get('isin') or '').upper().strip()
        if not isin:
            continue

        shares = float(row_dict.get('shares') or 0.0)
        price = float(row_dict.get('price') or 0.0)
        invested = float(row_dict.get('total_invested') or (shares * price))
        fees = float(row_dict.get('fees') or 0.0)

        total_capital_invested += invested
        total_fees_paid += fees

        if isin not in instruments_map:
            meta = POPULAR_INSTRUMENTS.get(isin, {})
            instruments_map[isin] = {
                "isin": isin,
                "ticker": row_dict.get('ticker') or meta.get('ticker') or isin[:6],
                "name": row_dict.get('name') or meta.get('name') or isin,
                "broker": row_dict.get('broker') or 'Directa',
                "asset_class": meta.get('asset_class', 'ETF / Azionario'),
                "total_shares": 0.0,
                "total_invested": 0.0,
                "total_fees": 0.0,
                "pmc": 0.0,
                "last_date": row_dict.get('date'),
                "orders_count": 0,
                "orders": []
            }

        inst = instruments_map[isin]
        inst['total_shares'] += shares
        inst['total_invested'] += invested
        inst['total_fees'] += fees
        inst['orders_count'] += 1
        inst['orders'].append(row_dict)

    # Calculate PMC (Prezzo Medio di Carico)
    instruments_list = []
    for isin, inst in instruments_map.items():
        if inst['total_shares'] > 0:
            inst['pmc'] = round(inst['total_invested'] / inst['total_shares'], 4)
        else:
            inst['pmc'] = 0.0
        inst['total_invested'] = round(inst['total_invested'], 2)
        inst['total_shares'] = round(inst['total_shares'], 4)
        instruments_list.append(inst)

    # Sort instruments by total invested desc
    instruments_list.sort(key=lambda x: x['total_invested'], reverse=True)

    # Check for recent broker transfers from bank statements
    pending_broker_deposits = find_recent_unlinked_broker_deposits(workspace_id, cursor)

    conn.close()

    return {
        "instruments": instruments_list,
        "total_capital_invested": round(total_capital_invested, 2),
        "total_fees_paid": round(total_fees_paid, 2),
        "instruments_count": len(instruments_list),
        "total_orders_count": len(rows),
        "recent_orders": [dict(r) for r in rows[:6]],
        "pending_broker_deposits": pending_broker_deposits
    }

def find_recent_unlinked_broker_deposits(workspace_id, cursor=None):
    """
    Finds bank transfers to brokers (Directa, Scalable, Degiro) that are marked as
    'Investimenti & PAC' in transactions, to propose 1-click allocation.
    """
    should_close = False
    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor()
        should_close = True

    # Get transaction IDs already linked to investments
    linked_ids = set()
    try:
        res = cursor.execute("SELECT transaction_id FROM investments WHERE workspace_id = ? AND transaction_id IS NOT NULL", (workspace_id,)).fetchall()
        linked_ids = {r[0] for r in res if r[0]}
    except Exception:
        pass

    # Query outgoing transactions containing Directa/Degiro or categorized as Investimenti & PAC
    q = """
        SELECT id, date, description, amount, category, sub_category, tags
        FROM transactions
        WHERE workspace_id = ?
        AND amount < 0
        AND (
            category = 'Risparmio & Investimenti'
            OR description LIKE '%DIRECTA%'
            OR description LIKE '%DEGIRO%'
            OR description LIKE '%SCALABLE%'
            OR tags LIKE '%#investimenti_pac%'
        )
        ORDER BY date DESC
        LIMIT 10
    """
    tx_rows = cursor.execute(q, (workspace_id,)).fetchall()
    
    unlinked = []
    for t in tx_rows:
        tx_id = t['id']
        if tx_id in linked_ids:
            continue
        
        # Check if description mentions broker
        desc_upper = (t['description'] or '').upper()
        detected_broker = 'Directa'
        if 'DEGIRO' in desc_upper:
            detected_broker = 'Degiro'
        elif 'SCALABLE' in desc_upper:
            detected_broker = 'Scalable Capital'
        elif 'TRADE REPUBLIC' in desc_upper:
            detected_broker = 'Trade Republic'

        unlinked.append({
            "transaction_id": tx_id,
            "date": t['date'],
            "description": t['description'],
            "amount": abs(float(t['amount'])),
            "detected_broker": detected_broker,
            "suggested_isin": "IE00BK5BQT80",
            "suggested_ticker": "VWCE",
            "suggested_name": "Vanguard FTSE All-World UCITS ETF"
        })

    if should_close:
        cursor.connection.close()

    return unlinked

def record_investment_order(workspace_id, profile_id, data):
    """
    Inserts a new investment purchase order into investments table.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    isin = (data.get('isin') or 'IE00BK5BQT80').strip().upper()
    ticker = (data.get('ticker') or 'VWCE').strip().upper()
    name = (data.get('name') or 'Vanguard FTSE All-World UCITS ETF').strip()
    broker = (data.get('broker') or 'Directa').strip()
    date_val = data.get('date') or datetime.now().strftime('%Y-%m-%d')
    
    shares = float(data.get('shares') or 0.0)
    price = float(data.get('price') or 0.0)
    fees = float(data.get('fees') or 0.0)
    total_invested = float(data.get('total_invested') or (shares * price))
    
    tx_id = data.get('transaction_id')
    if tx_id:
        try:
            tx_id = int(tx_id)
        except (ValueError, TypeError):
            tx_id = None

    notes = data.get('notes') or ''

    cursor.execute("""
        INSERT INTO investments (
            workspace_id, profile_id, transaction_id, isin, ticker, name,
            broker, date, shares, price, total_invested, fees, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        workspace_id, profile_id, tx_id, isin, ticker, name,
        broker, date_val, shares, price, total_invested, fees, notes
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return new_id

def delete_investment_order(workspace_id, order_id):
    """Deletes an investment entry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM investments WHERE workspace_id = ? AND id = ?", (workspace_id, order_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0
