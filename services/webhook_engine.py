import re
import hashlib
from datetime import datetime
from database import get_db_connection, log_webhook_event
from services.bank_importer import categorize_transaction, load_workspace_category_rules, MACRO_CATEGORIES

def parse_amount_str(val_str):
    """Parses European and standard amount strings into float."""
    if val_str is None or val_str == '':
        return 0.0
    if isinstance(val_str, (int, float)):
        return float(val_str)
        
    s = str(val_str).strip()
    s = s.replace("€", "").replace("EUR", "").replace("eur", "").replace("euro", "").replace("Euro", "").strip()
    
    # Handle brackets or trailing minus
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    if s.endswith("-"):
        s = "-" + s[:-1]
        
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
        
    s = re.sub(r"[^\d.-]", "", s)
    try:
        return float(s)
    except ValueError:
        return 0.0

# Non-financial notification filter (promotions, OTPs, login alerts, service messages)
NON_FINANCIAL_KEYWORDS = [
    "codice otp", "codice di sicurezza", "codice temporaneo", "codice verifica", 
    "usa questo codice", "non condividere", "non condividerlo", "one-time password",
    "accesso effettuato", "nuovo accesso", "login", "dispositivo non riconosciuto",
    "nuovo documento", "documento disponibile", "estratto conto disponibile", "comunicazione online",
    "scopri l'offerta", "scopri le novita", "passa a", "passa al conto", "apri un conto",
    "aggiorna l'app", "nuova versione disponibile", "condizioni contrattuali",
    "sensitive notification", "contenuto nascosto", "enhanced notifications"
]

