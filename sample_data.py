import random
from datetime import datetime, timedelta
import uuid

ASSETS = [
    'USD/INR (OTC)',
    'EUR/INR (OTC)',
    'GBP/INR (OTC)',
    'USD/BRL (OTC)',
    'EUR/USD',
    'GBP/JPY (OTC)',
    'CAD/CHF (OTC)',
    'USD/INR (OTC)',
    'EUR/INR (OTC)',
    'AUD/CAD (OTC)'
]

STAKES = [350.0, 700.0, 1000.0, 1500.0, 2500.0, 5000.0, 10000.0]

def generate_sample_trades(num_trades=350):
    """
    Generates realistic trade history matching the screenshots:
    ~54% win rate, ~38% loss rate, ~8% refund rate.
    Realistic payouts: 82% to 92%.
    Spans the last 90 to 180 days up to today.
    """
    trades = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=120)
    
    total_seconds = int((end_date - start_date).total_seconds())
    
    # We want a realistic upward equity curve with natural pullbacks like the screenshot
    timestamps = sorted([
        start_date + timedelta(seconds=random.randint(0, total_seconds))
        for _ in range(num_trades)
    ])
    
    for i, dt in enumerate(timestamps):
        asset = random.choice(ASSETS)
        direction = random.choice(['UP', 'DOWN'])
        investment = random.choice(STAKES)
        payout_rate = random.choice([85.0, 88.0, 90.0, 92.0, 95.0])
        
        # 53% win, 40% loss, 7% refund
        rand_val = random.random()
        if rand_val < 0.53:
            result = 'WIN'
            profit = round(investment * (payout_rate / 100.0), 2)
        elif rand_val < 0.93:
            result = 'LOSS'
            profit = round(-investment, 2)
        else:
            result = 'REFUND'
            profit = 0.0
            
        trade_id = f"QX-{1000000 + i}"
        
        trades.append({
            'trade_id': trade_id,
            'date_time': dt.strftime('%Y-%m-%d %H:%M:%S'),
            'asset': asset,
            'direction': direction,
            'investment': investment,
            'payout_rate': payout_rate,
            'profit': profit,
            'result': result,
            'open_price': round(random.uniform(1.0500, 1.3500), 5),
            'close_price': round(random.uniform(1.0500, 1.3500), 5)
        })
        
    return trades

def generate_sample_csv():
    trades = generate_sample_trades(num_trades=80)
    lines = ["Trade ID,Date/Time,Asset,Direction,Investment,Payout %,Result,Profit"]
    for t in trades:
        profit_str = f"+{t['profit']}" if t['profit'] > 0 else f"{t['profit']}"
        lines.append(f"{t['trade_id']},{t['date_time']},{t['asset']},{t['direction']},{t['investment']},{t['payout_rate']}%,{t['result']},{profit_str}")
    return "\n".join(lines)
