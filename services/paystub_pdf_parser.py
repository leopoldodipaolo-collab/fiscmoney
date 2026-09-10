import re
import io
from datetime import datetime

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pypdf
except ImportError:
    pypdf = None

ITALIAN_MONTHS = {
    'gennaio': 1, 'gen': 1,
    'febbraio': 2, 'feb': 2,
    'marzo': 3, 'mar': 3,
    'aprile': 4, 'apr': 4,
    'maggio': 5, 'mag': 5,
    'giugno': 6, 'giu': 6,
    'luglio': 7, 'lug': 7,
    'agosto': 8, 'ago': 8,
    'settembre': 9, 'set': 9,
    'ottobre': 10, 'ott': 10,
    'novembre': 11, 'nov': 11,
    'dicembre': 12, 'dic': 12,
    'tredicesima': 13, '13esima': 13, '13ª': 13, '13a': 13,
    'quattordicesima': 14, '14esima': 14, '14ª': 14, '14a': 14,
    'mens.suppl': 13, 'mensilita supplementare': 13, 'acconto mens suppl': 13, 'mens suppl': 13
}

def clean_amount(s):
    """Parses Italian formatted currency strings (e.g., '1.950,50' or '2450.00' or '€ 3.064,44')."""
    if not s:
        return 0.0
    try:
        s = str(s).replace("€", "").replace("EUR", "").strip()
        is_neg = False
        if s.endswith("-") or (s.startswith("(") and s.endswith(")")) or s.startswith("-"):
            is_neg = True
            s = s.replace("-", "").strip("()")
        
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        
        val = float(s)
        return -val if is_neg else val
    except (ValueError, TypeError):
        return 0.0

def extract_text_from_pdf(file_stream_or_path):
    """Extracts raw text and table structures from a PDF."""
    full_text = ""
    tables_data = []

    if isinstance(file_stream_or_path, bytes):
        stream = io.BytesIO(file_stream_or_path)
    else:
        stream = file_stream_or_path

    if pdfplumber:
        try:
            if hasattr(stream, 'seek'):
                stream.seek(0)
            with pdfplumber.open(stream) as pdf:
                for page in pdf.pages:
                    t = page.extract_text(layout=True) or page.extract_text() or ""
                    full_text += t + "\n"
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables_data.extend(page_tables)
            if full_text.strip():
                return full_text, tables_data
        except Exception as e:
            print(f"pdfplumber extraction fallback: {e}")

    if pypdf:
        try:
            if hasattr(stream, 'seek'):
                stream.seek(0)
            reader = pypdf.PdfReader(stream)
            for page in reader.pages:
                full_text += (page.extract_text() or "") + "\n"
        except Exception as e:
            print(f"pypdf extraction error: {e}")

    return full_text, tables_data

