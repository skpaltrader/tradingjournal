import csv
import io
import re
import uuid
from datetime import datetime
from dateutil import parser as date_parser

def clean_number(val):
    """
    Cleans string with currency symbols ($1,234.50, -50, (500), 92%) into a float.
    """
    if val is None:
        return 0.0
    val_str = str(val).strip()
    if not val_str:
        return 0.0
        
    is_paren_negative = False
    if val_str.startswith('(') and val_str.endswith(')'):
        is_paren_negative = True
        val_str = val_str[1:-1]
        
    # Strip % and non-number chars
    cleaned = re.sub(r'[^\d.\-+]', '', val_str)
    if not cleaned or cleaned in ['-', '+', '.']:
        return 0.0
        
    try:
        num = float(cleaned)
        if is_paren_negative and num > 0:
            num = -num
        return num
    except ValueError:
        return 0.0

def parse_date_string(date_str):
    """
    Parses date formats to ISO YYYY-MM-DD HH:MM:SS string.
    Quotex format is strictly DD-MM-YYYY HH:MM or DD.MM.YYYY HH:MM:SS.
    Uses regex first to guarantee day and month are never swapped.
    """
    if not date_str or not str(date_str).strip():
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    s = str(date_str).strip()
    
    # 1. Match DD-MM-YYYY or DD.MM.YYYY or DD/MM/YYYY with optional HH:MM[:SS]
    m_ddmmyyyy = re.match(
        r'^(\d{1,2})[-./](\d{1,2})[-./](\d{4})(?:[\sT]+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?',
        s
    )
    if m_ddmmyyyy:
        day = int(m_ddmmyyyy.group(1))
        month = int(m_ddmmyyyy.group(2))
        year = int(m_ddmmyyyy.group(3))
        hour = int(m_ddmmyyyy.group(4)) if m_ddmmyyyy.group(4) is not None else 0
        minute = int(m_ddmmyyyy.group(5)) if m_ddmmyyyy.group(5) is not None else 0
        second = int(m_ddmmyyyy.group(6)) if m_ddmmyyyy.group(6) is not None else 0
        
        # Sanity check: valid month (1-12) and day (1-31)
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"

    # 2. Match ISO YYYY-MM-DD or YYYY.MM.DD or YYYY/MM/DD
    m_yyyymmdd = re.match(
        r'^(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?:[\sT]+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?',
        s
    )
    if m_yyyymmdd:
        year = int(m_yyyymmdd.group(1))
        month = int(m_yyyymmdd.group(2))
        day = int(m_yyyymmdd.group(3))
        hour = int(m_yyyymmdd.group(4)) if m_yyyymmdd.group(4) is not None else 0
        minute = int(m_yyyymmdd.group(5)) if m_yyyymmdd.group(5) is not None else 0
        second = int(m_yyyymmdd.group(6)) if m_yyyymmdd.group(6) is not None else 0
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"

    # 3. Fallback to date_parser with dayfirst=True
    try:
        dt = date_parser.parse(s, dayfirst=True)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        pass
        
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def normalize_header(header_name):
    return re.sub(r'[^a-z0-9]', '', str(header_name).lower())

def match_column_exact(header_name, candidates):
    norm = normalize_header(header_name)
    for cand in candidates:
        if normalize_header(cand) == norm:
            return True
    return False

def match_column_fuzzy(header_name, candidates):
    norm = normalize_header(header_name)
    for cand in candidates:
        cand_norm = normalize_header(cand)
        if cand_norm and cand_norm in norm:
            return True
    return False

