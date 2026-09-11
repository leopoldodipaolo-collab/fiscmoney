import os
import re
import uuid
import functools
import urllib.parse
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from database import (
    init_db, get_db_connection, DB_PATH, log_admin_action, get_active_announcement,
    create_workspace_invitation, get_invitation_by_token, accept_invitation,
    get_workspace_personalization, save_workspace_personalization
)
from services.bank_importer import (
    MACRO_CATEGORIES,
    CATEGORY_SMART_TAGS,
    CATEGORY_SEARCH_DICTIONARY,
    parse_bank_file,
    categorize_transaction,
    extract_account_metadata,
    extract_clean_merchant_pattern,
    aggregate_transactions_by_merchant,
    group_transactions_by_category,
    load_workspace_category_rules,
    save_or_update_category_rule,
    apply_rule_retroactively,
    apply_all_workspace_rules,
    build_dynamic_smart_tags,
    seed_personalization_rules
)
from services.cashflow_engine import (
    MONTH_NAMES_IT,
    MONTH_NAMES_IT_SHORT,
    get_monthly_cashflow_data,
    get_multi_month_trend_data,
    get_macro_advisor_insights,
    get_monthly_forecast_and_considerations
)
from services.vertical_focus_engine import (
    get_active_focus_categories,
    toggle_focus_category,
    get_vertical_category_data,
    get_mortgage_deep_dive,
    get_mortgage_profile
)
from services.couple_split_engine import (
    get_couple_split_analytics,
    get_couple_category_transactions,
    bulk_set_category_shared
)
from services.deadlines_radar_engine import (
    get_annual_deadlines_radar,
    auto_seed_typical_family_deadlines
)
from services.paystub_engine import (
    calculate_paystub_metrics,
    find_candidate_bank_transfers,
    get_month_bank_coverage,
    compare_two_paystubs,
    get_profile_paystubs_summary,
    detect_paystub_anomalies,
    PAYSTUB_GLOSSARY
)
from services.paystub_pdf_parser import parse_paystub_pdf
from services.online_ai_classifier import classify_merchant_online
from services.assistant_engine import (
    ASSISTANT_PERSONAS,
    get_persona,
    generate_paystub_assistant_briefing,
    generate_dashboard_assistant_briefing
)
from services.tax_730_parser import parse_tax_730_pdf
from services.tax_730_engine import (
    find_matching_paystub_for_730,
    calculate_tax_optimization_insights,
    generate_730_assistant_briefing,
    perform_730_audit_and_action_plan
)
import json


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "FiscMoney_Super_Secure_Secret_2026_Key!")
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=14)

# Temporary In-Memory Storage for Import Previews
IMPORT_CACHE = {}

# Initialize Database Schema on startup
init_db()

@app.route('/health')
def health_check():
    return {"status": "ok", "app": "FiscMoney", "version": "2.0"}, 200

# Bank Institution Themes and Visual Branding
BANK_THEMES = {
    "BPER Banca": {"icon": "🏛️", "color": "#0ea5e9", "badge_bg": "rgba(14, 165, 233, 0.15)"},
    "Poste Italiane (BancoPosta)": {"icon": "📮", "color": "#eab308", "badge_bg": "rgba(234, 179, 8, 0.15)"},
    "Poste Italiane (Postepay)": {"icon": "💳", "color": "#f59e0b", "badge_bg": "rgba(245, 158, 11, 0.15)"},
    "Poste Italiane": {"icon": "📮", "color": "#eab308", "badge_bg": "rgba(234, 179, 8, 0.15)"},
    "BCC - Credito Cooperativo": {"icon": "🏦", "color": "#10b981", "badge_bg": "rgba(16, 185, 129, 0.15)"},
    "Intesa Sanpaolo": {"icon": "🏛️", "color": "#22c55e", "badge_bg": "rgba(34, 197, 94, 0.15)"},
    "UniCredit": {"icon": "🔴", "color": "#ef4444", "badge_bg": "rgba(239, 68, 68, 0.15)"},
    "Fineco Bank": {"icon": "📊", "color": "#3b82f6", "badge_bg": "rgba(59, 130, 246, 0.15)"},
    "Revolut": {"icon": "🚀", "color": "#6366f1", "badge_bg": "rgba(99, 102, 241, 0.15)"},
    "BBVA": {"icon": "🌐", "color": "#0284c7", "badge_bg": "rgba(2, 132, 199, 0.15)"},
    "Altro": {"icon": "💳", "color": "#94a3b8", "badge_bg": "rgba(148, 163, 184, 0.15)"}
}

def get_bank_theme(bank_name):
    if not bank_name:
        return BANK_THEMES["Altro"]
    for k, v in BANK_THEMES.items():
        if k.lower() in bank_name.lower() or bank_name.lower() in k.lower():
            return v
    return BANK_THEMES["Altro"]

@app.template_filter('eur')
def format_eur(val):
    if val is None or val == '':
        return "€ 0,00"
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return f"{val}"
    is_neg = fval < 0
    abs_val = abs(fval)
    formatted = f"{abs_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-€ {formatted}" if is_neg else f"€ {formatted}"

@app.template_filter('eur_sign')
def format_eur_sign(val):
    if val is None or val == '':
        return "€ 0,00"
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return f"{val}"
    abs_val = abs(fval)
    formatted = f"{abs_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if fval > 0:
        return f"+€ {formatted}"
    elif fval < 0:
        return f"-€ {formatted}"
    return f"€ {formatted}"

@app.context_processor
def inject_formatters():
    current_persona_key = session.get('assistant_persona', 'demetrio')
    if current_persona_key == 'leo':
        current_persona_key = 'demetrio'
    active_persona = get_persona(current_persona_key)
    active_announcement = get_active_announcement()
    
    ws_id = session.get('workspace_id')
    ws_pers = get_workspace_personalization(ws_id) if ws_id else None
    dyn_smart_tags = build_dynamic_smart_tags(ws_pers)
    
    user_sub_plan = session.get('subscription_plan', 'FREE')
    user_sub_status = session.get('subscription_status', 'ACTIVE')
    user_sub_expires_at = session.get('subscription_expires_at')
    
    sub_days_left = None
    sub_is_expired = False
    if user_sub_expires_at:
        try:
            exp_date = datetime.strptime(str(user_sub_expires_at)[:10], "%Y-%m-%d").date()
            today = datetime.now().date()
            delta = (exp_date - today).days
            sub_days_left = delta
            if delta < 0:
                sub_is_expired = True
        except Exception:
            sub_days_left = None
    
    return dict(
        eur=format_eur, 
        eur_sign=format_eur_sign,
        active_persona=active_persona,
        all_personas=ASSISTANT_PERSONAS,
        current_persona_key=current_persona_key,
        macro_categories_dict=MACRO_CATEGORIES,
        category_guide_items=CATEGORY_SEARCH_DICTIONARY,
        category_smart_tags=dyn_smart_tags,
        workspace_personalization=ws_pers,
        active_announcement=active_announcement,
        is_impersonating=bool(session.get('original_admin_id')),
        original_admin_name=session.get('original_admin_name', ''),
        user_role=session.get('role', 'USER'),
        user_subscription_plan=user_sub_plan,
        user_subscription_status=user_sub_status,
        user_subscription_expires_at=user_sub_expires_at,
        subscription_days_left=sub_days_left,
        subscription_is_expired=sub_is_expired
    )


# Login Required Decorator
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if session.get('user_id') is None:
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

# Super Admin Required Decorator
def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        # Allow if currently super admin, or if super admin is impersonating
        if session.get('user_id') is None:
            flash("Effettua l'accesso per accedere a questa sezione.", "error")
            return redirect(url_for('login'))
        if session.get('role') != 'SUPER_ADMIN' and not session.get('original_admin_id'):
            flash("Accesso riservato all'Amministratore della piattaforma.", "error")
            return redirect(url_for('dashboard'))
        return view(**kwargs)
    return wrapped_view

@app.route("/")
def index():
    if session.get('user_id'):
        if session.get('role') == 'SUPER_ADMIN' and not session.get('original_admin_id'):
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            # Check if suspended
            if user['subscription_status'] == 'SUSPENDED':
                conn.close()
                flash("Questo account è stato sospeso dall'amministratore. Contatta il supporto.", "error")
                return redirect(url_for('login'))

            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_name'] = user['full_name']
            session['role'] = user['role']
            session['subscription_plan'] = user['subscription_plan'] or 'FREE'
            session['subscription_status'] = user['subscription_status'] or 'ACTIVE'
            session['subscription_expires_at'] = user['subscription_expires_at']
            
            # Update last_login_at
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (user['id'],))
            conn.commit()
            
            # Fetch default workspace for user
            ws = conn.execute('''
                SELECT w.* FROM workspaces w
                JOIN workspace_members wm ON w.id = wm.workspace_id
                WHERE wm.user_id = ? LIMIT 1
            ''', (user['id'],)).fetchone()
            
            if ws:
                session['workspace_id'] = ws['id']
                session['workspace_name'] = ws['name']
            
            conn.close()
            flash(f"Bentornato {user['full_name']}!", "success")
            
            if user['role'] == 'SUPER_ADMIN':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
            
        conn.close()
        flash("Email o password non corrette.", "error")
        
    return render_template("auth/login.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

def validate_password_complexity(password):
    """
    Validates password strength:
    - Minimum 8 characters
    - At least 1 number (0-9)
    - At least 1 letter (a-z, A-Z)
    - At least 1 special character (!@#$%^&* etc.)
    """
    if len(password) < 8:
        return False, "La password deve contenere almeno 8 caratteri."
    if not re.search(r'\d', password):
        return False, "La password deve contenere almeno un numero (0-9)."
    if not re.search(r'[a-zA-Z]', password):
        return False, "La password deve contenere almeno una lettera."
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':",.<>/?\\|`~]', password):
        return False, "La password deve contenere almeno un carattere speciale (es. ! @ # $ % ? * &)."
    return True, None


