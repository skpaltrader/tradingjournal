import sqlite3
import os
import urllib.request
import json
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quotex_trades.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_live_usd_inr_rate():
    """Fetches the latest live USD to INR exchange rate from open API."""
    try:
        req = urllib.request.Request("https://open.er-api.com/v6/latest/USD", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return round(float(data['rates']['INR']), 4)
    except Exception:
        return 95.0757

def ensure_all_exchange_rates():
    """
    Checks all trade dates in trades table and ensures a USD/INR exchange rate is cached
    for every date. Automatically fetches missing historical or future rates.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT substr(date_time, 1, 10) as dt FROM trades ORDER BY dt ASC")
        trade_dates = [r['dt'] for r in cursor.fetchall()]
        if not trade_dates:
            conn.close()
            return
            
        cursor.execute("SELECT date FROM exchange_rates")
        cached = set(r['date'] for r in cursor.fetchall())
        conn.close()

        missing = [d for d in trade_dates if d not in cached]
        today_str = datetime.now().strftime('%Y-%m-%d')
        if today_str not in cached:
            missing.append(today_str)

        if not missing:
            return

        start_d = min(missing)
        end_d = max(missing)
        rates_map = {}
        try:
            url = f"https://api.frankfurter.dev/v1/{start_d}..{end_d}?from=USD&to=INR"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for d, r in data.get('rates', {}).items():
                    rates_map[d] = round(float(r['INR']), 4)
        except Exception as e:
            print(f"Forex fetch notice: {e}")

        live_rate = fetch_live_usd_inr_rate()
        conn = get_connection()
        cursor = conn.cursor()
        known_dates = sorted(rates_map.keys())
        
        for d in missing:
            if d in rates_map:
                r = rates_map[d]
            else:
                preceding = [kd for kd in known_dates if kd <= d]
                r = rates_map[preceding[-1]] if preceding else live_rate
            cursor.execute("INSERT OR REPLACE INTO exchange_rates (date, usd_inr_rate) VALUES (?, ?)", (d, r))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Warning in ensure_all_exchange_rates: {e}")

def get_all_exchange_rates():
    """Returns a dictionary of all cached exchange rates and latest rate."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT date, usd_inr_rate FROM exchange_rates ORDER BY date ASC")
    rates = {r['date']: r['usd_inr_rate'] for r in cursor.fetchall()}
    conn.close()
    latest = rates.get(datetime.now().strftime('%Y-%m-%d'), 95.0757)
    return rates, latest

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT UNIQUE,
            date_time TEXT NOT NULL,
            asset TEXT NOT NULL,
            direction TEXT NOT NULL,
            investment REAL NOT NULL,
            payout_rate REAL NOT NULL DEFAULT 85.0,
            profit REAL NOT NULL,
            result TEXT NOT NULL,
            open_price REAL,
            close_price REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_date_time ON trades(date_time)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_result ON trades(result)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset ON trades(asset)')
    
    # Files table for tracking uploaded CSVs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            trades_count INTEGER DEFAULT 0,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Exchange rates cache table for seamless USD/INR conversions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exchange_rates (
            date TEXT PRIMARY KEY,
            usd_inr_rate REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Clean up any leftover demo/sample trades
    cursor.execute("DELETE FROM trades WHERE trade_id LIKE 'QX-1000%'")
    conn.commit()

    # Check if trades table is empty
    cursor.execute("SELECT count(*) FROM trades")
    trade_count = cursor.fetchone()[0]
    
    conn.close()

    # Auto-restore authentic trades from quotex_history.csv if database has 0 trades
    if trade_count == 0:
        history_csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quotex_history.csv')
        if os.path.exists(history_csv_path):
            try:
                from csv_parser import parse_quotex_csv
                with open(history_csv_path, 'rb') as f:
                    csv_bytes = f.read()
                trades, err = parse_quotex_csv(csv_bytes)
                if trades:
                    insert_trades_bulk(trades)
                    print(f"Auto-restored {len(trades)} trades from quotex_history.csv on startup.")
            except Exception as e:
                print(f"Warning: could not auto-load quotex_history.csv: {e}")

    # Ensure exchange rates are cached
    ensure_all_exchange_rates()


