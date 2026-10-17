import os
import io
import time
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    Response,
    session,
    redirect,
    url_for
)
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from database import (
    init_db,
    insert_trades_bulk,
    add_single_trade,
    clear_all_trades,
    delete_trade_by_id,
    get_trade_by_id,
    update_trade_by_id,
    get_stats,
    get_equity_curve,
    get_daily_pnl_chart,
    get_calendar_heatmap,
    get_breakdown,
    get_trades,
    add_uploaded_file,
    get_uploaded_files,
    get_uploaded_file_by_id,
    delete_uploaded_file_by_id
)
from csv_parser import parse_quotex_csv
from sample_data import generate_sample_trades, generate_sample_csv

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

# Initialize database tables on startup
init_db()

# -------------------------------------------------------------------------
# AUTHENTICATION & SECURITY HOOKS
# -------------------------------------------------------------------------
def verify_credentials(username, password):
    """Verifies credentials against Config settings (supports plain or hashed)."""
    if username != Config.ADMIN_USERNAME:
        return False
    if Config.ADMIN_PASSWORD.startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
        return check_password_hash(Config.ADMIN_PASSWORD, password)
    return password == Config.ADMIN_PASSWORD

@app.before_request
def require_authentication():
    """Protects all routes, pages, and API endpoints behind session authentication."""
    # Allow login, static files, and health check endpoints without authentication
    public_endpoints = ['login', 'static', 'health']
    if request.endpoint in public_endpoints:
        return
    if request.path.startswith('/static/'):
        return

    # Check session
    if not session.get('logged_in'):
        # For API requests, return JSON 401 Unauthorized
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Unauthorized. Please log in first.'}), 401
        # For browser requests, redirect to login page
        return redirect(url_for('login', next=request.path))

@app.route('/login', methods=['GET', 'POST', 'HEAD'])
def login():
    if request.method in ('GET', 'HEAD'):
        if session.get('logged_in'):
            return redirect(url_for('index'))
        return render_template(
            'login.html',
            next_url=request.args.get('next', ''),
            default_user=''
        )
    
    # POST handling
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    next_url = request.form.get('next', '')
    
    if verify_credentials(username, password):
        session['logged_in'] = True
        session['username'] = username
        session.permanent = True  # Keep session active
        
        # Safe redirect
        if next_url and not next_url.startswith('//') and not next_url.startswith('http'):
            return redirect(next_url)
        return redirect(url_for('index'))
    else:
        return render_template(
            'login.html',
            error='Invalid username or password. Please check your credentials and try again.',
            next_url=next_url,
            default_user=username
        )

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'authenticated': bool(session.get('logged_in')),
        'version': '2.0.0'
    })

# -------------------------------------------------------------------------
# DASHBOARD PAGES
# -------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html', username=session.get('username', Config.ADMIN_USERNAME))