def parse_quotex_csv(file_content, default_payout=85.0):
    """
    Parses CSV text or bytes and returns list of trade dicts.
    Specially optimized for Quotex's official export columns:
    Info, Profit, ID, Open time, Open Price, Close Time, Close Price, Type, Amount, Income
    """
    if isinstance(file_content, bytes):
        try:
            content_str = file_content.decode('utf-8-sig')
        except UnicodeDecodeError:
            content_str = file_content.decode('latin-1', errors='replace')
    else:
        content_str = str(file_content)

    # Detect delimiter
    sample = content_str[:2048]
    delimiter = ','
    if ';' in sample and sample.count(';') > sample.count(','):
        delimiter = ';'
    elif '\t' in sample and sample.count('\t') > sample.count(','):
        delimiter = '\t'

    reader = csv.reader(io.StringIO(content_str), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return [], "CSV file is empty."

    header = [h.strip() for h in rows[0]]
    norm_headers = [normalize_header(h) for h in header]

    # Check for Quotex official export layout (has Info, Profit (percentage), and Income)
    is_quotex_official = ('info' in norm_headers and ('income' in norm_headers or 'amount' in norm_headers))

    col_map = {
        'id': None,
        'date_time': None,
        'asset': None,
        'direction': None,
        'investment': None,
        'payout_rate': None,
        'profit': None,
        'income': None,
        'result': None,
        'open_price': None,
        'close_price': None
    }

    if is_quotex_official:
        # Precision mapping for Quotex's exact official header scheme
        category_candidates = [
            ('asset', ['info', 'asset', 'pair', 'currency', 'symbol']),
            ('payout_rate', ['profit', 'payoutrate', 'payoutpercent', 'profitpercent', 'yield']),
            ('id', ['id', 'dealid', 'tradeid', 'ticket']),
            ('date_time', ['opentime', 'timeopen', 'datetime', 'timestamp', 'date']),
            ('open_price', ['openprice', 'openingquote', 'entryprice', 'openquote']),
            ('close_price', ['closeprice', 'closingquote', 'exitprice', 'closequote']),
            ('direction', ['type', 'direction', 'action', 'option']),
            ('investment', ['amount', 'investment', 'invest', 'stake']),
            ('income', ['income', 'grossincome', 'payoutamount', 'return'])
        ]
    else:
        category_candidates = [
            ('id', ['ticket', 'dealid', 'tradeid', 'orderid', 'order', 'deal', 'id']),
            ('date_time', ['timeopen', 'opentime', 'datetime', 'timestamp', 'createdat', 'date', 'time', 'closetime']),
            ('asset', ['info', 'asset', 'pair', 'currency', 'symbol', 'market', 'instrument']),
            ('direction', ['direction', 'type', 'action', 'option', 'callput', 'side', 'tradetype']),
            ('open_price', ['openingquote', 'openquote', 'openprice', 'entryprice', 'strike']),
            ('close_price', ['closingquote', 'closequote', 'closeprice', 'exitprice']),
            ('investment', ['investment', 'invest', 'stake', 'amount', 'volume', 'value', 'size']),
            ('profit', ['netprofit', 'profit', 'netincome', 'pnl']),
            ('income', ['income', 'payoutamount', 'grossincome', 'payout', 'return']),
            ('payout_rate', ['payoutrate', 'payoutpercent', 'profitpercent', 'returnpercent', 'yield']),
            ('result', ['result', 'status', 'outcome', 'dealresult', 'traderesult', 'state'])
        ]

    assigned_indices = set()
    # Pass 1: Exact matches
    for key, cands in category_candidates:
        if col_map[key] is None:
            for idx, col in enumerate(header):
                if idx not in assigned_indices and match_column_exact(col, cands):
                    col_map[key] = idx
                    assigned_indices.add(idx)
                    break

    # Pass 2: Fuzzy matches for remaining unmapped columns
    for key, cands in category_candidates:
        if col_map[key] is None:
            for idx, col in enumerate(header):
                if idx not in assigned_indices and match_column_fuzzy(col, cands):
                    col_map[key] = idx
                    assigned_indices.add(idx)
                    break

    trades = []
    
    for row_idx, row in enumerate(rows[1:], start=2):
        if not row or not any(cell.strip() for cell in row):
            continue
            
        def get_val(key):
            idx = col_map[key]
            if idx is not None and idx < len(row):
                return row[idx].strip()
            return ""

        raw_id = get_val('id')
        raw_date = get_val('date_time')
        raw_asset = get_val('asset') or 'USD/INR (OTC)'
        raw_dir = get_val('direction').lower()
        raw_invest = clean_number(get_val('investment'))
        raw_payout = clean_number(get_val('payout_rate'))
        raw_income_str = get_val('income')
        raw_income = clean_number(raw_income_str) if raw_income_str else None
        raw_profit_str = get_val('profit')
        raw_profit = clean_number(raw_profit_str) if raw_profit_str else None
        raw_result = get_val('result').lower()
        open_p = clean_number(get_val('open_price')) if get_val('open_price') else None
        close_p = clean_number(get_val('close_price')) if get_val('close_price') else None

        # Determine Direction
        if any(d in raw_dir for d in ['call', 'up', 'buy', 'high', 'higher', 'green', 'long']):
            direction = 'UP'
        elif any(d in raw_dir for d in ['put', 'down', 'sell', 'low', 'lower', 'red', 'short']):
            direction = 'DOWN'
        else:
            direction = 'UP'

        # Investment fallback
        investment = raw_invest if raw_invest > 0 else 100.0

        # Payout rate fallback
        if raw_payout <= 0:
            payout_rate = default_payout
        elif raw_payout <= 1.0: # e.g. 0.85 -> 85.0%
            payout_rate = raw_payout * 100.0
        else:
            payout_rate = raw_payout

        # Determine Result & Net Profit
        result = None
        profit = None

        # Priority 1: Official Quotex with 'Income' column
        if raw_income is not None:
            if abs(raw_income - investment) < 0.01 and investment > 0:
                result = 'REFUND' # Breakeven: invested 500, returned 500
                profit = 0.0
            elif raw_income > investment:
                result = 'WIN'
                profit = round(raw_income - investment, 2)
            elif raw_income == 0 or raw_income < investment:
                result = 'LOSS'
                profit = round(-investment, 2)
        else:
            # Priority 2: Explicit Result column if present
            if raw_result:
                if any(w in raw_result for w in ['win', 'won', 'profit', 'success', 'itp']):
                    result = 'WIN'
                elif any(l in raw_result for l in ['loss', 'lost', 'fail', 'otm']):
                    result = 'LOSS'
                elif any(r in raw_result for r in ['refund', 'tie', 'equal', 'push', 'draw', 'void', 'atm', 'neutral', 'return', 'breakeven', 'even']):
                    result = 'REFUND'

            # Priority 3: Price comparison (Open quote vs Close quote)
            if result is None and open_p is not None and close_p is not None and open_p > 0 and close_p > 0:
                if abs(close_p - open_p) < 1e-9:
                    result = 'REFUND'
                    profit = 0.0
                elif direction == 'UP':
                    if close_p > open_p:
                        result = 'WIN'
                    else:
                        result = 'LOSS'
                else: # DOWN
                    if close_p < open_p:
                        result = 'WIN'
                    else:
                        result = 'LOSS'

            # Priority 4: Monetary Profit column
            if result is None:
                if raw_profit is not None and raw_profit_str:
                    if raw_profit < 0:
                        result = 'LOSS'
                        profit = raw_profit
                    elif raw_profit > investment:
                        result = 'WIN'
                        profit = round(raw_profit - investment, 2)
                    elif abs(raw_profit - investment) < 0.01:
                        result = 'REFUND'
                        profit = 0.0
                    elif raw_profit > 0:
                        result = 'WIN'
                        profit = raw_profit
                    else:
                        result = 'LOSS'
                        profit = round(-investment, 2)
                else:
                    result = 'WIN'

            # Compute profit based on result if still unset
            if result == 'WIN':
                if profit is None:
                    profit = round(investment * (payout_rate / 100.0), 2)
            elif result == 'LOSS':
                if profit is None:
                    profit = round(-investment, 2)
            else:
                profit = 0.0

        date_time = parse_date_string(raw_date)
        trade_id = raw_id if raw_id else f"QX-{uuid.uuid4().hex[:10].upper()}"

        trades.append({
            'trade_id': trade_id,
            'date_time': date_time,
            'asset': raw_asset,
            'direction': direction,
            'investment': investment,
            'payout_rate': payout_rate,
            'profit': profit,
            'result': result,
            'open_price': open_p,
            'close_price': close_p
        })

    return trades, None