@app.route("/register", methods=["POST"])
def register():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    privacy_consent = request.form.get("privacy_consent")
    
    if not email or not password or not full_name:
        flash("Tutti i campi sono obbligatori.", "error")
        return redirect(url_for('login'))
        
    if not privacy_consent:
        flash("È necessario accettare l'Informativa sulla Privacy per procedere con la registrazione.", "error")
        return redirect(url_for('login'))
        
    is_valid, err_msg = validate_password_complexity(password)
    if not is_valid:
        flash(err_msg, "error")
        return redirect(url_for('login') + '#register')
        
    conn = get_db_connection()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        flash("Questa email è già registrata. Prova ad accedere.", "error")
        return redirect(url_for('login'))
        
    pwd_hash = generate_password_hash(password)
    
    # Calculate 60-Day Free Trial expiration date
    trial_expires = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
    
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (email, password_hash, full_name, role, subscription_plan, subscription_status, subscription_expires_at, assistant_persona)
        VALUES (?, ?, ?, 'USER', 'PRO_ANNUAL', 'ACTIVE', ?, 'demetrio')
    ''', (email, pwd_hash, full_name, trial_expires))
    
    user_id = cursor.lastrowid
    
    # Check if this email was invited to an existing family workspace
    invited_profiles = conn.execute("SELECT * FROM profiles WHERE invited_email = ?", (email,)).fetchall()
    
    if invited_profiles:
        for inv_p in invited_profiles:
            cursor.execute("UPDATE profiles SET linked_user_id = ? WHERE id = ?", (user_id, inv_p['id']))
            cursor.execute("INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, 'MEMBER')", (inv_p['workspace_id'], user_id))
    else:
        # Create Default Single Workspace for User
        ws_name = f"Workspace di {full_name.split()[0]}"
        cursor.execute("INSERT INTO workspaces (name, type) VALUES (?, 'SINGLE')", (ws_name,))
        ws_id = cursor.lastrowid
        cursor.execute("INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, 'OWNER')", (ws_id, user_id))
        cursor.execute("INSERT INTO profiles (workspace_id, name, is_primary, assistant_persona) VALUES (?, ?, 1, 'demetrio')", (ws_id, full_name))
    
    conn.commit()
    conn.close()
    
    # Auto-login newly registered user
    session['user_id'] = user_id
    session['user_email'] = email
    session['user_name'] = full_name
    session['role'] = 'USER'
    session['assistant_persona'] = 'demetrio'
    session['subscription_plan'] = 'PRO_ANNUAL'
    session['subscription_status'] = 'ACTIVE'
    session['subscription_expires_at'] = trial_expires
    session['workspace_id'] = ws_id if not invited_profiles else invited_profiles[0]['workspace_id']
    session['workspace_name'] = ws_name if not invited_profiles else "Workspace Condiviso"
    
    flash(f"🎉 Registrazione completata! Benvenuto in FiscMoney, {full_name}. Il tuo Piano PRO è attivo in prova gratuita per 60 giorni.", "success")
    return redirect(url_for('welcome_assistant'))

@app.route("/onboarding/welcome")
@login_required
def welcome_assistant():
    return render_template(
        "auth/welcome_assistant.html",
        personas=ASSISTANT_PERSONAS
    )

@app.route("/logout")
def logout():
    session.clear()
    flash("Sessione chiusa correttamente.", "success")
    return redirect(url_for('login'))

def get_workspace_privacy_context(conn, ws_id, user_id):
    ws = conn.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone() if ws_id else None
    sharing_mode = ws['sharing_mode'] if ws and ws['sharing_mode'] else 'FULL'
    
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone() if user_id else None
    mem = conn.execute("SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?", (ws_id, user_id)).fetchone() if ws_id and user_id else None
    is_admin = bool((mem and mem['role'] in ['OWNER', 'ADMIN']) or (user and user['role'] == 'SUPER_ADMIN'))
    
    all_profiles = conn.execute("SELECT * FROM profiles WHERE workspace_id = ? ORDER BY is_primary DESC, id ASC", (ws_id,)).fetchall() if ws_id else []
    if not all_profiles and ws_id:
        u_name = user['full_name'] if user else 'Leopoldo Di Paolo'
        conn.execute("INSERT INTO profiles (workspace_id, name, is_primary, role_title) VALUES (?, ?, 1, 'Titolare')", (ws_id, u_name))
        conn.commit()
        all_profiles = conn.execute("SELECT * FROM profiles WHERE workspace_id = ? ORDER BY is_primary DESC, id ASC", (ws_id,)).fetchall()
        
    my_profile = None
    for p in all_profiles:
        if p['linked_user_id'] == user_id:
            my_profile = p
            break
        elif is_admin and p['is_primary']:
            my_profile = p
    if not my_profile and all_profiles:
        my_profile = all_profiles[0]
        
    if not is_admin and sharing_mode in ['ADMIN_ONLY', 'HYBRID'] and my_profile:
        # Strictly locked for non-admin in restricted privacy modes
        active_filter = str(my_profile['id'])
        session['profile_filter'] = active_filter
        selected_profile = my_profile
        visible_profiles = [my_profile]
        p_id_filter = my_profile['id']
    else:
        visible_profiles = all_profiles
        active_filter = session.get('profile_filter', 'all')
        selected_profile = None
        if active_filter != 'all':
            try:
                prof_id = int(active_filter)
                selected_profile = conn.execute("SELECT * FROM profiles WHERE id = ? AND workspace_id = ?", (prof_id, ws_id)).fetchone()
                if not selected_profile:
                    active_filter = 'all'
                    session['profile_filter'] = 'all'
            except (ValueError, TypeError):
                active_filter = 'all'
                session['profile_filter'] = 'all'
        p_id_filter = int(active_filter) if active_filter != 'all' else None
        
    return {
        "ws": ws,
        "user": user,
        "sharing_mode": sharing_mode,
        "is_admin": is_admin,
        "my_profile": my_profile,
        "all_profiles": all_profiles,
        "visible_profiles": visible_profiles,
        "active_filter": active_filter,
        "selected_profile": selected_profile,
        "p_id_filter": p_id_filter
    }

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()
    ws_id = session.get('workspace_id')
    user_id = session.get('user_id')
    
    ctx = get_workspace_privacy_context(conn, ws_id, user_id)
    user = ctx["user"]
    ws = ctx["ws"]
    sharing_mode = ctx["sharing_mode"]
    is_admin = ctx["is_admin"]
    my_profile = ctx["my_profile"]
    all_profiles = ctx["all_profiles"]
    visible_profiles = ctx["visible_profiles"]
    active_filter = ctx["active_filter"]
    selected_profile = ctx["selected_profile"]
    p_id_filter = ctx["p_id_filter"]

    # Calculate Total Balance based on active filter & privacy
    total_balance = 0.0
    if ws_id:
        if not is_admin and sharing_mode in ['ADMIN_ONLY', 'HYBRID'] and my_profile:
            row = conn.execute("SELECT SUM(balance) as total FROM accounts WHERE workspace_id = ? AND (profile_id = ? OR is_shared = 1 OR profile_id IS NULL)", (ws_id, my_profile['id'])).fetchone()
        elif active_filter == 'all':
            row = conn.execute("SELECT SUM(balance) as total FROM accounts WHERE workspace_id = ?", (ws_id,)).fetchone()
        else:
            row = conn.execute("SELECT SUM(balance) as total FROM accounts WHERE workspace_id = ? AND profile_id = ?", (ws_id, selected_profile['id'])).fetchone()
            
        if row and row['total']:
            total_balance = row['total']
            
    # Calculate Balance per profile for family breakdown
    member_balances = []
    if ws_id:
        for p in visible_profiles:
            p_bal_row = conn.execute(
                "SELECT SUM(balance) as total, COUNT(id) as acc_count FROM accounts WHERE workspace_id = ? AND profile_id = ?",
                (ws_id, p['id'])
            ).fetchone()
            p_total = p_bal_row['total'] if p_bal_row and p_bal_row['total'] else 0.0
            p_acc_count = p_bal_row['acc_count'] if p_bal_row else 0
            member_balances.append({
                'id': p['id'],
                'name': p['name'],
                'role_title': p['role_title'] if 'role_title' in p.keys() and p['role_title'] else ('Titolare' if p['is_primary'] else 'Membro'),
                'is_primary': p['is_primary'],
                'invited_email': p['invited_email'] if 'invited_email' in p.keys() else None,
                'linked_user_id': p['linked_user_id'] if 'linked_user_id' in p.keys() else None,
                'total_balance': p_total,
                'accounts_count': p_acc_count
            })
            
    # Calculate Bank Groups for the active filter & privacy
    acc_query = "SELECT a.*, p.name as profile_name FROM accounts a LEFT JOIN profiles p ON a.profile_id = p.id WHERE a.workspace_id = ?"
    acc_params = [ws_id]
    
    if not is_admin and sharing_mode in ['ADMIN_ONLY', 'HYBRID'] and my_profile:
        acc_query += " AND (a.profile_id = ? OR a.is_shared = 1 OR a.profile_id IS NULL)"
        acc_params.append(my_profile['id'])
    elif active_filter != 'all' and selected_profile:
        acc_query += " AND a.profile_id = ?"
        acc_params.append(selected_profile['id'])
        
    acc_rows = conn.execute(acc_query, acc_params).fetchall()

    bank_groups = {}
    for acc in acc_rows:
        b_name = acc['bank_name'] or 'Altro Istituto'
        group_key = b_name
        if "poste" in b_name.lower():
            group_key = "Poste Italiane"
        elif "bper" in b_name.lower():
            group_key = "BPER Banca"
        elif "bcc" in b_name.lower() or "credito cooperativo" in b_name.lower():
            group_key = "BCC - Credito Cooperativo"
            
        if group_key not in bank_groups:
            theme = get_bank_theme(group_key)
            bank_groups[group_key] = {
                "name": group_key,
                "icon": theme["icon"],
                "color": theme["color"],
                "badge_bg": theme["badge_bg"],
                "total_balance": 0.0,
                "accounts": []
            }
        bank_groups[group_key]["total_balance"] += acc['balance']
        
        tx_c = conn.execute("SELECT COUNT(*) FROM transactions WHERE account_id = ?", (acc['id'],)).fetchone()[0]
        acc_d = dict(acc)
        acc_d["tx_count"] = tx_c
        bank_groups[group_key]["accounts"].append(acc_d)
        
    bank_groups_list = list(bank_groups.values())
    for bg in bank_groups_list:
        bg["percent"] = round((bg["total_balance"] / total_balance * 100), 1) if total_balance > 0 else 0.0

    # Retrieve Custom Salary & Target Savings from session or parameters
    custom_salary = request.args.get('salary') or session.get('custom_salary')
    if custom_salary:
        try:
            custom_salary = float(str(custom_salary).replace(',', '.'))
        except (ValueError, TypeError):
            custom_salary = None

    custom_target = request.args.get('target') or session.get('custom_target')
    if custom_target:
        try:
            custom_target = float(str(custom_target).replace(',', '.'))
        except (ValueError, TypeError):
            custom_target = None

    # Calculate Cash Flow summary for current month and Multi-Month Trend
    p_id_filter = int(active_filter) if active_filter != 'all' else None
    cashflow_summary = get_monthly_cashflow_data(ws_id, p_id_filter) if ws_id else None
    
    trend_range = request.args.get('trend_range', '12').strip()
    try:
        trend_count = int(trend_range)
        if trend_count not in [6, 12, 18, 24]:
            trend_count = 12
    except (ValueError, TypeError):
        trend_count = 12

    trend_data = get_multi_month_trend_data(ws_id, p_id_filter, months_count=trend_count) if ws_id else None
    advisor_insights = get_macro_advisor_insights(ws_id, p_id_filter) if ws_id else []

    user_p_name = selected_profile['name'] if selected_profile else (user['full_name'] if user else 'Utente')
    monthly_forecast = get_monthly_forecast_and_considerations(
        cashflow_summary,
        custom_salary=custom_salary,
        custom_target=custom_target,
        profile_name=user_p_name
    ) if cashflow_summary else None

    # Fetch Latest 730 Declaration
    t730_query = "SELECT * FROM tax_declarations_730 WHERE workspace_id = ?"
    t730_params = [ws_id]
    if active_filter != 'all' and selected_profile:
        t730_query += " AND profile_id = ?"
        t730_params.append(selected_profile['id'])
    t730_query += " ORDER BY declaration_year DESC, tax_year DESC LIMIT 1"
    latest_730_row = conn.execute(t730_query, t730_params).fetchone()
    latest_730 = dict(latest_730_row) if latest_730_row else None
    if latest_730:
        opt_ins = calculate_tax_optimization_insights(latest_730)
        latest_730['pension_headroom'] = opt_ins['pension_headroom']
        latest_730['potential_pension_tax_savings'] = opt_ins['potential_pension_tax_savings']
        latest_730['tax_outcome_val'] = (latest_730.get('final_refund_or_debit') or 0.0) * (1 if latest_730.get('is_refund', 1) else -1)
        latest_730['tax_outcome_type'] = 'Rimborso' if latest_730.get('is_refund', 1) else 'A Debito'

    # Fetch Latest Paystub
    ps_query = "SELECT * FROM paystubs WHERE workspace_id = ?"
    ps_params = [ws_id]
    if active_filter != 'all' and selected_profile:
        ps_query += " AND profile_id = ?"
        ps_params.append(selected_profile['id'])
    ps_query += " ORDER BY year DESC, month DESC LIMIT 1"
    latest_ps_row = conn.execute(ps_query, ps_params).fetchone()
    latest_paystub = dict(latest_ps_row) if latest_ps_row else None
    month_names = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
                   "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    if latest_paystub and 1 <= latest_paystub.get('month', 0) <= 12:
        latest_paystub['month_name'] = month_names[latest_paystub['month']]
        latest_paystub['period'] = f"{latest_paystub['month_name']} {latest_paystub.get('year', '')}".strip()
    if latest_paystub:
        latest_paystub['net_salary'] = latest_paystub.get('net_amount', 0.0)
        latest_paystub['ticket_total'] = latest_paystub.get('ticket_total_value', 0.0)

    # Generate Dashboard Assistant Briefing
    current_persona_key = session.get('assistant_persona') or (my_profile['assistant_persona'] if my_profile and 'assistant_persona' in my_profile.keys() and my_profile['assistant_persona'] else None) or (user['assistant_persona'] if user and 'assistant_persona' in user.keys() and user['assistant_persona'] else None) or 'demetrio'
    dashboard_briefing = generate_dashboard_assistant_briefing(
        persona_key=current_persona_key,
        profile_name=user_p_name,
        cashflow=cashflow_summary,
        latest_paystub=latest_paystub,
        latest_730=latest_730,
        total_balance=total_balance
    )

    # Fetch Mortgage Snapshot and Active Focus Categories for Dashboard Widget
    mortgage_data = get_mortgage_deep_dive(ws_id, p_id_filter) if ws_id else None
    active_focus_categories = get_active_focus_categories(ws_id) if ws_id else []

    # Fetch Annual Deadlines Radar (Scadenzario Annuale Famiglia & Avanzamento Quote)
    if ws_id:
        auto_seed_typical_family_deadlines(ws_id)
        deadlines_radar = get_annual_deadlines_radar(ws_id, p_id_filter)
    else:
        deadlines_radar = None

    # Total and uncategorized transactions in workspace for onboarding checklist
    tx_count = conn.execute("SELECT COUNT(*) FROM transactions WHERE workspace_id = ?", (ws_id,)).fetchone()[0] if ws_id else 0
    uncat_count = conn.execute("SELECT COUNT(*) FROM transactions WHERE workspace_id = ? AND (category IS NULL OR category = '' OR category = 'Da Categorizzare' OR category = 'Altro')", (ws_id,)).fetchone()[0] if ws_id else 0

    conn.close()
    
    return render_template(
        "dashboard.html",
        user=user,
        active_workspace=ws,
        profiles=visible_profiles,
        all_profiles=all_profiles,
        active_filter=active_filter,
        selected_profile=selected_profile,
        total_balance=total_balance,
        member_balances=member_balances,
        bank_groups=bank_groups_list,
        cashflow=cashflow_summary,
        trend_data=trend_data,
        advisor_insights=advisor_insights,
        monthly_forecast=monthly_forecast,
        latest_730=latest_730,
        latest_paystub=latest_paystub,
        mortgage_data=mortgage_data,
        active_focus_categories=active_focus_categories,
        deadlines_radar=deadlines_radar,
        assistant_briefing=dashboard_briefing,
        dashboard_briefing=dashboard_briefing,
        is_admin=is_admin,
        my_profile=my_profile,
        total_transactions=tx_count,
        uncategorized_tx_count=uncat_count
    )


@app.route("/assistant/set-persona/<persona_key>", methods=["GET", "POST"])
@login_required
def set_assistant_persona(persona_key):
    valid_key = persona_key
    if persona_key in ('leo', 'demetrio'):
        valid_key = 'demetrio'
    elif persona_key in ('dott_fiscale', 'commercialista'):
        valid_key = 'commercialista'
    
    if valid_key in ASSISTANT_PERSONAS:
        session['assistant_persona'] = valid_key
        u_id = session.get('user_id')
        ws_id = session.get('workspace_id')
        if u_id:
            conn = get_db_connection()
            conn.execute("UPDATE users SET assistant_persona = ? WHERE id = ?", (valid_key, u_id))
            if ws_id:
                conn.execute("UPDATE profiles SET assistant_persona = ? WHERE workspace_id = ?", (valid_key, ws_id))
            conn.commit()
            conn.close()
        persona_obj = ASSISTANT_PERSONAS[valid_key]
        flash(f"Assistente impostato su {persona_obj['name']} {persona_obj['avatar']}", "success")
    
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'persona': valid_key})
    
    next_url = request.args.get('next')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    ref = request.referrer
    if ref and '/login' not in ref and '/register' not in ref:
        return redirect(ref)
    return redirect(url_for('dashboard'))


@app.route("/api/dashboard/trend", methods=["GET"])
@login_required
def api_dashboard_trend():
    ws_id = session.get("workspace_id")
    if not ws_id:
        return jsonify({"success": False, "error": "No active workspace"}), 400
    
    active_filter = session.get("active_profile_filter", "all")
    p_id_filter = int(active_filter) if active_filter != "all" else None
    
    trend_range = request.args.get("range", "12").strip()
    try:
        trend_count = int(trend_range)
        if trend_count not in [6, 12, 18, 24]:
            trend_count = 12
    except (ValueError, TypeError):
        trend_count = 12
        
    trend_data = get_multi_month_trend_data(ws_id, p_id_filter, months_count=trend_count)
    return jsonify({"success": True, "trend_data": trend_data})


# ---------------------------------------------------------
# WORKSPACE MEMBERS & INVITATION ONBOARDING ENGINE
# ---------------------------------------------------------
@app.route("/workspace/profile/add", methods=["POST"])
@login_required
def workspace_add_member():
    ws_id = session.get('workspace_id')
    if not ws_id:
        flash("Workspace non trovato.", "error")
        return redirect(url_for('dashboard'))
        
    name = request.form.get("name", "").strip()
    role_title = request.form.get("role_title", "Partner / Coniuge").strip()
    tax_code = request.form.get("tax_code", "").strip().upper() or None
    
    if not name:
        flash("Il nome del membro è obbligatorio.", "error")
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Switch workspace type to FAMILY if was SINGLE
    cursor.execute("UPDATE workspaces SET type = 'FAMILY' WHERE id = ?", (ws_id,))
    
    # 2. Insert new profile
    cursor.execute('''
        INSERT INTO profiles (workspace_id, name, role_title, tax_code, is_primary, assistant_persona)
        VALUES (?, ?, ?, ?, 0, 'leo')
    ''', (ws_id, name, role_title, tax_code))
    
    new_profile_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    flash(f"Membro '{name}' aggiunto con successo al nucleo familiare! 🎉", "success")
    return redirect(url_for('dashboard'))


@app.route("/workspace/profile/delete/<int:profile_id>", methods=["POST"])
@login_required
def workspace_delete_member(profile_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        flash("Workspace non trovato.", "error")
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verify profile belongs to this workspace and is not primary owner
    prof = cursor.execute("SELECT * FROM profiles WHERE id = ? AND workspace_id = ?", (profile_id, ws_id)).fetchone()
    if not prof:
        conn.close()
        flash("Profilo non trovato.", "error")
        return redirect(url_for('dashboard'))
        
    if prof['is_primary']:
        conn.close()
        flash("Non puoi eliminare il profilo principale del capofamiglia.", "error")
        return redirect(url_for('dashboard'))
        
    # Delete associated accounts and transactions
    acc_ids = [r['id'] for r in cursor.execute("SELECT id FROM accounts WHERE profile_id = ?", (profile_id,)).fetchall()]
    if acc_ids:
        cursor.execute(f"DELETE FROM transactions WHERE account_id IN ({','.join(['?']*len(acc_ids))})", acc_ids)
        cursor.execute("DELETE FROM accounts WHERE profile_id = ?", (profile_id,))
        
    cursor.execute("DELETE FROM paystubs WHERE profile_id = ?", (profile_id,))
    cursor.execute("DELETE FROM tax_declarations_730 WHERE profile_id = ?", (profile_id,))
    cursor.execute("DELETE FROM workspace_invitations WHERE profile_id = ?", (profile_id,))
    cursor.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
    
    # Check remaining profiles count, if 1 revert to SINGLE
    rem_count = cursor.execute("SELECT COUNT(*) FROM profiles WHERE workspace_id = ?", (ws_id,)).fetchone()[0]
    if rem_count <= 1:
        cursor.execute("UPDATE workspaces SET type = 'SINGLE' WHERE id = ?", (ws_id,))
        
    conn.commit()
    conn.close()
    
    flash(f"Profilo '{prof['name']}' e relativi dati collegati eliminati con successo.", "success")
    return redirect(url_for('dashboard'))


@app.route("/api/workspace/profile/invite/<int:profile_id>", methods=["POST"])
@login_required
def api_workspace_profile_invite(profile_id):
    ws_id = session.get('workspace_id')
    u_id = session.get('user_id')
    if not ws_id or not u_id:
        return jsonify({"success": False, "error": "Non autorizzato"}), 401
        
    conn = get_db_connection()
    prof = conn.execute("SELECT * FROM profiles WHERE id = ? AND workspace_id = ?", (profile_id, ws_id)).fetchone()
    ws = conn.execute("SELECT * FROM workspaces WHERE id = ?", (ws_id,)).fetchone()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (u_id,)).fetchone()
    conn.close()
    
    if not prof:
        return jsonify({"success": False, "error": "Profilo non trovato nel tuo spazio"}), 404
        
    # Read optional target email and phone
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    target_email = data.get("email", "").strip().lower() or None
    target_phone = data.get("phone", "").strip() or None
    
    # Generate cryptographic token
    token = create_workspace_invitation(
        workspace_id=ws_id,
        profile_id=profile_id,
        inviter_user_id=u_id,
        target_name=prof['name'],
        target_email=target_email
    )
    
    # Build Absolute Invite URL & WhatsApp Share URL
    base_url = request.host_url.rstrip('/')
    invite_url = f"{base_url}/join?token={token}"
    
    inviter_first_name = user['full_name'].split()[0] if user and user['full_name'] else "Io"
    member_name = prof['name']
    
    wa_message = f"Ciao {member_name}! {inviter_first_name} ti ha invitato a gestire il bilancio familiare su FiscMoney 🎯 Entra da questo link sicuro per attivare il tuo profilo: {invite_url}"
    
    # If phone is provided, format phone URL; otherwise generic WhatsApp share URL
    if target_phone:
        clean_phone = target_phone.replace("+", "").replace(" ", "").replace("-", "")
        if not clean_phone.startswith("39") and len(clean_phone) == 10:
            clean_phone = "39" + clean_phone
        whatsapp_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_message)}"
    else:
        whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(wa_message)}"
        
    return jsonify({
        "success": True,
        "token": token,
        "invite_url": invite_url,
        "whatsapp_url": whatsapp_url,
        "profile_name": member_name,
        "target_email": target_email or (prof['invited_email'] if 'invited_email' in prof.keys() else None),
        "expires_in_days": 7
    })


@app.route("/join")
@app.route("/invito/<token>")
def join_workspace_invite(token=None):
    if not token:
        token = request.args.get('token', '').strip()
        
    if not token:
        flash("Link di invito non valido o mancante.", "error")
        return redirect(url_for('login'))
        
    inv = get_invitation_by_token(token)
    if not inv:
        return render_template("join_invite.html", error="Link di invito inesistente o non trovato.", token=token)
        
    if inv["status"] != "PENDING":
        return render_template(
            "join_invite.html", 
            error=f"Questo invito non è più valido (Stato: {inv['status']}).", 
            token=token, 
            invitation=inv
        )
        
    # Check if current user is already logged in
    logged_in_user = None
    if session.get('user_id'):
        conn = get_db_connection()
        logged_in_user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        conn.close()
        
    return render_template(
        "join_invite.html",
        invitation=inv,
        token=token,
        logged_in_user=logged_in_user
    )


@app.route("/join/accept", methods=["POST"])
def join_accept_invitation():
    token = request.form.get("token", "").strip()
    mode = request.form.get("mode", "register").strip() # 'register', 'login', or 'current_user'
    
    if not token:
        flash("Token di invito non valido.", "error")
        return redirect(url_for('login'))
        
    inv = get_invitation_by_token(token)
    if not inv or inv["status"] != "PENDING":
        flash("Invito non valido o scaduto.", "error")
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    target_user_id = None
    
    if mode == "current_user":
        # Logged-in user accepts directly
        if not session.get('user_id'):
            conn.close()
            flash("Devi effettuare l'accesso per accettare l'invito.", "error")
            return redirect(url_for('join_workspace_invite', token=token))
        target_user_id = session['user_id']
        
    elif mode == "login":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not check_password_hash(user['password_hash'], password):
            conn.close()
            flash("Email o password errati per l'account esistente.", "error")
            return redirect(url_for('join_workspace_invite', token=token, mode='login'))
            
        target_user_id = user['id']
        # Setup session for logged in user
        session['user_id'] = user['id']
        session['user_email'] = user['email']
        session['user_name'] = user['full_name']
        session['role'] = user['role']
        session['subscription_plan'] = user['subscription_plan'] or 'FREE'
        
    elif mode == "register":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        if not full_name or not email or not password:
            conn.close()
            flash("Tutti i campi (Nome, Email, Password) sono obbligatori.", "error")
            return redirect(url_for('join_workspace_invite', token=token))
            
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash("Questa email è già registrata! Effettua il login per collegarti all'invito.", "warning")
            return redirect(url_for('join_workspace_invite', token=token, mode='login', prefill_email=email))
            
        pwd_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (email, password_hash, full_name, role, assistant_persona)
            VALUES (?, ?, ?, 'USER', 'demetrio')
        ''', (email, pwd_hash, full_name))
        
        target_user_id = cursor.lastrowid
        conn.commit()
        
        # Setup session
        session['user_id'] = target_user_id
        session['user_email'] = email
        session['user_name'] = full_name
        session['role'] = 'USER'
        session['assistant_persona'] = 'demetrio'
        session['subscription_plan'] = 'FREE'
        
    conn.close()
    
    if not target_user_id:
        flash("Impossibile associare l'account.", "error")
        return redirect(url_for('join_workspace_invite', token=token))
        
    # Accept and bind invitation
    ok, msg, ws_id, prof_id = accept_invitation(token, target_user_id)
    if not ok:
        flash(msg, "error")
        return redirect(url_for('dashboard'))
        
    # Set active workspace & profile in session
    session['workspace_id'] = ws_id
    session['profile_filter'] = str(prof_id)
    
    flash(f"🎉 Benvenuta/o nel nucleo familiare! Il tuo profilo '{inv['profile_name']}' è stato collegato con successo.", "success")
    if mode == "register":
        return redirect(url_for('welcome_assistant'))
    return redirect(url_for('dashboard'))



# ---------------------------------------------------------
# CASH FLOW & FIXED COSTS ENGINE
# ---------------------------------------------------------
@app.route("/cashflow")
@login_required
def cashflow():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    user_id = session.get('user_id')
    ctx = get_workspace_privacy_context(conn, ws_id, user_id)
    
    user = ctx["user"]
    ws = ctx["ws"]
    sharing_mode = ctx["sharing_mode"]
    is_admin = ctx["is_admin"]
    my_profile = ctx["my_profile"]
    visible_profiles = ctx["visible_profiles"]
    active_filter = ctx["active_filter"]
    p_id_filter = ctx["p_id_filter"]
    
    req_month = request.args.get('m', '').strip()
    cashflow_data = get_monthly_cashflow_data(ws_id, p_id_filter, req_month if req_month else None)
    advisor_insights = get_macro_advisor_insights(ws_id, p_id_filter)

    # Custom Salary & Target Savings
    custom_salary = request.args.get('salary') or session.get('custom_salary')
    if custom_salary:
        try:
            custom_salary = float(str(custom_salary).replace(',', '.'))
        except (ValueError, TypeError):
            custom_salary = None

    custom_target = request.args.get('target') or session.get('custom_target')
    if custom_target:
        try:
            custom_target = float(str(custom_target).replace(',', '.'))
        except (ValueError, TypeError):
            custom_target = None

    p_name = "Tutta la Famiglia"
    if p_id_filter:
        p_row = conn.execute("SELECT name FROM profiles WHERE id = ?", (p_id_filter,)).fetchone()
        if p_row:
            p_name = p_row['name']
    elif user and user['full_name']:
        p_name = user['full_name'].split()[0]

    monthly_forecast = get_monthly_forecast_and_considerations(
        cashflow_data,
        custom_salary=custom_salary,
        custom_target=custom_target,
        profile_name=p_name
    )
    
    conn.close()
    return render_template(
        "cashflow.html",
        user=user,
        active_workspace=ws,
        profiles=visible_profiles,
        all_profiles=ctx["all_profiles"],
        active_filter=active_filter,
        is_admin=is_admin,
        current_mode=sharing_mode,
        data=cashflow_data,
        advisor_insights=advisor_insights,
        monthly_forecast=monthly_forecast,
        macro_categories=MACRO_CATEGORIES,
        category_smart_tags=CATEGORY_SMART_TAGS
    )

@app.route("/cashflow/settings/save", methods=["POST"])
@login_required
def save_cashflow_settings():
    salary_str = request.form.get("salary", "").replace(",", ".").strip()
    target_str = request.form.get("target_savings", "").replace(",", ".").strip()
    if salary_str:
        try:
            session['custom_salary'] = float(salary_str)
        except (ValueError, TypeError):
            pass
    if target_str:
        try:
            session['custom_target'] = float(target_str)
        except (ValueError, TypeError):
            pass
    
    flash("Parametri di previsione aggiornati con successo!", "success")
    ref = request.referrer
    if ref and '/login' not in ref:
        return redirect(ref)
    return redirect(url_for('cashflow'))

