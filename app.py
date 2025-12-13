from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import os
import json
from datetime import datetime
import threading
import time
from pathlib import Path
import sys

# Import bot class
from dice_bot import DiceBot

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

# Bot control variables
bot_instance = None
bot_thread = None
bot_running = False
bot_should_stop = False

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


def update_status(updates):
    """Update bot status file"""
    try:
        status = read_status()
        status.update(updates)
        status['last_updated'] = datetime.now().isoformat()
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f, indent=2)
        return True
    except Exception as e:
        print(f"Error updating status: {e}")
        return False


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


def run_bot_wrapper():
    """Wrapper function to run the bot in a separate thread"""
    global bot_instance, bot_running, bot_should_stop
    
    try:
        print("🤖 Starting bot in background thread...")
        bot_instance = DiceBot()
        bot_running = True
        update_status({
            'status': 'running',
            'uptime_start': datetime.now().isoformat()
        })
        
        # Run the bot
        bot_instance.run()
        
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Error in bot execution: {str(e)}")
        update_status({
            'status': 'error',
            'errors': [f"Bot error: {str(e)}"]
        })
    finally:
        bot_running = False
        bot_should_stop = False
        if not bot_should_stop:  # Only set to idle if not manually stopped
            update_status({
                'status': 'idle',
                'uptime_start': None
            })
        print("🤖 Bot thread finished")


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
    
    # Add actual bot running state
    status['is_running'] = bot_running
    
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
    global bot_thread, bot_running, bot_should_stop, bot_instance
    
    try:
        if action == 'start':
            if bot_running:
                return jsonify({
                    'success': False,
                    'message': 'Bot is already running'
                })
            
            # Start bot in a new thread
            bot_should_stop = False
            bot_thread = threading.Thread(target=run_bot_wrapper, daemon=True)
            bot_thread.start()
            
            return jsonify({
                'success': True,
                'message': 'Bot started successfully',
                'status': 'running'
            })
            
        elif action == 'stop':
            if not bot_running:
                return jsonify({
                    'success': False,
                    'message': 'Bot is not running'
                })
            
            # Signal bot to stop
            bot_should_stop = True
            
            # Try to stop the bot gracefully
            if bot_instance:
                try:
                    # If bot has a stop method, call it
                    if hasattr(bot_instance, 'stop'):
                        bot_instance.stop()
                    
                    # Close the browser if it exists
                    if hasattr(bot_instance, 'driver') and bot_instance.driver:
                        bot_instance.driver.quit()
                except Exception as e:
                    print(f"Error stopping bot: {e}")
            
            bot_running = False
            update_status({
                'status': 'stopped',
                'uptime_start': None
            })
            
            return jsonify({
                'success': True,
                'message': 'Bot stopped successfully',
                'status': 'stopped'
            })
            
        elif action == 'pause':
            if not bot_running:
                return jsonify({
                    'success': False,
                    'message': 'Bot is not running'
                })
            
            update_status({'status': 'paused'})
            
            return jsonify({
                'success': True,
                'message': 'Bot paused',
                'status': 'paused'
            })
            
        elif action == 'resume':
            status = read_status()
            if status.get('status') != 'paused':
                return jsonify({
                    'success': False,
                    'message': 'Bot is not paused'
                })
            
            update_status({'status': 'running'})
            
            return jsonify({
                'success': True,
                'message': 'Bot resumed',
                'status': 'running'
            })
        
        else:
            return jsonify({
                'success': False,
                'message': f'Unknown action: {action}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })


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
    print("=" * 80)
    print("🤖 SmartApplyPro - Integrated Bot Control Dashboard")
    print("=" * 80)
    print(f"📊 Dashboard URL: http://localhost:5000")
    print(f"📝 Logs Directory: {LOGS_DIR}")
    print(f"💾 Data Directory: {DATA_DIR}")
    print("=" * 80)
    print("\n✨ Features:")
    print("   • Start/Stop bot directly from web interface")
    print("   • Real-time status monitoring")
    print("   • Live log viewing")
    print("   • Application tracking")
    print("\n🎮 Controls:")
    print("   • Click 'Start Bot' to begin job applications")
    print("   • Click 'Stop Bot' to halt the bot")
    print("   • Monitor progress in real-time")
    print("=" * 80)
    print("\n🚀 Starting server...\n")
    
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)