def parse_paystub_pdf(file_stream_or_path):
    """
    Intelligently parses Italian paystubs (Zucchetti, TeamSystem, ADP, Inaz, CGN, Datev, etc.)
    Handles regular months and supplementary months (13esima, 14esima, mensilità supplementari).
    """
    text, tables = extract_text_from_pdf(file_stream_or_path)
    if not text:
        return {
            'success': False,
            'error': "Impossibile estrarre testo dal file PDF."
        }

    raw_lower = text.lower()
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    data = {
        'success': True,
        'raw_text_length': len(text),
        'month': None,
        'year': None,
        'is_supplementary': False,
        'supplementary_name': None,
        'payment_date': None,
        'employee_name': None,
        'company_name': None,
        'ccnl': None,
        'base_salary': 0.0,
        'contingenza': 0.0,
        'superminimo': 0.0,
        'scatti_anzianita': 0.0,
        'overtime_amount': 0.0,
        'bonuses': 0.0,
        'fringe_benefit': 0.0,
        'other_additions': 0.0,
        'gross_amount': 0.0,
        'inps_tax': 0.0,
        'irpef_gross': 0.0,
        'tax_deductions': 0.0,
        'irpef_net': 0.0,
        'regional_tax': 0.0,
        'municipal_tax': 0.0,
        'trattamento_integrativo': 0.0,
        'other_deductions': 0.0,
        'net_amount': 0.0,
        'tfr_month': 0.0,
        'tfr_fund_type': 'Azienda',
        'tfr_accumulated_total': 0.0,
        'pension_fund_name': 'Azienda',
        'pension_fund_contrib_employee': 0.0,
        'pension_fund_contrib_company': 0.0,
        'pension_fund_tfr_month': 0.0,
        'pension_fund_total': 0.0,
        'ferie_residue_ore': 0.0,
        'rol_residui_ore': 0.0,
        'ticket_count': 0.0,
        'ticket_unit_value': 8.0,
        'ticket_total_value': 0.0,
        'bank_name': None,
        'iban': None,
        'confidence': {},
        'extracted_highlights': []
    }

    # -------------------------------------------------------------
    # 1. Detect Period (Month, Year, Supplementary Months)
    # -------------------------------------------------------------
    # Check for supplementary keywords
    if 'tredicesima' in raw_lower or '13esima' in raw_lower or '13ª' in raw_lower or '13 mens' in raw_lower:
        data['month'] = 13
        data['is_supplementary'] = True
        data['supplementary_name'] = '13ª Mensilità (Tredicesima)'
    elif 'quattordicesima' in raw_lower or '14esima' in raw_lower or '14ª' in raw_lower or '14 mens' in raw_lower:
        data['month'] = 14
        data['is_supplementary'] = True
        data['supplementary_name'] = '14ª Mensilità (Quattordicesima)'
    elif re.search(r'\b(?:mens\s*suppl|mens\.suppl|acconto\s+mens\s+suppl|mensilit[aà]\s+suppl)\b', raw_lower):
        data['month'] = 13  # Represented in 13 slot or supplementary
        data['is_supplementary'] = True
        data['supplementary_name'] = 'Mensilità Supplementare / Acconto'


    # Check Zucchetti header period: e.g. "PERIODO AGOSTO 2026", "PERIODO LUGLIO 2026", "PERIODO 08/2026"
    per_match = re.search(r'p\s*e\s*r\s*i\s*o\s*d\s*o\s+([a-zà-ú\s\.\_]+?)\s+(\d{4})', raw_lower)
    if per_match:
        m_txt = per_match.group(1).strip()
        y_txt = per_match.group(2).strip()
        data['year'] = int(y_txt)
        if not data['month']:
            for m_k, m_v in ITALIAN_MONTHS.items():
                if m_k in m_txt:
                    data['month'] = m_v
                    break

    # Secondary check for month & year if not found
    if not data['month']:
        for m_name, m_num in ITALIAN_MONTHS.items():
            if re.search(rf'\b{m_name}\b', raw_lower):
                data['month'] = m_num
                break

    # Secondary year search (look for payment date or standard 202X)
    if not data['year']:
        # e.g. payment date 31/08/2026
        dt_m = re.search(r'\b\d{2}/\d{2}/(202[0-9])\b', text)
        if dt_m:
            data['year'] = int(dt_m.group(1))
        else:
            y_search = re.search(r'\b(202[0-9])\b', text)
            if y_search:
                data['year'] = int(y_search.group(1))

    # Payment date & IBAN detection
    pay_m = re.search(r'(it\d{2}\s*[a-z]\s*\d{5}\s*\d{5}\s*[a-z0-9]{12})\s+(\d{2}/\d{2}/\d{4})', raw_lower)
    if pay_m:
        data['iban'] = pay_m.group(1).replace(" ", "").upper()
        data['payment_date'] = pay_m.group(2)
        if not data['year']:
            data['year'] = int(pay_m.group(2).split("/")[2])

    # -------------------------------------------------------------
    # 2. Extract Base Salary Components (Zucchetti / Standard Table)
    # -------------------------------------------------------------
    # Zucchetti patterns: "1000 RETRIBUZIONE BASE 2.583,36", "1023 SUPERMINIMO ASS. 2.404,67", "1025 SCATTI ANZIANITA' 182,05"
    paga_base_m = re.search(r'retribuzione\s+base[^\d\n\r]{0,25}?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if paga_base_m:
        data['base_salary'] = clean_amount(paga_base_m.group(1))

    superm_m = re.search(r'superminimo[^\d\n\r]{0,25}?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if superm_m:
        data['superminimo'] = clean_amount(superm_m.group(1))

    scatti_m = re.search(r'scatti\s+anzianit[^\d\n\r]{0,25}?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if scatti_m:
        data['scatti_anzianita'] = clean_amount(scatti_m.group(1))

    conting_m = re.search(r'\b(?:contingenza|e\.d\.r\.)\b[^\d\n\r]{0,25}?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if conting_m:
        data['contingenza'] = clean_amount(conting_m.group(1))

    # -------------------------------------------------------------
    # 2.b Extract Bonuses / Premi / M.B.O. / Una Tantum
    # -------------------------------------------------------------
    # Matches patterns like:
    # "++ BONUS M.B.O                                                         12.048,45"
    # "1050 BONUS M.B.O. 12.048,45"
    # "PREMIO DI RISULTATO 1.500,00"
    for l in lines:
        l_low = l.lower()
        if any(k in l_low for k in ['bonus', 'm.b.o', 'mbo', 'premio', 'una tantum', 'gratifica', 'incentiv']):
            # Exclude lines that are unrelated (e.g. bonus 100 euro / trattamento integrativo)
            if 'trattamento integrativo' in l_low or 'dl 3/2020' in l_low or 'cuneo' in l_low:
                continue
            amounts = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', l)
            if amounts:
                val = clean_amount(amounts[-1])
                if val > data['bonuses']:
                    data['bonuses'] = val

    if data['bonuses'] > 0:
        data['extracted_highlights'].append(f"Bonus / M.B.O.: € {data['bonuses']:,.2f}")

    # -------------------------------------------------------------
    # 2.c Straordinari / Maggiorazioni
    # -------------------------------------------------------------
    for l in lines:
        l_low = l.lower()
        if any(k in l_low for k in ['straordinar', 'maggioraz', 'lavoro straord']):
            amounts = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', l)
            if amounts:
                val = clean_amount(amounts[-1])
                if val > data['overtime_amount']:
                    data['overtime_amount'] = val

    if data['overtime_amount'] > 0:
        data['extracted_highlights'].append(f"Straordinari: € {data['overtime_amount']:,.2f}")

    # -------------------------------------------------------------
    # 3. Net Amount (Netto a Pagare)
    # -------------------------------------------------------------
    # Match spaced or non-spaced "N e t to a P a g ar e ... EURO 3.064,44"
    net_m = re.search(r'n\s*e\s*t\s*t\s*o[^\d\n\r]{0,100}?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if not net_m:
        net_m = re.search(r'(?:accredito|totale\s+netto|netto\s+in\s+busta)[^\d\n\r]{0,80}?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    
    if net_m:
        data['net_amount'] = clean_amount(net_m.group(1))
        data['extracted_highlights'].append(f"Netto Busta: € {data['net_amount']:,.2f}")

    # -------------------------------------------------------------
    # 4. Gross Total & Totals Line
    # -------------------------------------------------------------
    # Zucchetti line: "T o ta li 5.170,08 2.105,64" (Competenze e Trattenute)
    totali_m = re.search(r't\s*o\s*t\s*a\s*l\s*i\s+(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})\s+(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if totali_m:
        data['gross_amount'] = clean_amount(totali_m.group(1))
    else:
        imp_m = re.search(r'\b(?:totale\s+competenze|imp\.prev\.|imponibile\s+previdenziale|tot\.retribuzione)\b[^\d\n\r]{0,25}?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
        if imp_m:
            data['gross_amount'] = clean_amount(imp_m.group(1))

    # Cross-check gross against sum of components
    sum_comp = round(data['base_salary'] + data['contingenza'] + data['superminimo'] + 
                     data['scatti_anzianita'] + data['overtime_amount'] + data['bonuses'] + 
                     data['other_additions'], 2)
    if data['gross_amount'] < sum_comp:
        data['gross_amount'] = sum_comp

    if data['gross_amount'] > 0:
        data['extracted_highlights'].append(f"Lordo Competenze: € {data['gross_amount']:,.2f}")

    # -------------------------------------------------------------
    # 5. INPS Contributions
    # -------------------------------------------------------------
    # Look for "CTR.INPS DIP.CUD 495,48" or "5154 INPS ... 490,63"
    inps_cud_m = re.search(r'ctr\.inps\s+dip\.cud[^\d\n\r]{0,25}?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if inps_cud_m:
        data['inps_tax'] = clean_amount(inps_cud_m.group(1))
    else:
        inps_line_m = re.search(r'contributi[^\d\n\r]{0,25}?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
        if inps_line_m:
            data['inps_tax'] = clean_amount(inps_line_m.group(1))


    # -------------------------------------------------------------
    # 6. IRPEF & Addizionali
    # -------------------------------------------------------------
    # "IRPEF NETTA MESE 1.282,31" or "7833 IMPOSTA 1.282,31"
    irp_net_m = re.search(r'irpef\s+netta\s+mese\s+([€\s]*\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if not irp_net_m:
        irp_net_m = re.search(r'(?:7833\s+)?imposta\s+([€\s]*\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if irp_net_m:
        data['irpef_net'] = clean_amount(irp_net_m.group(1))

    irp_lorda_m = re.search(r'irpef\s+lorda\s+mese\s+([€\s]*\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if irp_lorda_m:
        data['irpef_gross'] = clean_amount(irp_lorda_m.group(1))

    detr_m = re.search(r'tot\.detraz\.mese\s+([€\s]*\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if detr_m:
        data['tax_deductions'] = clean_amount(detr_m.group(1))

    # Addizionale Regionale (es. "7853 RATA ADD.REG. A.P. 115,74")
    reg_m = re.search(r'add\.reg\.[\w\s\.\']*?([€\s]*\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if reg_m:
        data['regional_tax'] = clean_amount(reg_m.group(1))

    # Addizionale Comunale (es. "RATA ADD.COM. A.P. 20,23" + "RATA ACC.ADD.COM. 11,04")
    mun_saldo_m = re.search(r'rata\s+add\.com\.[\w\s\.\']*?([€\s]*\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    mun_acc_m = re.search(r'rata\s+acc\.add\.com\.[\w\s\.\']*?([€\s]*\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    mun_tot = 0.0
    if mun_saldo_m:
        mun_tot += clean_amount(mun_saldo_m.group(1))
    if mun_acc_m:
        mun_tot += clean_amount(mun_acc_m.group(1))
    if mun_tot > 0:
        data['municipal_tax'] = round(mun_tot, 2)

    # -------------------------------------------------------------
    # 7. TFR & Fondo Pensione (FONDAPI, COMETA, FONCHIM, FONTE, ecc.)
    # -------------------------------------------------------------
    if 'fondapi' in raw_lower:
        data['pension_fund_name'] = 'FONDAPI'
        data['tfr_fund_type'] = 'FONDAPI'
    elif 'cometa' in raw_lower:
        data['pension_fund_name'] = 'COMETA'
        data['tfr_fund_type'] = 'Fondo COMETA'
    elif 'fonchim' in raw_lower:
        data['pension_fund_name'] = 'FONCHIM'
        data['tfr_fund_type'] = 'Fondo Fonchim'
    elif 'fonte' in raw_lower:
        data['pension_fund_name'] = 'FONTE'
        data['tfr_fund_type'] = 'Fondo Fonte'

    # Contributo Dipendente Fondo: "5277 CTR. FONDAPI METAL 2.583,36 7,0000 180,84" or "CONTR. DIP. ... 180,84"
    for l in lines:
        l_low = l.lower()
        if any(k in l_low for k in ['ctr. fondapi', 'ctr. cometa', 'ctr. fonchim', 'ctr. fonte', 'contr. dip', 'fondapi dip', 'cometa dip']):
            amounts = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', l_low)
            if amounts:
                data['pension_fund_contrib_employee'] = clean_amount(amounts[-1])
                break

    # Quota TFR Mese Versata al Fondo
    tfr_m_m = re.search(r'q(?:ta|uota)\s+tfr\s+(?:fondapi|cometa|fonchim|fonte|fondo)?[\w\s\.\']*?([€\s]*\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if not tfr_m_m:
        tfr_m_m = re.search(r'quota\s+tfr\s+([€\s]*\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if tfr_m_m:
        data['tfr_month'] = clean_amount(tfr_m_m.group(1))
        data['pension_fund_tfr_month'] = data['tfr_month']

    # Contributo Datore di Lavoro (Company contribution):
    # If not explicitly on paystub, CCNL Metalmeccanico PMI FONDAPI is 2% of base_salary
    fond_dtr_m = re.search(r'contr\.?\s*(?:dtr|azienda|datoriale)[\w\s\.\,\%]*?(\d{1,3}(?:\.\d{3})*,\d{2})', raw_lower)
    if fond_dtr_m:
        data['pension_fund_contrib_company'] = clean_amount(fond_dtr_m.group(1))
    elif data['pension_fund_name'] != 'Azienda' and data['base_salary'] > 0:
        data['pension_fund_contrib_company'] = round(data['base_salary'] * 0.02, 2)

    # TFR Totale Accumulato / Posizione Fondo: "QUOTA TFR ... Totale 32.590,25"
    tfr_tot_m = re.search(r'quota\s+tfr\s+[\d\.\,]+\s+quota\s+tfr\s+[\d\.\,]+\s+quota\s+tfr\s+([€\s]*\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if not tfr_tot_m:
        tfr_tot_m = re.search(r'tfr\s+teorico\s+totale\s+([€\s]*\d{1,3}(?:\.\d{3})*,\d{2}|\d+\.\d{2})', raw_lower)
    if tfr_tot_m:
        data['tfr_accumulated_total'] = clean_amount(tfr_tot_m.group(1))
        data['pension_fund_total'] = data['tfr_accumulated_total']

    # -------------------------------------------------------------
    # 8. Ferie, ROL, Conto Ore & PAR
    # -------------------------------------------------------------
    # Zucchetti table:
    # FERIE ... Saldo Sp. 12,74
    # P.A.R. ... 48,00
    # CONTO ORE ... 105,50
    ferie_m = re.search(r'ferie\s+[\d\.\,]+\s+[\d\.\,]+\s+[\d\.\,]+\s+(\d{1,3}(?:[\,\.]\d{1,2})?)', raw_lower)
    if ferie_m:
        data['ferie_residue_ore'] = clean_amount(ferie_m.group(1))

    par_m = re.search(r'p\.a\.r\.[\s\d\.\,]+?(\d{1,3}(?:[\,\.]\d{1,2})?)\s*$', raw_lower, re.MULTILINE)
    conto_ore_m = re.search(r'conto\s+ore[\s\d\.\,]+?(\d{1,3}(?:[\,\.]\d{1,2})?)\s*$', raw_lower, re.MULTILINE)
    
    rol_total = 0.0
    if par_m:
        rol_total += clean_amount(par_m.group(1))
    if conto_ore_m:
        rol_total += clean_amount(conto_ore_m.group(1))
    if rol_total > 0:
        data['rol_residui_ore'] = round(rol_total, 2)

    # -------------------------------------------------------------
    # 9. Buoni Pasto Elettronici / Ticket Restaurant (Welfare)
    # -------------------------------------------------------------
    # E.g. "3989 NR. TICKET ELETT. 16,00 16,00 1,0000 25V1" or "BUONI PASTO 18"
    for l in lines:
        l_low = l.lower()
        if any(k in l_low for k in ['ticket elett', 'nr. ticket', 'nr ticket', 'buoni pasto', 'ticket restaurant']):
            # find numbers, skipping 4-digit codes like 3989
            tokens = l_low.replace('nr.', 'nr').split()
            for t in tokens:
                t_clean = t.replace(',', '.')
                try:
                    num = float(t_clean)
                    # Ticket count is usually between 1 and 31
                    if 1 <= num <= 31 and num not in [3989, 1000, 2000]:
                        data['ticket_count'] = num
                        data['ticket_unit_value'] = 8.0 # Standard electronic voucher cap
                        data['ticket_total_value'] = round(num * 8.0, 2)
                        data['extracted_highlights'].append(f"Buoni Pasto: {int(num)} ticket ({data['ticket_total_value']:,.2f} € esentasse)")
                        break
                except ValueError:
                    continue
            if data['ticket_count'] > 0:
                break

    # -------------------------------------------------------------
    # 10. Fallback & Cross-check validation
    # -------------------------------------------------------------
    if data['gross_amount'] == 0.0 and (data['base_salary'] + data['contingenza'] + data['superminimo']) > 0:
        data['gross_amount'] = round(data['base_salary'] + data['contingenza'] + data['superminimo'] + data['scatti_anzianita'], 2)

    if data['tfr_month'] == 0.0 and data['gross_amount'] > 0:
        data['tfr_month'] = round(data['gross_amount'] / 13.5, 2)

    return data