def insert_trades_bulk(trades_list):
    """
    Inserts a list of trade dictionaries. Ignores duplicates based on trade_id.
    """
    if not trades_list:
        return 0
    conn = get_connection()
    cursor = conn.cursor()
    inserted_count = 0
    for t in trades_list:
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO trades 
                (trade_id, date_time, asset, direction, investment, payout_rate, profit, result, open_price, close_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                t.get('trade_id'),
                t.get('date_time'),
                t.get('asset', 'Unknown'),
                t.get('direction', 'UP'),
                float(t.get('investment', 0.0)),
                float(t.get('payout_rate', 85.0)),
                float(t.get('profit', 0.0)),
                t.get('result', 'REFUND').upper(),
                t.get('open_price'),
                t.get('close_price')
            ))
            if cursor.rowcount > 0:
                inserted_count += 1
        except Exception as e:
            print(f"Error inserting trade {t}: {e}")
            continue
    conn.commit()
    conn.close()
    if inserted_count > 0:
        ensure_all_exchange_rates()
    return inserted_count

def add_single_trade(trade_data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO trades 
        (trade_id, date_time, asset, direction, investment, payout_rate, profit, result, open_price, close_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        trade_data.get('trade_id'),
        trade_data.get('date_time'),
        trade_data.get('asset', 'Unknown'),
        trade_data.get('direction', 'UP'),
        float(trade_data.get('investment', 0.0)),
        float(trade_data.get('payout_rate', 85.0)),
        float(trade_data.get('profit', 0.0)),
        trade_data.get('result', 'REFUND').upper(),
        trade_data.get('open_price'),
        trade_data.get('close_price')
    ))
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trade_id

def clear_all_trades():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM trades')
    conn.commit()
    conn.close()