def parse_notification_text(text):
    """
    Intelligently extracts transaction fields from push notification text of Italian banking apps:
    BPER Banca, Poste Italiane, Postepay, BancoPosta, Intesa Sanpaolo, Revolut, UniCredit, Satispay, etc.
    Safely rejects informational, promotional, OTP and security notifications.
    """
    text_clean = (text or "").strip()
    if not text_clean:
        return None

    # Play su MacroDroid senza notifica lascia i placeholder letterali
    if re.search(r'\{not_(title|text|app_name)\}|\[not_(title|text)\]', text_clean, re.IGNORECASE):
        return {
            "raw_text": text_clean,
            "amount": 0.0,
            "is_income": False,
            "merchant": "Placeholder MacroDroid",
            "card_pan": None,
            "bank_hint": None,
            "is_non_transactional": True,
            "skip_reason": "I placeholder {not_title}/{not_text} non sono stati sostituiti. Non usare Play sull'azione HTTP: la macro deve scattare da una notifica BPER vera (inserisci i campi dal pulsante …)."
        }
        
    text_lower = text_clean.lower()
    
    # 0. Safety Guard: Discard non-financial messages (OTP, security, promotional, new documents)
    if any(k in text_lower for k in NON_FINANCIAL_KEYWORDS):
        return {
            "raw_text": text_clean,
            "amount": 0.0,
            "is_income": False,
            "merchant": "Notifica Informativa",
            "card_pan": None,
            "bank_hint": None,
            "is_non_transactional": True,
            "skip_reason": "Notifica promozionale, OTP o di servizio non dispositiva"
        }
    
    # 1. Income detection
    income_kw = [
        "bonifico ricevuto", "accredito", "ricarica ricevuta", "stipendio", 
        "ricevuto", "rimborso", "accreditati", "bonifico in accredito"
    ]
    is_income = any(k in text_lower for k in income_kw)
    
    # 2. Extract Amount with Strict Currency Context
    # Must have an explicit currency symbol/word OR be preceded by an explicit financial action
    raw_amount = 0.0
    matched_amt_str = ""
    
    text_amt = text_clean.replace("\xa0", " ").replace("\u202f", " ").replace("\u2009", " ")
    amt_num = r'([0-9]{1,3}(?:[.\s][0-9]{3})*(?:[.,][0-9]{1,2})|[0-9]+(?:[.,][0-9]{1,2})?)'

    # A. Currency attached (e.g. "EUR 12,50", "12,50 €", "Euro 1.250,00", "€ 45,00")
    curr_match = re.search(r'(?:euro|eur|€)\s*' + amt_num, text_amt, re.IGNORECASE)
    if not curr_match:
        curr_match = re.search(amt_num + r'\s*(?:euro|eur|€)', text_amt, re.IGNORECASE)
        
    if curr_match:
        matched_amt_str = curr_match.group(0)
        raw_amount = parse_amount_str(curr_match.group(1))
    else:
        # B. Transactional keyword followed by "di [importo]"
        action_match = re.search(
            r'(?:pagamento|spesa|addebito|bonifico|prelievo|operazione|accredito|autorizzazione|ricarica|movimento|transazione|pagato|addebitati|prelevati|importo)\s+(?:di|da|per)?\s*' + amt_num,
            text_amt,
            re.IGNORECASE
        )
        if action_match:
            matched_amt_str = action_match.group(0)
            raw_amount = parse_amount_str(action_match.group(1))
            
    if raw_amount == 0.0:
        return {
            "raw_text": text_clean,
            "amount": 0.0,
            "is_income": False,
            "merchant": "Notifica Senza Spesa",
            "card_pan": None,
            "bank_hint": None,
            "is_non_transactional": True,
            "skip_reason": "Nessuna spesa o importo in valuta rilevato nel testo"
        }
        
    final_amount = abs(raw_amount) if is_income else -abs(raw_amount)

    
    # 3. Extract Card PAN / Last digits (*2651, **1234, terminante con 9876)
    card_pan = None
    pan_match = re.search(r'(?:\*+|\.{2,}|terminante\s+con\s+|carta\s+n\.?\s*)(\d{4})\b', text_clean, re.IGNORECASE)
    if pan_match:
        card_pan = pan_match.group(1)
        
    # 4. Bank Hint
    bank_hint = None
    if "bper" in text_lower:
        bank_hint = "BPER Banca"
    elif "postepay" in text_lower:
        bank_hint = "Postepay"
    elif "bancoposta" in text_lower or "poste" in text_lower:
        bank_hint = "Poste Italiane"
    elif "intesa" in text_lower or "sanpaolo" in text_lower:
        bank_hint = "Intesa Sanpaolo"
    elif "revolut" in text_lower:
        bank_hint = "Revolut"
    elif "unicredit" in text_lower:
        bank_hint = "UniCredit"
    elif "bbva" in text_lower:
        bank_hint = "BBVA"
    elif "satispay" in text_lower:
        bank_hint = "Satispay"
        
    # 5. Extract Merchant / Beneficiary / Reason
    merchant = None
    
    # Rule A: "presso [Esercente]" (Highest confidence for Italian POS & online purchases)
    presso_match = re.search(r'\bpresso\s+([A-Za-z0-9\s\'\.\-\&]+?)(?=\s+eseguita|\s+con\s+carta|\s+il\s+\d|\s+completat|\.|$)', text_clean, re.IGNORECASE)
    if presso_match:
        cand = presso_match.group(1).strip()
        if len(cand) >= 2:
            merchant = cand
            
    # Rule B: "a favore di [Beneficiario]" (Bonifico)
    if not merchant:
        favore_match = re.search(r'\ba\s+favore\s+di\s+([A-Za-z0-9\s\'\.\-\&]+?)(?=\.|$)', text_clean, re.IGNORECASE)
        if favore_match:
            merchant = favore_match.group(1).strip()
            
    # Rule C: "da [Ordinante]" (Bonifico ricevuto o accredito)
    if not merchant and is_income:
        da_match = re.search(r'\bda\s+([A-Za-z0-9\s\'\.\-\&]+?)(?=\.|$)', text_clean, re.IGNORECASE)
        if da_match:
            merchant = da_match.group(1).strip()
            
    # Rule D: "per [Causale / Rata]"
    if not merchant:
        per_match = re.search(r'\bper\s+([A-Za-z0-9\s\'\.\-\&]+?)(?=\s+eseguita|\s+con\s+carta|\.|$)', text_clean, re.IGNORECASE)
        if per_match:
            merchant = per_match.group(1).strip()
            
    # Rule E: "a [Esercente] completato" (es. Apple Pay o Satispay)
    if not merchant:
        a_match = re.search(r'\ba\s+([A-Za-z0-9\s\'\.\-\&]+?)(?=\s+completato|\s+effettuato|\.|$)', text_clean, re.IGNORECASE)
        if a_match:
            cand = a_match.group(1).strip()
            cand_clean = re.sub(r'^(favore\s+di|la\s+carta|carta)\s+', '', cand, flags=re.IGNORECASE)
            if len(cand_clean) >= 2:
                merchant = cand_clean
                
    # Fallback cleanup if merchant still empty
    if not merchant:
        fallback = text_clean
        if matched_amt_str:
            fallback = fallback.replace(matched_amt_str, "")
        words_to_strip = [
            "bper", "banca", "postepay", "bancoposta", "poste", "italiane", 
            "autorizzazione", "pagamento", "spesa", "operazione", "eseguita", 
            "completato", "effettuata", "con", "carta", "presso", "euro", "eur", 
            "pos", "addebito", "hai", "speso", "da"
        ]
        for w in words_to_strip:
            fallback = re.sub(r'\b' + w + r'\b', '', fallback, flags=re.IGNORECASE)
        fallback = re.sub(r'[\*\:\-\#]', ' ', fallback)
        fallback = re.sub(r'\s+', ' ', fallback).strip()
        merchant = fallback if len(fallback) >= 2 else "Movimento da Notifica Smartphone"
        
    # Clean trailing or leading punctuation
    merchant = merchant.strip(" .,-:")
    if len(merchant) > 70:
        merchant = merchant[:70].strip()
        
    return {
        "raw_text": text_clean,
        "amount": final_amount,
        "is_income": is_income,
        "merchant": merchant,
        "card_pan": card_pan,
        "bank_hint": bank_hint
    }

