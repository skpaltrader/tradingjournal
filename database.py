import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quotex_trades.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
    conn.commit()
    conn.close()

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

def get_stats(timeframe='all', start_date=None, end_date=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    where_clause = ""
    params = []
    
    if start_date and end_date:
        where_clause = "WHERE date_time >= ? AND date_time <= ?"
        params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
    elif timeframe != 'all':
        where_clause, params = get_timeframe_filter(timeframe)
        
    query = f'''
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
            COALESCE(SUM(profit), 0) as total_pnl,
            COALESCE(SUM(investment), 0) as total_volume,
            COALESCE(SUM(CASE WHEN result = 'WIN' THEN profit ELSE 0 END), 0) as gross_profit,
            COALESCE(SUM(CASE WHEN result = 'LOSS' THEN ABS(profit) ELSE 0 END), 0) as gross_loss,
            COALESCE(MAX(profit), 0) as best_trade,
            COALESCE(MIN(profit), 0) as worst_trade
        FROM trades
        {where_clause}
    '''
    cursor.execute(query, params)
    row = cursor.fetchone()
    conn.close()
    
    if not row or row['total_trades'] == 0:
        return {
            'total_trades': 0,
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
            'total_volume': 0.0
        }
        
    total_trades = row['total_trades']
    wins = row['wins'] or 0
    losses = row['losses'] or 0
    refunds = row['refunds'] or 0
    total_pnl = round(row['total_pnl'] or 0.0, 2)
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
        'total_volume': round(row['total_volume'] or 0.0, 2)
    }