def cleanup_sample_trades():
    """Removes demo/sample trades (QX-1000...) from the database so they do not contaminate real data."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades WHERE trade_id LIKE 'QX-1000%'")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted

def delete_trade_by_id(trade_pk):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM trades WHERE id = ?', (trade_pk,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def get_timeframe_filter(timeframe):
    """
    Returns SQL where clause and params for timeframe.
    Timeframes: all, today, week, month, 3month, 1year, or None
    """
    now = datetime.now()
    if timeframe == 'today':
        start = now.strftime('%Y-%m-%d 00:00:00')
        return "WHERE date_time >= ?", [start]
    elif timeframe == 'week':
        # Start of current week (Monday)
        start_date = now - timedelta(days=now.weekday())
        start = start_date.strftime('%Y-%m-%d 00:00:00')
        return "WHERE date_time >= ?", [start]
    elif timeframe == 'month':
        start = now.strftime('%Y-%m-01 00:00:00')
        return "WHERE date_time >= ?", [start]
    elif timeframe == '3month':
        start_date = now - timedelta(days=90)
        start = start_date.strftime('%Y-%m-%d 00:00:00')
        return "WHERE date_time >= ?", [start]
    elif timeframe == '1year':
        start_date = now - timedelta(days=365)
        start = start_date.strftime('%Y-%m-%d 00:00:00')
        return "WHERE date_time >= ?", [start]
    return "", []

def get_stats(timeframe='all', start_date=None, end_date=None, currency='INR'):
    conn = get_connection()
    cursor = conn.cursor()
    
    where_clause = ""
    params = []
    
    if start_date and end_date:
        where_clause = "WHERE t.date_time >= ? AND t.date_time <= ?"
        params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
    elif timeframe != 'all':
        wc, params = get_timeframe_filter(timeframe)
        where_clause = wc.replace('date_time', 't.date_time')
        
    is_usd = (currency and currency.upper() == 'USD')
    
    if is_usd:
        query = f'''
            SELECT 
                COUNT(*) as total_trades,
                COUNT(DISTINCT substr(t.date_time, 1, 10)) as trading_days,
                SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
                COALESCE(SUM(t.profit / COALESCE(er.usd_inr_rate, 95.0757)), 0) as total_pnl,
                COALESCE(SUM(t.investment / COALESCE(er.usd_inr_rate, 95.0757)), 0) as total_volume,
                COALESCE(SUM(CASE WHEN t.result = 'WIN' THEN (t.profit / COALESCE(er.usd_inr_rate, 95.0757)) ELSE 0 END), 0) as gross_profit,
                COALESCE(SUM(CASE WHEN t.result = 'LOSS' THEN ABS(t.profit / COALESCE(er.usd_inr_rate, 95.0757)) ELSE 0 END), 0) as gross_loss,
                COALESCE(MAX(t.profit / COALESCE(er.usd_inr_rate, 95.0757)), 0) as best_trade,
                COALESCE(MIN(t.profit / COALESCE(er.usd_inr_rate, 95.0757)), 0) as worst_trade
            FROM trades t
            LEFT JOIN exchange_rates er ON er.date = substr(t.date_time, 1, 10)
            {where_clause}
        '''
    else:
        query = f'''
            SELECT 
                COUNT(*) as total_trades,
                COUNT(DISTINCT substr(t.date_time, 1, 10)) as trading_days,
                SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
                COALESCE(SUM(t.profit), 0) as total_pnl,
                COALESCE(SUM(t.investment), 0) as total_volume,
                COALESCE(SUM(CASE WHEN t.result = 'WIN' THEN t.profit ELSE 0 END), 0) as gross_profit,
                COALESCE(SUM(CASE WHEN t.result = 'LOSS' THEN ABS(t.profit) ELSE 0 END), 0) as gross_loss,
                COALESCE(MAX(t.profit), 0) as best_trade,
                COALESCE(MIN(t.profit), 0) as worst_trade
            FROM trades t
            {where_clause}
        '''
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    
    if not row or row['total_trades'] == 0:
        return {
            'total_trades': 0,
            'trading_days': 0,
            'wins': 0,
            'losses': 0,
            'refunds': 0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'expectancy': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0,
            'total_pnl': 0.0,
            'total_volume': 0.0,
            'avg_daily_volume': 0.0,
            'currency': 'USD' if is_usd else 'INR'
        }
        
    total_trades = row['total_trades']
    trading_days = row['trading_days'] or 1
    wins = row['wins'] or 0
    losses = row['losses'] or 0
    refunds = row['refunds'] or 0
    total_pnl = round(row['total_pnl'] or 0.0, 2)
    total_volume = round(row['total_volume'] or 0.0, 2)
    avg_daily_volume = round(total_volume / trading_days, 2) if trading_days > 0 else 0.0
    gross_profit = row['gross_profit'] or 0.0
    gross_loss = row['gross_loss'] or 0.0
    
    # Win rate calculation
    decisive_trades = wins + losses
    win_rate = round((wins / decisive_trades * 100), 2) if decisive_trades > 0 else 0.0
    
    # Profit factor
    if gross_loss > 0:
        profit_factor = round(gross_profit / gross_loss, 2)
    elif gross_profit > 0:
        profit_factor = round(gross_profit, 2)
    else:
        profit_factor = 0.0
        
    avg_win = round(gross_profit / wins, 2) if wins > 0 else 0.0
    avg_loss = round(gross_loss / losses, 2) if losses > 0 else 0.0
    expectancy = round(total_pnl / total_trades, 2) if total_trades > 0 else 0.0
    
    return {
        'total_trades': total_trades,
        'trading_days': trading_days,
        'wins': wins,
        'losses': losses,
        'refunds': refunds,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'expectancy': expectancy,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'best_trade': round(row['best_trade'] or 0.0, 2),
        'worst_trade': round(row['worst_trade'] or 0.0, 2),
        'total_pnl': total_pnl,
        'total_volume': total_volume,
        'avg_daily_volume': avg_daily_volume,
        'currency': 'USD' if is_usd else 'INR'
    }

def get_equity_curve(timeframe='all', start_date=None, end_date=None, currency='INR'):
    """
    Returns time series of cumulative P&L.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    where_clause = ""
    params = []
    if start_date and end_date:
        where_clause = "WHERE t.date_time >= ? AND t.date_time <= ?"
        params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
    elif timeframe != 'all':
        wc, params = get_timeframe_filter(timeframe)
        where_clause = wc.replace('date_time', 't.date_time')
        
    is_usd = (currency and currency.upper() == 'USD')
    if is_usd:
        query = f'''
            SELECT t.date_time, ROUND(t.profit / COALESCE(er.usd_inr_rate, 95.0), 2) as profit, t.result, t.asset
            FROM trades t
            LEFT JOIN exchange_rates er ON er.date = substr(t.date_time, 1, 10)
            {where_clause}
            ORDER BY t.date_time ASC
        '''
    else:
        query = f'''
            SELECT t.date_time, t.profit, t.result, t.asset
            FROM trades t
            {where_clause}
            ORDER BY t.date_time ASC
        '''
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    curve = []
    cumulative = 0.0
    for row in rows:
        cumulative = round(cumulative + row['profit'], 2)
        curve.append({
            'date_time': row['date_time'],
            'profit': row['profit'],
            'balance': cumulative,
            'result': row['result'],
            'asset': row['asset']
        })
    return curve

