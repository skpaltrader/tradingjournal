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

def match_column_name(header_name, candidates):
    normalized = re.sub(r'[^a-z0-9]', '', header_name.lower())
    for cand in candidates:
        cand_norm = re.sub(r'[^a-z0-9]', '', cand.lower())
        if cand_norm == normalized or cand_norm in normalized or normalized in cand_norm:
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
    
    date_candidates = ['date', 'time', 'opentime', 'closetime', 'timestamp', 'datetime', 'createdat', 'date/time']
    asset_candidates = ['asset', 'pair', 'currency', 'symbol', 'market', 'instrument']
    dir_candidates = ['direction', 'type', 'action', 'option', 'callput', 'side', 'tradetype']
    invest_candidates = ['investment', 'invest', 'amount', 'stake', 'volume', 'value', 'size']
    payout_candidates = ['payout', 'payoutrate', 'profitpercent', 'returnpercent', 'yield']
    profit_candidates = ['profit', 'netprofit', 'pnl', 'income', 'payoutamount', 'netincome', 'return']
    result_candidates = ['result', 'status', 'outcome', 'state', 'dealresult', 'traderesult']
    id_candidates = ['id', 'dealid', 'tradeid', 'ticket', 'order', 'deal']
    open_candidates = ['openprice', 'openingquote', 'entryprice', 'openquote', 'strike']
    close_candidates = ['closeprice', 'closingquote', 'exitprice', 'closequote']

    for idx, col in enumerate(header):
        if not col:
            continue
        if col_map['id'] is None and match_column_name(col, id_candidates):
            col_map['id'] = idx
        elif col_map['date_time'] is None and match_column_name(col, date_candidates):
            col_map['date_time'] = idx
        elif col_map['asset'] is None and match_column_name(col, asset_candidates):
            col_map['asset'] = idx
        elif col_map['direction'] is None and match_column_name(col, dir_candidates):
            col_map['direction'] = idx
        elif col_map['investment'] is None and match_column_name(col, invest_candidates):
            col_map['investment'] = idx
        elif col_map['payout_rate'] is None and match_column_name(col, payout_candidates):
            col_map['payout_rate'] = idx
        elif col_map['profit'] is None and match_column_name(col, profit_candidates):
            col_map['profit'] = idx
        elif col_map['result'] is None and match_column_name(col, result_candidates):
            col_map['result'] = idx
        elif col_map['open_price'] is None and match_column_name(col, open_candidates):
            col_map['open_price'] = idx
        elif col_map['close_price'] is None and match_column_name(col, close_candidates):
            col_map['close_price'] = idx

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

        if raw_result:
            if any(w in raw_result for w in ['win', 'won', 'profit', 'success', 'itp']):
                result = 'WIN'
            elif any(l in raw_result for l in ['loss', 'lost', 'fail', 'otm']):
                result = 'LOSS'
            elif any(r in raw_result for r in ['refund', 'tie', 'equal', 'push', 'draw', 'void', 'atm', 'neutral', 'return']):
                result = 'REFUND'

        # If profit string explicitly existed
        if raw_profit is not None and raw_profit_str:
            profit = raw_profit
            if result is None:
                if profit > 0:
                    result = 'WIN'
                elif profit < 0:
                    result = 'LOSS'
                else:
                    result = 'REFUND'
        else:
            # Profit was not specified, compute from result
            if result == 'WIN':
                profit = round(investment * (payout_rate / 100.0), 2)
            elif result == 'LOSS':
                profit = round(-investment, 2)
            elif result == 'REFUND':
                profit = 0.0

        # If still undefined, deduce from open and close prices if available
        if result is None:
            if open_p is not None and close_p is not None:
                if direction == 'UP':
                    if close_p > open_p:
                        result = 'WIN'
                        profit = round(investment * (payout_rate / 100.0), 2)
                    elif close_p < open_p:
                        result = 'LOSS'
                        profit = round(-investment, 2)
                    else:
                        result = 'REFUND'
                        profit = 0.0
                else: # DOWN
                    if close_p < open_p:
                        result = 'WIN'
                        profit = round(investment * (payout_rate / 100.0), 2)
                    elif close_p > open_p:
                        result = 'LOSS'
                        profit = round(-investment, 2)
                    else:
                        result = 'REFUND'
                        profit = 0.0
            else:
                # Default to REFUND if unknown
                result = 'REFUND'
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