@app.route("/fixed-costs/add", methods=["POST"])
@login_required
def add_fixed_cost():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('cashflow'))
        
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "Casa & Utenze").strip()
    amount_str = request.form.get("expected_amount", "0").replace(",", ".").strip()
    due_day_str = request.form.get("due_day", "1").strip()
    frequency = request.form.get("frequency", "MONTHLY").strip()
    pattern = request.form.get("match_pattern", "").strip()
    is_income = 1 if request.form.get("is_income") == "1" else 0
    
    active_months = None
    if frequency == 'BIMONTHLY_EVEN':
        active_months = '2,4,6,8,10,12'
    elif frequency == 'BIMONTHLY_ODD':
        active_months = '1,3,5,7,9,11'
    elif frequency == 'QUARTERLY':
        active_months = '3,6,9,12'
        
    try:
        expected_amount = float(amount_str)
        due_day = int(due_day_str)
    except ValueError:
        flash("Importo o giorno di scadenza non valido.", "error")
        return redirect(url_for('cashflow'))
        
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO fixed_costs (workspace_id, name, category, expected_amount, due_day, frequency, active_months, match_pattern, is_income, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    ''', (ws_id, name, category, expected_amount, due_day, frequency, active_months, pattern, is_income))
    conn.commit()
    conn.close()
    
    flash(f"Spesa fissa '{name}' aggiunta con successo!", "success")
    return redirect(url_for('cashflow'))

@app.route("/fixed-costs/delete/<int:item_id>", methods=["POST"])
@login_required
def delete_fixed_cost(item_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('cashflow'))
        
    conn = get_db_connection()
    conn.execute("DELETE FROM fixed_costs WHERE id = ? AND workspace_id = ?", (item_id, ws_id))
    conn.commit()
    conn.close()
    
    flash("Spesa fissa rimossa dalle regole.", "success")
    return redirect(url_for('cashflow'))

# ---------------------------------------------------------
# PLANNED DEADLINES & TAXES (TARI, BOLLO, REVISIONE, ETC.)
# ---------------------------------------------------------
@app.route("/deadlines/add", methods=["POST"])
@login_required
def add_planned_deadline():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "Tasse & Finanza").strip()
    amount_str = request.form.get("expected_amount", "0").replace(",", ".").strip()
    year_month = request.form.get("year_month", "").strip()
    due_day_str = request.form.get("due_day", "15").strip()
    pattern = request.form.get("match_pattern", "").strip()
    recurrence = request.form.get("recurrence", "ANNUAL").strip()
    target_type = request.form.get("target_type", "SHARED_50_50").strip()
    p1_paid_str = request.form.get("p1_paid_amount", "0").replace(",", ".").strip()
    p2_paid_str = request.form.get("p2_paid_amount", "0").replace(",", ".").strip()
    notes = request.form.get("notes", "").strip()
    redirect_to = request.form.get("redirect_to", "dashboard").strip()
    custom_months_list = request.form.getlist("custom_months")
    custom_months_str = ",".join(custom_months_list) if custom_months_list else None
    
    if not year_month:
        year_month = datetime.now().strftime("%Y-%m")
        
    try:
        expected_amount = float(amount_str)
        due_day = int(due_day_str)
        p1_paid = float(p1_paid_str) if p1_paid_str else 0.0
        p2_paid = float(p2_paid_str) if p2_paid_str else 0.0
    except ValueError:
        flash("Importo o giorno di scadenza non valido.", "error")
        return redirect(url_for('dashboard') if redirect_to == 'dashboard' else url_for('cashflow', m=year_month))
        
    is_paid = 1 if (p1_paid + p2_paid) >= (expected_amount - 0.05) else 0

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO planned_deadlines (
            workspace_id, name, category, expected_amount, year_month, due_day, 
            match_pattern, recurrence, target_type, p1_paid_amount, p2_paid_amount, is_paid, custom_months, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (ws_id, name, category, expected_amount, year_month, due_day, pattern, recurrence, target_type, p1_paid, p2_paid, is_paid, custom_months_str, notes))
    conn.commit()
    conn.close()
    
    flash(f"🎯 Scadenza '{name}' ({expected_amount:.2f} €) programmata per {year_month}!", "success")
    return redirect(url_for('dashboard') if redirect_to == 'dashboard' else url_for('cashflow', m=year_month))

@app.route("/deadlines/delete/<int:dl_id>", methods=["POST"])
@login_required
def delete_planned_deadline(dl_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    m = request.form.get("m", "")
    redirect_to = request.form.get("redirect_to", "cashflow").strip()
    conn = get_db_connection()
    conn.execute("DELETE FROM planned_deadlines WHERE id = ? AND workspace_id = ?", (dl_id, ws_id))
    conn.commit()
    conn.close()
    
    flash("Scadenza rimossa con successo.", "success")
    if redirect_to == 'dashboard':
        return redirect(url_for('dashboard'))
    return redirect(url_for('cashflow', m=m) if m else url_for('cashflow'))

@app.route("/deadlines/toggle-paid/<int:dl_id>", methods=["POST"])
@login_required
def toggle_paid_deadline(dl_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    m = request.form.get("m", "")
    redirect_to = request.form.get("redirect_to", "cashflow").strip()
    conn = get_db_connection()
    row = conn.execute("SELECT expected_amount, is_paid FROM planned_deadlines WHERE id = ? AND workspace_id = ?", (dl_id, ws_id)).fetchone()
    if row:
        new_status = 0 if row['is_paid'] else 1
        exp_amt = float(row['expected_amount'] or 0.0)
        # If marking as paid, split quota equally between partners if not already set
        if new_status == 1:
            conn.execute("UPDATE planned_deadlines SET is_paid = 1, p1_paid_amount = ?, p2_paid_amount = ? WHERE id = ?", (exp_amt / 2, exp_amt / 2, dl_id))
        else:
            conn.execute("UPDATE planned_deadlines SET is_paid = 0, p1_paid_amount = 0, p2_paid_amount = 0 WHERE id = ?", (dl_id,))
        conn.commit()
    conn.close()
    
    flash("Stato pagamento scadenza aggiornato.", "success")
    if redirect_to == 'dashboard':
        return redirect(url_for('dashboard'))
    return redirect(url_for('cashflow', m=m) if m else url_for('cashflow'))

@app.route("/deadlines/update-quotas/<int:dl_id>", methods=["POST"])
@login_required
def update_deadline_quotas(dl_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "No workspace"}), 400
        
    p1_paid = float(request.form.get("p1_paid", 0.0))
    p2_paid = float(request.form.get("p2_paid", 0.0))
    
    conn = get_db_connection()
    row = conn.execute("SELECT expected_amount FROM planned_deadlines WHERE id = ? AND workspace_id = ?", (dl_id, ws_id)).fetchone()
    if row:
        exp = float(row['expected_amount'] or 0.0)
        is_paid = 1 if (p1_paid + p2_paid) >= (exp - 0.05) else 0
        conn.execute("UPDATE planned_deadlines SET p1_paid_amount = ?, p2_paid_amount = ?, is_paid = ? WHERE id = ?", (p1_paid, p2_paid, is_paid, dl_id))
        conn.commit()
    conn.close()
    
    flash("Quote della scadenza aggiornate.", "success")
    return redirect(request.referrer or url_for('dashboard'))

# ---------------------------------------------------------
# VERTICAL FOCUS & SPECIAL MORTGAGE HUB
# ---------------------------------------------------------
@app.route("/focus")
@login_required
def focus_hub():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    user_id = session.get('user_id')
    ctx = get_workspace_privacy_context(conn, ws_id, user_id)
    
    user = ctx["user"]
    ws = ctx["ws"]
    sharing_mode = ctx["sharing_mode"]
    is_admin = ctx["is_admin"]
    my_profile = ctx["my_profile"]
    visible_profiles = ctx["visible_profiles"]
    active_filter = ctx["active_filter"]
    p_id_filter = ctx["p_id_filter"]
    
    preset = request.args.get('preset', '6M').strip().upper()
    from_ym = request.args.get('from_ym', '').strip()
    to_ym = request.args.get('to_ym', '').strip()
    
    if from_ym and to_ym:
        preset = 'CUSTOM'
        
    # Get active focus categories for workspace
    active_cat_names = get_active_focus_categories(ws_id, p_id_filter)
    
    # Compute analytics for each active category
    categories_data = []
    for c_name in active_cat_names:
        c_data = get_vertical_category_data(ws_id, c_name, preset=preset, from_ym=from_ym, to_ym=to_ym, profile_id=p_id_filter)
        categories_data.append(c_data)
        
    # Mortgage Deep Dive Hub
    mortgage_data = get_mortgage_deep_dive(ws_id, p_id_filter)
    
    # Couple Split & Shared Expenses Engine
    couple_split_data = get_couple_split_analytics(ws_id, preset=preset, from_ym=from_ym, to_ym=to_ym) if ws_id else None
    
    # Available months in DB for manual range selector
    month_rows = conn.execute('''
        SELECT DISTINCT substr(date, 1, 7) as ym 
        FROM transactions 
        WHERE workspace_id = ? 
        ORDER BY ym DESC
    ''', (ws_id,)).fetchall()
    raw_months = [r['ym'] for r in month_rows if r['ym']]
    if not raw_months:
        raw_months = [datetime.now().strftime("%Y-%m")]
        
    available_months = []
    for ym_val in raw_months:
        try:
            y, m = ym_val.split('-')
            m_name = MONTH_NAMES_IT.get(int(m), m)
            label = f"{m_name} {y}"
        except Exception:
            label = ym_val
        available_months.append({'ym': ym_val, 'label': label})
        
    active_profile_row = None
    if p_id_filter:
        active_profile_row = next((p for p in visible_profiles if p['id'] == p_id_filter), None)
    elif visible_profiles:
        active_profile_row = visible_profiles[0]

    persona_key = session.get('assistant_persona') or (active_profile_row['assistant_persona'] if active_profile_row and 'assistant_persona' in active_profile_row.keys() and active_profile_row['assistant_persona'] else None) or (user['assistant_persona'] if user and 'assistant_persona' in user.keys() and user['assistant_persona'] else 'demetrio')
    persona = get_persona(persona_key)
    
    conn.close()
    
    return render_template(
        "focus.html",
        user=user,
        active_workspace=ws,
        profiles=visible_profiles,
        all_profiles=ctx["all_profiles"],
        active_filter=active_filter,
        is_admin=is_admin,
        current_mode=sharing_mode,
        active_cat_names=active_cat_names,
        categories_data=categories_data,
        mortgage_data=mortgage_data,
        couple_split_data=couple_split_data,
        all_macro_categories=MACRO_CATEGORIES,
        preset=preset,
        from_ym=from_ym if from_ym else (available_months[-1]['ym'] if available_months else ''),
        to_ym=to_ym if to_ym else (available_months[0]['ym'] if available_months else ''),
        available_months=available_months,
        persona=persona
    )

@app.route("/api/transactions/<int:tx_id>/toggle-shared", methods=["POST"])
@login_required
def api_toggle_transaction_shared(tx_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Workspace non trovato"}), 400
        
    conn = get_db_connection()
    tx = conn.execute("SELECT id, is_shared, amount, description FROM transactions WHERE id = ? AND workspace_id = ?", (tx_id, ws_id)).fetchone()
    if not tx:
        conn.close()
        return jsonify({"success": False, "error": "Transazione non trovata"}), 404
        
    new_state = 0 if tx['is_shared'] == 1 else 1
    conn.execute("UPDATE transactions SET is_shared = ? WHERE id = ?", (new_state, tx_id))
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "status": "ok",
        "tx_id": tx_id,
        "is_shared": new_state,
        "message": "Spesa impostata come Condivisa 🤝" if new_state == 1 else "Spesa impostata come Personale 👤"
    })

@app.route("/api/couple-split/data")
@login_required
def api_couple_split_data():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Workspace non trovato"}), 400
        
    preset = request.args.get('preset', 'THIS_MONTH').strip().upper()
    from_ym = request.args.get('from_ym', '').strip() or None
    to_ym = request.args.get('to_ym', '').strip() or None
    split_ratio_str = request.args.get('split_ratio', '0.5').strip()
    try:
        split_ratio = float(split_ratio_str)
    except Exception:
        split_ratio = 0.5
        
    data = get_couple_split_analytics(ws_id, preset=preset, from_ym=from_ym, to_ym=to_ym, split_ratio=split_ratio)
    return jsonify({"success": True, "data": data})

@app.route("/api/couple-split/category-transactions")
@login_required
def api_couple_category_transactions():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Workspace non trovato"}), 400
        
    category = request.args.get('category', '').strip()
    if not category:
        return jsonify({"success": False, "error": "Categoria non specificata"}), 400
        
    preset = request.args.get('preset', 'THIS_MONTH').strip().upper()
    from_ym = request.args.get('from_ym', '').strip() or None
    to_ym = request.args.get('to_ym', '').strip() or None
    
    data = get_couple_category_transactions(ws_id, category=category, preset=preset, from_ym=from_ym, to_ym=to_ym)
    return jsonify({"success": True, "data": data})

@app.route("/api/couple-split/bulk-toggle-shared", methods=["POST"])
@login_required
def api_couple_bulk_toggle_shared():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Workspace non trovato"}), 400
        
    payload = request.get_json() or {}
    category = payload.get('category', '').strip()
    target_state = int(payload.get('target_state', 1))
    preset = payload.get('preset', 'THIS_MONTH').strip().upper()
    from_ym = payload.get('from_ym', '').strip() or None
    to_ym = payload.get('to_ym', '').strip() or None
    
    if not category:
        return jsonify({"success": False, "error": "Categoria mancante"}), 400
        
    res = bulk_set_category_shared(ws_id, category=category, target_state=target_state, preset=preset, from_ym=from_ym, to_ym=to_ym)
    return jsonify({"success": True, "status": "ok", "affected": res.get("affected", 0)})

@app.route("/focus/mortgage/save", methods=["POST"])
@login_required
def save_mortgage_settings():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('focus_hub'))
        
    name = request.form.get("name", "Mutuo Prima Casa").strip()
    bank_name = request.form.get("bank_name", "Banca").strip()
    orig_amt_str = request.form.get("original_amount", "200000").replace(",", ".").strip()
    start_date = request.form.get("start_date", "2021-01-01").strip()
    duration_years_str = request.form.get("duration_years", "20").strip()
    interest_type = request.form.get("interest_type", "FIXED").strip()
    rate_str = request.form.get("annual_interest_rate", "3.2").replace(",", ".").strip()
    inst_str = request.form.get("monthly_installment", "1050").replace(",", ".").strip()
    is_primary = 1 if request.form.get("is_primary_residence") == "1" else 0
    notes = request.form.get("notes", "").strip()
    
    try:
        orig_amt = float(orig_amt_str)
        dur_months = int(float(duration_years_str) * 12) if int(duration_years_str) < 50 else int(duration_years_str)
        rate = float(rate_str)
        inst = float(inst_str)
    except (ValueError, TypeError):
        flash("Valori numerici del mutuo non validi. Riprova.", "error")
        return redirect(url_for('focus_hub'))
        
    conn = get_db_connection()
    existing = conn.execute("SELECT id FROM mortgage_profiles WHERE workspace_id = ? LIMIT 1", (ws_id,)).fetchone()
    if existing:
        conn.execute("""
            UPDATE mortgage_profiles SET
                name = ?, bank_name = ?, original_amount = ?, start_date = ?,
                duration_months = ?, interest_type = ?, annual_interest_rate = ?,
                monthly_installment = ?, is_primary_residence = ?, notes = ?
            WHERE id = ?
        """, (name, bank_name, orig_amt, start_date, dur_months, interest_type, rate, inst, is_primary, notes, existing['id']))
    else:
        conn.execute("""
            INSERT INTO mortgage_profiles (
                workspace_id, name, bank_name, original_amount, start_date,
                duration_months, interest_type, annual_interest_rate,
                monthly_installment, is_primary_residence, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ws_id, name, bank_name, orig_amt, start_date, dur_months, interest_type, rate, inst, is_primary, notes))
        
    conn.commit()
    conn.close()
    
    flash("Parametri contrattuali e piano di ammortamento del mutuo aggiornati con successo!", "success")
    return redirect(url_for('focus_hub'))

@app.route("/focus/categories/toggle", methods=["POST"])
@login_required
def toggle_focus_cat_route():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('focus_hub'))
        
    cat_name = request.form.get("category_name", "").strip()
    action = request.form.get("action", "add") # 'add' or 'remove'
    
    if cat_name in MACRO_CATEGORIES:
        toggle_focus_category(ws_id, cat_name, is_active=(action == 'add'))
        if action == 'add':
            flash(f"Categoria '{cat_name}' aggiunta al tuo Focus Hub!", "success")
        else:
            flash(f"Categoria '{cat_name}' rimossa dalla vista.", "info")
            
    return redirect(url_for('focus_hub'))

@app.route("/api/focus/category-data", methods=["GET"])
@login_required
def api_focus_category_data():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "No active workspace"}), 400
        
    cat_name = request.args.get('category_name', '').strip()
    preset = request.args.get('preset', '6M').strip().upper()
    from_ym = request.args.get('from_ym', '').strip()
    to_ym = request.args.get('to_ym', '').strip()
    
    active_filter = session.get('profile_filter', 'all')
    p_id_filter = int(active_filter) if active_filter != 'all' else None
    
    if from_ym and to_ym:
        preset = 'CUSTOM'
        
    c_data = get_vertical_category_data(ws_id, cat_name, preset=preset, from_ym=from_ym, to_ym=to_ym, profile_id=p_id_filter)
    return jsonify({"success": True, "data": c_data})



@app.route("/workspace/settings/sharing", methods=["POST"])
@login_required
def update_workspace_sharing():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    mem = conn.execute("SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?", (ws_id, session['user_id'])).fetchone()
    is_admin = bool((mem and mem['role'] in ['OWNER', 'ADMIN']) or session.get('role') == 'SUPER_ADMIN')
    if not is_admin:
        conn.close()
        flash("Solo l'amministratore / capofamiglia può modificare la privacy del nucleo.", "error")
        return redirect(url_for('dashboard'))

    sharing_mode = request.form.get("sharing_mode", "FULL").strip()
    if sharing_mode not in ['FULL', 'HYBRID', 'ADMIN_ONLY']:
        sharing_mode = 'FULL'
        
    conn.execute("UPDATE workspaces SET sharing_mode = ? WHERE id = ?", (sharing_mode, ws_id))
    conn.commit()
    conn.close()
    
    labels = {
        'FULL': 'Trasparenza Totale (Patrimonio Unito)',
        'HYBRID': 'Ibrida (Spese Comuni + Privacy Personale)',
        'ADMIN_ONLY': 'Capofamiglia Gestore'
    }
    flash(f"Impostazioni di condivisione aggiornate a: {labels.get(sharing_mode)}!", "success")
    return redirect(url_for('dashboard'))

@app.route("/workspace/filter/<filter_val>")
@login_required
def set_profile_filter(filter_val):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    user_id = session.get('user_id')
    ctx = get_workspace_privacy_context(conn, ws_id, user_id)
    
    # If not admin and mode is HYBRID or ADMIN_ONLY, strictly lock to own profile
    if not ctx["is_admin"] and ctx["sharing_mode"] in ['ADMIN_ONLY', 'HYBRID']:
        if ctx["my_profile"]:
            session['profile_filter'] = str(ctx["my_profile"]['id'])
        conn.close()
        return redirect(request.referrer or url_for('dashboard'))
        
    conn.close()
    session['profile_filter'] = filter_val
    return redirect(request.referrer or url_for('dashboard'))

# ---------------------------------------------------------
# ACCOUNTS & CARDS MANAGEMENT (WIZARD & CRUD)
# ---------------------------------------------------------
@app.route("/accounts/wizard")
@login_required
def account_wizard():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    user_id = session.get('user_id')
    ctx = get_workspace_privacy_context(conn, ws_id, user_id)
    
    is_admin = ctx["is_admin"]
    sharing_mode = ctx["sharing_mode"]
    my_profile = ctx["my_profile"]
    visible_profiles = ctx["visible_profiles"]
    
    if not is_admin and sharing_mode in ['ADMIN_ONLY', 'HYBRID'] and my_profile:
        accounts = conn.execute('''
            SELECT a.*, p.name as profile_name 
            FROM accounts a 
            LEFT JOIN profiles p ON a.profile_id = p.id 
            WHERE a.workspace_id = ? AND (a.profile_id = ? OR a.is_shared = 1 OR a.profile_id IS NULL)
            ORDER BY a.id ASC
        ''', (ws_id, my_profile['id'])).fetchall()
    else:
        accounts = conn.execute('''
            SELECT a.*, p.name as profile_name 
            FROM accounts a 
            LEFT JOIN profiles p ON a.profile_id = p.id 
            WHERE a.workspace_id = ? 
            ORDER BY a.id ASC
        ''', (ws_id,)).fetchall()
        
    conn.close()
    
    prefill_type = request.args.get('type', 'CHECKING')
    
    return render_template(
        "account_wizard.html",
        profiles=visible_profiles,
        all_profiles=ctx["all_profiles"],
        is_admin=is_admin,
        current_mode=sharing_mode,
        accounts=accounts,
        bank_themes=BANK_THEMES,
        prefill_type=prefill_type
    )

@app.route("/accounts/wizard/save", methods=["POST"])
@login_required
def account_wizard_save():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    name = request.form.get("name", "").strip()
    acc_type = request.form.get("type", "CHECKING").strip()
    bank_name = request.form.get("bank_name", "").strip()
    iban = request.form.get("iban", "").strip().upper()
    card_pan = request.form.get("card_pan", "").strip()
    holder_name = request.form.get("holder_name", "").strip()
    profile_id = request.form.get("profile_id")
    initial_balance = request.form.get("balance", "0").replace(",", ".").strip()
    
    try:
        balance_float = float(initial_balance)
    except ValueError:
        balance_float = 0.0
        
    p_id_val = int(profile_id) if profile_id and profile_id.isdigit() else None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if not p_id_val:
        prim = cursor.execute("SELECT id FROM profiles WHERE workspace_id = ? AND is_primary = 1", (ws_id,)).fetchone()
        if prim:
            p_id_val = prim[0]
        else:
            first_p = cursor.execute("SELECT id FROM profiles WHERE workspace_id = ? ORDER BY id ASC LIMIT 1", (ws_id,)).fetchone()
            if first_p:
                p_id_val = first_p[0]

    if not name:
        if bank_name:
            type_label = "Conto Corrente" if acc_type == 'CHECKING' else "Carta Prepagata" if acc_type == 'CARD' else "Conto Deposito" if acc_type == 'SAVINGS' else "Portafoglio"
            name = f"{bank_name} - {type_label}"
        else:
            name = "Nuovo Conto / Carta"

    cursor.execute('''
        INSERT INTO accounts (
            workspace_id, profile_id, name, type, balance, currency,
            bank_name, iban, card_pan, holder_name
        )
        VALUES (?, ?, ?, ?, ?, 'EUR', ?, ?, ?, ?)
    ''', (ws_id, p_id_val, name, acc_type, balance_float, bank_name, iban, card_pan, holder_name))
    conn.commit()
    conn.close()
    
    flash(f"✨ {name} configurato e aggiunto con successo!", "success")
    return redirect(url_for('transactions'))

@app.route("/accounts/add", methods=["POST"])
@login_required
def add_account():
    return account_wizard_save()

@app.route("/accounts/edit/<int:account_id>", methods=["POST"])
@login_required
def edit_account(account_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    name = request.form.get("name", "").strip()
    acc_type = request.form.get("type", "CHECKING").strip()
    bank_name = request.form.get("bank_name", "").strip()
    iban = request.form.get("iban", "").strip().upper()
    card_pan = request.form.get("card_pan", "").strip()
    holder_name = request.form.get("holder_name", "").strip()
    profile_id = request.form.get("profile_id")
    is_shared = 1 if request.form.get("is_shared") == "1" else 0
    update_tx_profiles = (request.form.get("update_tx_profiles") == "1")
    
    p_id_val = int(profile_id) if profile_id and profile_id.isdigit() else None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    acc = cursor.execute("SELECT * FROM accounts WHERE id = ? AND workspace_id = ?", (account_id, ws_id)).fetchone()
    if not acc:
        conn.close()
        flash("Conto non trovato.", "error")
        return redirect(url_for('transactions'))
        
    cursor.execute('''
        UPDATE accounts
        SET name = ?, type = ?, bank_name = ?, iban = ?, card_pan = ?,
            holder_name = ?, profile_id = ?, is_shared = ?
        WHERE id = ? AND workspace_id = ?
    ''', (name or acc['name'], acc_type, bank_name, iban, card_pan, holder_name, p_id_val, is_shared, account_id, ws_id))
    
    # Retroactively update profile_id on all transactions of this account if requested
    tx_updated_count = 0
    if update_tx_profiles and p_id_val:
        res = cursor.execute('''
            UPDATE transactions
            SET profile_id = ?
            WHERE account_id = ? AND workspace_id = ?
        ''', (p_id_val, account_id, ws_id))
        tx_updated_count = res.rowcount
        
    conn.commit()
    conn.close()
    
    profile_msg = f" e riassegnati {tx_updated_count} movimenti" if tx_updated_count > 0 else ""
    flash(f"⚙️ Impostazioni del conto '{name or acc['name']}' aggiornate con successo{profile_msg}!", "success")
    return redirect(url_for('transactions'))

@app.route("/accounts/delete/<int:account_id>", methods=["POST"])
@login_required
def delete_account(account_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    acc = conn.execute("SELECT * FROM accounts WHERE id = ? AND workspace_id = ?", (account_id, ws_id)).fetchone()
    if not acc:
        conn.close()
        flash("Conto non trovato.", "error")
        return redirect(url_for('transactions'))
        
    conn.execute("DELETE FROM accounts WHERE id = ? AND workspace_id = ?", (account_id, ws_id))
    conn.commit()
    conn.close()
    
    flash(f"Conto '{acc['name']}' eliminato con successo.", "success")
    return redirect(url_for('transactions'))

# ---------------------------------------------------------
# CATEGORY & AUTO-LEARNING RULES APIS
# ---------------------------------------------------------
@app.route("/api/transactions/<int:tx_id>/categorize", methods=["POST"])
@login_required
def api_update_transaction_category(tx_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Non autorizzato"}), 401
        
    data = request.get_json() or {}
    new_category = data.get("category", "").strip()
    new_subcategory = data.get("sub_category", "").strip()
    new_tags = data.get("tags", "").strip()
    apply_to_similar = bool(data.get("apply_to_similar", False))
    custom_pattern = data.get("custom_pattern", "").strip()
    match_type = data.get("match_type", "CONTAINS").strip()
    
    if not new_category:
        return jsonify({"success": False, "error": "Categoria obbligatoria."}), 400
        
    conn = get_db_connection()
    tx = conn.execute("SELECT * FROM transactions WHERE id = ? AND workspace_id = ?", (tx_id, ws_id)).fetchone()
    if not tx:
        conn.close()
        return jsonify({"success": False, "error": "Transazione non trovata."}), 404
        
    # 1. Update target transaction
    conn.execute('''
        UPDATE transactions
        SET category = ?, sub_category = ?, tags = ?
        WHERE id = ? AND workspace_id = ?
    ''', (new_category, new_subcategory, new_tags, tx_id, ws_id))
    conn.commit()
    conn.close()
    
    updated_count = 1
    pattern_used = ""
    
    # 2. If user opted to apply to all similar and future imports
    if apply_to_similar:
        pattern_used = custom_pattern if custom_pattern else extract_clean_merchant_pattern(tx['description'] or tx['raw_description'])
        if pattern_used:
            save_or_update_category_rule(
                workspace_id=ws_id,
                pattern=pattern_used,
                category=new_category,
                sub_category=new_subcategory,
                tags=new_tags,
                match_type=match_type
            )
            updated_count = apply_rule_retroactively(
                workspace_id=ws_id,
                pattern=pattern_used,
                category=new_category,
                sub_category=new_subcategory,
                tags=new_tags,
                match_type=match_type
            )
            
    return jsonify({
        "success": True,
        "message": f"Categoria aggiornata con successo! (Aggiornati {updated_count} movimenti)",
        "updated_count": updated_count,
        "pattern_saved": pattern_used if apply_to_similar else None,
        "category": new_category,
        "sub_category": new_subcategory,
        "tags": new_tags
    })

@app.route("/settings/rules")
@login_required
def settings_rules():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    rules = conn.execute("SELECT * FROM category_rules WHERE workspace_id = ? ORDER BY id DESC", (ws_id,)).fetchall()
    conn.close()
    
    return render_template(
        "settings_rules.html",
        rules=[dict(r) for r in rules],
        categories=MACRO_CATEGORIES
    )

@app.route("/settings/rules/save", methods=["POST"])
@login_required
def settings_rules_save():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    pattern = request.form.get("pattern", "").strip()
    category = request.form.get("category", "").strip()
    sub_category = request.form.get("sub_category", "").strip()
    tags = request.form.get("tags", "").strip()
    match_type = request.form.get("match_type", "CONTAINS").strip()
    apply_retro = request.form.get("apply_retro") == "1"
    
    if not pattern or not category:
        flash("Pattern e Categoria sono obbligatori.", "error")
        return redirect(url_for('settings_rules'))
        
    save_or_update_category_rule(ws_id, pattern, category, sub_category, tags, match_type)
    
    if apply_retro:
        count = apply_rule_retroactively(ws_id, pattern, category, sub_category, tags, match_type)
        flash(f"Regola per '{pattern}' salvata e applicata retroattivamente a {count} transazioni!", "success")
    else:
        flash(f"Regola per '{pattern}' salvata con successo per i futuri import!", "success")
        
    return redirect(url_for('settings_rules'))

@app.route("/settings/rules/apply-all", methods=["POST"])
@login_required
def settings_rules_apply_all():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
    
    count = apply_all_workspace_rules(ws_id)
    flash(f"⚡ Regole sincronizzate con successo! Aggiornate {count} transazioni.", "success")
    return redirect(url_for('settings_rules'))

@app.route("/settings/rules/delete/<int:rule_id>", methods=["POST"])
@login_required
def settings_rules_delete(rule_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    conn.execute("DELETE FROM category_rules WHERE id = ? AND workspace_id = ?", (rule_id, ws_id))
    conn.commit()
    conn.close()
    
    flash("Regola eliminata con successo.", "success")
    return redirect(url_for('settings_rules'))

# ---------------------------------------------------------
# TRANSACTIONS & EXPENSES LEDGER
# ---------------------------------------------------------
@app.route("/transactions")
@login_required
def transactions():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    user_id = session.get('user_id')
    ctx = get_workspace_privacy_context(conn, ws_id, user_id)
    
    user = ctx["user"]
    ws = ctx["ws"]
    sharing_mode = ctx["sharing_mode"]
    is_admin = ctx["is_admin"]
    my_profile = ctx["my_profile"]
    visible_profiles = ctx["visible_profiles"]
    active_filter = ctx["active_filter"]
    p_id_filter = ctx["p_id_filter"]
    
    # Retrieve accounts for this workspace (filtered by privacy for non-admin)
    if not is_admin and sharing_mode in ['ADMIN_ONLY', 'HYBRID'] and my_profile:
        accounts = conn.execute('''
            SELECT a.*, p.name as profile_name 
            FROM accounts a 
            LEFT JOIN profiles p ON a.profile_id = p.id 
            WHERE a.workspace_id = ? AND (a.profile_id = ? OR a.is_shared = 1 OR a.profile_id IS NULL)
            ORDER BY a.id ASC
        ''', (ws_id, my_profile['id'])).fetchall()
    else:
        accounts = conn.execute('''
            SELECT a.*, p.name as profile_name 
            FROM accounts a 
            LEFT JOIN profiles p ON a.profile_id = p.id 
            WHERE a.workspace_id = ? 
            ORDER BY a.id ASC
        ''', (ws_id,)).fetchall()
    
    # Active filters
    month_arg = request.args.get('month')
    selected_category = request.args.get('category', '').strip()
    search_query = request.args.get('q', '').strip().lower()
    selected_tag = request.args.get('tag', '').strip()
    selected_account_id = request.args.get('account_id', '').strip()
    status_filter = request.args.get('status', '').strip()
    
    # Calculate status counts for the current profile scope
    base_count_sql = "SELECT COUNT(*) FROM transactions t LEFT JOIN accounts a ON t.account_id = a.id WHERE t.workspace_id = ?"
    base_count_params = [ws_id]
    
    if not is_admin and sharing_mode in ['ADMIN_ONLY', 'HYBRID'] and my_profile:
        if sharing_mode == 'HYBRID':
            base_count_sql += " AND (t.profile_id = ? OR t.is_shared = 1 OR a.is_shared = 1)"
            base_count_params.append(my_profile['id'])
        else:
            base_count_sql += " AND t.profile_id = ?"
            base_count_params.append(my_profile['id'])
    elif active_filter != 'all':
        try:
            base_count_sql += " AND t.profile_id = ?"
            base_count_params.append(int(active_filter))
        except (ValueError, TypeError):
            pass

    total_tx_count = conn.execute(base_count_sql, base_count_params).fetchone()[0]
    untagged_count = conn.execute(base_count_sql + " AND (t.tags IS NULL OR trim(t.tags) = '')", base_count_params).fetchone()[0]
    uncategorized_count = conn.execute(base_count_sql + " AND (t.category IS NULL OR trim(t.category) = '' OR t.category = 'Altro')", base_count_params).fetchone()[0]
    tax_730_count = conn.execute(base_count_sql + " AND t.tags LIKE '%#detraibile_730%'", base_count_params).fetchone()[0]

    # Calculate available months list with status indicators (uncat/untagged counts)
    month_query = '''
        SELECT 
            strftime('%Y-%m', t.date) as ym,
            COUNT(*) as tx_count,
            SUM(CASE WHEN t.category IS NULL OR trim(t.category) = '' OR t.category = 'Altro' THEN 1 ELSE 0 END) as uncat_count,
            SUM(CASE WHEN t.tags IS NULL OR trim(t.tags) = '' THEN 1 ELSE 0 END) as untagged_count,
            SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END) as income,
            SUM(CASE WHEN t.amount < 0 THEN abs(t.amount) ELSE 0 END) as expenses
        FROM transactions t
        LEFT JOIN accounts a ON t.account_id = a.id
        WHERE t.workspace_id = ?
    '''
    m_params = [ws_id]
    if not is_admin and sharing_mode in ['ADMIN_ONLY', 'HYBRID'] and my_profile:
        if sharing_mode == 'HYBRID':
            month_query += " AND (t.profile_id = ? OR t.is_shared = 1 OR a.is_shared = 1)"
            m_params.append(my_profile['id'])
        else:
            month_query += " AND t.profile_id = ?"
            m_params.append(my_profile['id'])
    elif active_filter != 'all':
        try:
            m_params.append(int(active_filter))
            month_query += " AND t.profile_id = ?"
        except (ValueError, TypeError):
            pass
    month_query += " GROUP BY ym ORDER BY ym DESC"
    m_rows = conn.execute(month_query, m_params).fetchall()
    
    cur_ym_now = datetime.now().strftime('%Y-%m')
    available_months = []
    for mr in m_rows:
        ym = mr['ym']
        if not ym or len(ym) < 7:
            continue
        try:
            y_i, m_i = int(ym.split('-')[0]), int(ym.split('-')[1])
            m_name_short = f"{MONTH_NAMES_IT_SHORT.get(m_i, '')} '{str(y_i)[2:]}"
            m_name_full = f"{MONTH_NAMES_IT.get(m_i, '')} {y_i}"
        except:
            m_name_short = ym
            m_name_full = ym
            
        available_months.append({
            "ym": ym,
            "name_short": m_name_short,
            "name_full": m_name_full,
            "is_current_month": (ym == cur_ym_now),
            "tx_count": mr['tx_count'],
            "uncat_count": mr['uncat_count'] or 0,
            "untagged_count": mr['untagged_count'] or 0,
            "income": round(mr['income'] or 0.0, 2),
            "expenses": round(mr['expenses'] or 0.0, 2),
            "net_savings": round((mr['income'] or 0.0) - (mr['expenses'] or 0.0), 2)
        })

    # Default to 'all' (Tutti i Mesi) if not explicitly specified
    if not month_arg:
        selected_month = 'all'
    else:
        selected_month = month_arg.strip()

    selected_month_info = None
    if selected_month and selected_month != 'all':
        for m in available_months:
            if m["ym"] == selected_month:
                selected_month_info = m
                break
    elif selected_month == 'all':
        selected_month_info = {
            "ym": "all",
            "name_short": "Tutti i Mesi",
            "name_full": "Tutti i Mesi (Storico Completo)",
            "is_current_month": False,
            "tx_count": total_tx_count,
            "uncat_count": uncategorized_count,
            "untagged_count": untagged_count,
            "income": 0.0,
            "expenses": 0.0,
            "net_savings": 0.0
        }

    query = '''
        SELECT t.*, a.name as account_name, a.type as account_type, p.name as profile_name 
        FROM transactions t
        LEFT JOIN accounts a ON t.account_id = a.id
        LEFT JOIN profiles p ON t.profile_id = p.id
        WHERE t.workspace_id = ?
    '''
    params = [ws_id]
    
    if not is_admin and sharing_mode in ['ADMIN_ONLY', 'HYBRID'] and my_profile:
        if sharing_mode == 'HYBRID':
            query += " AND (t.profile_id = ? OR t.is_shared = 1 OR a.is_shared = 1)"
            params.append(my_profile['id'])
        else:
            query += " AND t.profile_id = ?"
            params.append(my_profile['id'])
    elif active_filter != 'all':
        try:
            p_id = int(active_filter)
            query += " AND t.profile_id = ?"
            params.append(p_id)
        except (ValueError, TypeError):
            pass
            
    if selected_account_id and selected_account_id.isdigit():
        query += " AND t.account_id = ?"
        params.append(int(selected_account_id))
        
    if selected_month and selected_month != 'all':
        query += " AND t.date LIKE ?"
        params.append(f"{selected_month}%")

    if selected_category:
        query += " AND (t.category = ? OR t.category LIKE ? OR t.category LIKE ?)"
        params.extend([selected_category, f"{selected_category}%", f"%{selected_category}%"])
        
    if search_query:
        query += " AND (LOWER(t.description) LIKE ? OR LOWER(t.raw_description) LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])
        
    if selected_tag:
        query += " AND t.tags LIKE ?"
        params.append(f"%{selected_tag}%")

    if status_filter == 'review':
        query += " AND ((t.category IS NULL OR trim(t.category) = '' OR t.category = 'Altro') OR (t.tags IS NULL OR trim(t.tags) = ''))"
    elif status_filter == 'uncategorized':
        query += " AND (t.category IS NULL OR trim(t.category) = '' OR t.category = 'Altro')"
    elif status_filter == 'untagged':
        query += " AND (t.tags IS NULL OR trim(t.tags) = '')"
    elif status_filter == 'tax_730':
        query += " AND t.tags LIKE '%#detraibile_730%'"
    elif status_filter == 'tagged':
        query += " AND (t.tags IS NOT NULL AND trim(t.tags) != '')"

        
    query += " ORDER BY t.date DESC, t.id DESC LIMIT 300"
    tx_list = [dict(t) for t in conn.execute(query, params).fetchall()]
    
    # Calculate transaction counts per account
    accounts_with_counts = []
    for acc in accounts:
        cnt_row = conn.execute("SELECT COUNT(*) FROM transactions WHERE account_id = ?", (acc['id'],)).fetchone()
        acc_dict = dict(acc)
        acc_dict['tx_count'] = cnt_row[0] if cnt_row else 0
        accounts_with_counts.append(acc_dict)
    
    # Summary Metrics for the filtered view
    total_income = 0.0
    total_expenses = 0.0
    health_730_total = 0.0
    category_totals = {}
    
    for tx in tx_list:
        amt = tx['amount']
        cat = tx['category'] or 'Altro'
        tags = tx['tags'] or ''
        
        if amt > 0:
            total_income += amt
        else:
            total_expenses += abs(amt)
            category_totals[cat] = category_totals.get(cat, 0.0) + abs(amt)
            
        if "#detraibile_730" in tags:
            health_730_total += abs(amt)
            
    net_period = total_income - total_expenses

    # Detailed Category Breakdown with percentages and icons
    category_breakdown = []
    for cat_name, cat_meta in MACRO_CATEGORIES.items():
        spent = category_totals.get(cat_name, 0.0)
        pct = round((spent / total_expenses * 100), 1) if total_expenses > 0 else 0.0
        cnt = sum(1 for tx in tx_list if (tx['category'] == cat_name or (tx['category'] and tx['category'].startswith(cat_name))))
        category_breakdown.append({
            "name": cat_name,
            "icon": cat_meta.get("icon", "📦"),
            "color": cat_meta.get("color", "#64748b"),
            "spent": spent,
            "percent": pct,
            "tx_count": cnt
        })
    category_breakdown.sort(key=lambda x: x["spent"], reverse=True)
            
    # Filter accounts by active member if selected
    if active_filter != 'all':
        try:
            f_pid = int(active_filter)
            display_accounts = [a for a in accounts_with_counts if a.get('profile_id') == f_pid]
        except (ValueError, TypeError):
            display_accounts = accounts_with_counts
    else:
        display_accounts = accounts_with_counts

    # Calculate Bank Groups for accounts
    bank_groups = {}
    for acc in display_accounts:
        b_name = acc['bank_name'] or 'Altro Istituto'
        group_key = b_name
        if "poste" in b_name.lower():
            group_key = "Poste Italiane"
        elif "bper" in b_name.lower():
            group_key = "BPER Banca"
        elif "bcc" in b_name.lower() or "credito cooperativo" in b_name.lower():
            group_key = "BCC - Credito Cooperativo"
            
        if group_key not in bank_groups:
            theme = get_bank_theme(group_key)
            bank_groups[group_key] = {
                "name": group_key,
                "icon": theme["icon"],
                "color": theme["color"],
                "badge_bg": theme["badge_bg"],
                "total_balance": 0.0,
                "tx_count": 0,
                "accounts": []
            }
        bank_groups[group_key]["total_balance"] += acc['balance']
        bank_groups[group_key]["tx_count"] += acc.get('tx_count', 0)
        bank_groups[group_key]["accounts"].append(acc)
        
    total_account_balance = sum(acc['balance'] for acc in display_accounts)
    bank_groups_list = list(bank_groups.values())
    for bg in bank_groups_list:
        bg["percent"] = round((bg["total_balance"] / total_account_balance * 100), 1) if total_account_balance > 0 else 0.0

    # Calculate Merchant Frequency Groups & Triage Completion Stats
    merchant_groups = aggregate_transactions_by_merchant(tx_list)
    category_folders = group_transactions_by_category(tx_list, MACRO_CATEGORIES)
    pending_groups = [g for g in merchant_groups if not g.get('is_homogeneous') or g.get('is_unassigned')]
    completed_groups = [g for g in merchant_groups if g.get('is_homogeneous') and not g.get('is_unassigned')]
    triage_stats = {
        'total_count': len(merchant_groups),
        'pending_count': len(pending_groups),
        'completed_count': len(completed_groups),
        'percent': round(len(completed_groups) / len(merchant_groups) * 100) if merchant_groups else 100
    }
    
    uncategorized_txs = [
        {
            "id": tx["id"],
            "date": tx["date"],
            "amount": tx["amount"],
            "description": tx["description"] or tx.get("raw_description") or "Movimento Bancario",
            "account_name": tx["account_name"] or "Conto Corrente",
            "profile_name": tx["profile_name"] or ""
        }
        for tx in tx_list
        if not tx["category"] or tx["category"] == "Altro"
    ]
    
    return render_template(
        "transactions.html",
        transactions=tx_list,
        uncategorized_txs=uncategorized_txs,
        merchant_groups=merchant_groups,
        category_folders=category_folders,
        triage_stats=triage_stats,
        accounts=display_accounts,
        all_accounts=accounts_with_counts,
        bank_groups=bank_groups_list,
        total_account_balance=total_account_balance,
        profiles=[dict(p) for p in visible_profiles],
        all_profiles=ctx["all_profiles"],
        is_admin=is_admin,
        current_mode=sharing_mode,
        macro_categories=MACRO_CATEGORIES,
        active_filter=active_filter,
        selected_month=selected_month,
        selected_month_info=selected_month_info,
        available_months=available_months,
        category_breakdown=category_breakdown,
        selected_account_id=selected_account_id,
        selected_category=selected_category,
        search_query=search_query,
        selected_tag=selected_tag,
        status_filter=status_filter,
        total_tx_count=total_tx_count,
        untagged_count=untagged_count,
        uncategorized_count=uncategorized_count,
        tax_730_count=tax_730_count,
        total_income=total_income,
        total_expenses=total_expenses,
        net_period=net_period,
        health_730_total=health_730_total,
        category_totals=category_totals,
        category_smart_tags=CATEGORY_SMART_TAGS
    )

@app.route("/transactions/quick-update", methods=["POST"])
@login_required
def quick_update_transaction():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Sessione non valida"}), 401
        
    data = request.get_json(silent=True) or {}
    tx_id = data.get("tx_id")
    category = data.get("category", "").strip()
    sub_category = data.get("sub_category", "").strip()
    tags = data.get("tags", "").strip()
    learn_rule = data.get("learn_rule", True)
    
    if not tx_id or not category:
        return jsonify({"success": False, "error": "ID o Categoria mancante"}), 400
        
    conn = get_db_connection()
    tx = conn.execute("SELECT * FROM transactions WHERE id = ? AND workspace_id = ?", (tx_id, ws_id)).fetchone()
    if not tx:
        conn.close()
        return jsonify({"success": False, "error": "Movimento non trovato"}), 404
        
    conn.execute('''
        UPDATE transactions 
        SET category = ?, sub_category = ?, tags = ?
        WHERE id = ?
    ''', (category, sub_category, tags, tx_id))
    conn.commit()
    conn.close()
    
    retro_count = 0
    pat = None
    if learn_rule and (tx['description'] or tx['raw_description']):
        pat = extract_clean_merchant_pattern(tx['description'] or tx['raw_description'])
        if pat:
            save_or_update_category_rule(
                workspace_id=ws_id,
                pattern=pat,
                category=category,
                sub_category=sub_category,
                tags=tags,
                match_type='CONTAINS'
            )
            retro_count = apply_rule_retroactively(
                workspace_id=ws_id,
                pattern=pat,
                category=category,
                sub_category=sub_category,
                tags=tags,
                match_type='CONTAINS'
            )
            
    cat_info = MACRO_CATEGORIES.get(category, {"icon": "📦", "color": "#64748b"})
    return jsonify({
        "success": True,
        "tx_id": tx_id,
        "category": category,
        "category_icon": cat_info.get("icon", "📦"),
        "category_color": cat_info.get("color", "#64748b"),
        "sub_category": sub_category,
        "tags": tags,
        "pattern": pat,
        "retro_count": retro_count
    })

@app.route("/transactions/bulk-update", methods=["POST"])
@login_required
def bulk_update_transactions():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Sessione non valida"}), 401
        
    data = request.get_json(silent=True) or {}
    tx_ids = data.get("tx_ids", [])
    category = data.get("category", "").strip()
    sub_category = data.get("sub_category", "").strip()
    tags = data.get("tags", "").strip()
    learn_rule = data.get("learn_rule", True)
    
    if not tx_ids or not category:
        return jsonify({"success": False, "error": "Seleziona almeno un movimento e una categoria"}), 400
        
    conn = get_db_connection()
    updated_count = 0
    patterns_learned = set()
    
    for tid in tx_ids:
        tx = conn.execute("SELECT * FROM transactions WHERE id = ? AND workspace_id = ?", (tid, ws_id)).fetchone()
        if tx:
            conn.execute('''
                UPDATE transactions 
                SET category = ?, sub_category = ?, tags = ?
                WHERE id = ?
            ''', (category, sub_category, tags, tid))
            updated_count += 1
            if learn_rule and (tx['description'] or tx['raw_description']):
                pat = extract_clean_merchant_pattern(tx['description'] or tx['raw_description'])
                if pat:
                    patterns_learned.add(pat)
                    
    conn.commit()
    conn.close()
    
    for pat in patterns_learned:
        save_or_update_category_rule(
            workspace_id=ws_id,
            pattern=pat,
            category=category,
            sub_category=sub_category,
            tags=tags,
            match_type='CONTAINS'
        )
        apply_rule_retroactively(
            workspace_id=ws_id,
            pattern=pat,
            category=category,
            sub_category=sub_category,
            tags=tags,
            match_type='CONTAINS'
        )
        
    return jsonify({
        "success": True,
        "updated_count": updated_count,
        "rules_count": len(patterns_learned)
    })

@app.route("/api/transactions/batch-categorize-merchant", methods=["POST"])
@login_required
def batch_categorize_merchant():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Sessione non valida"}), 401
        
    data = request.get_json(silent=True) or {}
    tx_ids = data.get("tx_ids", [])
    pattern = (data.get("pattern") or "").strip()
    category = (data.get("category") or "").strip()
    sub_category = (data.get("sub_category") or "").strip()
    tags = (data.get("tags") or "").strip()
    save_rule = data.get("save_rule", True)
    
    if not category:
        return jsonify({"success": False, "error": "Seleziona una categoria valida"}), 400
        
    conn = get_db_connection()
    updated_count = 0
    
    # 1. Update matching transactions
    if tx_ids and isinstance(tx_ids, list):
        clean_ids = [int(x) for x in tx_ids if str(x).isdigit()]
        if clean_ids:
            placeholders = ','.join('?' for _ in clean_ids)
            params = [category, sub_category if sub_category else None]
            if tags:
                params.append(tags)
                sql = f"UPDATE transactions SET category = ?, sub_category = ?, tags = ? WHERE id IN ({placeholders}) AND workspace_id = ?"
            else:
                sql = f"UPDATE transactions SET category = ?, sub_category = ? WHERE id IN ({placeholders}) AND workspace_id = ?"
            params.extend(clean_ids)
            params.append(ws_id)
            cursor = conn.execute(sql, params)
            updated_count = cursor.rowcount
            conn.commit()
    elif pattern:
        params = [category, sub_category if sub_category else None]
        if tags:
            params.append(tags)
            sql = "UPDATE transactions SET category = ?, sub_category = ?, tags = ? WHERE workspace_id = ? AND (LOWER(description) LIKE ? OR LOWER(raw_description) LIKE ?)"
        else:
            sql = "UPDATE transactions SET category = ?, sub_category = ? WHERE workspace_id = ? AND (LOWER(description) LIKE ? OR LOWER(raw_description) LIKE ?)"
        params.append(ws_id)
        params.append(f"%{pattern.lower()}%")
        params.append(f"%{pattern.lower()}%")
        cursor = conn.execute(sql, params)
        updated_count = cursor.rowcount
        conn.commit()
        
    conn.close()
    
    # 2. Save Rule if requested
    rule_saved = False
    if save_rule and pattern:
        save_or_update_category_rule(
            workspace_id=ws_id,
            pattern=pattern,
            category=category,
            sub_category=sub_category if sub_category else None,
            tags=tags if tags else None,
            match_type='CONTAINS'
        )
        apply_rule_retroactively(
            workspace_id=ws_id,
            pattern=pattern,
            category=category,
            sub_category=sub_category if sub_category else None,
            tags=tags if tags else None,
            match_type='CONTAINS'
        )
        rule_saved = True
        
    return jsonify({
        "success": True,
        "updated_count": updated_count,
        "pattern": pattern,
        "category": category,
        "sub_category": sub_category,
        "rule_saved": rule_saved
    })


@app.route("/api/ai/online-merchant-lookup", methods=["POST"])
@login_required
def api_online_merchant_lookup():
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or data.get("description") or data.get("pattern") or "").strip()
    if not query:
        return jsonify({"success": False, "error": "Descrizione o nome esercente richiesto"}), 400
    
    result = classify_merchant_online(query)
    return jsonify(result)








@app.route("/api/personalization", methods=["GET", "POST"])
@login_required
def api_workspace_personalization():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Workspace non valido."}), 400
        
    if request.method == "GET":
        pers = get_workspace_personalization(ws_id)
        return jsonify({"success": True, "personalization": pers})
        
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    pers = save_workspace_personalization(ws_id, data)
    
    # Generate customized workspace rules
    generated_patterns = seed_personalization_rules(ws_id, pers)
    
    # Optionally apply retroactively
    retro_updated = 0
    if data.get("apply_retroactively") in (1, True, "1", "true", "on"):
        retro_updated = apply_all_workspace_rules(ws_id)
        
    return jsonify({
        "success": True, 
        "personalization": pers,
        "generated_patterns": generated_patterns,
        "retro_updated": retro_updated
    })

@app.route("/api/personalization/apply-retro", methods=["POST"])
@login_required
def api_personalization_apply_retro():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Workspace non valido."}), 400
    
    updated = apply_all_workspace_rules(ws_id)
    return jsonify({"success": True, "updated_count": updated})
@app.route("/transactions/preview-import", methods=["POST"])
@login_required
def preview_import():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Nessun workspace attivo."}), 400
        
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "Nessun file caricato."}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Nome file vuoto."}), 400
        
    file_bytes = file.read()
    
    conn = get_db_connection()
    custom_rules = conn.execute("SELECT * FROM category_rules WHERE workspace_id = ?", (ws_id,)).fetchall()
    custom_rules_list = [dict(r) for r in custom_rules]
    
    result = parse_bank_file(file_bytes, file.filename, ws_id, custom_rules=custom_rules_list)
    if not result.get("success"):
        conn.close()
        return jsonify({"success": False, "error": result.get("error", "Errore durante la lettura del file.")}), 400
        
    meta = result.get("account_meta", {})
    parsed_txs = result.get("transactions", [])
    if not parsed_txs:
        conn.close()
        return jsonify({"success": False, "error": "Nessun movimento valido trovato nel file."}), 400
        
    # Check for existing accounts matching IBAN, account_number, card_pan or bank_name
    matching_acc = None
    if meta.get("iban"):
        matching_acc = conn.execute("SELECT * FROM accounts WHERE workspace_id = ? AND iban = ?", (ws_id, meta["iban"])).fetchone()
    if not matching_acc and meta.get("account_number"):
        matching_acc = conn.execute("SELECT * FROM accounts WHERE workspace_id = ? AND account_number = ?", (ws_id, meta["account_number"])).fetchone()
    if not matching_acc and meta.get("card_pan"):
        matching_acc = conn.execute("SELECT * FROM accounts WHERE workspace_id = ? AND card_pan = ?", (ws_id, meta["card_pan"])).fetchone()
        
    # Calculate preview statistics
    income = sum(t["amount"] for t in parsed_txs if t["amount"] > 0)
    expenses = sum(abs(t["amount"]) for t in parsed_txs if t["amount"] < 0)
    
    # Calculate category distribution for pre-commit visual review
    cat_breakdown = {}
    for t in parsed_txs:
        cat = t.get("category", "Altro")
        if cat not in cat_breakdown:
            cat_info = MACRO_CATEGORIES.get(cat, {"icon": "🏷️", "color": "#64748b"})
            cat_breakdown[cat] = {
                "name": cat,
                "count": 0,
                "total": 0.0,
                "icon": cat_info.get("icon", "🏷️"),
                "color": cat_info.get("color", "#64748b")
            }
        cat_breakdown[cat]["count"] += 1
        cat_breakdown[cat]["total"] = round(cat_breakdown[cat]["total"] + abs(t["amount"]), 2)

    cat_list = sorted(cat_breakdown.values(), key=lambda x: x["count"], reverse=True)

    # Store parsed data in memory cache for confirmation step
    import_token = str(uuid.uuid4())
    IMPORT_CACHE[import_token] = {
        "workspace_id": ws_id,
        "filename": file.filename,
        "account_meta": meta,
        "transactions": parsed_txs
    }
    
    conn.close()
    
    return jsonify({
        "success": True,
        "import_token": import_token,
        "account_meta": meta,
        "matching_account_id": matching_acc["id"] if matching_acc else None,
        "matching_account_name": matching_acc["name"] if matching_acc else None,
        "total_transactions": len(parsed_txs),
        "total_income": round(income, 2),
        "total_expenses": round(expenses, 2),
        "category_breakdown": cat_list,
        "sample_transactions": parsed_txs[:15]
    })

@app.route("/transactions/confirm-import", methods=["POST"])
@login_required
def confirm_import():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Nessun workspace attivo."}), 400
        
    data = request.get_json() or {}
    import_token = data.get("import_token")
    if not import_token or import_token not in IMPORT_CACHE:
        return jsonify({"success": False, "error": "Sessione di importazione scaduta o non valida. Ricarica il file."}), 400
        
    cached_data = IMPORT_CACHE[import_token]
    if cached_data.get("workspace_id") != ws_id:
        return jsonify({"success": False, "error": "Non autorizzato."}), 403
        
    meta = cached_data.get("account_meta", {})
    parsed_txs = cached_data.get("transactions", [])
    
    account_choice = data.get("account_choice", "existing")
    account_id = data.get("account_id")
    sync_balance = data.get("sync_balance", True)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    target_account = None
    
    # 1. Handle New Account Creation
    if account_choice == "new":
        new_name = data.get("new_account_name") or f"{meta.get('bank_name', 'Conto')} ({meta.get('iban', 'Nuovo')[:10]}...)"
        new_type = data.get("new_account_type", meta.get("account_type", "CHECKING"))
        new_profile_id = data.get("new_account_profile_id")
        p_id = None
        if new_profile_id:
            new_profile_id_str = str(new_profile_id).strip()
            if new_profile_id_str.startswith("__NEW_MEMBER__:"):
                new_name_member = new_profile_id_str.replace("__NEW_MEMBER__:", "").strip()
                if new_name_member:
                    cursor.execute('''
                        INSERT INTO profiles (workspace_id, name, role_title, is_primary)
                        VALUES (?, ?, 'Partner / Coniuge', 0)
                    ''', (ws_id, new_name_member))
                    p_id = cursor.lastrowid
                    cursor.execute("UPDATE workspaces SET type = 'FAMILY' WHERE id = ?", (ws_id,))
        if not p_id:
            prim = cursor.execute("SELECT id FROM profiles WHERE workspace_id = ? AND is_primary = 1", (ws_id,)).fetchone()
            if prim:
                p_id = prim[0]
            else:
                first_p = cursor.execute("SELECT id FROM profiles WHERE workspace_id = ? ORDER BY id ASC LIMIT 1", (ws_id,)).fetchone()
                if first_p:
                    p_id = first_p[0]

        initial_bal = 0.0
        if meta.get("extracted_balance") is not None:
            initial_bal = meta["extracted_balance"]
            
        cursor.execute('''
            INSERT INTO accounts (
                workspace_id, profile_id, name, type, balance, currency, 
                bank_name, iban, account_number, card_pan, holder_name
            ) VALUES (?, ?, ?, ?, ?, 'EUR', ?, ?, ?, ?, ?)
        ''', (
            ws_id, p_id, new_name, new_type, initial_bal,
            meta.get("bank_name"), meta.get("iban"), meta.get("account_number"),
            meta.get("card_pan"), meta.get("holder_name")
        ))
        account_id = cursor.lastrowid
        target_account = {"id": account_id, "name": new_name, "profile_id": p_id}
    else:
        # Existing Account
        if not account_id:
            conn.close()
            return jsonify({"success": False, "error": "Seleziona un conto di destinazione."}), 400
        target_account = conn.execute("SELECT * FROM accounts WHERE id = ? AND workspace_id = ?", (account_id, ws_id)).fetchone()
        if not target_account:
            conn.close()
            return jsonify({"success": False, "error": "Conto selezionato non trovato."}), 400
            
        # Update account with IBAN/Bank metadata if not already filled
        if meta.get("iban") and not target_account["iban"]:
            cursor.execute("UPDATE accounts SET iban = ? WHERE id = ?", (meta["iban"], account_id))
        if meta.get("bank_name") and not target_account["bank_name"]:
            cursor.execute("UPDATE accounts SET bank_name = ? WHERE id = ?", (meta["bank_name"], account_id))
        if meta.get("holder_name") and not target_account["holder_name"]:
            cursor.execute("UPDATE accounts SET holder_name = ? WHERE id = ?", (meta["holder_name"], account_id))

    profile_id = target_account["profile_id"] if target_account else None
    
    # 2. Apply any Category, Subcategory, and Tag Overrides from Step 3
    category_overrides = data.get("category_overrides", {}) # e.g. {"0": "Auto & Trasporti"}
    subcategory_overrides = data.get("subcategory_overrides", {}) # e.g. {"0": "Carburante & Ricarica"}
    tag_overrides = data.get("tag_overrides", {}) # e.g. {"0": "#carburante"}
    learn_overrides = data.get("learn_overrides", True)
    
    for idx_str, new_cat in category_overrides.items():
        try:
            idx = int(idx_str)
            if 0 <= idx < len(parsed_txs) and new_cat:
                parsed_txs[idx]["category"] = new_cat
                if str(idx) in subcategory_overrides:
                    parsed_txs[idx]["sub_category"] = subcategory_overrides[str(idx)]
                if str(idx) in tag_overrides:
                    parsed_txs[idx]["tags"] = tag_overrides[str(idx)]
                    
                # Auto-learn rule if requested
                if learn_overrides:
                    pat = extract_clean_merchant_pattern(parsed_txs[idx]["description"] or parsed_txs[idx]["raw_description"])
                    if pat:
                        save_or_update_category_rule(
                            workspace_id=ws_id,
                            pattern=pat,
                            category=new_cat,
                            sub_category=parsed_txs[idx].get("sub_category", ""),
                            tags=parsed_txs[idx].get("tags", "")
                        )
        except Exception:
            pass

    # 3. Insert Transactions with Deduplication
    existing_hashes = set(row[0] for row in conn.execute(
        "SELECT import_hash FROM transactions WHERE workspace_id = ? AND import_hash IS NOT NULL", 
        (ws_id,)
    ).fetchall())
    
    new_count = 0
    skipped_count = 0
    total_delta = 0.0
    
    for tx in parsed_txs:
        h = tx["import_hash"]
        if h in existing_hashes:
            skipped_count += 1
            continue
            
        cursor.execute('''
            INSERT INTO transactions (
                workspace_id, profile_id, account_id, date, amount, category, 
                sub_category, description, raw_description, is_transfer, tags, import_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ws_id, profile_id, account_id, tx['date'], tx['amount'], tx['category'],
            tx['sub_category'], tx['description'], tx['raw_description'], tx['is_transfer'],
            tx['tags'], tx['import_hash']
        ))
        existing_hashes.add(h)
        new_count += 1
        total_delta += tx['amount']
        
    # 3. Synchronize Account Balance
    if sync_balance and meta.get("extracted_balance") is not None:
        cursor.execute("UPDATE accounts SET balance = ? WHERE id = ?", (meta["extracted_balance"], account_id))
    else:
        cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (total_delta, account_id))
        
    conn.commit()
    conn.close()
    
    # Clear cache
    del IMPORT_CACHE[import_token]
    
    flash(f"✅ Importazione completata su '{target_account['name']}': {new_count} nuovi movimenti registrati ({skipped_count} duplicati ignorati).", "success")
    return jsonify({
        "success": True,
        "imported_count": new_count,
        "skipped_count": skipped_count,
        "redirect_url": url_for("transactions")
    })