def get_daily_pnl_chart(timeframe='all', start_date=None, end_date=None, currency='INR'):
    """
    Returns daily aggregated net P&L with dates for bar charts.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    where_clause = ""
    params = []
    if start_date and end_date:
        where_clause = "WHERE t.date_time >= ? AND t.date_time <= ?"
        params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
    elif timeframe != 'all':
        wc, params = get_timeframe_filter(timeframe)
        where_clause = wc.replace('date_time', 't.date_time')
        
    is_usd = (currency and currency.upper() == 'USD')
    if is_usd:
        query = f'''
            SELECT 
                substr(t.date_time, 1, 10) as day,
                ROUND(SUM(t.profit / COALESCE(er.usd_inr_rate, 95.0757)), 2) as daily_pnl,
                ROUND(SUM(t.investment / COALESCE(er.usd_inr_rate, 95.0757)), 2) as daily_volume,
                COUNT(*) as trades_count,
                SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as refunds
            FROM trades t
            LEFT JOIN exchange_rates er ON er.date = substr(t.date_time, 1, 10)
            {where_clause}
            GROUP BY day
            ORDER BY day ASC
        '''
    else:
        query = f'''
            SELECT 
                substr(t.date_time, 1, 10) as day,
                ROUND(SUM(t.profit), 2) as daily_pnl,
                ROUND(SUM(t.investment), 2) as daily_volume,
                COUNT(*) as trades_count,
                SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as refunds
            FROM trades t
            {where_clause}
            GROUP BY day
            ORDER BY day ASC
        '''
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            'date': r['day'],
            'pnl': r['daily_pnl'],
            'volume': r['daily_volume'],
            'trades_count': r['trades_count'],
            'wins': r['wins'],
            'losses': r['losses'],
            'refunds': r['refunds']
        }
        for r in rows
    ]

def get_calendar_heatmap(year_month=None, tab='this_month', start_date=None, end_date=None, range_type=None, currency='INR'):
    """
    Returns daily P&L dictionary for LegendJournal heatmap tabs:
    - this_month: current active month
    - last_month: previous month
    - 3months: last 3 months
    - 6months: last 6 months
    - lifetime: all months with trades
    - custom: user-specified start_date to end_date
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Find most recent month with trades
    cursor.execute("SELECT substr(date_time, 1, 7) as ym FROM trades ORDER BY date_time DESC LIMIT 1")
    row = cursor.fetchone()
    latest_ym = row['ym'] if row else datetime.now().strftime('%Y-%m')
    
    base_ym = year_month if year_month else latest_ym
    by_y, by_m = map(int, base_ym.split('-'))
    
    # Get available months list
    cursor.execute('''
        SELECT DISTINCT substr(date_time, 1, 7) as ym
        FROM trades
        ORDER BY ym DESC
    ''')
    available_months = [r['ym'] for r in cursor.fetchall()]
    
    # Determine target months based on range_type or tab
    target_months = []
    
    if range_type == '3m' or tab == '3months':
        for i in range(2, -1, -1):
            cur_m = by_m - i
            cur_y = by_y
            while cur_m < 1:
                cur_m += 12
                cur_y -= 1
            target_months.append(f"{cur_y:04d}-{cur_m:02d}")
    elif range_type == '12m' or tab in ('12months', '1year'):
        target_months = [f"{by_y:04d}-{i:02d}" for i in range(1, 13)]
    elif tab == 'last_month':
        prev_m = by_m - 1
        prev_y = by_y
        if prev_m < 1:
            prev_m = 12
            prev_y -= 1
        target_months = [f"{prev_y:04d}-{prev_m:02d}"]
    elif tab == '6months':
        for i in range(5, -1, -1):
            cur_m = by_m - i
            cur_y = by_y
            while cur_m < 1:
                cur_m += 12
                cur_y -= 1
            target_months.append(f"{cur_y:04d}-{cur_m:02d}")
    elif tab == 'lifetime':
        cursor.execute("SELECT DISTINCT substr(date_time, 1, 7) as ym FROM trades ORDER BY ym ASC")
        all_months = [r['ym'] for r in cursor.fetchall()]
        target_months = all_months if all_months else [base_ym]
    elif tab == 'custom' and start_date and end_date:
        # Generate all months between start_date and end_date
        sy, sm = map(int, start_date[:7].split('-'))
        ey, em = map(int, end_date[:7].split('-'))
        cur_y, cur_m = sy, sm
        while (cur_y < ey) or (cur_y == ey and cur_m <= em):
            target_months.append(f"{cur_y:04d}-{cur_m:02d}")
            cur_m += 1
            if cur_m > 12:
                cur_m = 1
                cur_y += 1
    elif range_type == '12m':
        target_months = [f"{by_y:04d}-{i:02d}" for i in range(1, 13)]
    else:
        target_months = [base_ym]
        
    months_data = []
    overall_pnl = 0.0
    overall_volume = 0.0
    overall_trades = 0
    overall_wins = 0
    overall_losses = 0
    overall_refunds = 0
    
    is_usd = (currency and currency.upper() == 'USD')
    
    for ym in target_months:
        where_extra = ""
        params = [ym]
        
        if tab == 'custom' and start_date and end_date:
            where_extra = " AND t.date_time >= ? AND t.date_time <= ?"
            params.extend([f"{start_date} 00:00:00", f"{end_date} 23:59:59"])
            
        if is_usd:
            cursor.execute(f'''
                SELECT 
                    substr(t.date_time, 1, 10) as day,
                    ROUND(SUM(t.profit / COALESCE(er.usd_inr_rate, 95.0757)), 2) as pnl,
                    ROUND(SUM(t.investment / COALESCE(er.usd_inr_rate, 95.0757)), 2) as volume,
                    COUNT(*) as trades_count,
                    SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as refunds
                FROM trades t
                LEFT JOIN exchange_rates er ON er.date = substr(t.date_time, 1, 10)
                WHERE substr(t.date_time, 1, 7) = ? {where_extra}
                GROUP BY day
                ORDER BY day ASC
            ''', params)
        else:
            cursor.execute(f'''
                SELECT 
                    substr(t.date_time, 1, 10) as day,
                    ROUND(SUM(t.profit), 2) as pnl,
                    ROUND(SUM(t.investment), 2) as volume,
                    COUNT(*) as trades_count,
                    SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as refunds
                FROM trades t
                WHERE substr(t.date_time, 1, 7) = ? {where_extra}
                GROUP BY day
                ORDER BY day ASC
            ''', params)
        rows = cursor.fetchall()
        
        days_dict = {
            r['day']: {
                'pnl': r['pnl'],
                'volume': r['volume'] or 0.0,
                'trades_count': r['trades_count'],
                'wins': r['wins'],
                'losses': r['losses'],
                'refunds': r['refunds']
            }
            for r in rows
        }
        
        if is_usd:
            cursor.execute(f'''
                SELECT 
                    ROUND(SUM(t.profit / COALESCE(er.usd_inr_rate, 95.0757)), 2) as m_pnl,
                    ROUND(SUM(t.investment / COALESCE(er.usd_inr_rate, 95.0757)), 2) as m_volume,
                    COUNT(*) as m_trades,
                    SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as m_wins,
                    SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as m_losses,
                    SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as m_refunds
                FROM trades t
                LEFT JOIN exchange_rates er ON er.date = substr(t.date_time, 1, 10)
                WHERE substr(t.date_time, 1, 7) = ? {where_extra}
            ''', params)
        else:
            cursor.execute(f'''
                SELECT 
                    ROUND(SUM(t.profit), 2) as m_pnl,
                    ROUND(SUM(t.investment), 2) as m_volume,
                    COUNT(*) as m_trades,
                    SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as m_wins,
                    SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as m_losses,
                    SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as m_refunds
                FROM trades t
                WHERE substr(t.date_time, 1, 7) = ? {where_extra}
            ''', params)
        summary_row = cursor.fetchone()
        
        m_pnl = summary_row['m_pnl'] if summary_row and summary_row['m_pnl'] is not None else 0.0
        m_volume = summary_row['m_volume'] if summary_row and summary_row['m_volume'] is not None else 0.0
        m_trades = summary_row['m_trades'] if summary_row and summary_row['m_trades'] is not None else 0
        m_wins = summary_row['m_wins'] if summary_row and summary_row['m_wins'] is not None else 0
        m_losses = summary_row['m_losses'] if summary_row and summary_row['m_losses'] is not None else 0
        m_refunds = summary_row['m_refunds'] if summary_row and summary_row['m_refunds'] is not None else 0
        
        overall_pnl = round(overall_pnl + m_pnl, 2)
        overall_volume = round(overall_volume + m_volume, 2)
        overall_trades += m_trades
        overall_wins += m_wins
        overall_losses += m_losses
        overall_refunds += m_refunds
        
        # Month name
        ym_year, ym_month = map(int, ym.split('-'))
        dt_obj = datetime(ym_year, ym_month, 1)
        month_name = dt_obj.strftime('%B %Y')
        
        months_data.append({
            'year_month': ym,
            'month_name': month_name,
            'month_pnl': m_pnl,
            'month_volume': round(m_volume, 2),
            'trades_count': m_trades,
            'wins': m_wins,
            'losses': m_losses,
            'refunds': m_refunds,
            'days': days_dict
        })
        
    conn.close()
    
    primary_month_data = months_data[-1] if months_data else {
        'year_month': base_ym,
        'month_pnl': 0.0,
        'month_volume': 0.0,
        'days': {}
    }
    
    return {
        'tab': tab,
        'range_type': range_type or ('1m' if len(target_months) == 1 else f"{len(target_months)}m"),
        'year_month': base_ym,
        'month_pnl': overall_pnl,
        'overall_pnl': overall_pnl,
        'overall_volume': overall_volume,
        'overall_trades': overall_trades,
        'overall_wins': overall_wins,
        'overall_losses': overall_losses,
        'overall_refunds': overall_refunds,
        'days': primary_month_data['days'],
        'months': months_data,
        'available_months': available_months
    }

