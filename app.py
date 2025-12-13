from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import os
import json
from datetime import datetime
import threading
import time
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Configuration
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / 'logs'
DATA_DIR = BASE_DIR / 'data'
TRACKING_FILE = DATA_DIR / 'applications_tracking.json'
STATUS_FILE = DATA_DIR / 'bot_status.json'

# Ensure directories exist
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# Initialize status file if it doesn't exist
if not STATUS_FILE.exists():
    initial_status = {
        'status': 'idle',
        'last_updated': datetime.now().isoformat(),
        'total_applications': 0,
        'successful_applications': 0,
        'failed_applications': 0,
        'current_job': None,
        'uptime_start': None,
        'errors': []
    }
    with open(STATUS_FILE, 'w') as f:
        json.dump(initial_status, f, indent=2)


def read_status():
    """Read current bot status"""
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        return {'error': str(e)}


def read_tracking_data():
    """Read applications tracking data"""
    try:
        if TRACKING_FILE.exists():
            with open(TRACKING_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        return {'error': str(e)}


def get_recent_logs(log_file='bot.log', lines=100):
    """Read recent log entries"""
    try:
        log_path = LOGS_DIR / log_file
        if log_path.exists():
            with open(log_path, 'r') as f:
                all_lines = f.readlines()
                return all_lines[-lines:]
        return []
    except Exception as e:
        return [f"Error reading logs: {str(e)}"]


def get_log_files():
    """Get list of available log files"""
    try:
        if LOGS_DIR.exists():
            return [f.name for f in LOGS_DIR.iterdir() if f.is_file() and f.suffix == '.log']
        return []
    except Exception as e:
        return []


def calculate_statistics():
    """Calculate application statistics"""
    tracking_data = read_tracking_data()
    status = read_status()
    
    stats = {
        'total_applications': len(tracking_data),
        'successful': sum(1 for app in tracking_data.values() if app.get('status') == 'success'),
        'failed': sum(1 for app in tracking_data.values() if app.get('status') == 'failed'),
        'pending': sum(1 for app in tracking_data.values() if app.get('status') == 'pending'),
        'today': 0,
        'this_week': 0,
        'bot_status': status.get('status', 'unknown'),
        'last_activity': status.get('last_updated', 'N/A')
    }
    
    # Calculate today's and this week's applications
    today = datetime.now().date()
    for app in tracking_data.values():
        app_date_str = app.get('applied_date', app.get('timestamp', ''))
        if app_date_str:
            try:
                app_date = datetime.fromisoformat(app_date_str.replace('Z', '+00:00')).date()
                if app_date == today:
                    stats['today'] += 1
                if (today - app_date).days <= 7:
                    stats['this_week'] += 1
            except:
                pass
    
    return stats


@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/logs')
def logs_page():
    """Logs viewer page"""
    log_files = get_log_files()
    return render_template('logs.html', log_files=log_files)


@app.route('/applications')
def applications_page():
    """Applications history page"""
    return render_template('applications.html')


@app.route('/api/status')
def api_status():
    """API endpoint for bot status"""
    status = read_status()
    stats = calculate_statistics()
    
    # Calculate uptime if bot is running
    uptime = None
    if status.get('uptime_start'):
        try:
            start_time = datetime.fromisoformat(status['uptime_start'])
            uptime_seconds = (datetime.now() - start_time).total_seconds()
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            uptime = f"{hours}h {minutes}m"
        except:
            pass
    
    return jsonify({
        'status': status,
        'statistics': stats,
        'uptime': uptime
    })


@app.route('/api/logs')
def api_logs():
    """API endpoint for logs"""
    log_file = request.args.get('file', 'bot.log')
    lines = int(request.args.get('lines', 100))
    
    logs = get_recent_logs(log_file, lines)
    
    return jsonify({
        'logs': logs,
        'file': log_file,
        'total_lines': len(logs)
    })


@app.route('/api/applications')
def api_applications():
    """API endpoint for applications data"""
    tracking_data = read_tracking_data()
    
    # Convert to list and sort by date
    applications = []
    for job_id, app_data in tracking_data.items():
        app_data['job_id'] = job_id
        applications.append(app_data)
    
    # Sort by timestamp (newest first)
    applications.sort(key=lambda x: x.get('timestamp', x.get('applied_date', '')), reverse=True)
    
    # Pagination
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    return jsonify({
        'applications': applications[start_idx:end_idx],
        'total': len(applications),
        'page': page,
        'per_page': per_page,
        'total_pages': (len(applications) + per_page - 1) // per_page
    })


@app.route('/api/control/<action>', methods=['POST'])
def api_control(action):
    """API endpoint for bot control (start/stop/pause)"""
    # This is a placeholder - you'll need to integrate with your actual bot control
    status = read_status()
    
    if action == 'start':
        status['status'] = 'running'
        status['uptime_start'] = datetime.now().isoformat()
    elif action == 'stop':
        status['status'] = 'idle'
        status['uptime_start'] = None
    elif action == 'pause':
        status['status'] = 'paused'
    
    status['last_updated'] = datetime.now().isoformat()
    
    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f, indent=2)
    
    return jsonify({'success': True, 'status': status})


@app.route('/api/clear_logs', methods=['POST'])
def api_clear_logs():
    """API endpoint to clear log files"""
    log_file = request.json.get('file', 'bot.log')
    
    try:
        log_path = LOGS_DIR / log_file
        if log_path.exists():
            with open(log_path, 'w') as f:
                f.write(f"Log cleared at {datetime.now().isoformat()}\n")
            return jsonify({'success': True, 'message': f'{log_file} cleared'})
        return jsonify({'success': False, 'message': 'Log file not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/export_data')
def api_export_data():
    """API endpoint to export application data"""
    tracking_data = read_tracking_data()
    
    return jsonify({
        'success': True,
        'data': tracking_data,
        'exported_at': datetime.now().isoformat()
    })


if __name__ == '__main__':
    print("=" * 60)
    print("SmartApplyPro Dashboard Starting...")
    print("=" * 60)
    print(f"Dashboard URL: http://localhost:5000")
    print(f"Logs Directory: {LOGS_DIR}")
    print(f"Data Directory: {DATA_DIR}")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)