def get_equity_curve(timeframe='all', start_date=None, end_date=None):
    """
    Returns time series of cumulative P&L.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    where_clause = ""
    params = []
    if start_date and end_date:
        where_clause = "WHERE date_time >= ? AND date_time <= ?"
        params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
    elif timeframe != 'all':
        where_clause, params = get_timeframe_filter(timeframe)
        
    query = f'''
        SELECT date_time, profit, result, asset
        FROM trades
        {where_clause}
        ORDER BY date_time ASC
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

def get_daily_pnl_chart(timeframe='all', start_date=None, end_date=None):
    """
    Returns daily aggregated net P&L with dates for bar charts.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    where_clause = ""
    params = []
    if start_date and end_date:
        where_clause = "WHERE date_time >= ? AND date_time <= ?"
        params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
    elif timeframe != 'all':
        where_clause, params = get_timeframe_filter(timeframe)
        
    query = f'''
        SELECT 
            substr(date_time, 1, 10) as day,
            ROUND(SUM(profit), 2) as daily_pnl,
            COUNT(*) as trades_count,
            SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'REFUND' THEN 1 ELSE 0 END) as refunds
        FROM trades
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
            'trades_count': r['trades_count'],
            'wins': r['wins'],
            'losses': r['losses'],
            'refunds': r['refunds']
        }
        for r in rows
    ]

def get_calendar_heatmap(year_month=None, tab='this_month', start_date=None, end_date=None, range_type=None):
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
    overall_trades = 0
    overall_wins = 0
    overall_losses = 0
    overall_refunds = 0
    
    for ym in target_months:
        where_extra = ""
        params = [ym]
        
        if tab == 'custom' and start_date and end_date:
            where_extra = " AND date_time >= ? AND date_time <= ?"
            params.extend([f"{start_date} 00:00:00", f"{end_date} 23:59:59"])
            
        cursor.execute(f'''
            SELECT 
                substr(date_time, 1, 10) as day,
                ROUND(SUM(profit), 2) as pnl,
                COUNT(*) as trades_count,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'REFUND' THEN 1 ELSE 0 END) as refunds
            FROM trades
            WHERE substr(date_time, 1, 7) = ? {where_extra}
            GROUP BY day
            ORDER BY day ASC
        ''', params)
        rows = cursor.fetchall()
        
        days_dict = {
            r['day']: {
                'pnl': r['pnl'],
                'trades_count': r['trades_count'],
                'wins': r['wins'],
                'losses': r['losses'],
                'refunds': r['refunds']
            }
            for r in rows
        }
        
        cursor.execute(f'''
            SELECT 
                ROUND(SUM(profit), 2) as m_pnl,
                COUNT(*) as m_trades,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as m_wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as m_losses,
                SUM(CASE WHEN result = 'REFUND' THEN 1 ELSE 0 END) as m_refunds
            FROM trades
            WHERE substr(date_time, 1, 7) = ? {where_extra}
        ''', params)
        summary_row = cursor.fetchone()
        
        m_pnl = summary_row['m_pnl'] if summary_row and summary_row['m_pnl'] is not None else 0.0
        m_trades = summary_row['m_trades'] if summary_row and summary_row['m_trades'] is not None else 0
        m_wins = summary_row['m_wins'] if summary_row and summary_row['m_wins'] is not None else 0
        m_losses = summary_row['m_losses'] if summary_row and summary_row['m_losses'] is not None else 0
        m_refunds = summary_row['m_refunds'] if summary_row and summary_row['m_refunds'] is not None else 0
        
        overall_pnl = round(overall_pnl + m_pnl, 2)
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
        'days': {}
    }
    
    return {
        'tab': tab,
        'range_type': range_type or ('1m' if len(target_months) == 1 else f"{len(target_months)}m"),
        'year_month': base_ym,
        'month_pnl': overall_pnl,
        'overall_pnl': overall_pnl,
        'overall_trades': overall_trades,
        'overall_wins': overall_wins,
        'overall_losses': overall_losses,
        'overall_refunds': overall_refunds,
        'days': primary_month_data['days'],
        'months': months_data,
        'available_months': available_months
    }

def get_breakdown(period_type='daily'):
    """
    Returns breakdown list for period_type:
    'daily', 'weekly', 'monthly', '3month', '1year'
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    if period_type == 'daily':
        query = '''
            SELECT 
                substr(date_time, 1, 10) as period_label,
                COUNT(*) as total_trades,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
                ROUND(SUM(investment), 2) as total_volume,
                ROUND(SUM(profit), 2) as net_pnl
            FROM trades
            GROUP BY period_label
            ORDER BY period_label DESC
        '''
        cursor.execute(query)
        rows = cursor.fetchall()
        
    elif period_type == 'weekly':
        # Group by year and week
        query = '''
            SELECT 
                strftime('%Y-W%W', date_time) as period_key,
                MIN(substr(date_time, 1, 10)) as week_start,
                MAX(substr(date_time, 1, 10)) as week_end,
                COUNT(*) as total_trades,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
                ROUND(SUM(investment), 2) as total_volume,
                ROUND(SUM(profit), 2) as net_pnl
            FROM trades
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
        query = '''
            SELECT 
                substr(date_time, 1, 7) as period_label,
                COUNT(*) as total_trades,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
                ROUND(SUM(investment), 2) as total_volume,
                ROUND(SUM(profit), 2) as net_pnl
            FROM trades
            GROUP BY period_label
            ORDER BY period_label DESC
        '''
        cursor.execute(query)
        rows = cursor.fetchall()

    elif period_type == '3month':
        # Group into quarters: Q1 (01-03), Q2 (04-06), Q3 (07-09), Q4 (10-12)
        query = '''
            SELECT 
                substr(date_time, 1, 4) || ' - Q' || (((CAST(substr(date_time, 6, 2) AS INTEGER) - 1) / 3) + 1) as period_label,
                MIN(substr(date_time, 1, 7)) as start_month,
                MAX(substr(date_time, 1, 7)) as end_month,
                COUNT(*) as total_trades,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
                ROUND(SUM(investment), 2) as total_volume,
                ROUND(SUM(profit), 2) as net_pnl
            FROM trades
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
        query = '''
            SELECT 
                substr(date_time, 1, 4) as period_label,
                COUNT(*) as total_trades,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'REFUND' THEN 1 ELSE 0 END) as refunds,
                ROUND(SUM(investment), 2) as total_volume,
                ROUND(SUM(profit), 2) as net_pnl
            FROM trades
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
            'is_neutral': net_pnl == 0
        })
    return result_list

def get_trades(limit=50, offset=0, result_filter=None, asset_filter=None, search=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    where_clauses = []
    params = []
    
    if result_filter and result_filter.upper() in ['WIN', 'LOSS', 'REFUND']:
        where_clauses.append("result = ?")
        params.append(result_filter.upper())
        
    if asset_filter and asset_filter.strip():
        where_clauses.append("asset = ?")
        params.append(asset_filter.strip())
        
    if search and search.strip():
        where_clauses.append("(asset LIKE ? OR trade_id LIKE ?)")
        s = f"%{search.strip()}%"
        params.extend([s, s])
        
    where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    
    # Get total count
    count_query = f"SELECT COUNT(*) as total FROM trades {where_str}"
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()['total']
    
    # Get rows
    data_query = f'''
        SELECT id, trade_id, date_time, asset, direction, investment, payout_rate, profit, result, open_price, close_price
        FROM trades
        {where_str}
        ORDER BY date_time DESC, id DESC
        LIMIT ? OFFSET ?
    '''
    cursor.execute(data_query, params + [limit, offset])
    rows = cursor.fetchall()
    
    # Distinct assets for dropdown filter
    cursor.execute("SELECT DISTINCT asset FROM trades ORDER BY asset ASC")
    assets = [r['asset'] for r in cursor.fetchall()]
    
    conn.close()
    
    return {
        'total': total_count,
        'limit': limit,
        'offset': offset,
        'assets': assets,
        'trades': [dict(r) for r in rows]
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
