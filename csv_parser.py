import csv
import io
import re
import uuid
from datetime import datetime
from dateutil import parser as date_parser

def clean_number(val):
    """
    Cleans string with currency symbols ($1,234.50, -€50, (500)) into a float.
    """
    if val is None:
        return 0.0
    val_str = str(val).strip()
    if not val_str:
        return 0.0
        
    # Check for accounting style negative: (500.00)
    is_paren_negative = False
    if val_str.startswith('(') and val_str.endswith(')'):
        is_paren_negative = True
        val_str = val_str[1:-1]
        
    # Remove currency symbols and formatting
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
    Parses various date formats to ISO YYYY-MM-DD HH:MM:SS string.
    """
    if not date_str or not str(date_str).strip():
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    s = str(date_str).strip()
    try:
        # Common Quotex format: DD.MM.YYYY HH:MM:SS or YYYY-MM-DD HH:MM:SS
        dt = date_parser.parse(s, dayfirst=True)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        pass
        
    try:
        dt = date_parser.parse(s)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
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
    
    # Map column indexes
    col_map = {
        'id': None,
        'date_time': None,
        'asset': None,
        'direction': None,
        'investment': None,
        'payout_rate': None,
        'profit': None,
        'result': None,
        'open_price': None,
        'close_price': None
    }
    
    category_candidates = [
        ('id', ['ticket', 'dealid', 'tradeid', 'orderid', 'order', 'deal', 'id']),
        ('date_time', ['timeopen', 'opentime', 'datetime', 'timestamp', 'createdat', 'date', 'time', 'closetime', 'timeclose']),
        ('asset', ['asset', 'pair', 'currency', 'symbol', 'market', 'instrument']),
        ('direction', ['direction', 'type', 'action', 'option', 'callput', 'side', 'tradetype']),
        ('open_price', ['openingquote', 'openquote', 'openprice', 'entryprice', 'strike']),
        ('close_price', ['closingquote', 'closequote', 'closeprice', 'exitprice']),
        ('investment', ['investment', 'invest', 'stake', 'amount', 'volume', 'value', 'size']),
        ('profit', ['netprofit', 'profit', 'netincome', 'pnl', 'payoutamount', 'income']),
        ('payout_rate', ['payoutrate', 'payoutpercent', 'profitpercent', 'returnpercent', 'yield', 'payout']),
        ('result', ['result', 'status', 'outcome', 'dealresult', 'traderesult', 'state'])
    ]

    assigned_indices = set()
    # Pass 1: Exact matches for highest priority and accuracy
    for key, cands in category_candidates:
        if col_map[key] is None:
            for idx, col in enumerate(header):
                if idx not in assigned_indices and match_column_exact(col, cands):
                    col_map[key] = idx
                    assigned_indices.add(idx)
                    break

    # Pass 2: Substring / Fuzzy matches for remaining unmapped columns
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
        raw_asset = get_val('asset') or 'EUR/USD'
        raw_dir = get_val('direction').lower()
        raw_invest = clean_number(get_val('investment'))
        raw_payout = clean_number(get_val('payout_rate'))
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
        elif raw_payout <= 1.0: # like 0.85
            payout_rate = raw_payout * 100.0
        else:
            payout_rate = raw_payout

        # Determine Result & Profit
        result = None
        profit = None

        # 1. Explicit Result column if present
        if raw_result:
            if any(w in raw_result for w in ['win', 'won', 'profit', 'success', 'itp']):
                result = 'WIN'
            elif any(l in raw_result for l in ['loss', 'lost', 'fail', 'otm']):
                result = 'LOSS'
            elif any(r in raw_result for r in ['refund', 'tie', 'equal', 'push', 'draw', 'void', 'atm', 'neutral', 'return', 'breakeven', 'even', 'be']):
                result = 'REFUND'

        # 2. Priority 1: Check Breakeven where return amount equals investment (invested 500 -> returned 500: no loss, no gain)
        if result is None and raw_profit is not None and raw_profit_str:
            if abs(raw_profit - investment) < 0.01 and investment > 0:
                result = 'REFUND'
                profit = 0.0

        # 3. Priority 2: Mathematical outcome from Opening Quote vs Closing Quote
        # When opening quote equals closing quote, it is a Breakeven/Tie in binary options
        if result is None and open_p is not None and close_p is not None and open_p > 0 and close_p > 0:
            if abs(close_p - open_p) < 1e-9:
                # Exact same quote -> Breakeven / Tie
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

        # 4. Priority 3: Deduce from raw_profit / payout column
        if result is None:
            if raw_profit is not None and raw_profit_str:
                if raw_profit < 0:
                    result = 'LOSS'
                elif raw_profit > investment:
                    # Gross return > stake -> WIN
                    result = 'WIN'
                elif abs(raw_profit - investment) < 0.01:
                    # Return equals stake (Breakeven / Tie)
                    result = 'REFUND'
                elif raw_profit > 0:
                    # Positive net profit -> WIN
                    result = 'WIN'
                else:
                    # In Quotex and binary brokers, payout/profit of 0 indicates a LOSS
                    result = 'LOSS'
            else:
                result = 'WIN'

        # 5. Compute accurate net profit based on result
        if result == 'WIN':
            if raw_profit is not None and raw_profit_str:
                if raw_profit > investment:
                    # Gross payout (e.g. 925 on 500 investment -> net profit = +425)
                    profit = round(raw_profit - investment, 2)
                elif raw_profit > 0:
                    # Already net profit (e.g. +425)
                    profit = round(raw_profit, 2)
                else:
                    profit = round(investment * (payout_rate / 100.0), 2)
            else:
                profit = round(investment * (payout_rate / 100.0), 2)
        elif result == 'LOSS':
            if raw_profit is not None and raw_profit < 0:
                profit = round(raw_profit, 2)
            else:
                # Binary options loss forfeits the entire stake
                profit = round(-investment, 2)
        else: # REFUND / BREAKEVEN (No loss, no gain)
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