# ---------------------------------------------------------
# DRAG & DROP BANK IMPORTER (DIRECT FALLBACK)
# ---------------------------------------------------------
@app.route("/transactions/import", methods=["POST"])
@login_required
def import_transactions():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    if 'file' not in request.files:
        flash("Nessun file selezionato per l'importazione.", "error")
        return redirect(url_for('transactions'))
        
    file = request.files['file']
    if file.filename == '':
        flash("Nessun file selezionato.", "error")
        return redirect(url_for('transactions'))
        
    account_id_raw = request.form.get("account_id")
    if not account_id_raw or not account_id_raw.isdigit():
        flash("Seleziona il conto corrente o la carta su cui importare i movimenti.", "error")
        return redirect(url_for('transactions'))
        
    account_id = int(account_id_raw)
    
    conn = get_db_connection()
    acc = conn.execute("SELECT * FROM accounts WHERE id = ? AND workspace_id = ?", (account_id, ws_id)).fetchone()
    if not acc:
        conn.close()
        flash("Conto non valido o inesistente.", "error")
        return redirect(url_for('transactions'))
        
    profile_id = acc['profile_id']
    custom_rules = conn.execute("SELECT * FROM category_rules WHERE workspace_id = ?", (ws_id,)).fetchall()
    custom_rules_list = [dict(r) for r in custom_rules]
    
    file_bytes = file.read()
    result = parse_bank_file(file_bytes, file.filename, ws_id, account_id, custom_rules=custom_rules_list)
    
    if not result.get("success"):
        conn.close()
        flash(f"Errore durante l'importazione: {result.get('error')}", "error")
        return redirect(url_for('transactions'))
        
    parsed_txs = result.get("transactions", [])
    if not parsed_txs:
        conn.close()
        flash("Nessun movimento valido trovato nel file.", "error")
        return redirect(url_for('transactions'))
        
    existing_hashes = set(row[0] for row in conn.execute(
        "SELECT import_hash FROM transactions WHERE workspace_id = ? AND import_hash IS NOT NULL", 
        (ws_id,)
    ).fetchall())
    
    new_count = 0
    skipped_count = 0
    total_delta = 0.0
    cursor = conn.cursor()
    
    for tx in parsed_txs:
        h = tx['import_hash']
        if h in existing_hashes:
            skipped_count += 1
            continue
            
        cursor.execute('''
            INSERT INTO transactions (
                workspace_id, profile_id, account_id, date, amount, category, 
                sub_category, description, raw_description, is_transfer, tags, import_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ws_id, profile_id, account_id, tx['date'], tx['amount'], tx['category'],
            tx['sub_category'], tx['description'], tx['raw_description'], tx['is_transfer'],
            tx['tags'], tx['import_hash']
        ))
        
        existing_hashes.add(h)
        new_count += 1
        total_delta += tx['amount']
        
    cursor.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (total_delta, account_id))
    conn.commit()
    conn.close()
    
    if new_count > 0:
        flash(f"✅ Importazione completata! Aggiunti {new_count} nuovi movimenti su '{acc['name']}' ({skipped_count} duplicati già presenti ignorati).", "success")
    else:
        flash(f"ℹ️ Nessun nuovo movimento da importare: tutti i {skipped_count} movimenti erano già presenti.", "error")
        
    return redirect(url_for('transactions'))

# ---------------------------------------------------------
# TRANSACTION EDIT & USER AUTO-LEARNING
# ---------------------------------------------------------
@app.route("/transactions/update/<int:tx_id>", methods=["POST"])
@login_required
def update_transaction(tx_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    category = request.form.get("category", "").strip()
    sub_category = request.form.get("sub_category", "").strip()
    tags = request.form.get("tags", "").strip()
    learn_rule = request.form.get("learn_rule") == "1"
    set_fixed_cost = request.form.get("set_fixed_cost") == "1"
    fixed_freq = request.form.get("fixed_frequency", "MONTHLY")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    tx = conn.execute("SELECT * FROM transactions WHERE id = ? AND workspace_id = ?", (tx_id, ws_id)).fetchone()
    if not tx:
        conn.close()
        flash("Movimento non trovato.", "error")
        return redirect(url_for('transactions'))
        
    cursor.execute('''
        UPDATE transactions 
        SET category = ?, sub_category = ?, tags = ?
        WHERE id = ?
    ''', (category, sub_category, tags, tx_id))
    
    # Set as recurring fixed cost if requested
    if set_fixed_cost and tx['description']:
        fc_name = tx['description'].split()[0].strip()
        fc_amt = abs(tx['amount'])
        fc_day = int(tx['date'].split("-")[2]) if "-" in tx['date'] else 1
        
        active_m = None
        if fixed_freq == 'BIMONTHLY_EVEN':
            active_m = '2,4,6,8,10,12'
        elif fixed_freq == 'BIMONTHLY_ODD':
            active_m = '1,3,5,7,9,11'
            
        cursor.execute('''
            INSERT INTO fixed_costs (workspace_id, profile_id, name, category, expected_amount, due_day, frequency, active_months, match_pattern, is_income, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
        ''', (ws_id, tx['profile_id'], fc_name, category, fc_amt, fc_day, fixed_freq, active_m, fc_name))
        
    # Pianifica nel Radar Scadenze Future se richiesto dall'utente
    set_radar_dl = request.form.get("set_radar_deadline") == "1"
    if set_radar_dl and tx['description']:
        r_target_type = request.form.get("radar_target_type", "LEOPOLDO_ONLY")
        r_recurrence = request.form.get("radar_recurrence", "ANNUAL")
        r_custom_months = request.form.getlist("radar_custom_months")
        r_custom_months_str = ",".join(r_custom_months) if r_custom_months else None
        
        # Estrai nome pulito ed esercente per match pattern (es. "ACI" o "AUTOMOBILE CLUB")
        pat_clean = extract_clean_merchant_pattern(tx['description'] or tx['raw_description']) or tx['description'][:20].strip()
        expected_amt = abs(float(tx['amount']))
        due_day = int(tx['date'].split("-")[2]) if "-" in tx['date'] else 15
        due_ym = tx['date'][:7] if "-" in tx['date'] else datetime.now().strftime("%Y-%m")
        
        # Determina p1 e p2 paid in base alla pertinenza
        if r_target_type == 'LEOPOLDO_ONLY':
            p1_paid = expected_amt
            p2_paid = 0.0
        elif r_target_type == 'NUNZIA_ONLY':
            p1_paid = 0.0
            p2_paid = expected_amt
        else: # SHARED_50_50
            p1_paid = expected_amt / 2
            p2_paid = expected_amt / 2

        cursor.execute('''
            INSERT INTO planned_deadlines (
                workspace_id, name, category, expected_amount, year_month, due_day, 
                match_pattern, recurrence, target_type, p1_paid_amount, p2_paid_amount, is_paid, custom_months, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ws_id, f"{category} - {pat_clean}", category, expected_amt, due_ym, due_day,
            pat_clean, r_recurrence, r_target_type, p1_paid, p2_paid, 1, r_custom_months_str,
            f"Registrato automaticamente dal movimento del {tx['date']} ({pat_clean})"
        ))
        
    conn.commit()
    conn.close()

    # Save learning rule & apply retroactively if requested (now that DB connection is closed)
    if learn_rule and tx['description']:
        pat = extract_clean_merchant_pattern(tx['description'] or tx['raw_description'])
        if pat:
            save_or_update_category_rule(
                workspace_id=ws_id,
                pattern=pat,
                category=category,
                sub_category=sub_category,
                tags=tags,
                match_type='CONTAINS'
            )
            retro_count = apply_rule_retroactively(
                workspace_id=ws_id,
                pattern=pat,
                category=category,
                sub_category=sub_category,
                tags=tags,
                match_type='CONTAINS'
            )
            flash(f"Movimento aggiornato! Regola per '{pat}' salvata e applicata a {retro_count} movimenti storici e futuri!", "success")
        else:
            flash("Movimento aggiornato con successo!", "success")
    else:
        flash("Movimento aggiornato con successo!", "success")
        
    return redirect(url_for('transactions'))

@app.route("/transactions/delete/<int:tx_id>", methods=["POST"])
@login_required
def delete_transaction(tx_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    tx = conn.execute("SELECT * FROM transactions WHERE id = ? AND workspace_id = ?", (tx_id, ws_id)).fetchone()
    if tx:
        cursor.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        if tx['account_id']:
            cursor.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (tx['amount'], tx['account_id']))
        conn.commit()
        flash("Movimento eliminato e saldo aggiornato.", "success")
        
    conn.close()
    return redirect(url_for('transactions'))

# ---------------------------------------------------------
# CEDOLINO & BUSTA PAGA MODULE
# ---------------------------------------------------------
@app.route("/paystubs")
@login_required
def paystubs():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    profiles = conn.execute("SELECT * FROM profiles WHERE workspace_id = ? ORDER BY is_primary DESC, id ASC", (ws_id,)).fetchall()
    
    if not profiles:
        conn.close()
        flash("Nessun profilo trovato nel workspace.", "warning")
        return redirect(url_for('dashboard'))

    req_profile_id = request.args.get('profile_id', type=int)
    active_profile = None
    if req_profile_id:
        active_profile = next((p for p in profiles if p['id'] == req_profile_id), None)
    
    if not active_profile:
        active_filter = session.get('profile_filter', 'all')
        if active_filter != 'all':
            active_profile = next((p for p in profiles if str(p['id']) == active_filter), None)
    
    if not active_profile:
        active_profile = profiles[0]

    from datetime import datetime
    req_year = request.args.get('year', type=int) or datetime.now().year

    # Check distinct years available in paystubs
    years_rows = conn.execute("SELECT DISTINCT year FROM paystubs WHERE workspace_id = ? ORDER BY year DESC", (ws_id,)).fetchall()
    available_years = [r['year'] for r in years_rows]
    if req_year not in available_years:
        available_years.append(req_year)
    available_years.sort(reverse=True)

    summary = get_profile_paystubs_summary(ws_id, active_profile['id'], req_year)
    conn.close()

    return render_template(
        "paystubs.html",
        profiles=profiles,
        active_profile=active_profile,
        current_year=req_year,
        available_years=available_years,
        summary=summary
    )

@app.route("/paystubs/new")
@login_required
def paystub_new():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    profiles = conn.execute("SELECT * FROM profiles WHERE workspace_id = ? ORDER BY is_primary DESC, id ASC", (ws_id,)).fetchall()
    
    req_profile_id = request.args.get('profile_id', type=int)
    profile = next((p for p in profiles if p['id'] == req_profile_id), profiles[0] if profiles else None)
    if not profile:
        conn.close()
        flash("Profilo non trovato.", "error")
        return redirect(url_for('paystubs'))

    from datetime import datetime
    current_year = datetime.now().year
    default_month = datetime.now().month

    edit_id = request.args.get('edit_id', type=int)
    clone_from_id = request.args.get('clone_from', type=int)
    paystub = {}
    edit_mode = False

    if edit_id:
        row = conn.execute("SELECT * FROM paystubs WHERE id = ? AND workspace_id = ?", (edit_id, ws_id)).fetchone()
        if row:
            paystub = dict(row)
            edit_mode = True
            default_month = paystub['month']
            current_year = paystub['year']
    elif clone_from_id:
        row = conn.execute("SELECT * FROM paystubs WHERE id = ? AND workspace_id = ?", (clone_from_id, ws_id)).fetchone()
        if row:
            paystub = dict(row)
            paystub['id'] = None
            paystub['matched_tx_id'] = None
            # Advance month
            m = paystub.get('month', 1)
            y = paystub.get('year', current_year)
            if m < 12:
                paystub['month'] = m + 1
            else:
                paystub['month'] = 1
                paystub['year'] = y + 1
            default_month = paystub['month']
            current_year = paystub['year']

    # Check for PDF Parser Pre-fill from session
    pdf_prefill = session.pop('pdf_prefill', None)
    if pdf_prefill and not edit_mode:
        paystub = pdf_prefill
        if paystub.get('month'):
            default_month = paystub['month']
        if paystub.get('year'):
            current_year = paystub['year']

    # Get last paystub for cloning shortcut
    last_ps = conn.execute("SELECT * FROM paystubs WHERE workspace_id = ? AND profile_id = ? ORDER BY year DESC, month DESC LIMIT 1", (ws_id, profile['id'])).fetchone()

    # Find candidate bank transfers
    net_to_match = paystub.get('net_amount', 0.0)
    candidate_transfers = find_candidate_bank_transfers(ws_id, profile['id'], default_month, current_year, net_to_match)


    conn.close()

    return render_template(
        "paystub_form.html",
        profiles=profiles,
        profile=profile,
        paystub=paystub,
        edit_mode=edit_mode,
        last_paystub=dict(last_ps) if last_ps else None,
        candidate_transfers=candidate_transfers,
        current_year=current_year,
        default_month=default_month
    )

@app.route("/paystubs/upload-pdf", methods=["POST"])
@login_required
def paystub_upload_pdf():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({"success": False, "error": "Sessione scaduta"}), 401

    if 'file' not in request.files:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({"success": False, "error": "Nessun file selezionato"}), 400
        flash("Nessun file selezionato.", "error")
        return redirect(url_for('paystubs'))

    file = request.files['file']
    if not file or file.filename == '':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({"success": False, "error": "Nessun file selezionato"}), 400
        flash("Nessun file selezionato.", "error")
        return redirect(url_for('paystubs'))

    fname_lower = (file.filename or '').lower()
    if not fname_lower.endswith('.pdf') and not file.mimetype.startswith('application/pdf'):
        err_msg = "Formato non supportato. Per favore carica il file PDF originale della busta paga (es. Zucchetti, TeamSystem, ADP)."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({"success": False, "error": err_msg}), 400
        flash(err_msg, "error")
        return redirect(url_for('paystubs'))

    profile_id = request.form.get('profile_id', type=int)

    try:
        file_bytes = file.read()
        if not file_bytes:
            err_msg = "Il file PDF selezionato è vuoto (0 KB)."
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify({"success": False, "error": err_msg}), 400
            flash(err_msg, "error")
            return redirect(url_for('paystub_new', profile_id=profile_id))

        parsed_data = parse_paystub_pdf(file_bytes)
        if not parsed_data.get('success'):
            err_msg = parsed_data.get('error', 'Impossibile estrarre i dati dal PDF. Assicurati che sia un PDF con testo selezionabile.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify({"success": False, "error": err_msg}), 400
            flash(err_msg, "error")
            return redirect(url_for('paystub_new', profile_id=profile_id))

        prefill_payload = {
            'month': parsed_data.get('month'),
            'year': parsed_data.get('year'),
            'base_salary': parsed_data.get('base_salary', 0.0),
            'contingenza': parsed_data.get('contingenza', 0.0),
            'superminimo': parsed_data.get('superminimo', 0.0),
            'scatti_anzianita': parsed_data.get('scatti_anzianita', 0.0),
            'overtime_amount': parsed_data.get('overtime_amount', 0.0),
            'bonuses': parsed_data.get('bonuses', 0.0),
            'other_additions': parsed_data.get('other_additions', 0.0),
            'gross_amount': parsed_data.get('gross_amount', 0.0),
            'inps_tax': parsed_data.get('inps_tax', 0.0),
            'irpef_gross': parsed_data.get('irpef_gross', 0.0),
            'tax_deductions': parsed_data.get('tax_deductions', 0.0),
            'irpef_net': parsed_data.get('irpef_net', 0.0),
            'regional_tax': parsed_data.get('regional_tax', 0.0),
            'municipal_tax': parsed_data.get('municipal_tax', 0.0),
            'trattamento_integrativo': parsed_data.get('trattamento_integrativo', 0.0),
            'other_deductions': parsed_data.get('other_deductions', 0.0),
            'net_amount': parsed_data.get('net_amount', 0.0),
            'tfr_month': parsed_data.get('tfr_month', 0.0),
            'tfr_accumulated_total': parsed_data.get('tfr_accumulated_total', 0.0),
            'pension_fund_name': parsed_data.get('pension_fund_name', 'Azienda'),
            'pension_fund_contrib_employee': parsed_data.get('pension_fund_contrib_employee', 0.0),
            'pension_fund_contrib_company': parsed_data.get('pension_fund_contrib_company', 0.0),
            'pension_fund_tfr_month': parsed_data.get('pension_fund_tfr_month', 0.0),
            'pension_fund_total': parsed_data.get('pension_fund_total', 0.0),
            'ferie_residue_ore': parsed_data.get('ferie_residue_ore', 0.0),
            'rol_residui_ore': parsed_data.get('rol_residui_ore', 0.0),
            'ticket_count': parsed_data.get('ticket_count', 0.0),
            'ticket_unit_value': parsed_data.get('ticket_unit_value', 8.0),
            'ticket_total_value': parsed_data.get('ticket_total_value', 0.0)
        }
        session['pdf_prefill'] = prefill_payload

        # Check if AJAX
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({
                "success": True,
                "data": parsed_data,
                "prefill": prefill_payload,
                "message": f"Dati estratti con successo! Lordo: € {parsed_data.get('gross_amount', 0):,.2f}, Netto: € {parsed_data.get('net_amount', 0):,.2f}"
            })

        flash("PDF analizzato con successo! Verifica i campi precompilati prima di salvare.", "success")
        return redirect(url_for('paystub_new', profile_id=profile_id))

    except Exception as e:
        print(f"Error parsing paystub PDF: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({"success": False, "error": str(e)}), 500
        flash(f"Errore durante l'analisi del PDF: {str(e)}", "error")
        return redirect(url_for('paystub_new', profile_id=profile_id))

@app.route("/paystubs/save", methods=["POST"])

@login_required
def paystub_save():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))

    profile_id = request.form.get('profile_id', type=int)
    month = request.form.get('month', type=int)
    year = request.form.get('year', type=int)
    paystub_id = request.form.get('paystub_id', type=int)

    if not profile_id or not month or not year:
        flash("Profilo, mese e anno sono obbligatori.", "error")
        return redirect(url_for('paystubs'))

    # Calculate metrics with engine
    metrics = calculate_paystub_metrics(request.form)

    matched_tx_id = request.form.get('matched_tx_id')
    matched_tx_id = int(matched_tx_id) if matched_tx_id and matched_tx_id.isdigit() else None
    notes = request.form.get('notes', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    if paystub_id:
        # Update existing
        cursor.execute('''
            UPDATE paystubs SET
                month = ?, year = ?, gross_amount = ?, net_amount = ?,
                base_salary = ?, contingenza = ?, superminimo = ?, scatti_anzianita = ?,
                overtime_amount = ?, bonuses = ?, fringe_benefit = ?, other_additions = ?,
                inps_tax = ?, irpef_tax = ?, irpef_gross = ?, tax_deductions = ?, irpef_net = ?,
                regional_tax = ?, municipal_tax = ?, municipal_tax_acc = ?, municipal_tax_saldo = ?,
                trattamento_integrativo = ?, other_deductions = ?,
                tfr_month = ?, tfr_fund_type = ?, tfr_accumulated_total = ?,
                pension_fund_name = ?, pension_fund_contrib_employee = ?, pension_fund_contrib_company = ?,
                pension_fund_tfr_month = ?, pension_fund_total = ?,
                ferie_residue_ore = ?, rol_residui_ore = ?,
                ticket_count = ?, ticket_unit_value = ?, ticket_total_value = ?,
                matched_tx_id = ?, notes = ?
            WHERE id = ? AND workspace_id = ?
        ''', (
            month, year, metrics['gross_amount'], metrics['net_amount'],
            metrics['base_salary'], metrics['contingenza'], metrics['superminimo'], metrics['scatti_anzianita'],
            metrics['overtime_amount'], metrics['bonuses'], metrics['fringe_benefit'], metrics['other_additions'],
            metrics['inps_tax'], metrics['irpef_net'], metrics['irpef_gross'], metrics['tax_deductions'], metrics['irpef_net'],
            metrics['regional_tax'], metrics['municipal_tax'], metrics['municipal_tax_acc'], metrics['municipal_tax_saldo'],
            metrics['trattamento_integrativo'], metrics['other_deductions'],
            metrics['tfr_month'], metrics['tfr_fund_type'], metrics['tfr_accumulated_total'],
            metrics.get('pension_fund_name', 'Azienda'), metrics.get('pension_fund_contrib_employee', 0.0),
            metrics.get('pension_fund_contrib_company', 0.0), metrics.get('pension_fund_tfr_month', 0.0),
            metrics.get('pension_fund_total', 0.0),
            metrics['ferie_residue_ore'], metrics['rol_residui_ore'],
            metrics.get('ticket_count', 0.0), metrics.get('ticket_unit_value', 8.0), metrics.get('ticket_total_value', 0.0),
            matched_tx_id, notes, paystub_id, ws_id
        ))
        saved_id = paystub_id
        flash(f"Cedolino di {month}/{year} aggiornato con successo!", "success")
    else:
        # Check if already exists for this profile, month, year
        existing = conn.execute("SELECT id FROM paystubs WHERE workspace_id = ? AND profile_id = ? AND month = ? AND year = ?",
                                (ws_id, profile_id, month, year)).fetchone()
        if existing:
            # Overwrite existing
            cursor.execute('''
                UPDATE paystubs SET
                    gross_amount = ?, net_amount = ?,
                    base_salary = ?, contingenza = ?, superminimo = ?, scatti_anzianita = ?,
                    overtime_amount = ?, bonuses = ?, fringe_benefit = ?, other_additions = ?,
                    inps_tax = ?, irpef_tax = ?, irpef_gross = ?, tax_deductions = ?, irpef_net = ?,
                    regional_tax = ?, municipal_tax = ?, municipal_tax_acc = ?, municipal_tax_saldo = ?,
                    trattamento_integrativo = ?, other_deductions = ?,
                    tfr_month = ?, tfr_fund_type = ?, tfr_accumulated_total = ?,
                    pension_fund_name = ?, pension_fund_contrib_employee = ?, pension_fund_contrib_company = ?,
                    pension_fund_tfr_month = ?, pension_fund_total = ?,
                    ferie_residue_ore = ?, rol_residui_ore = ?,
                    ticket_count = ?, ticket_unit_value = ?, ticket_total_value = ?,
                    matched_tx_id = ?, notes = ?
                WHERE id = ?
            ''', (
                metrics['gross_amount'], metrics['net_amount'],
                metrics['base_salary'], metrics['contingenza'], metrics['superminimo'], metrics['scatti_anzianita'],
                metrics['overtime_amount'], metrics['bonuses'], metrics['fringe_benefit'], metrics['other_additions'],
                metrics['inps_tax'], metrics['irpef_net'], metrics['irpef_gross'], metrics['tax_deductions'], metrics['irpef_net'],
                metrics['regional_tax'], metrics['municipal_tax'], metrics['municipal_tax_acc'], metrics['municipal_tax_saldo'],
                metrics['trattamento_integrativo'], metrics['other_deductions'],
                metrics['tfr_month'], metrics['tfr_fund_type'], metrics['tfr_accumulated_total'],
                metrics.get('pension_fund_name', 'Azienda'), metrics.get('pension_fund_contrib_employee', 0.0),
                metrics.get('pension_fund_contrib_company', 0.0), metrics.get('pension_fund_tfr_month', 0.0),
                metrics.get('pension_fund_total', 0.0),
                metrics['ferie_residue_ore'], metrics['rol_residui_ore'],
                metrics.get('ticket_count', 0.0), metrics.get('ticket_unit_value', 8.0), metrics.get('ticket_total_value', 0.0),
                matched_tx_id, notes, existing['id']
            ))
            saved_id = existing['id']
            flash(f"Cedolino di {month}/{year} sovrascritto e salvato!", "success")
        else:
            cursor.execute('''
                INSERT INTO paystubs (
                    workspace_id, profile_id, month, year, gross_amount, net_amount,
                    base_salary, contingenza, superminimo, scatti_anzianita,
                    overtime_amount, bonuses, fringe_benefit, other_additions,
                    inps_tax, irpef_tax, irpef_gross, tax_deductions, irpef_net,
                    regional_tax, municipal_tax, municipal_tax_acc, municipal_tax_saldo,
                    trattamento_integrativo, other_deductions,
                    tfr_month, tfr_fund_type, tfr_accumulated_total,
                    pension_fund_name, pension_fund_contrib_employee, pension_fund_contrib_company,
                    pension_fund_tfr_month, pension_fund_total,
                    ferie_residue_ore, rol_residui_ore,
                    ticket_count, ticket_unit_value, ticket_total_value,
                    matched_tx_id, notes
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?
                )
            ''', (
                ws_id, profile_id, month, year, metrics['gross_amount'], metrics['net_amount'],
                metrics['base_salary'], metrics['contingenza'], metrics['superminimo'], metrics['scatti_anzianita'],
                metrics['overtime_amount'], metrics['bonuses'], metrics['fringe_benefit'], metrics['other_additions'],
                metrics['inps_tax'], metrics['irpef_net'], metrics['irpef_gross'], metrics['tax_deductions'], metrics['irpef_net'],
                metrics['regional_tax'], metrics['municipal_tax'], metrics['municipal_tax_acc'], metrics['municipal_tax_saldo'],
                metrics['trattamento_integrativo'], metrics['other_deductions'],
                metrics['tfr_month'], metrics['tfr_fund_type'], metrics['tfr_accumulated_total'],
                metrics.get('pension_fund_name', 'Azienda'), metrics.get('pension_fund_contrib_employee', 0.0),
                metrics.get('pension_fund_contrib_company', 0.0), metrics.get('pension_fund_tfr_month', 0.0),
                metrics.get('pension_fund_total', 0.0),
                metrics['ferie_residue_ore'], metrics['rol_residui_ore'],
                metrics.get('ticket_count', 0.0), metrics.get('ticket_unit_value', 8.0), metrics.get('ticket_total_value', 0.0),
                matched_tx_id, notes
            ))
            saved_id = cursor.lastrowid
            flash(f"Cedolino di {month}/{year} archiviato con successo!", "success")

    conn.commit()
    conn.close()

    return redirect(url_for('paystub_detail', paystub_id=saved_id))

@app.route("/assistant/switch", methods=["POST"])
@login_required
def switch_assistant():
    persona_key = request.form.get('persona', 'leo')
    if persona_key not in ASSISTANT_PERSONAS:
        persona_key = 'leo'
    
    user_id = session.get('user_id')
    conn = get_db_connection()
    conn.execute("UPDATE users SET assistant_persona = ? WHERE id = ?", (persona_key, user_id))
    session['assistant_persona'] = persona_key
    
    profile_id = request.form.get('profile_id', type=int)
    if profile_id:
        conn.execute("UPDATE profiles SET assistant_persona = ? WHERE id = ?", (persona_key, profile_id))
        
    conn.commit()
    conn.close()
    
    next_url = request.form.get('next') or request.referrer or url_for('dashboard')
    flash(f"Assistente virtuale impostato su {ASSISTANT_PERSONAS[persona_key]['name']} ({ASSISTANT_PERSONAS[persona_key]['title']})!", "success")
    return redirect(next_url)

@app.route("/paystubs/<int:paystub_id>")
@login_required
def paystub_detail(paystub_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM paystubs WHERE id = ? AND workspace_id = ?", (paystub_id, ws_id)).fetchone()
    if not row:
        conn.close()
        flash("Cedolino non trovato.", "error")
        return redirect(url_for('paystubs'))

    paystub = dict(row)
    profile = conn.execute("SELECT * FROM profiles WHERE id = ?", (paystub['profile_id'],)).fetchone()
    profile = dict(profile) if profile else None

    # Find previous month paystub for diff
    prev_m = paystub['month'] - 1 if paystub['month'] > 1 else 12
    prev_y = paystub['year'] if paystub['month'] > 1 else paystub['year'] - 1
    prev_row = conn.execute("SELECT * FROM paystubs WHERE workspace_id = ? AND profile_id = ? AND month = ? AND year = ?",
                            (ws_id, paystub['profile_id'], prev_m, prev_y)).fetchone()
    
    diff_info = compare_two_paystubs(paystub, dict(prev_row) if prev_row else None)

    # Matched transaction details
    matched_tx = None
    if paystub.get('matched_tx_id'):
        tx_row = conn.execute('''
            SELECT t.*, a.name as account_name, a.bank_name
            FROM transactions t
            LEFT JOIN accounts a ON t.account_id = a.id
            WHERE t.id = ?
        ''', (paystub['matched_tx_id'],)).fetchone()
        if tx_row:
            matched_tx = dict(tx_row)

    # Assistant Persona Resolution
    user_id = session.get('user_id')
    user_row = conn.execute("SELECT assistant_persona FROM users WHERE id = ?", (user_id,)).fetchone()
    
    # Allow URL preview override ?persona=anna or profile preference or user preference
    current_persona_key = request.args.get('persona') or (profile.get('assistant_persona') if profile else None) or (user_row['assistant_persona'] if user_row and user_row['assistant_persona'] else 'leo')
    if current_persona_key not in ASSISTANT_PERSONAS:
        current_persona_key = 'leo'

    # Analyze bank coverage (completeness of imported transactions for this month)
    bank_coverage = get_month_bank_coverage(ws_id, paystub['month'], paystub['year'], paystub['profile_id'])

    # Detect paystub anomalies
    anomalies = detect_paystub_anomalies(
        paystub,
        profile=profile,
        matched_tx=matched_tx,
        prev_paystub=dict(prev_row) if prev_row else None,
        bank_coverage=bank_coverage
    )

    profile_name = profile['name'] if profile else "Lavoratore"
    assistant_briefing = generate_paystub_assistant_briefing(
        paystub,
        profile_name=profile_name,
        persona_key=current_persona_key,
        matched_tx=matched_tx,
        diff_info=diff_info,
        anomalies=anomalies,
        bank_coverage=bank_coverage
    )

    month_names = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
                   "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
                   "13ª Mensilità (Tredicesima)", "14ª Mensilità (Quattordicesima)", "Premio di Risultato / Una Tantum"]
    month_name = month_names[paystub['month']] if 1 <= paystub['month'] < len(month_names) else f"Mese {paystub['month']}"

    conn.close()

    return render_template(
        "paystub_detail.html",
        paystub=paystub,
        profile=profile,
        diff_info=diff_info,
        matched_tx=matched_tx,
        bank_coverage=bank_coverage,
        month_name=month_name,
        glossary=PAYSTUB_GLOSSARY,
        assistant_briefing=assistant_briefing,
        anomalies=anomalies,
        personas=ASSISTANT_PERSONAS,
        current_persona=current_persona_key
    )

@app.route("/paystubs/<int:paystub_id>/delete", methods=["POST"])
@login_required
def paystub_delete(paystub_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    ps = conn.execute("SELECT * FROM paystubs WHERE id = ? AND workspace_id = ?", (paystub_id, ws_id)).fetchone()
    if ps:
        p_id = ps['profile_id']
        y = ps['year']
        cursor.execute("DELETE FROM paystubs WHERE id = ? AND workspace_id = ?", (paystub_id, ws_id))
        conn.commit()
        flash("Cedolino eliminato con successo.", "success")
        conn.close()
        return redirect(url_for('paystubs', profile_id=p_id, year=y))
        
    conn.close()
    return redirect(url_for('paystubs'))

# -------------------------------------------------------------
# Modello 730 & Fisco Routes
# -------------------------------------------------------------
@app.route("/tax730")
@app.route("/tax-730")
@login_required
def tax_730_list():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    profiles = conn.execute("SELECT * FROM profiles WHERE workspace_id = ? ORDER BY is_primary DESC, id ASC", (ws_id,)).fetchall()
    
    selected_profile_id = request.args.get('profile_id', type=int)
    if not selected_profile_id and profiles:
        selected_profile_id = profiles[0]['id']

    query = '''
        SELECT d.*, p.name as profile_name, ps.month as matched_ps_month, ps.year as matched_ps_year, ps.net_amount as matched_ps_net
        FROM tax_declarations_730 d
        LEFT JOIN profiles p ON d.profile_id = p.id
        LEFT JOIN paystubs ps ON d.matched_paystub_id = ps.id
        WHERE d.workspace_id = ?
    '''
    params = [ws_id]
    if selected_profile_id:
        query += " AND d.profile_id = ?"
        params.append(selected_profile_id)
    
    query += " ORDER BY d.declaration_year DESC, d.tax_year DESC"
    declarations = [dict(row) for row in conn.execute(query, params).fetchall()]

    # Parse details_json and compute aggregate metrics
    total_refunds = 0.0
    total_debits = 0.0
    total_deductions_used = 0.0
    total_net_tax_paid = 0.0
    total_income_all = 0.0

    month_names = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
                   "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

    for d in declarations:
        if d.get('details_json'):
            try:
                d['details'] = json.loads(d['details_json'])
            except Exception:
                d['details'] = {}
        else:
            d['details'] = {}

        if d.get('is_refund') and (d.get('final_refund_or_debit') or 0.0) > 0:
            total_refunds += float(d['final_refund_or_debit'])
        elif not d.get('is_refund') and (d.get('final_refund_or_debit') or 0.0) > 0:
            total_debits += float(d['final_refund_or_debit'])

        total_deductions_used += float(d.get('total_deductions') or 0.0)
        total_net_tax_paid += float(d.get('net_tax') or 0.0)
        total_income_all += float(d.get('total_income') or 0.0)

        if d.get('matched_ps_month'):
            m_idx = d['matched_ps_month']
            d['matched_ps_month_name'] = month_names[m_idx] if 1 <= m_idx <= 12 else f"Mese {m_idx}"

    avg_effective_rate = round((total_net_tax_paid / total_income_all * 100), 2) if total_income_all > 0 else 0.0

    conn.close()

    return render_template(
        "tax_730_list.html",
        profiles=profiles,
        selected_profile_id=selected_profile_id,
        declarations=declarations,
        total_refunds=total_refunds,
        total_debits=total_debits,
        total_deductions_used=total_deductions_used,
        total_net_tax_paid=total_net_tax_paid,
        avg_effective_rate=avg_effective_rate
    )


@app.route("/tax-730/upload-pdf", methods=["POST"])
@login_required
def tax_730_upload_pdf():
    ws_id = session.get('workspace_id')
    if not ws_id:
        return jsonify({'success': False, 'error': 'Workspace non selezionato'}), 400

    profile_id = request.form.get('profile_id', type=int)
    files = request.files.getlist('pdf_files') or [request.files.get('pdf_file')]
    files = [f for f in files if f and f.filename.endswith('.pdf')]

    if not files:
        flash("Nessun file PDF 730 valido selezionato.", "error")
        return redirect(url_for('tax_730_list', profile_id=profile_id))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get default profile if none selected
    if not profile_id:
        p_row = conn.execute("SELECT id FROM profiles WHERE workspace_id = ? ORDER BY is_primary DESC LIMIT 1", (ws_id,)).fetchone()
        profile_id = p_row['id'] if p_row else 1

    imported_count = 0
    last_inserted_id = None

    for f in files:
        file_bytes = f.read()
        parsed = parse_tax_730_pdf(file_bytes)
        if not parsed.get('success'):
            continue

        # Look for matching summer paystub
        matched_ps = find_matching_paystub_for_730(
            workspace_id=ws_id,
            profile_id=profile_id,
            declaration_year=parsed['declaration_year'],
            amount=parsed['final_refund_or_debit']
        )
        matched_ps_id = matched_ps['id'] if matched_ps else None

        # Check if declaration already exists for this tax_year & profile
        existing = conn.execute('''
            SELECT id FROM tax_declarations_730 
            WHERE workspace_id = ? AND profile_id = ? AND tax_year = ?
        ''', (ws_id, profile_id, parsed['tax_year'])).fetchone()

        details_json_str = json.dumps(parsed.get('expenses_breakdown', []))

        if existing:
            decl_id = existing['id']
            cursor.execute('''
                UPDATE tax_declarations_730 SET
                    declaration_year = ?,
                    taxpayer_name = ?,
                    fiscal_code = ?,
                    is_joint_declaration = ?,
                    declaration_type = ?,
                    total_income = ?,
                    principal_residence_deduction = ?,
                    taxable_income = ?,
                    gross_tax = ?,
                    employee_tax_credit = ?,
                    total_deductions = ?,
                    net_tax = ?,
                    withholdings_paid = ?,
                    tax_difference = ?,
                    regional_tax_due = ?,
                    municipal_tax_due = ?,
                    municipal_tax_acc = ?,
                    final_refund_or_debit = ?,
                    is_refund = ?,
                    medical_expenses = ?,
                    medical_expenses_deductible = ?,
                    mortgage_interest = ?,
                    pension_fund_deduction = ?,
                    building_renovations = ?,
                    other_expenses_total = ?,
                    details_json = ?,
                    matched_paystub_id = ?,
                    pdf_filename = ?
                WHERE id = ?
            ''', (
                parsed['declaration_year'], parsed['taxpayer_name'], parsed['fiscal_code'],
                parsed['is_joint_declaration'], parsed['declaration_type'], parsed['total_income'],
                parsed['principal_residence_deduction'], parsed['taxable_income'], parsed['gross_tax'],
                parsed['employee_tax_credit'], parsed['total_deductions'], parsed['net_tax'],
                parsed['withholdings_paid'], parsed['tax_difference'], parsed['regional_tax_due'],
                parsed['municipal_tax_due'], parsed['municipal_tax_acc'], parsed['final_refund_or_debit'],
                parsed['is_refund'], parsed['medical_expenses'], parsed['medical_expenses_deductible'],
                parsed['mortgage_interest'], parsed['pension_fund_deduction'], parsed['building_renovations'],
                parsed['other_expenses_total'], details_json_str, matched_ps_id, f.filename,
                decl_id
            ))
            last_inserted_id = decl_id
        else:
            cursor.execute('''
                INSERT INTO tax_declarations_730 (
                    workspace_id, profile_id, tax_year, declaration_year, taxpayer_name, fiscal_code,
                    is_joint_declaration, declaration_type, total_income, principal_residence_deduction,
                    taxable_income, gross_tax, employee_tax_credit, total_deductions, net_tax,
                    withholdings_paid, tax_difference, regional_tax_due, municipal_tax_due,
                    municipal_tax_acc, final_refund_or_debit, is_refund, medical_expenses,
                    medical_expenses_deductible, mortgage_interest, pension_fund_deduction,
                    building_renovations, other_expenses_total, details_json, matched_paystub_id,
                    pdf_filename
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?
                )
            ''', (
                ws_id, profile_id, parsed['tax_year'], parsed['declaration_year'], parsed['taxpayer_name'], parsed['fiscal_code'],
                parsed['is_joint_declaration'], parsed['declaration_type'], parsed['total_income'], parsed['principal_residence_deduction'],
                parsed['taxable_income'], parsed['gross_tax'], parsed['employee_tax_credit'], parsed['total_deductions'], parsed['net_tax'],
                parsed['withholdings_paid'], parsed['tax_difference'], parsed['regional_tax_due'], parsed['municipal_tax_due'],
                parsed['municipal_tax_acc'], parsed['final_refund_or_debit'], parsed['is_refund'], parsed['medical_expenses'],
                parsed['medical_expenses_deductible'], parsed['mortgage_interest'], parsed['pension_fund_deduction'],
                parsed['building_renovations'], parsed['other_expenses_total'], details_json_str, matched_ps_id,
                f.filename
            ))
            last_inserted_id = cursor.lastrowid
        
        imported_count += 1

    conn.commit()
    conn.close()

    if imported_count == 1 and last_inserted_id:
        flash("Modello 730 importato con successo!", "success")
        return redirect(url_for('tax_730_detail', decl_id=last_inserted_id))
    elif imported_count > 1:
        flash(f"{imported_count} Dichiarazioni 730 importate con successo!", "success")
        return redirect(url_for('tax_730_list', profile_id=profile_id))
    else:
        flash("Impossibile analizzare il file 730 PDF selezionato.", "error")
        return redirect(url_for('tax_730_list', profile_id=profile_id))


@app.route("/tax-730/<int:decl_id>")
@login_required
def tax_730_detail(decl_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    row = conn.execute('''
        SELECT d.*, p.name as profile_name
        FROM tax_declarations_730 d
        LEFT JOIN profiles p ON d.profile_id = p.id
        WHERE d.id = ? AND d.workspace_id = ?
    ''', (decl_id, ws_id)).fetchone()


    if not row:
        conn.close()
        flash("Dichiarazione 730 non trovata.", "error")
        return redirect(url_for('tax_730_list'))

    tax_decl = dict(row)

    # Parse details_json (expenses breakdown)
    if tax_decl.get('details_json'):
        try:
            tax_decl['expenses_breakdown'] = json.loads(tax_decl['details_json'])
        except Exception:
            tax_decl['expenses_breakdown'] = []
    else:
        tax_decl['expenses_breakdown'] = []

    # Get or find matching paystub
    matched_paystub = None
    if tax_decl.get('matched_paystub_id'):
        ps_row = conn.execute('''
            SELECT p.*, t.date as matched_tx_date, t.amount as matched_tx_amount
            FROM paystubs p
            LEFT JOIN transactions t ON p.matched_tx_id = t.id
            WHERE p.id = ?
        ''', (tax_decl['matched_paystub_id'],)).fetchone()
        if ps_row:
            matched_paystub = dict(ps_row)
    
    if not matched_paystub and (tax_decl.get('final_refund_or_debit') or 0.0) > 0:
        matched_paystub = find_matching_paystub_for_730(
            workspace_id=ws_id,
            profile_id=tax_decl['profile_id'],
            declaration_year=tax_decl['declaration_year'],
            amount=tax_decl['final_refund_or_debit']
        )

    month_names = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
                   "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    if matched_paystub:
        m_idx = matched_paystub.get('month', 0)
        matched_paystub['month_name'] = month_names[m_idx] if 1 <= m_idx <= 12 else f"Mese {m_idx}"

    # Calculate Tax Optimization Insights & Comprehensive Audit Action Plan
    insights = calculate_tax_optimization_insights(tax_decl)
    audit_report = perform_730_audit_and_action_plan(ws_id, tax_decl['profile_id'], tax_decl)

    # Virtual Assistant Persona selection
    persona_key = request.args.get('persona') or session.get('assistant_persona') or 'dott_fiscale'
    if persona_key not in ASSISTANT_PERSONAS:
        persona_key = 'dott_fiscale'
    session['assistant_persona'] = persona_key

    assistant_briefing = generate_730_assistant_briefing(
        tax_decl=tax_decl,
        matched_paystub=matched_paystub,
        insights=insights,
        persona_key=persona_key
    )

    conn.close()

    return render_template(
        "tax_730_detail.html",
        decl=tax_decl,
        matched_paystub=matched_paystub,
        insights=insights,
        assistant_briefing=assistant_briefing,
        audit_report=audit_report,
        personas=ASSISTANT_PERSONAS,
        current_persona=persona_key
    )



@app.route("/tax-730/<int:decl_id>/delete", methods=["POST"])
@login_required
def tax_730_delete(decl_id):
    ws_id = session.get('workspace_id')
    if not ws_id:
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    row = conn.execute("SELECT profile_id FROM tax_declarations_730 WHERE id = ? AND workspace_id = ?", (decl_id, ws_id)).fetchone()
    if row:
        p_id = row['profile_id']
        cursor.execute("DELETE FROM tax_declarations_730 WHERE id = ? AND workspace_id = ?", (decl_id, ws_id))
        conn.commit()
        flash("Dichiarazione 730 eliminata.", "success")
        conn.close()
        return redirect(url_for('tax_730_list', profile_id=p_id))
    
    conn.close()
    return redirect(url_for('tax_730_list'))


# ==========================================
# SUPER-ADMIN BACKEND & SAAS PLATFORM ROUTES
# ==========================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    
    # 1. User & Workspace counts
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_workspaces = conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
    family_workspaces = conn.execute("SELECT COUNT(*) FROM workspaces WHERE type = 'FAMILY'").fetchone()[0]
    
    # Plan distribution
    plan_rows = conn.execute("SELECT subscription_plan, COUNT(*) as cnt FROM users GROUP BY subscription_plan").fetchall()
    plan_counts = {r['subscription_plan'] or 'FREE': r['cnt'] for r in plan_rows}
    
    # Status distribution
    status_rows = conn.execute("SELECT subscription_status, COUNT(*) as cnt FROM users GROUP BY subscription_status").fetchall()
    status_counts = {r['subscription_status'] or 'ACTIVE': r['cnt'] for r in status_rows}
    
    # 2. Financial volume & records telemetry
    tx_stats = conn.execute("SELECT COUNT(*) as total_tx, COALESCE(SUM(ABS(amount)), 0) as total_vol FROM transactions").fetchone()
    total_tx = tx_stats['total_tx']
    total_volume = tx_stats['total_vol']
    
    total_paystubs = conn.execute("SELECT COUNT(*) FROM paystubs").fetchone()[0]
    total_tax_730 = conn.execute("SELECT COUNT(*) FROM tax_declarations_730").fetchone()[0]
    total_accounts = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    total_profiles = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
    
    # 3. Global Rules count
    total_global_rules = conn.execute("SELECT COUNT(*) FROM global_category_rules").fetchone()[0]
    
    # 4. Storage & System Health
    db_size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    db_size_mb = round(db_size_bytes / (1024 * 1024), 2)
    
    # 5. Full Users List with workspace & profile metrics
    users_list = conn.execute('''
        SELECT u.*, 
            (SELECT COUNT(*) FROM workspace_members wm WHERE wm.user_id = u.id) as ws_count,
            (SELECT COUNT(*) FROM profiles p 
             JOIN workspace_members wm ON p.workspace_id = wm.workspace_id 
             WHERE wm.user_id = u.id) as profile_count,
            (SELECT COUNT(*) FROM accounts a 
             JOIN workspace_members wm ON a.workspace_id = wm.workspace_id 
             WHERE wm.user_id = u.id) as account_count,
            (SELECT COUNT(*) FROM transactions t 
             JOIN workspace_members wm ON t.workspace_id = wm.workspace_id 
             WHERE wm.user_id = u.id) as tx_count
        FROM users u 
        ORDER BY u.id DESC
    ''').fetchall()
    
    # 6. Global Category Master Rules
    global_rules = conn.execute("SELECT * FROM global_category_rules ORDER BY priority DESC, pattern ASC").fetchall()
    
    # 7. System Broadcast Announcements
    announcements = conn.execute("SELECT * FROM system_announcements ORDER BY created_at DESC").fetchall()
    
    # 8. Recent Audit Logs (last 25)
    recent_audits = conn.execute('''
        SELECT a.*, u.email as admin_email, u.full_name as admin_name,
               tu.email as target_user_email, tu.full_name as target_user_name
        FROM system_audit_logs a
        LEFT JOIN users u ON a.admin_user_id = u.id
        LEFT JOIN users tu ON a.target_user_id = tu.id
        ORDER BY a.created_at DESC LIMIT 25
    ''').fetchall()
    
    conn.close()
    
    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_workspaces=total_workspaces,
        family_workspaces=family_workspaces,
        plan_counts=plan_counts,
        status_counts=status_counts,
        total_tx=total_tx,
        total_volume=total_volume,
        total_paystubs=total_paystubs,
        total_tax_730=total_tax_730,
        total_accounts=total_accounts,
        total_profiles=total_profiles,
        total_global_rules=total_global_rules,
        db_size_mb=db_size_mb,
        users_list=users_list,
        global_rules=global_rules,
        announcements=announcements,
        recent_audits=recent_audits
    )


@app.route("/admin/users/<int:user_id>/update-plan", methods=["POST"])
@admin_required
def admin_update_user_plan(user_id):
    admin_id = session.get('original_admin_id') or session['user_id']
    plan = request.form.get("subscription_plan", "FREE").strip()
    status = request.form.get("subscription_status", "ACTIVE").strip()
    role = request.form.get("role", "USER").strip()
    expires_at = request.form.get("subscription_expires_at", "").strip() or None
    
    conn = get_db_connection()
    target_user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if not target_user:
        conn.close()
        flash("Utente non trovato.", "error")
        return redirect(url_for('admin_dashboard'))
        
    conn.execute('''
        UPDATE users 
        SET subscription_plan = ?, subscription_status = ?, role = ?, subscription_expires_at = ?
        WHERE id = ?
    ''', (plan, status, role, expires_at, user_id))
    conn.commit()
    conn.close()
    
    log_admin_action(
        admin_id=admin_id,
        action="UPDATE_USER_PLAN",
        target_user_id=user_id,
        details=f"Piano: {plan}, Stato: {status}, Ruolo: {role}, Scadenza: {expires_at or 'Illimitata'}",
        ip_address=request.remote_addr
    )
    
    flash(f"Piano dell'utente {target_user['full_name']} aggiornato con successo a '{plan}' ({status}).", "success")
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def admin_reset_user_password(user_id):
    admin_id = session.get('original_admin_id') or session['user_id']
    new_password = request.form.get("new_password", "").strip()
    
    is_valid, err_msg = validate_password_complexity(new_password)
    if not is_valid:
        flash(err_msg, "error")
        return redirect(url_for('admin_dashboard'))
        
    conn = get_db_connection()
    target_user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if not target_user:
        conn.close()
        flash("Utente non trovato.", "error")
        return redirect(url_for('admin_dashboard'))
        
    pwd_hash = generate_password_hash(new_password)
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pwd_hash, user_id))
    conn.commit()
    conn.close()
    
    log_admin_action(
        admin_id=admin_id,
        action="RESET_USER_PASSWORD",
        target_user_id=user_id,
        details=f"Password reimpostata manualmente per {target_user['email']}",
        ip_address=request.remote_addr
    )
    
    flash(f"Password per l'utente {target_user['full_name']} ({target_user['email']}) reimpostata con successo.", "success")
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/users/<int:user_id>/impersonate", methods=["POST"])
@admin_required
def admin_impersonate_user(user_id):
    admin_id = session.get('original_admin_id') or session['user_id']
    admin_name = session.get('original_admin_name') or session['user_name']
    
    conn = get_db_connection()
    target_user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if not target_user:
        conn.close()
        flash("Utente non trovato per la sessione di supporto.", "error")
        return redirect(url_for('admin_dashboard'))
        
    # Find user's default workspace
    ws = conn.execute('''
        SELECT w.* FROM workspaces w
        JOIN workspace_members wm ON w.id = wm.workspace_id
        WHERE wm.user_id = ? LIMIT 1
    ''', (user_id,)).fetchone()
    conn.close()
    
    # Store original admin identity in session
    session['original_admin_id'] = admin_id
    session['original_admin_name'] = admin_name
    
    # Switch session identity to target user
    session['user_id'] = target_user['id']
    session['user_email'] = target_user['email']
    session['user_name'] = target_user['full_name']
    session['role'] = target_user['role']
    session['subscription_plan'] = target_user['subscription_plan'] or 'FREE'
    session['subscription_status'] = target_user['subscription_status'] or 'ACTIVE'
    
    if ws:
        session['workspace_id'] = ws['id']
        session['workspace_name'] = ws['name']
    
    log_admin_action(
        admin_id=admin_id,
        action="IMPERSONATE_USER",
        target_user_id=user_id,
        details=f"Admin {admin_name} ha avviato sessione di supporto come {target_user['email']}",
        ip_address=request.remote_addr
    )
    
    flash(f"🛡️ Modalità Assistenza Attiva: stai operando come {target_user['full_name']} ({target_user['email']}).", "warning")
    return redirect(url_for('dashboard'))


@app.route("/admin/impersonate/exit", methods=["POST", "GET"])
def admin_exit_impersonation():
    original_admin_id = session.get('original_admin_id')
    if not original_admin_id:
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    admin_user = conn.execute("SELECT * FROM users WHERE id = ?", (original_admin_id,)).fetchone()
    
    if not admin_user:
        session.clear()
        conn.close()
        flash("Sessione terminata. Effettua nuovamente l'accesso.", "info")
        return redirect(url_for('login'))
        
    # Find admin's workspace
    ws = conn.execute('''
        SELECT w.* FROM workspaces w
        JOIN workspace_members wm ON w.id = wm.workspace_id
        WHERE wm.user_id = ? LIMIT 1
    ''', (admin_user['id'],)).fetchone()
    conn.close()
    
    # Clear impersonation flags
    session.pop('original_admin_id', None)
    session.pop('original_admin_name', None)
    
    # Restore admin session
    session['user_id'] = admin_user['id']
    session['user_email'] = admin_user['email']
    session['user_name'] = admin_user['full_name']
    session['role'] = admin_user['role']
    session['subscription_plan'] = admin_user['subscription_plan'] or 'LIFETIME'
    session['subscription_status'] = admin_user['subscription_status'] or 'ACTIVE'
    
    if ws:
        session['workspace_id'] = ws['id']
        session['workspace_name'] = ws['name']
        
    log_admin_action(
        admin_id=original_admin_id,
        action="EXIT_IMPERSONATION",
        details="Admin ha terminato la modalità assistenza e ripreso il controllo",
        ip_address=request.remote_addr
    )
    
    flash("👑 Sessione di assistenza terminata. Bentornato nella Suite Super-Admin.", "success")
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    admin_id = session.get('original_admin_id') or session['user_id']
    
    # Prevent deleting admin itself or master id 1
    if user_id == session.get('user_id') or user_id == 1:
        flash("Non è possibile eliminare l'amministratore principale o il proprio account corrente.", "error")
        return redirect(url_for('admin_dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    target_user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    
    if not target_user:
        conn.close()
        flash("Utente non trovato.", "error")
        return redirect(url_for('admin_dashboard'))
        
    # Find all workspaces owned solely by this user
    owned_workspaces = conn.execute('''
        SELECT wm.workspace_id FROM workspace_members wm
        WHERE wm.user_id = ? AND wm.role = 'OWNER'
    ''', (user_id,)).fetchall()
    
    for ow in owned_workspaces:
        ws_id = ow['workspace_id']
        # Count other members in workspace
        other_members = conn.execute('''
            SELECT COUNT(*) FROM workspace_members WHERE workspace_id = ? AND user_id != ?
        ''', (ws_id, user_id)).fetchone()[0]
        
        if other_members == 0:
            # Full cascade delete of this workspace and all associated financial records
            cursor.execute("DELETE FROM tax_declarations_730 WHERE workspace_id = ?", (ws_id,))
            cursor.execute("DELETE FROM paystubs WHERE workspace_id = ?", (ws_id,))
            cursor.execute("DELETE FROM category_rules WHERE workspace_id = ?", (ws_id,))
            cursor.execute("DELETE FROM transactions WHERE workspace_id = ?", (ws_id,))
            cursor.execute("DELETE FROM accounts WHERE workspace_id = ?", (ws_id,))
            cursor.execute("DELETE FROM profiles WHERE workspace_id = ?", (ws_id,))
            cursor.execute("DELETE FROM workspace_members WHERE workspace_id = ?", (ws_id,))
            cursor.execute("DELETE FROM workspaces WHERE id = ?", (ws_id,))
    
    # Delete user from users table
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    log_admin_action(
        admin_id=admin_id,
        action="GDPR_DELETE_USER",
        target_user_id=user_id,
        details=f"Eliminazione integrale GDPR dell'utente {target_user['email']} ({target_user['full_name']})",
        ip_address=request.remote_addr
    )
    
    flash(f"Account di {target_user['full_name']} ({target_user['email']}) e tutti i dati correlati eliminati definitivamente.", "success")
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/global-rules/add", methods=["POST"])
@admin_required
def admin_add_global_rule():
    admin_id = session.get('original_admin_id') or session['user_id']
    pattern = request.form.get("pattern", "").strip().upper()
    category = request.form.get("category", "").strip()
    sub_category = request.form.get("sub_category", "").strip()
    tags = request.form.get("tags", "").strip().lower()
    match_type = request.form.get("match_type", "CONTAINS").strip()
    priority = int(request.form.get("priority", 10))
    is_tax_deductible = 1 if request.form.get("is_tax_deductible") else 0
    
    if not pattern or not category:
        flash("Pattern e Categoria sono campi obbligatori.", "error")
        return redirect(url_for('admin_dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO global_category_rules (pattern, category, sub_category, tags, match_type, priority, is_tax_deductible)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pattern) DO UPDATE SET
            category = excluded.category,
            sub_category = excluded.sub_category,
            tags = excluded.tags,
            match_type = excluded.match_type,
            priority = excluded.priority,
            is_tax_deductible = excluded.is_tax_deductible
    ''', (pattern, category, sub_category, tags, match_type, priority, is_tax_deductible))
    conn.commit()
    conn.close()
    
    log_admin_action(
        admin_id=admin_id,
        action="SAVE_GLOBAL_RULE",
        details=f"Pattern: {pattern} -> {category}/{sub_category} (Detraibile: {is_tax_deductible})",
        ip_address=request.remote_addr
    )
    
    flash(f"Regola globale '{pattern}' salvata con successo.", "success")
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/global-rules/<int:rule_id>/edit", methods=["POST"])
@admin_required
def admin_edit_global_rule(rule_id):
    admin_id = session.get('original_admin_id') or session['user_id']
    pattern = request.form.get("pattern", "").strip().upper()
    category = request.form.get("category", "").strip()
    sub_category = request.form.get("sub_category", "").strip()
    tags = request.form.get("tags", "").strip().lower()
    match_type = request.form.get("match_type", "CONTAINS").strip()
    priority = int(request.form.get("priority", 10))
    is_tax_deductible = 1 if request.form.get("is_tax_deductible") else 0

    if not pattern or not category:
        flash("Pattern e Categoria sono obbligatori.", "error")
        return redirect(url_for('admin_dashboard'))

    conn = get_db_connection()
    conn.execute('''
        UPDATE global_category_rules 
        SET pattern = ?, category = ?, sub_category = ?, tags = ?, match_type = ?, priority = ?, is_tax_deductible = ?
        WHERE id = ?
    ''', (pattern, category, sub_category, tags, match_type, priority, is_tax_deductible, rule_id))
    conn.commit()
    conn.close()

    log_admin_action(
        admin_id=admin_id,
        action="EDIT_GLOBAL_RULE",
        details=f"Aggiornata regola globale ID {rule_id}: {pattern} -> {category}/{sub_category}",
        ip_address=request.remote_addr
    )
    flash(f"Regola globale '{pattern}' modificata con successo.", "success")
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/global-rules/<int:rule_id>/delete", methods=["POST"])
@admin_required
def admin_delete_global_rule(rule_id):
    admin_id = session.get('original_admin_id') or session['user_id']
    conn = get_db_connection()
    rule = conn.execute("SELECT * FROM global_category_rules WHERE id = ?", (rule_id,)).fetchone()
    
    if rule:
        conn.execute("DELETE FROM global_category_rules WHERE id = ?", (rule_id,))
        conn.commit()
        log_admin_action(
            admin_id=admin_id,
            action="DELETE_GLOBAL_RULE",
            details=f"Rimossa regola globale '{rule['pattern']}'",
            ip_address=request.remote_addr
        )
        flash(f"Regola globale '{rule['pattern']}' eliminata.", "success")
    conn.close()
    
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/global-rules/propagate", methods=["POST"])
@admin_required
def admin_propagate_global_rules():
    admin_id = session.get('original_admin_id') or session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    global_rules = conn.execute("SELECT * FROM global_category_rules").fetchall()
    workspaces = conn.execute("SELECT id FROM workspaces").fetchall()
    
    added_count = 0
    for ws in workspaces:
        ws_id = ws['id']
        for gr in global_rules:
            # Check if this rule pattern already exists in workspace
            exists = conn.execute('''
                SELECT id FROM category_rules WHERE workspace_id = ? AND UPPER(pattern) = UPPER(?)
            ''', (ws_id, gr['pattern'])).fetchone()
            
            if not exists:
                cursor.execute('''
                    INSERT INTO category_rules (workspace_id, pattern, category, sub_category, tags, match_type, priority)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (ws_id, gr['pattern'], gr['category'], gr['sub_category'], gr['tags'], gr['match_type'], gr['priority']))
                added_count += 1
                
    conn.commit()
    conn.close()
    
    log_admin_action(
        admin_id=admin_id,
        action="PROPAGATE_GLOBAL_RULES",
        details=f"Sincronizzate {added_count} regole mancanti su {len(workspaces)} workspace",
        ip_address=request.remote_addr
    )
    
    flash(f"🧠 Propagazione completata con successo: inserite {added_count} nuove regole su tutti i workspace!", "success")
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/announcements/save", methods=["POST"])
@admin_required
def admin_save_announcement():
    admin_id = session.get('original_admin_id') or session['user_id']
    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()
    level = request.form.get("level", "INFO").strip()
    is_active = 1 if request.form.get("is_active") else 0
    
    if not title or not message:
        flash("Titolo e Messaggio sono obbligatori.", "error")
        return redirect(url_for('admin_dashboard'))
        
    conn = get_db_connection()
    # If this is set as active, optionally deactivate other active ones to have a single clear message
    if is_active:
        conn.execute("UPDATE system_announcements SET is_active = 0")
        
    conn.execute('''
        INSERT INTO system_announcements (title, message, level, is_active)
        VALUES (?, ?, ?, ?)
    ''', (title, message, level, is_active))
    conn.commit()
    conn.close()
    
    log_admin_action(
        admin_id=admin_id,
        action="SAVE_ANNOUNCEMENT",
        details=f"Creato avviso '{title}' [Livello: {level}, Attivo: {is_active}]",
        ip_address=request.remote_addr
    )
    
    flash("📢 Avviso di sistema broadcast salvato con successo!", "success")
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/announcements/<int:ann_id>/toggle", methods=["POST"])
@admin_required
def admin_toggle_announcement(ann_id):
    admin_id = session.get('original_admin_id') or session['user_id']
    conn = get_db_connection()
    ann = conn.execute("SELECT * FROM system_announcements WHERE id = ?", (ann_id,)).fetchone()
    
    if ann:
        new_status = 0 if ann['is_active'] else 1
        if new_status == 1:
            conn.execute("UPDATE system_announcements SET is_active = 0")
        conn.execute("UPDATE system_announcements SET is_active = ? WHERE id = ?", (new_status, ann_id))
        conn.commit()
        log_admin_action(
            admin_id=admin_id,
            action="TOGGLE_ANNOUNCEMENT",
            details=f"Avviso '{ann['title']}' impostato a {'ATTIVO' if new_status else 'DISATTIVO'}",
            ip_address=request.remote_addr
        )
        flash(f"Stato dell'avviso aggiornato a {'Attivo' if new_status else 'Disattivo'}.", "info")
    conn.close()
    
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/announcements/<int:ann_id>/delete", methods=["POST"])
@admin_required
def admin_delete_announcement(ann_id):
    admin_id = session.get('original_admin_id') or session['user_id']
    conn = get_db_connection()
    conn.execute("DELETE FROM system_announcements WHERE id = ?", (ann_id,))
    conn.commit()
    conn.close()
    
    log_admin_action(
        admin_id=admin_id,
        action="DELETE_ANNOUNCEMENT",
        details=f"Eliminato avviso ID: {ann_id}",
        ip_address=request.remote_addr
    )
    
    flash("Avviso broadcast rimosso.", "success")
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/system/vacuum", methods=["POST"])
@admin_required
def admin_system_vacuum():
    admin_id = session.get('original_admin_id') or session['user_id']
    try:
        conn = get_db_connection()
        conn.execute("VACUUM;")
        conn.execute("ANALYZE;")
        conn.close()
        
        log_admin_action(
            admin_id=admin_id,
            action="SYSTEM_VACUUM",
            details="Esecuzione VACUUM & ANALYZE per ottimizzazione indici e spazio database",
            ip_address=request.remote_addr
        )
        flash("✨ Ottimizzazione del Database completata con successo (VACUUM & ANALYZE eseguiti).", "success")
    except Exception as e:
        flash(f"Errore durante l'ottimizzazione del database: {e}", "error")
        
    return redirect(url_for('admin_dashboard'))


@app.route("/admin/system/backup", methods=["GET"])
@admin_required
def admin_system_backup():
    admin_id = session.get('original_admin_id') or session['user_id']
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    download_filename = f"FiscMoney_backup_{timestamp_str}.db"
    
    log_admin_action(
        admin_id=admin_id,
        action="SYSTEM_BACKUP",
        details=f"Download snapshot database: {download_filename}",
        ip_address=request.remote_addr
    )
    
    return send_file(
        DB_PATH,
        as_attachment=True,
        download_name=download_filename,
        mimetype="application/x-sqlite3"
    )


if __name__ == "__main__":
    print("Avvio del server FiscMoney su http://localhost:5020")
    app.run(host="0.0.0.0", port=5020, debug=True)