def get_breakdown(period_type='daily', currency='INR'):
    """
    Returns breakdown list for period_type:
    'daily', 'weekly', 'monthly', '3month', '1year'
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    is_usd = (currency and currency.upper() == 'USD')
    if is_usd:
        vol_col = "ROUND(SUM(t.investment / COALESCE(er.usd_inr_rate, 95.0757)), 2)"
        pnl_col = "ROUND(SUM(t.profit / COALESCE(er.usd_inr_rate, 95.0757)), 2)"
        join_clause = "LEFT JOIN exchange_rates er ON er.date = substr(t.date_time, 1, 10)"
    else:
        vol_col = "ROUND(SUM(t.investment), 2)"
        pnl_col = "ROUND(SUM(t.profit), 2)"
        join_clause = ""
        
    if period_type == 'daily':
        query = f'''
            SELECT 
                substr(t.date_time, 1, 10) as period_label,
                COUNT(*) as total_trades,
                SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
                {vol_col} as total_volume,
                {pnl_col} as net_pnl
            FROM trades t
            {join_clause}
            GROUP BY period_label
            ORDER BY period_label DESC
        '''
        cursor.execute(query)
        rows = cursor.fetchall()
        
    elif period_type == 'weekly':
        # Group by year and week
        query = f'''
            SELECT 
                strftime('%Y-W%W', t.date_time) as period_key,
                MIN(substr(t.date_time, 1, 10)) as week_start,
                MAX(substr(t.date_time, 1, 10)) as week_end,
                COUNT(*) as total_trades,
                SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
                {vol_col} as total_volume,
                {pnl_col} as net_pnl
            FROM trades t
            {join_clause}
            GROUP BY period_key
            ORDER BY period_key DESC
        '''
        cursor.execute(query)
        raw_rows = cursor.fetchall()
        rows = []
        for r in raw_rows:
            label = f"{r['period_key']} ({r['week_start']} to {r['week_end']})"
            rows.append({
                'period_label': label,
                'total_trades': r['total_trades'],
                'wins': r['wins'],
                'losses': r['losses'],
                'refunds': r['refunds'],
                'total_volume': r['total_volume'],
                'net_pnl': r['net_pnl']
            })
            
    elif period_type == 'monthly':
        query = f'''
            SELECT 
                substr(t.date_time, 1, 7) as period_label,
                COUNT(*) as total_trades,
                SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
                {vol_col} as total_volume,
                {pnl_col} as net_pnl
            FROM trades t
            {join_clause}
            GROUP BY period_label
            ORDER BY period_label DESC
        '''
        cursor.execute(query)
        rows = cursor.fetchall()
        
    elif period_type == '3month':
        # Group into quarters: Q1 (01-03), Q2 (04-06), Q3 (07-09), Q4 (10-12)
        query = f'''
            SELECT 
                substr(t.date_time, 1, 4) || ' - Q' || (((CAST(substr(t.date_time, 6, 2) AS INTEGER) - 1) / 3) + 1) as period_label,
                MIN(substr(t.date_time, 1, 7)) as start_month,
                MAX(substr(t.date_time, 1, 7)) as end_month,
                COUNT(*) as total_trades,
                SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
                {vol_col} as total_volume,
                {pnl_col} as net_pnl
            FROM trades t
            {join_clause}
            GROUP BY period_label
            ORDER BY period_label DESC
        '''
        cursor.execute(query)
        raw_rows = cursor.fetchall()
        rows = []
        for r in raw_rows:
            label = f"{r['period_label']} ({r['start_month']} ~ {r['end_month']})"
            rows.append({
                'period_label': label,
                'total_trades': r['total_trades'],
                'wins': r['wins'],
                'losses': r['losses'],
                'refunds': r['refunds'],
                'total_volume': r['total_volume'],
                'net_pnl': r['net_pnl']
            })

    elif period_type == '1year':
        query = f'''
            SELECT 
                substr(t.date_time, 1, 4) as period_label,
                COUNT(*) as total_trades,
                SUM(CASE WHEN t.result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN t.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN t.result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
                {vol_col} as total_volume,
                {pnl_col} as net_pnl
            FROM trades t
            {join_clause}
            GROUP BY period_label
            ORDER BY period_label DESC
        '''
        cursor.execute(query)
        rows = cursor.fetchall()
    else:
        rows = []
        
    conn.close()
    
    result_list = []
    for r in rows:
        wins = r['wins'] or 0
        losses = r['losses'] or 0
        refunds = r['refunds'] or 0
        decisive = wins + losses
        win_rate = round((wins / decisive * 100), 1) if decisive > 0 else 0.0
        net_pnl = r['net_pnl'] or 0.0
        
        result_list.append({
            'period_label': r['period_label'],
            'total_trades': r['total_trades'],
            'wins': wins,
            'losses': losses,
            'refunds': refunds,
            'win_rate': win_rate,
            'total_volume': r['total_volume'] or 0.0,
            'net_pnl': net_pnl,
            'is_positive': net_pnl > 0,
            'is_negative': net_pnl < 0,
            'is_neutral': net_pnl == 0,
            'currency': 'USD' if is_usd else 'INR'
        })
    return result_list

def get_trades(limit=50, offset=0, result_filter=None, asset_filter=None, search=None, currency='INR'):
    conn = get_connection()
    cursor = conn.cursor()
    
    where_clauses = []
    params = []
    
    if result_filter and result_filter.upper() in ['WIN', 'LOSS', 'REFUND']:
        where_clauses.append("t.result = ?")
        params.append(result_filter.upper())
        
    if asset_filter and asset_filter.strip():
        where_clauses.append("t.asset = ?")
        params.append(asset_filter.strip())
        
    if search and search.strip():
        where_clauses.append("(t.asset LIKE ? OR t.trade_id LIKE ?)")
        s = f"%{search.strip()}%"
        params.extend([s, s])
        
    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    
    # Get total count
    count_query = f"SELECT COUNT(*) as total FROM trades t {where_str}"
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()['total']
    
    is_usd = (currency and currency.upper() == 'USD')
    
    # Get rows with exchange rate joined
    data_query = f'''
        SELECT 
            t.id, t.trade_id, t.date_time, t.asset, t.direction, t.investment, t.payout_rate, t.profit, t.result, t.open_price, t.close_price,
            COALESCE(er.usd_inr_rate, 95.0757) as rate
        FROM trades t
        LEFT JOIN exchange_rates er ON er.date = substr(t.date_time, 1, 10)
        {where_str}
        ORDER BY t.date_time DESC, t.id DESC
        LIMIT ? OFFSET ?
    '''
    cursor.execute(data_query, params + [limit, offset])
    rows = cursor.fetchall()
    
    trades_out = []
    for r in rows:
        d = dict(r)
        d['invest_inr'] = d['investment']
        d['profit_inr'] = d['profit']
        rate = d['rate']
        d['invest_usd'] = round(d['investment'] / rate, 2)
        d['profit_usd'] = round(d['profit'] / rate, 2)
        if is_usd:
            d['investment'] = d['invest_usd']
            d['profit'] = d['profit_usd']
        trades_out.append(d)
    
    # Distinct assets for dropdown filter
    cursor.execute("SELECT DISTINCT asset FROM trades ORDER BY asset ASC")
    assets = [r['asset'] for r in cursor.fetchall()]
    
    conn.close()
    
    return {
        'total': total_count,
        'limit': limit,
        'offset': offset,
        'assets': assets,
        'trades': trades_out,
        'currency': 'USD' if is_usd else 'INR'
    }

def get_trade_by_id(trade_id):
    """Retrieves a single trade by its database ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_trade_by_id(trade_id, data):
    """Updates an existing trade record."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Calculate profit if not directly provided
    inv = float(data.get('investment', 0.0))
    payout = float(data.get('payout_rate', 85.0))
    result = str(data.get('result', 'WIN')).upper()
    
    if 'profit' in data and data['profit'] is not None and str(data['profit']).strip() != '':
        profit = float(data['profit'])
    else:
        if result == 'WIN':
            profit = round(inv * (payout / 100.0), 2)
        elif result == 'LOSS':
            profit = -round(inv, 2)
        else:
            profit = 0.0

    cursor.execute('''
        UPDATE trades
        SET date_time = ?, asset = ?, direction = ?, investment = ?, payout_rate = ?, profit = ?, result = ?, open_price = ?, close_price = ?
        WHERE id = ?
    ''', (
        data.get('date_time'),
        data.get('asset'),
        data.get('direction', 'UP').upper(),
        inv,
        payout,
        profit,
        result,
        float(data.get('open_price')) if data.get('open_price') not in (None, '') else None,
        float(data.get('close_price')) if data.get('close_price') not in (None, '') else None,
        trade_id
    ))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

# -------------------------------------------------------------------------
# UPLOADED FILES TRACKING
# -------------------------------------------------------------------------
def add_uploaded_file(filename, original_name, file_size, file_path, trades_count=0):
    """Registers an uploaded file in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO uploaded_files (filename, original_name, file_size, file_path, trades_count)
        VALUES (?, ?, ?, ?, ?)
    ''', (filename, original_name, file_size, file_path, trades_count))
    file_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return file_id

def get_uploaded_files():
    """Returns list of all uploaded files."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, filename, original_name, file_size, file_path, trades_count, uploaded_at
        FROM uploaded_files
        ORDER BY uploaded_at DESC, id DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_uploaded_file_by_id(file_id):
    """Returns metadata for a specific uploaded file."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM uploaded_files WHERE id = ?', (file_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_uploaded_file_by_id(file_id):
    """Deletes an uploaded file record and removes file from disk."""
    file_meta = get_uploaded_file_by_id(file_id)
    if not file_meta:
        return False, "File not found"
    
    # Try deleting physical file
    path = file_meta.get('file_path')
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"Warning: could not delete physical file {path}: {e}")
            
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM uploaded_files WHERE id = ?', (file_id,))
    conn.commit()
    conn.close()
    return True, "File deleted successfully"
