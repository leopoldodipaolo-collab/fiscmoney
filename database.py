import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "fiscmoney.db"))

def get_db_connection():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

def init_db():
    """Initializes the FiscMoney database schema with multi-tenancy and security."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT DEFAULT 'USER', -- 'USER' or 'SUPER_ADMIN'
            assistant_persona TEXT DEFAULT 'demetrio',
            subscription_plan TEXT DEFAULT 'FREE', -- 'FREE', 'PRO_ANNUAL', 'LIFETIME'
            subscription_status TEXT DEFAULT 'ACTIVE', -- 'ACTIVE', 'TRIAL', 'EXPIRED', 'SUSPENDED'
            subscription_expires_at TIMESTAMP,
            last_login_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Safe migration: add assistant_persona & subscription columns to users if missing
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [col[1] for col in cursor.fetchall()]
    if "assistant_persona" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN assistant_persona TEXT DEFAULT 'demetrio'")
    if "subscription_plan" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN subscription_plan TEXT DEFAULT 'FREE'")
    if "subscription_status" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN subscription_status TEXT DEFAULT 'ACTIVE'")
    if "subscription_expires_at" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN subscription_expires_at TIMESTAMP")
    if "last_login_at" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP")
    
    # 2. Workspaces Table (Single vs Family)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT CHECK(type IN ('SINGLE', 'FAMILY')) DEFAULT 'SINGLE',
            sharing_mode TEXT DEFAULT 'FULL', -- 'FULL', 'HYBRID', 'ADMIN_ONLY'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Safe migration: add sharing_mode to workspaces if missing
    cursor.execute("PRAGMA table_info(workspaces)")
    ws_cols = [col[1] for col in cursor.fetchall()]
    if "sharing_mode" not in ws_cols:
        cursor.execute("ALTER TABLE workspaces ADD COLUMN sharing_mode TEXT DEFAULT 'FULL'")

    
    # 3. Workspace Members (Users linked to Workspaces)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workspace_members (
            workspace_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT CHECK(role IN ('OWNER', 'MEMBER', 'READONLY')) DEFAULT 'MEMBER',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, user_id),
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # 4. Profiles Table (Individual profiles inside a workspace, e.g. Self, Partner, Figlio)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            role_title TEXT DEFAULT 'Titolare',
            tax_code TEXT,
            is_primary BOOLEAN DEFAULT 0,
            assistant_persona TEXT DEFAULT 'demetrio',
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )
    ''')
    
    # Safe migration: add role_title, invited_email, linked_user_id, assistant_persona to profiles
    cursor.execute("PRAGMA table_info(profiles)")
    columns = [col[1] for col in cursor.fetchall()]
    if "role_title" not in columns:
        cursor.execute("ALTER TABLE profiles ADD COLUMN role_title TEXT DEFAULT 'Titolare'")
    if "invited_email" not in columns:
        cursor.execute("ALTER TABLE profiles ADD COLUMN invited_email TEXT")
    if "linked_user_id" not in columns:
        cursor.execute("ALTER TABLE profiles ADD COLUMN linked_user_id INTEGER")
    if "assistant_persona" not in columns:
        cursor.execute("ALTER TABLE profiles ADD COLUMN assistant_persona TEXT DEFAULT 'demetrio'")
    
    # 5. Accounts Table (Bank accounts, cards, cash)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            profile_id INTEGER,
            name TEXT NOT NULL,
            type TEXT DEFAULT 'CHECKING',
            balance REAL DEFAULT 0.0,
            currency TEXT DEFAULT 'EUR',
            bank_name TEXT,
            iban TEXT,
            account_number TEXT,
            card_pan TEXT,
            holder_name TEXT,
            last_statement_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE SET NULL
        )
    ''')
    
    # Safe migration: add metadata columns to accounts if missing
    cursor.execute("PRAGMA table_info(accounts)")
    acc_cols = [col[1] for col in cursor.fetchall()]
    if "bank_name" not in acc_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN bank_name TEXT")
    if "iban" not in acc_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN iban TEXT")
    if "account_number" not in acc_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN account_number TEXT")
    if "card_pan" not in acc_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN card_pan TEXT")
    if "holder_name" not in acc_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN holder_name TEXT")
    if "last_statement_date" not in acc_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN last_statement_date TEXT")
    if "created_at" not in acc_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN created_at TIMESTAMP")
    if "is_shared" not in acc_cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN is_shared BOOLEAN DEFAULT 0")
    
    # 6. Transactions Table (Enriched with Macro-Families, Sub-categories, Tags & Hash)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            profile_id INTEGER,
            account_id INTEGER,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            sub_category TEXT,
            description TEXT,
            raw_description TEXT,
            is_transfer BOOLEAN DEFAULT 0,
            is_shared BOOLEAN DEFAULT 0,
            tags TEXT,
            import_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE SET NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE SET NULL
        )
    ''')
    
    # Safe migration: add missing columns to transactions if existing in old schema
    cursor.execute("PRAGMA table_info(transactions)")
    tx_cols = [col[1] for col in cursor.fetchall()]
    if "sub_category" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN sub_category TEXT")
    if "raw_description" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN raw_description TEXT")
    if "tags" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN tags TEXT")
    if "import_hash" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN import_hash TEXT")
    if "is_shared" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN is_shared BOOLEAN DEFAULT 0")
        
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_hash ON transactions(workspace_id, import_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(workspace_id, date)")

    # 7. Category Rules Table (User auto-learning rules)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS category_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            pattern TEXT NOT NULL,
            category TEXT NOT NULL,
            sub_category TEXT,
            tags TEXT,
            match_type TEXT DEFAULT 'CONTAINS', -- 'CONTAINS', 'EXACT', 'REGEX'
            priority INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )
    ''')
    
    # Safe migration: add tags, match_type, priority to category_rules if missing
    cursor.execute("PRAGMA table_info(category_rules)")
    cr_cols = [col[1] for col in cursor.fetchall()]
    if "tags" not in cr_cols:
        cursor.execute("ALTER TABLE category_rules ADD COLUMN tags TEXT")
    if "match_type" not in cr_cols:
        cursor.execute("ALTER TABLE category_rules ADD COLUMN match_type TEXT DEFAULT 'CONTAINS'")
    if "priority" not in cr_cols:
        cursor.execute("ALTER TABLE category_rules ADD COLUMN priority INTEGER DEFAULT 10")
        
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cat_rules_ws ON category_rules(workspace_id, pattern)")
    
    # 7.1. Workspace Smart Personalization (AI Profiling & Context Tags)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workspace_personalization (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER UNIQUE NOT NULL,
            children_names TEXT,
            pets_names TEXT,
            housing_type TEXT DEFAULT 'MUTUO',
            mortgage_bank TEXT,
            vehicle_types TEXT,
            employment_type TEXT DEFAULT 'DIPENDENTE',
            has_pension_fund BOOLEAN DEFAULT 0,
            onboarding_completed BOOLEAN DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
        )
    ''')
    
    # 7.2. Paystubs Table (Cedolini)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS paystubs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            gross_amount REAL NOT NULL,
            net_amount REAL NOT NULL,
            base_salary REAL DEFAULT 0.0,
            contingenza REAL DEFAULT 0.0,
            superminimo REAL DEFAULT 0.0,
            scatti_anzianita REAL DEFAULT 0.0,
            overtime_amount REAL DEFAULT 0.0,
            bonuses REAL DEFAULT 0.0,
            fringe_benefit REAL DEFAULT 0.0,
            other_additions REAL DEFAULT 0.0,
            inps_tax REAL DEFAULT 0.0,
            irpef_tax REAL DEFAULT 0.0,
            irpef_gross REAL DEFAULT 0.0,
            tax_deductions REAL DEFAULT 0.0,
            irpef_net REAL DEFAULT 0.0,
            regional_tax REAL DEFAULT 0.0,
            municipal_tax REAL DEFAULT 0.0,
            municipal_tax_acc REAL DEFAULT 0.0,
            municipal_tax_saldo REAL DEFAULT 0.0,
            trattamento_integrativo REAL DEFAULT 0.0,
            other_deductions REAL DEFAULT 0.0,
            tfr_month REAL DEFAULT 0.0,
            tfr_fund_type TEXT DEFAULT 'Azienda',
            tfr_accumulated_total REAL DEFAULT 0.0,
            pension_fund_name TEXT DEFAULT 'Azienda',
            pension_fund_contrib_employee REAL DEFAULT 0.0,
            pension_fund_contrib_company REAL DEFAULT 0.0,
            pension_fund_tfr_month REAL DEFAULT 0.0,
            pension_fund_total REAL DEFAULT 0.0,
            ferie_residue_ore REAL DEFAULT 0.0,
            rol_residui_ore REAL DEFAULT 0.0,
            ticket_count REAL DEFAULT 0.0,
            ticket_unit_value REAL DEFAULT 8.0,
            ticket_total_value REAL DEFAULT 0.0,
            matched_tx_id INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            FOREIGN KEY (matched_tx_id) REFERENCES transactions(id) ON DELETE SET NULL
        )
    ''')

    # Safe migration: add missing columns to paystubs table
    cursor.execute("PRAGMA table_info(paystubs)")
    ps_cols = [col[1] for col in cursor.fetchall()]
    new_ps_cols = [
        ("base_salary", "REAL DEFAULT 0.0"),
        ("contingenza", "REAL DEFAULT 0.0"),
        ("superminimo", "REAL DEFAULT 0.0"),
        ("scatti_anzianita", "REAL DEFAULT 0.0"),
        ("overtime_amount", "REAL DEFAULT 0.0"),
        ("bonuses", "REAL DEFAULT 0.0"),
        ("fringe_benefit", "REAL DEFAULT 0.0"),
        ("other_additions", "REAL DEFAULT 0.0"),
        ("irpef_gross", "REAL DEFAULT 0.0"),
        ("tax_deductions", "REAL DEFAULT 0.0"),
        ("irpef_net", "REAL DEFAULT 0.0"),
        ("municipal_tax_acc", "REAL DEFAULT 0.0"),
        ("municipal_tax_saldo", "REAL DEFAULT 0.0"),
        ("trattamento_integrativo", "REAL DEFAULT 0.0"),
        ("other_deductions", "REAL DEFAULT 0.0"),
        ("tfr_month", "REAL DEFAULT 0.0"),
        ("tfr_fund_type", "TEXT DEFAULT 'Azienda'"),
        ("tfr_accumulated_total", "REAL DEFAULT 0.0"),
        ("pension_fund_name", "TEXT DEFAULT 'Azienda'"),
        ("pension_fund_contrib_employee", "REAL DEFAULT 0.0"),
        ("pension_fund_contrib_company", "REAL DEFAULT 0.0"),
        ("pension_fund_tfr_month", "REAL DEFAULT 0.0"),
        ("pension_fund_total", "REAL DEFAULT 0.0"),
        ("ferie_residue_ore", "REAL DEFAULT 0.0"),
        ("rol_residui_ore", "REAL DEFAULT 0.0"),
        ("ticket_count", "REAL DEFAULT 0.0"),
        ("ticket_unit_value", "REAL DEFAULT 8.0"),
        ("ticket_total_value", "REAL DEFAULT 0.0"),
        ("matched_tx_id", "INTEGER"),
        ("notes", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    ]

    for col_name, col_def in new_ps_cols:
        if col_name not in ps_cols:
            cursor.execute(f"ALTER TABLE paystubs ADD COLUMN {col_name} {col_def}")

    # 8. Modello 730 Tax Declarations Table (Dichiarazioni dei Redditi)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tax_declarations_730 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL,
            tax_year INTEGER NOT NULL,
            declaration_year INTEGER NOT NULL,
            taxpayer_name TEXT,
            fiscal_code TEXT,
            is_joint_declaration BOOLEAN DEFAULT 0,
            declaration_type TEXT DEFAULT 'ORDINARIO',
            total_income REAL DEFAULT 0.0,
            principal_residence_deduction REAL DEFAULT 0.0,
            taxable_income REAL DEFAULT 0.0,
            gross_tax REAL DEFAULT 0.0,
            employee_tax_credit REAL DEFAULT 0.0,
            family_tax_credit REAL DEFAULT 0.0,
            total_deductions REAL DEFAULT 0.0,
            net_tax REAL DEFAULT 0.0,
            withholdings_paid REAL DEFAULT 0.0,
            tax_difference REAL DEFAULT 0.0,
            regional_tax_due REAL DEFAULT 0.0,
            municipal_tax_due REAL DEFAULT 0.0,
            municipal_tax_acc REAL DEFAULT 0.0,
            final_refund_or_debit REAL DEFAULT 0.0,
            is_refund BOOLEAN DEFAULT 1,
            medical_expenses REAL DEFAULT 0.0,
            medical_expenses_deductible REAL DEFAULT 0.0,
            mortgage_interest REAL DEFAULT 0.0,
            pension_fund_deduction REAL DEFAULT 0.0,
            building_renovations REAL DEFAULT 0.0,
            other_expenses_total REAL DEFAULT 0.0,
            details_json TEXT,
            matched_paystub_id INTEGER,
            pdf_filename TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            FOREIGN KEY (matched_paystub_id) REFERENCES paystubs(id) ON DELETE SET NULL
        )
    ''')


    # 9. Global Category Master Rules (Global AI & Pattern Intelligence)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS global_category_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL,
            sub_category TEXT,
            tags TEXT,
            match_type TEXT DEFAULT 'CONTAINS', -- 'CONTAINS', 'EXACT', 'REGEX'
            priority INTEGER DEFAULT 10,
            is_tax_deductible BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 10. System Audit Logs (Action trail for compliance and support)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_user_id INTEGER,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON system_audit_logs(created_at DESC)")

    # 11. System Broadcast Announcements
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            level TEXT DEFAULT 'INFO', -- 'INFO', 'WARNING', 'DANGER'
            is_active BOOLEAN DEFAULT 1,
            start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 12. Workspace & Family Member Invitations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workspace_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL,
            inviter_user_id INTEGER NOT NULL,
            invite_token TEXT UNIQUE NOT NULL,
            target_email TEXT,
            target_name TEXT,
            status TEXT DEFAULT 'PENDING', -- 'PENDING', 'ACCEPTED', 'EXPIRED', 'REVOKED'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            FOREIGN KEY (inviter_user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invitation_token ON workspace_invitations(invite_token)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invitation_profile ON workspace_invitations(profile_id, status)")

    # Seed Default Super-Admin if none exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'SUPER_ADMIN'")
    if cursor.fetchone()[0] == 0:
        default_email = os.environ.get("ADMIN_EMAIL", "admin@fiscmoney.it").strip().lower()
        raw_password = os.environ.get("ADMIN_PASSWORD", "FiscMoney2026Admin!")
        default_name = os.environ.get("ADMIN_NAME", "Leopoldo Admin")
        default_pwd = generate_password_hash(raw_password)
        cursor.execute('''
            INSERT INTO users (email, password_hash, full_name, role, subscription_plan, subscription_status)
            VALUES (?, ?, ?, 'SUPER_ADMIN', 'LIFETIME', 'ACTIVE')
        ''', (default_email, default_pwd, default_name))
        
        admin_id = cursor.lastrowid
        cursor.execute("INSERT INTO workspaces (name, type) VALUES ('Workspace Admin', 'SINGLE')")
        ws_id = cursor.lastrowid
        cursor.execute("INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (?, ?, 'OWNER')", (ws_id, admin_id))
        cursor.execute("INSERT INTO profiles (workspace_id, name, is_primary) VALUES (?, 'Admin', 1)", (ws_id,))

    # Seed or Update Master Global Rules
    seed_or_update_global_rules(cursor)

    conn.commit()
    conn.close()

def seed_or_update_global_rules(cursor=None):
    """Populates or updates the master baseline global category rules."""
    should_close = False
    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor()
        should_close = True

    default_global_rules = [
        # 1. Spesa & Alimentari
        ("ESSELUNGA", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("CONAD", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("COOP", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("IPERCOOP", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("TIGRE", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("CARREFOUR", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("LIDL", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("EUROSPIN", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("DESPAR", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("PAM", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("MD SPA", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("PENNY MARKET", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("BENNET", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("CRAI", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("NATURASI", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("IPERAL", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("FAMILA", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("TODIS", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("IN'S MERCATO", "Spesa & Alimentari", "Supermercato", "#supermercato", "CONTAINS", 15, 0),
        ("PANIFICIO", "Spesa & Alimentari", "Panetteria & Forno", "#panetteria_forno", "CONTAINS", 12, 0),
        ("PANETTERIA", "Spesa & Alimentari", "Panetteria & Forno", "#panetteria_forno", "CONTAINS", 12, 0),
        ("MACELLERIA", "Spesa & Alimentari", "Macelleria", "#macelleria", "CONTAINS", 12, 0),
        ("PESCHERIA", "Spesa & Alimentari", "Pescheria", "#pescheria", "CONTAINS", 12, 0),
        ("ORTOFRUTTA", "Spesa & Alimentari", "Ortofrutta", "#frutta_verdura", "CONTAINS", 12, 0),

        # 2. Casa, Utenze & Immobili
        ("MUTUO", "Casa & Immobili", "Mutuo", "#mutuo #casa", "CONTAINS", 25, 1),
        ("AFFITTO", "Casa & Immobili", "Affitto", "#affitto #casa", "CONTAINS", 25, 0),
        ("CONDOMINIO", "Casa & Immobili", "Condominio", "#condominio", "CONTAINS", 20, 0),
        ("ACQUA & SAPONE", "Casa & Immobili", "Cura Casa & Igiene", "#curacasa #igiene #detersivi", "CONTAINS", 18, 0),
        ("ACQUA E SAPONE", "Casa & Immobili", "Cura Casa & Igiene", "#curacasa #igiene #detersivi", "CONTAINS", 18, 0),
        ("RISPARMIO CASA", "Casa & Immobili", "Cura Casa & Igiene", "#curacasa #igiene #detersivi", "CONTAINS", 18, 0),
        ("TIGOTA", "Casa & Immobili", "Cura Casa & Igiene", "#curacasa #igiene #detersivi", "CONTAINS", 18, 0),
        ("CADDY'S", "Casa & Immobili", "Cura Casa & Igiene", "#curacasa #igiene #detersivi", "CONTAINS", 18, 0),
        ("IPERSOAP", "Casa & Immobili", "Cura Casa & Igiene", "#curacasa #igiene #detersivi", "CONTAINS", 18, 0),
        ("PRODET", "Casa & Immobili", "Cura Casa & Igiene", "#curacasa #igiene #detersivi", "CONTAINS", 18, 0),
        ("LEROY MERLIN", "Casa & Immobili", "Arredo & Brico", "#brico #faidate #casa", "CONTAINS", 18, 0),
        ("BRICO", "Casa & Immobili", "Arredo & Brico", "#brico #faidate #casa", "CONTAINS", 15, 0),
        ("BRICOMAN", "Casa & Immobili", "Arredo & Brico", "#brico #faidate #casa", "CONTAINS", 18, 0),
        ("TECNOMAT", "Casa & Immobili", "Arredo & Brico", "#brico #faidate #casa", "CONTAINS", 18, 0),
        ("OBI", "Casa & Immobili", "Arredo & Brico", "#brico #faidate #casa", "CONTAINS", 15, 0),
        ("IKEA", "Casa & Immobili", "Arredo & Brico", "#arredo #mobili #casa", "CONTAINS", 18, 0),
        ("MONDO CONVENIENZA", "Casa & Immobili", "Arredo & Brico", "#arredo #mobili #casa", "CONTAINS", 18, 0),
        ("MAISONS DU MONDE", "Casa & Immobili", "Arredo & Brico", "#arredo #mobili #casa", "CONTAINS", 18, 0),
        ("POLTRONESOFA", "Casa & Immobili", "Arredo & Brico", "#arredo #mobili #casa", "CONTAINS", 18, 0),

        # 3. Bollette & Utenze
        ("ENEL", "Bollette & Utenze", "Luce & Gas", "#luce #bollette", "CONTAINS", 22, 0),
        ("SERVIZIO ELETTRICO", "Bollette & Utenze", "Luce & Gas", "#luce #bollette", "CONTAINS", 22, 0),
        ("OCTOPUS ENERGY", "Bollette & Utenze", "Luce & Gas", "#luce #bollette", "CONTAINS", 22, 0),
        ("SORGENIA", "Bollette & Utenze", "Luce & Gas", "#luce #bollette", "CONTAINS", 22, 0),
        ("EDISON", "Bollette & Utenze", "Luce & Gas", "#luce #bollette", "CONTAINS", 22, 0),
        ("A2A ENERGIA", "Bollette & Utenze", "Luce & Gas", "#luce #bollette", "CONTAINS", 22, 0),
        ("PLENITUDE", "Bollette & Utenze", "Gas", "#gas #bollette", "CONTAINS", 22, 0),
        ("ENI PLENITUDE", "Bollette & Utenze", "Gas", "#gas #bollette", "CONTAINS", 22, 0),
        ("ITALGAS", "Bollette & Utenze", "Gas", "#gas #bollette", "CONTAINS", 22, 0),
        ("ACQUEDOTTO", "Bollette & Utenze", "Acqua & Rifiuti", "#acqua #bollette", "CONTAINS", 22, 0),
        ("ACEA", "Bollette & Utenze", "Acqua & Rifiuti", "#acqua #bollette", "CONTAINS", 22, 0),
        ("PUBLIACQUA", "Bollette & Utenze", "Acqua & Rifiuti", "#acqua #bollette", "CONTAINS", 22, 0),
        ("ABBANOA", "Bollette & Utenze", "Acqua & Rifiuti", "#acqua #bollette", "CONTAINS", 22, 0),
        ("SMAT", "Bollette & Utenze", "Acqua & Rifiuti", "#acqua #bollette", "CONTAINS", 22, 0),
        ("TARI", "Bollette & Utenze", "Acqua & Rifiuti", "#tari #rifiuti", "CONTAINS", 22, 0),

        # 4. Auto & Mobilità
        ("ENI STATION", "Auto & Mobilità", "Carburante & Ricarica", "#carburante", "CONTAINS", 18, 0),
        ("Q8", "Auto & Mobilità", "Carburante & Ricarica", "#carburante", "CONTAINS", 18, 0),
        ("IP GRUPPO", "Auto & Mobilità", "Carburante & Ricarica", "#carburante", "CONTAINS", 18, 0),
        ("ESSO", "Auto & Mobilità", "Carburante & Ricarica", "#carburante", "CONTAINS", 18, 0),
        ("TAMOIL", "Auto & Mobilità", "Carburante & Ricarica", "#carburante", "CONTAINS", 18, 0),
        ("REPSOL", "Auto & Mobilità", "Carburante & Ricarica", "#carburante", "CONTAINS", 18, 0),
        ("ENEL X WAY", "Auto & Mobilità", "Carburante & Ricarica", "#carburante", "CONTAINS", 18, 0),
        ("TESLA SUPERCHARGER", "Auto & Mobilità", "Carburante & Ricarica", "#carburante", "CONTAINS", 18, 0),
        ("TELEPASS", "Auto & Mobilità", "Telepass & Pedaggi", "#telepass #pedaggi", "CONTAINS", 22, 0),
        ("UNIPOLMOVE", "Auto & Mobilità", "Telepass & Pedaggi", "#telepass #pedaggi", "CONTAINS", 22, 0),
        ("AUTOSTRADE", "Auto & Mobilità", "Telepass & Pedaggi", "#telepass #pedaggi", "CONTAINS", 20, 0),
        ("EASYPARK", "Auto & Mobilità", "Parcheggi & Garage", "#parcheggio", "CONTAINS", 22, 0),
        ("MYCICERO", "Auto & Mobilità", "Parcheggi & Garage", "#parcheggio", "CONTAINS", 22, 0),
        ("MOONEYGO", "Auto & Mobilità", "Parcheggi & Garage", "#parcheggio", "CONTAINS", 22, 0),
        ("APCOA", "Auto & Mobilità", "Parcheggi & Garage", "#parcheggio", "CONTAINS", 22, 0),
        ("PARCHEGGIO", "Auto & Mobilità", "Parcheggi & Garage", "#parcheggio", "CONTAINS", 20, 0),
        ("PARCHEGGI", "Auto & Mobilità", "Parcheggi & Garage", "#parcheggio", "CONTAINS", 20, 0),
        ("SOSTA AUTO", "Auto & Mobilità", "Parcheggi & Garage", "#parcheggio", "CONTAINS", 20, 0),
        ("UNIPOLSAI", "Auto & Mobilità", "Assicurazione", "#assicurazione #auto", "CONTAINS", 22, 0),
        ("ALLIANZ", "Auto & Mobilità", "Assicurazione", "#assicurazione #auto", "CONTAINS", 22, 0),
        ("GENERALI", "Auto & Mobilità", "Assicurazione", "#assicurazione #auto", "CONTAINS", 22, 0),
        ("PRIMA ASSICURAZIONI", "Auto & Mobilità", "Assicurazione", "#assicurazione #auto", "CONTAINS", 22, 0),
        ("ZURICH", "Auto & Mobilità", "Assicurazione", "#assicurazione #auto", "CONTAINS", 22, 0),
        ("BOLLO AUTO", "Auto & Mobilità", "Bollo", "#bollo #auto", "CONTAINS", 25, 0),
        ("GOMMISTA", "Auto & Mobilità", "Cambio Gomme", "#cambiogomme #gommista", "CONTAINS", 20, 0),
        ("CAMBIO GOMME", "Auto & Mobilità", "Cambio Gomme", "#cambiogomme #gommista", "CONTAINS", 20, 0),
        ("REVISIONE", "Auto & Mobilità", "Tagliando & Manutenzione", "#revisione #auto", "CONTAINS", 20, 0),
        ("TAGLIANDO", "Auto & Mobilità", "Tagliando & Manutenzione", "#meccanico #tagliando", "CONTAINS", 20, 0),
        ("NORAUTO", "Auto & Mobilità", "Tagliando & Manutenzione", "#meccanico #tagliando", "CONTAINS", 20, 0),
        ("MIDAS", "Auto & Mobilità", "Tagliando & Manutenzione", "#meccanico #tagliando", "CONTAINS", 20, 0),
        ("AUTOFFICINA", "Auto & Mobilità", "Tagliando & Manutenzione", "#meccanico #tagliando", "CONTAINS", 20, 0),

        # 5. Salute & Benessere (730 Detraibile)
        ("FARMACIA", "Salute & Benessere", "Farmacia & Medicinali", "#detraibile_730 #farmacia", "CONTAINS", 22, 1),
        ("PARAFARMACIA", "Salute & Benessere", "Farmacia & Medicinali", "#detraibile_730 #farmacia", "CONTAINS", 22, 1),
        ("REDCARE", "Salute & Benessere", "Farmacia & Medicinali", "#detraibile_730 #farmacia", "CONTAINS", 20, 1),
        ("SYNLAB", "Salute & Benessere", "Visite Mediche & Esami", "#detraibile_730 #visite_esami", "CONTAINS", 22, 1),
        ("SANTAGOSTINO", "Salute & Benessere", "Visite Mediche & Esami", "#detraibile_730 #visite_esami", "CONTAINS", 22, 1),
        ("ASL", "Salute & Benessere", "Visite Mediche & Esami", "#detraibile_730 #visite_esami", "CONTAINS", 20, 1),
        ("TICKET SANITARIO", "Salute & Benessere", "Visite Mediche & Esami", "#detraibile_730 #visite_esami", "CONTAINS", 25, 1),
        ("STUDIO MEDICO", "Salute & Benessere", "Visite Mediche & Esami", "#detraibile_730 #visite_esami", "CONTAINS", 20, 1),
        ("DENTALPRO", "Salute & Benessere", "Dentista & Ottico", "#detraibile_730 #dentista_ottico", "CONTAINS", 22, 1),
        ("DENTISTA", "Salute & Benessere", "Dentista & Ottico", "#detraibile_730 #dentista_ottico", "CONTAINS", 22, 1),
        ("OTTICA", "Salute & Benessere", "Dentista & Ottico", "#detraibile_730 #dentista_ottico", "CONTAINS", 20, 1),
        ("SALMOIRAGHI", "Salute & Benessere", "Dentista & Ottico", "#detraibile_730 #dentista_ottico", "CONTAINS", 22, 1),
        ("GRANDVISION", "Salute & Benessere", "Dentista & Ottico", "#detraibile_730 #dentista_ottico", "CONTAINS", 22, 1),
        ("VIRGIN ACTIVE", "Salute & Benessere", "Palestra & Sport", "#palestra_sport", "CONTAINS", 18, 0),
        ("MCFIT", "Salute & Benessere", "Palestra & Sport", "#palestra_sport", "CONTAINS", 18, 0),
        ("FITACTIVE", "Salute & Benessere", "Palestra & Sport", "#palestra_sport", "CONTAINS", 18, 0),

        # 6. Shopping & Abbigliamento
        ("ZARA", "Shopping & Abbigliamento", "Abbigliamento & Scarpe", "#abbigliamento", "CONTAINS", 15, 0),
        ("H&M", "Shopping & Abbigliamento", "Abbigliamento & Scarpe", "#abbigliamento", "CONTAINS", 15, 0),
        ("OVS", "Shopping & Abbigliamento", "Abbigliamento & Scarpe", "#abbigliamento", "CONTAINS", 15, 0),
        ("INTIMISSIMI", "Shopping & Abbigliamento", "Abbigliamento & Scarpe", "#abbigliamento", "CONTAINS", 15, 0),
        ("CALZEDONIA", "Shopping & Abbigliamento", "Abbigliamento & Scarpe", "#abbigliamento", "CONTAINS", 15, 0),
        ("TEZENIS", "Shopping & Abbigliamento", "Abbigliamento & Scarpe", "#abbigliamento", "CONTAINS", 15, 0),
        ("DECATHLON", "Shopping & Abbigliamento", "Abbigliamento & Scarpe", "#abbigliamento", "CONTAINS", 18, 0),
        ("ZALANDO", "Shopping & Abbigliamento", "Abbigliamento & Scarpe", "#abbigliamento", "CONTAINS", 18, 0),
        ("ASOS", "Shopping & Abbigliamento", "Abbigliamento & Scarpe", "#abbigliamento", "CONTAINS", 18, 0),
        ("MEDIAWORLD", "Shopping & Abbigliamento", "Elettronica & Gadget", "#elettronica", "CONTAINS", 18, 0),
        ("UNIEURO", "Shopping & Abbigliamento", "Elettronica & Gadget", "#elettronica", "CONTAINS", 18, 0),
        ("EURONICS", "Shopping & Abbigliamento", "Elettronica & Gadget", "#elettronica", "CONTAINS", 18, 0),
        ("APPLE STORE", "Shopping & Abbigliamento", "Elettronica & Gadget", "#elettronica", "CONTAINS", 18, 0),
        ("AMAZON", "Shopping & Abbigliamento", "Acquisti Online Vari", "#amazon_online", "CONTAINS", 12, 0),

        # 7. Ristoranti & Bar
        ("MCDONALD", "Ristoranti & Bar", "Fast Food & Asporto", "#delivery #fastfood", "CONTAINS", 18, 0),
        ("BURGER KING", "Ristoranti & Bar", "Fast Food & Asporto", "#delivery #fastfood", "CONTAINS", 18, 0),
        ("KFC", "Ristoranti & Bar", "Fast Food & Asporto", "#delivery #fastfood", "CONTAINS", 18, 0),
        ("JUST EAT", "Ristoranti & Bar", "Fast Food & Asporto", "#delivery #fastfood", "CONTAINS", 18, 0),
        ("GLOVO", "Ristoranti & Bar", "Fast Food & Asporto", "#delivery #fastfood", "CONTAINS", 18, 0),
        ("DELIVEROO", "Ristoranti & Bar", "Fast Food & Asporto", "#delivery #fastfood", "CONTAINS", 18, 0),
        ("UBER EATS", "Ristoranti & Bar", "Fast Food & Asporto", "#delivery #fastfood", "CONTAINS", 18, 0),
        ("PIZZERIA", "Ristoranti & Bar", "Pizzerie", "#pizzeria", "CONTAINS", 15, 0),
        ("RISTORANTE", "Ristoranti & Bar", "Ristoranti", "#ristorante", "CONTAINS", 15, 0),
        ("TRATTORIA", "Ristoranti & Bar", "Ristoranti", "#ristorante", "CONTAINS", 15, 0),
        ("OSTERIA", "Ristoranti & Bar", "Ristoranti", "#ristorante", "CONTAINS", 15, 0),
        ("SUSHI", "Ristoranti & Bar", "Ristoranti", "#ristorante", "CONTAINS", 15, 0),
        ("POKE", "Ristoranti & Bar", "Ristoranti", "#ristorante", "CONTAINS", 15, 0),
        ("AUTOGRILL", "Ristoranti & Bar", "Bar & Colazioni", "#bar_caffetteria", "CONTAINS", 15, 0),

        # 8. Digitale, Tech & Tel
        ("ILIAD", "Digitale, Tech & Tel", "Telefonia & SIM", "#telefonia", "CONTAINS", 20, 0),
        ("TIM", "Digitale, Tech & Tel", "Telefonia & SIM", "#telefonia", "CONTAINS", 18, 0),
        ("VODAFONE", "Digitale, Tech & Tel", "Telefonia & SIM", "#telefonia", "CONTAINS", 18, 0),
        ("WINDTRE", "Digitale, Tech & Tel", "Telefonia & SIM", "#telefonia", "CONTAINS", 18, 0),
        ("HO. MOBILE", "Digitale, Tech & Tel", "Telefonia & SIM", "#telefonia", "CONTAINS", 20, 0),
        ("KENA", "Digitale, Tech & Tel", "Telefonia & SIM", "#telefonia", "CONTAINS", 20, 0),
        ("FASTWEB", "Digitale, Tech & Tel", "Fibra & Internet Casa", "#fibra_internet", "CONTAINS", 20, 0),
        ("EOLO", "Digitale, Tech & Tel", "Fibra & Internet Casa", "#fibra_internet", "CONTAINS", 20, 0),
        ("SKY WIFI", "Digitale, Tech & Tel", "Fibra & Internet Casa", "#fibra_internet", "CONTAINS", 20, 0),
        ("OPENAI", "Digitale, Tech & Tel", "Tool AI & Software", "#software_ai", "CONTAINS", 22, 0),
        ("CHATGPT", "Digitale, Tech & Tel", "Tool AI & Software", "#software_ai", "CONTAINS", 22, 0),
        ("CLAUDE", "Digitale, Tech & Tel", "Tool AI & Software", "#software_ai", "CONTAINS", 22, 0),
        ("MICROSOFT 365", "Digitale, Tech & Tel", "Tool AI & Software", "#software_ai", "CONTAINS", 22, 0),
        ("NETFLIX", "Digitale, Tech & Tel", "Streaming & Media", "#streaming", "CONTAINS", 22, 0),
        ("SPOTIFY", "Digitale, Tech & Tel", "Streaming & Media", "#streaming", "CONTAINS", 22, 0),
        ("DISNEY PLUS", "Digitale, Tech & Tel", "Streaming & Media", "#streaming", "CONTAINS", 22, 0),
        ("DAZN", "Digitale, Tech & Tel", "Streaming & Media", "#streaming", "CONTAINS", 22, 0),
        ("PRIME VIDEO", "Digitale, Tech & Tel", "Streaming & Media", "#streaming", "CONTAINS", 22, 0),

        # 9. Viaggi & Trasporti
        ("BOOKING.COM", "Viaggi & Tempo Libero", "Hotel & Alloggi", "#hotel_alloggi", "CONTAINS", 20, 0),
        ("AIRBNB", "Viaggi & Tempo Libero", "Hotel & Alloggi", "#hotel_alloggi", "CONTAINS", 20, 0),
        ("RYANAIR", "Viaggi & Tempo Libero", "Voli & Treni Lunghi", "#voli_treni", "CONTAINS", 20, 0),
        ("EASYJET", "Viaggi & Tempo Libero", "Voli & Treni Lunghi", "#voli_treni", "CONTAINS", 20, 0),
        ("WIZZ AIR", "Viaggi & Tempo Libero", "Voli & Treni Lunghi", "#voli_treni", "CONTAINS", 20, 0),
        ("TRENITALIA", "Viaggi & Tempo Libero", "Voli & Treni Lunghi", "#voli_treni", "CONTAINS", 20, 0),
        ("ITALO TRENO", "Viaggi & Tempo Libero", "Voli & Treni Lunghi", "#voli_treni", "CONTAINS", 20, 0),
        ("TICKETONE", "Viaggi & Tempo Libero", "Cinema & Concerti", "#cinema_eventi", "CONTAINS", 20, 0),

        # 10. Lavoro & Entrate
        ("STIPENDIO", "Lavoro & Entrate", "Stipendio", "#stipendio", "CONTAINS", 30, 0),
        ("EMOLUMENTI", "Lavoro & Entrate", "Stipendio", "#stipendio", "CONTAINS", 30, 0),
        ("PENSIONE", "Lavoro & Entrate", "Stipendio", "#stipendio", "CONTAINS", 30, 0),

        # 11. Risparmio & Investimenti
        ("FONDO PENSIONE", "Risparmio & Investimenti", "Fondo Pensione", "#deducibile_pensione", "CONTAINS", 25, 1),
        ("DEGIRO", "Risparmio & Investimenti", "Investimenti & PAC", "#investimenti_pac", "CONTAINS", 20, 0),
        ("DIRECTA", "Risparmio & Investimenti", "Investimenti & PAC", "#investimenti_pac", "CONTAINS", 20, 0),
        ("SCALABLE", "Risparmio & Investimenti", "Investimenti & PAC", "#investimenti_pac", "CONTAINS", 20, 0),
        ("GIROCONTO", "Risparmio & Investimenti", "Giroconto Interno", "#giroconto", "CONTAINS", 25, 0),

        # 12. Tasse & Banche
        ("PRELIEVO ATM", "Tasse, Fisco & Banche", "Prelievo Contante & Bancomat", "#prelievo_contante", "CONTAINS", 25, 0),
        ("PRELIEVO BANCOMAT", "Tasse, Fisco & Banche", "Prelievo Contante & Bancomat", "#prelievo_contante", "CONTAINS", 25, 0),
        ("PRELIEVO CONTANTE", "Tasse, Fisco & Banche", "Prelievo Contante & Bancomat", "#prelievo_contante", "CONTAINS", 25, 0),
        ("POSTAMAT PRELIEVO", "Tasse, Fisco & Banche", "Prelievo Contante & Bancomat", "#prelievo_contante", "CONTAINS", 25, 0),
        ("PRELIEVO", "Tasse, Fisco & Banche", "Prelievo Contante & Bancomat", "#prelievo_contante", "CONTAINS", 15, 0),
        ("F24", "Tasse, Fisco & Banche", "F24 & Imposte", "#f24_imposte", "CONTAINS", 30, 0),
        ("AGENZIA DELLE ENTRATE", "Tasse, Fisco & Banche", "F24 & Imposte", "#f24_imposte", "CONTAINS", 30, 0)
    ]

    for pat, cat, subcat, tags, mtype, prio, is_ded in default_global_rules:
        cursor.execute('''
            INSERT INTO global_category_rules (pattern, category, sub_category, tags, match_type, priority, is_tax_deductible)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pattern) DO UPDATE SET
                category=excluded.category,
                sub_category=excluded.sub_category,
                tags=excluded.tags,
                match_type=excluded.match_type,
                priority=excluded.priority,
                is_tax_deductible=excluded.is_tax_deductible
        ''', (pat, cat, subcat, tags, mtype, prio, is_ded))

    if should_close:
        conn.commit()
        conn.close()

def log_admin_action(admin_user_id=None, action="", target_user_id=None, details="", ip_address="", admin_id=None):
    """Records an administrative action in the system audit log."""
    if admin_user_id is None and admin_id is not None:
        admin_user_id = admin_id
    if admin_user_id is None:
        admin_user_id = 1
    try:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO system_audit_logs (admin_user_id, action, target_user_id, details, ip_address)
            VALUES (?, ?, ?, ?, ?)
        ''', (admin_user_id, action, target_user_id, str(details), str(ip_address)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging admin action: {e}")

def get_active_announcement():
    """Fetches the latest active broadcast announcement."""
    try:
        conn = get_db_connection()
        ann = conn.execute('''
            SELECT * FROM system_announcements 
            WHERE is_active = 1 
            ORDER BY created_at DESC LIMIT 1
        ''').fetchone()
        conn.close()
        return dict(ann) if ann else None
    except Exception as e:
        print(f"Error fetching active announcement: {e}")
        return None

# ---------------------------------------------------------
# WORKSPACE & FAMILY INVITATIONS ENGINE
# ---------------------------------------------------------
def create_workspace_invitation(workspace_id, profile_id, inviter_user_id, target_name=None, target_email=None, expires_in_days=7):
    """Generates a secure cryptographic invite token for a family member profile."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Invalidate previous pending invitations for this profile
    cursor.execute('''
        UPDATE workspace_invitations 
        SET status = 'REVOKED' 
        WHERE workspace_id = ? AND profile_id = ? AND status = 'PENDING'
    ''', (workspace_id, profile_id))
    
    # 2. Generate secure token & expiration
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(days=expires_in_days)).strftime("%Y-%m-%d %H:%M:%S")
    
    if not target_name:
        prof = cursor.execute("SELECT name FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        target_name = prof["name"] if prof else "Membro"

    cursor.execute('''
        INSERT INTO workspace_invitations (workspace_id, profile_id, inviter_user_id, invite_token, target_email, target_name, status, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)
    ''', (workspace_id, profile_id, inviter_user_id, token, target_email, target_name, expires_at))
    
    # Update profile with target_email if provided
    if target_email:
        cursor.execute("UPDATE profiles SET invited_email = ? WHERE id = ?", (target_email, profile_id))

    conn.commit()
    conn.close()
    return token

def get_invitation_by_token(token):
    """Fetches invitation details and validates expiration."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    row = cursor.execute('''
        SELECT i.*, 
               w.name as workspace_name, w.type as workspace_type,
               p.name as profile_name, p.role_title as profile_role, p.linked_user_id,
               u.full_name as inviter_name, u.email as inviter_email
        FROM workspace_invitations i
        JOIN workspaces w ON i.workspace_id = w.id
        JOIN profiles p ON i.profile_id = p.id
        JOIN users u ON i.inviter_user_id = u.id
        WHERE i.invite_token = ?
    ''', (token,)).fetchone()
    
    if not row:
        conn.close()
        return None
        
    inv = dict(row)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Check if expired
    if inv["status"] == "PENDING" and inv["expires_at"] < now_str:
        cursor.execute("UPDATE workspace_invitations SET status = 'EXPIRED' WHERE id = ?", (inv["id"],))
        conn.commit()
        inv["status"] = "EXPIRED"
        
    conn.close()
    return inv

def accept_invitation(token, user_id):
    """Binds an accepted invitation: links user_id to profile and adds to workspace_members."""
    inv = get_invitation_by_token(token)
    if not inv:
        return False, "Invito non valido o inesistente.", None, None
        
    if inv["status"] != "PENDING":
        return False, f"Questo link di invito non è più valido (Stato: {inv['status']}).", None, None
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Bind profile to user
        cursor.execute('''
            UPDATE profiles 
            SET linked_user_id = ?
            WHERE id = ?
        ''', (user_id, inv["profile_id"]))
        
        # 2. Add to workspace_members if not present
        cursor.execute('''
            INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role)
            VALUES (?, ?, 'MEMBER')
        ''', (inv["workspace_id"], user_id))
        
        # 3. Mark invitation as ACCEPTED
        cursor.execute('''
            UPDATE workspace_invitations 
            SET status = 'ACCEPTED'
            WHERE id = ?
        ''', (inv["id"],))
        
        conn.commit()
        conn.close()
        return True, "Invito accettato con successo!", inv["workspace_id"], inv["profile_id"]
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Errore durante l'associazione: {e}", None, None

def get_workspace_personalization(workspace_id):
    """Fetches the AI personalization profile for a workspace."""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM workspace_personalization WHERE workspace_id = ?", 
        (workspace_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        "workspace_id": workspace_id,
        "children_names": "",
        "pets_names": "",
        "housing_type": "MUTUO",
        "mortgage_bank": "",
        "vehicle_types": "Auto, Telepass",
        "employment_type": "DIPENDENTE",
        "has_pension_fund": 0,
        "onboarding_completed": 0
    }

def save_workspace_personalization(workspace_id, data):
    """Creates or updates workspace personalization settings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    children_names = (data.get("children_names") or "").strip()
    pets_names = (data.get("pets_names") or "").strip()
    housing_type = (data.get("housing_type") or "MUTUO").strip()
    mortgage_bank = (data.get("mortgage_bank") or "").strip()
    vehicle_types = (data.get("vehicle_types") or "").strip()
    employment_type = (data.get("employment_type") or "DIPENDENTE").strip()
    has_pension_fund = 1 if data.get("has_pension_fund") in (1, True, "1", "true", "on") else 0
    onboarding_completed = 1 if data.get("onboarding_completed") in (1, True, "1", "true", "on") else 0
    
    cursor.execute('''
        INSERT INTO workspace_personalization (
            workspace_id, children_names, pets_names, housing_type, 
            mortgage_bank, vehicle_types, employment_type, has_pension_fund, onboarding_completed, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(workspace_id) DO UPDATE SET
            children_names = excluded.children_names,
            pets_names = excluded.pets_names,
            housing_type = excluded.housing_type,
            mortgage_bank = excluded.mortgage_bank,
            vehicle_types = excluded.vehicle_types,
            employment_type = excluded.employment_type,
            has_pension_fund = excluded.has_pension_fund,
            onboarding_completed = excluded.onboarding_completed,
            updated_at = CURRENT_TIMESTAMP
    ''', (
        workspace_id, children_names, pets_names, housing_type,
        mortgage_bank, vehicle_types, employment_type, has_pension_fund, onboarding_completed
    ))
    
    conn.commit()
    conn.close()
    return get_workspace_personalization(workspace_id)

if __name__ == "__main__":
    init_db()
    print("Database FiscMoney inizializzato con successo!")