def match_workspace_account(workspace_id, bank_hint=None, card_pan=None, account_id=None, account_name=None):
    """
    Finds the most suitable account in the workspace based on:
    1. Explicit account_id
    2. Card PAN last 4 digits (e.g. '2651')
    3. Account Name matching
    4. Bank Name hint (BPER, Postepay, etc.)
    5. Fallback: primary workspace checking account
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Direct ID match
    if account_id:
        acc = cursor.execute("SELECT * FROM accounts WHERE id = ? AND workspace_id = ?", (account_id, workspace_id)).fetchone()
        if acc:
            conn.close()
            return dict(acc)
            
    # Fetch all accounts of workspace
    accounts = cursor.execute("SELECT * FROM accounts WHERE workspace_id = ? ORDER BY id ASC", (workspace_id,)).fetchall()
    conn.close()
    
    if not accounts:
        return None
        
    acc_list = [dict(a) for a in accounts]
    
    # 2. Match by card_pan (e.g. '2651' in '**** **** **** 2651')
    if card_pan:
        clean_pan = str(card_pan).strip()
        for a in acc_list:
            if a.get('card_pan') and clean_pan in str(a['card_pan']):
                return a
                
    # 3. Match by explicit account_name
    if account_name:
        name_lower = str(account_name).lower().strip()
        for a in acc_list:
            if name_lower in a['name'].lower():
                return a
                
    # 4. Match by bank_hint
    if bank_hint:
        hint_lower = bank_hint.lower()
        # First priority: check for specific card if Postepay / Card
        if "postepay" in hint_lower:
            for a in acc_list:
                if "postepay" in a['name'].lower() or a.get('type') == 'CARD':
                    return a
        # General bank match
        for a in acc_list:
            if (a.get('bank_name') and hint_lower in a['bank_name'].lower()) or (hint_lower in a['name'].lower()):
                return a
                
    # 5. Fallback: Preferred Checking account or first account
    for a in acc_list:
        if a.get('type') == 'CHECKING':
            return a
            
    return acc_list[0]

def process_webhook_transaction(workspace_id, payload_dict, source='SMARTPHONE'):
    """
    Main webhook handler: processes incoming notification or structured payload,
    categorizes, deduplicates, updates account balance and records transaction.
    """
    if not workspace_id:
        return {"success": False, "error": "Workspace ID mancante"}
        
    # A. Extract data either from raw notification text or structured fields
    text_keys = (
        'notification_text', 'text', 'message', 'raw_text',
        'not_text', 'not_title', 'ntitle', 'ntext', 'title', 'body', 'ticker'
    )
    chunks = []
    for k in text_keys:
        v = payload_dict.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s and s not in chunks:
            chunks.append(s)
    raw_text = " ".join(chunks).strip()
    
    amount = None
    description = None
    account_hint = payload_dict.get('account') or payload_dict.get('account_name')
    account_id = payload_dict.get('account_id')
    date_str = payload_dict.get('date') or datetime.now().strftime("%Y-%m-%d")
    try:
        from zoneinfo import ZoneInfo
        date_str = payload_dict.get('date') or datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d")
    except Exception:
        pass
    custom_category = payload_dict.get('category')
    custom_tags = payload_dict.get('tags')
    
    parsed_info = None
    if raw_text:
        parsed_info = parse_notification_text(raw_text)
        if parsed_info:
            if parsed_info.get('is_non_transactional'):
                reason = parsed_info.get('skip_reason', 'Notifica informativa o promozionale')
                log_webhook_event(workspace_id, source=source, raw_payload=payload_dict,
                                  parsed_amount=0.0, parsed_description=parsed_info.get('merchant', 'Informativa'),
                                  status='SKIPPED', error_message=reason)
                return {
                    "success": True,
                    "skipped": True,
                    "message": f"Notifica informativa ignorata: {reason}."
                }
            amount = parsed_info['amount']
            description = parsed_info['merchant']
            
    # Direct field override if provided in JSON
    if payload_dict.get('amount') is not None:
        amount = parse_amount_str(payload_dict.get('amount'))
        # If type is specified as EXPENSE and amount is positive, negate it
        tx_type = str(payload_dict.get('type', '')).upper()
        if tx_type in ['EXPENSE', 'USCITA', 'SPESA'] and amount > 0:
            amount = -amount
            
    if payload_dict.get('description'):
        description = str(payload_dict.get('description')).strip()
        
    if not description:
        description = "Spesa da Notifica Smartphone"
        
    if amount is None or amount == 0.0:
        err_msg = "Importo non identificato o pari a 0.00 nel payload."
        log_webhook_event(workspace_id, source=source, raw_payload=payload_dict, 
                          status='ERROR', error_message=err_msg)
        return {"success": False, "error": err_msg}
        
    # B. Match Account
    target_account = match_workspace_account(
        workspace_id, 
        bank_hint=parsed_info.get('bank_hint') if parsed_info else None,
        card_pan=parsed_info.get('card_pan') if parsed_info else None,
        account_id=account_id,
        account_name=account_hint
    )
    
    if not target_account:
        err_msg = "Nessun conto o carta trovato nel workspace per associare il movimento."
        log_webhook_event(workspace_id, source=source, raw_payload=payload_dict, 
                          parsed_amount=amount, parsed_description=description,
                          status='ERROR', error_message=err_msg)
        return {"success": False, "error": err_msg}
        
    acc_id = target_account['id']
    acc_name = target_account['name']
    
    # C. Categorization
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Primary Profile for Workspace
    prof = cursor.execute("SELECT id FROM profiles WHERE workspace_id = ? AND is_primary = 1", (workspace_id,)).fetchone()
    if not prof:
        prof = cursor.execute("SELECT id FROM profiles WHERE workspace_id = ? ORDER BY id ASC LIMIT 1", (workspace_id,)).fetchone()
    profile_id = prof['id'] if prof else None
    
    # Auto-categorize
    if custom_category:
        category = custom_category
        sub_category = payload_dict.get('sub_category') or ""
        tags = custom_tags or ""
        is_transfer = False
    else:
        custom_rules = load_workspace_category_rules(workspace_id)
        category, sub_category, tags, is_transfer = categorize_transaction(
            description, amount, custom_rules=custom_rules
        )
        if custom_tags:
            tags = (tags + " " + custom_tags).strip()
            
    # D. Deduplication Protection (SHA-256 Hash + 24h Window Check)
    # 1. SHA-256 Hash matching bank_importer format
    hash_input = f"{workspace_id}_{acc_id}_{date_str}_{amount:.2f}_{description.strip().lower()}"
    tx_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
    
    # Check by hash
    existing = cursor.execute(
        "SELECT id FROM transactions WHERE workspace_id = ? AND import_hash = ?", 
        (workspace_id, tx_hash)
    ).fetchone()
    
    if not existing:
        # Check identical transaction in same account within current day
        existing = cursor.execute('''
            SELECT id FROM transactions 
            WHERE workspace_id = ? AND account_id = ? AND date = ? AND amount = ? 
              AND LOWER(description) = LOWER(?)
        ''', (workspace_id, acc_id, date_str, amount, description)).fetchone()
        
    if existing:
        conn.close()
        log_webhook_event(
            workspace_id, source=source, raw_payload=payload_dict,
            parsed_amount=amount, parsed_description=description,
            account_id=acc_id, transaction_id=existing['id'],
            status='DUPLICATE', error_message="Movimento identico già registrato (deduplicato)"
        )
        return {
            "success": True,
            "duplicate": True,
            "transaction_id": existing['id'],
            "message": f"Movimento già presente (Deduplicato): {amount:.2f}€ '{description}' su '{acc_name}'.",
            "account_name": acc_name,
            "description": description,
            "amount": amount,
            "category": category
        }
        
    # E. Insert Transaction
    cursor.execute('''
        INSERT INTO transactions (
            workspace_id, profile_id, account_id, date, amount, category,
            sub_category, description, raw_description, is_transfer, tags, import_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        workspace_id, profile_id, acc_id, date_str, amount, category,
        sub_category, description, raw_text if raw_text else f"Webhook {source}: {description}",
        1 if is_transfer else 0, tags, tx_hash
    ))
    new_tx_id = cursor.lastrowid
    
    # F. Update Account Balance
    cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, acc_id))
    new_balance = target_account['balance'] + amount
    
    conn.commit()
    conn.close()
    
    # G. Log Event
    log_webhook_event(
        workspace_id, source=source, raw_payload=payload_dict,
        parsed_amount=amount, parsed_description=description,
        account_id=acc_id, transaction_id=new_tx_id,
        status='SUCCESS'
    )
    
    sign_str = "+" if amount > 0 else "-"
    formatted_amt = f"€ {abs(amount):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    return {
        "success": True,
        "duplicate": False,
        "transaction_id": new_tx_id,
        "message": f"Registrata con successo spesa di {sign_str}{formatted_amt} ({description}) su '{acc_name}'!",
        "account_id": acc_id,
        "account_name": acc_name,
        "description": description,
        "amount": amount,
        "date": date_str,
        "category": category,
        "sub_category": sub_category,
        "tags": tags,
        "new_balance": round(new_balance, 2)
    }