# -------------------------------------------------------------------------
# FILE UPLOAD & MANAGEMENT ENDPOINTS
# -------------------------------------------------------------------------
@app.route('/api/upload-csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided in request.'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected.'}), 400
        
    try:
        payout_rate = float(request.form.get('payout', 85.0))
    except (ValueError, TypeError):
        payout_rate = 85.0
        
    try:
        content = file.read()
        original_name = file.filename
        file_size = len(content)
        
        # Save physical file to uploads directory with timestamped unique name
        timestamp_prefix = int(time.time())
        clean_name = secure_filename(original_name) or "trades.csv"
        saved_filename = f"{timestamp_prefix}_{clean_name}"
        saved_file_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
        
        with open(saved_file_path, 'wb') as f:
            f.write(content)
            
        # Parse trades
        trades, err = parse_quotex_csv(content, default_payout=payout_rate)
        if err:
            return jsonify({'success': False, 'error': err}), 400
            
        inserted_count = insert_trades_bulk(trades)
        
        # Register in uploaded_files table
        file_id = add_uploaded_file(
            filename=saved_filename,
            original_name=original_name,
            file_size=file_size,
            file_path=saved_file_path,
            trades_count=inserted_count
        )
        
        return jsonify({
            'success': True,
            'message': f'Successfully uploaded {original_name} and saved {inserted_count} new Quotex trades!',
            'inserted': inserted_count,
            'total_parsed': len(trades),
            'file_id': file_id,
            'filename': original_name
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to process CSV: {str(e)}'}), 500

@app.route('/api/files', methods=['GET'])
def list_files_endpoint():
    """Returns list of uploaded files with metadata."""
    files = get_uploaded_files()
    return jsonify({'success': True, 'files': files})

@app.route('/api/files/download/<int:file_id>', methods=['GET'])
def download_file_endpoint(file_id):
    """Downloads an uploaded file to user's device."""
    file_meta = get_uploaded_file_by_id(file_id)
    if not file_meta or not os.path.exists(file_meta['file_path']):
        return jsonify({'success': False, 'error': 'File not found on server.'}), 404
        
    return send_file(
        file_meta['file_path'],
        as_attachment=True,
        download_name=file_meta['original_name'],
        mimetype='text/csv'
    )

@app.route('/api/files/delete/<int:file_id>', methods=['POST'])
def delete_file_endpoint(file_id):
    """Deletes an uploaded file from disk and database."""
    success, msg = delete_uploaded_file_by_id(file_id)
    return jsonify({'success': success, 'message': msg})

# -------------------------------------------------------------------------
# ANALYTICS & STATS ENDPOINTS
# -------------------------------------------------------------------------
@app.route('/api/stats', methods=['GET'])
def stats_endpoint():
    timeframe = request.args.get('timeframe', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    stats = get_stats(timeframe=timeframe, start_date=start_date, end_date=end_date)
    return jsonify({'success': True, 'stats': stats})

@app.route('/api/equity-curve', methods=['GET'])
def equity_curve_endpoint():
    timeframe = request.args.get('timeframe', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    curve = get_equity_curve(timeframe=timeframe, start_date=start_date, end_date=end_date)
    return jsonify({'success': True, 'data': curve})

@app.route('/api/daily-pnl', methods=['GET'])
def daily_pnl_endpoint():
    timeframe = request.args.get('timeframe', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    data = get_daily_pnl_chart(timeframe=timeframe, start_date=start_date, end_date=end_date)
    return jsonify({'success': True, 'data': data})

@app.route('/api/breakdown', methods=['GET'])
def breakdown_endpoint():
    period_type = request.args.get('type', 'daily') # 'daily', 'weekly', 'monthly', '3month', '1year'
    data = get_breakdown(period_type=period_type)
    return jsonify({'success': True, 'period_type': period_type, 'breakdown': data})

@app.route('/api/heatmap', methods=['GET'])
def heatmap_endpoint():
    month = request.args.get('month') # e.g. '2026-10'
    range_type = request.args.get('range', '1m') # '1m', '3m', '12m'
    tab = request.args.get('tab')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    data = get_calendar_heatmap(year_month=month, tab=tab, start_date=start_date, end_date=end_date, range_type=range_type)
    return jsonify({'success': True, 'heatmap': data})

# -------------------------------------------------------------------------
# TRADE MANAGEMENT ENDPOINTS (VIEW, ADD, EDIT, DELETE)
# -------------------------------------------------------------------------
@app.route('/api/trades', methods=['GET'])
def trades_endpoint():
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    result_filter = request.args.get('result')
    asset_filter = request.args.get('asset')
    search = request.args.get('search')
    
    result = get_trades(limit=limit, offset=offset, result_filter=result_filter, asset_filter=asset_filter, search=search)
    return jsonify({'success': True, 'data': result})

@app.route('/api/trades/<int:trade_id>', methods=['GET'])
def get_single_trade_endpoint(trade_id):
    """Retrieves a single trade for viewing or populating the edit modal."""
    trade = get_trade_by_id(trade_id)
    if not trade:
        return jsonify({'success': False, 'error': 'Trade not found.'}), 404
    return jsonify({'success': True, 'trade': trade})

@app.route('/api/trades/add', methods=['POST'])
def add_trade_endpoint():
    data = request.json or {}
    try:
        trade_id = add_single_trade(data)
        return jsonify({'success': True, 'trade_id': trade_id, 'message': 'New trade recorded.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/trades/update/<int:trade_id>', methods=['POST'])
def update_trade_endpoint(trade_id):
    """Updates an existing trade with new values."""
    data = request.json or {}
    try:
        success = update_trade_by_id(trade_id, data)
        if success:
            return jsonify({'success': True, 'message': f'Trade #{trade_id} updated successfully.'})
        return jsonify({'success': False, 'error': 'Trade not found or no changes made.'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/trades/delete/<int:trade_id>', methods=['POST'])
def delete_trade_endpoint(trade_id):
    success = delete_trade_by_id(trade_id)
    return jsonify({'success': success, 'message': 'Trade deleted.'})

@app.route('/api/trades/clear', methods=['POST'])
def clear_trades_endpoint():
    clear_all_trades()
    return jsonify({'success': True, 'message': 'All trade records cleared.'})

# -------------------------------------------------------------------------
# SAMPLE DATA & EXPORT
# -------------------------------------------------------------------------
@app.route('/api/load-sample', methods=['POST'])
def load_sample_endpoint():
    count = int(request.json.get('count', 320) if request.json else 320)
    sample_trades = generate_sample_trades(num_trades=count)
    inserted = insert_trades_bulk(sample_trades)
    return jsonify({'success': True, 'inserted': inserted, 'message': f'Loaded {inserted} realistic sample Quotex trades!'})

@app.route('/api/export-sample-csv', methods=['GET'])
def export_sample_csv():
    csv_text = generate_sample_csv()
    return Response(
        csv_text,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=quotex_sample_trades.csv"}
    )

# -------------------------------------------------------------------------
# SERVER ENTRYPOINT
# -------------------------------------------------------------------------
if __name__ == '__main__':
    port = Config.PORT
    print("=" * 65)
    print(" Quotex Trading Journal & P&L Analytics Server")
    print(f" Web Dashboard: http://localhost:{port}")
    print(f" Remote / Phone Access: http://0.0.0.0:{port}")
    print(f" Default Admin Login: {Config.ADMIN_USERNAME} / {Config.ADMIN_PASSWORD}")
    print("=" * 65)
    app.run(host=Config.HOST, port=port, debug=False)
