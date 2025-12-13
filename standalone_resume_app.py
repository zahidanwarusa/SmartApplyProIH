#!/usr/bin/env python3
"""
SmartApplyPro - Standalone Resume Generator
A lightweight, independent resume generation web interface
No bot dependencies - just pure resume generation!
"""

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import os
import json
from datetime import datetime
import hashlib
from pathlib import Path
from werkzeug.utils import secure_filename

# Import only resume-related modules
from resume_handler import ResumeHandler
from gemini_service import GeminiService

app = Flask(__name__)
CORS(app)

# Configuration
BASE_DIR = Path(__file__).parent
JOBS_DIR = BASE_DIR / 'data' / 'jobs'
RESUME_DIR = BASE_DIR / 'data' / 'resumes'
UPLOAD_FOLDER = BASE_DIR / 'uploads'
GENERATED_DIR = BASE_DIR / 'generated_resumes'

# File upload settings
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'json'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Ensure directories exist
for directory in [JOBS_DIR, RESUME_DIR, UPLOAD_FOLDER, GENERATED_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Statistics tracking
STATS_FILE = BASE_DIR / 'resume_stats.json'

def load_stats():
    """Load generation statistics"""
    if STATS_FILE.exists():
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    return {
        'total_generated': 0,
        'total_today': 0,
        'last_date': None,
        'history': []
    }

def save_stats(stats):
    """Save generation statistics"""
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)

def update_stats(job_data):
    """Update statistics after resume generation"""
    stats = load_stats()
    
    # Reset daily counter if new day
    today = datetime.now().strftime('%Y-%m-%d')
    if stats['last_date'] != today:
        stats['total_today'] = 0
        stats['last_date'] = today
    
    # Increment counters
    stats['total_generated'] += 1
    stats['total_today'] += 1
    
    # Add to history
    stats['history'].append({
        'timestamp': datetime.now().isoformat(),
        'job_title': job_data.get('title', 'Unknown'),
        'company': job_data.get('company', 'Unknown')
    })
    
    # Keep only last 100 in history
    stats['history'] = stats['history'][-100:]
    
    save_stats(stats)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(filepath):
    """Extract text from various file formats"""
    ext = filepath.suffix.lower()
    
    if ext == '.txt':
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    
    elif ext == '.pdf':
        try:
            import PyPDF2
            text = []
            with open(filepath, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text.append(page.extract_text())
            return '\n'.join(text)
        except Exception as e:
            raise Exception(f"Error reading PDF: {str(e)}")
    
    elif ext == '.docx':
        try:
            from docx import Document
            doc = Document(filepath)
            return '\n'.join([paragraph.text for paragraph in doc.paragraphs])
        except Exception as e:
            raise Exception(f"Error reading DOCX: {str(e)}")
    
    elif ext == '.json':
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'description' in data:
                return data['description']
            return json.dumps(data, indent=2)
    
    else:
        raise Exception(f"Unsupported file format: {ext}")

# ==================== ROUTES ====================

@app.route('/')
def home():
    """Main resume generator page"""
    stats = load_stats()
    return render_template('standalone_generator.html', stats=stats)

@app.route('/history')
def history():
    """Resume generation history page"""
    stats = load_stats()
    return render_template('resume_history.html', stats=stats)

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

# ==================== API ROUTES ====================

@app.route('/api/stats')
def api_stats():
    """Get generation statistics"""
    stats = load_stats()
    return jsonify(stats)

@app.route('/api/generate-from-text', methods=['POST'])
def api_generate_from_text():
    """Generate resume from job description text"""
    try:
        data = request.get_json()
        
        if not data or 'job_description' not in data:
            return jsonify({
                'success': False,
                'message': 'Job description is required'
            }), 400
        
        job_description = data['job_description']
        job_title = data.get('job_title', 'Software Engineer')
        company_name = data.get('company_name', 'Company')
        
        # Initialize services
        gemini = GeminiService()
        
        # Convert job description to JSON
        print(f"Processing job: {job_title} at {company_name}")
        job_json = gemini.convert_job_description_to_json(
            job_description, 
            job_title, 
            company_name
        )
        
        if not job_json:
            return jsonify({
                'success': False,
                'message': 'Failed to parse job description. Please check your API key or try again.'
            }), 500
        
        # Create job ID
        content = f"{job_json['title']}{job_json['company']}{job_json['description'][:100]}"
        job_id = hashlib.md5(content.encode()).hexdigest()
        job_json['job_id'] = job_id
        
        # Save job details
        job_file = JOBS_DIR / f"{job_id}.json"
        with open(job_file, 'w', encoding='utf-8') as f:
            json.dump(job_json, f, indent=2)
        
        # Generate resume
        handler = ResumeHandler()
        resume_path = handler.generate_resume(job_json)
        
        if not resume_path:
            return jsonify({
                'success': False,
                'message': 'Failed to generate resume'
            }), 500
        
        # Copy to generated directory for easy access
        resume_filename = Path(resume_path).name
        generated_path = GENERATED_DIR / resume_filename
        import shutil
        shutil.copy2(resume_path, generated_path)
        
        # Update statistics
        update_stats(job_json)
        
        return jsonify({
            'success': True,
            'message': 'Resume generated successfully',
            'job_id': job_id,
            'resume_filename': resume_filename,
            'job_data': {
                'title': job_json['title'],
                'company': job_json['company'],
                'skills': job_json.get('skills', [])[:15]
            }
        })
        
    except Exception as e:
        print(f"Error generating resume: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/generate-from-file', methods=['POST'])
def api_generate_from_file():
    """Generate resume from uploaded file"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file uploaded'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'No file selected'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'message': 'Invalid file type. Allowed: txt, pdf, docx, json'
            }), 400
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_filename = f"{timestamp}_{filename}"
        filepath = UPLOAD_FOLDER / saved_filename
        file.save(filepath)
        
        # Extract text from file
        try:
            job_description = extract_text_from_file(filepath)
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error reading file: {str(e)}'
            }), 500
        
        # Get additional parameters
        job_title = request.form.get('job_title', 'Software Engineer')
        company_name = request.form.get('company_name', 'Company')
        
        # Initialize services
        gemini = GeminiService()
        
        # Convert job description to JSON
        job_json = gemini.convert_job_description_to_json(
            job_description,
            job_title,
            company_name
        )
        
        if not job_json:
            return jsonify({
                'success': False,
                'message': 'Failed to parse job description'
            }), 500
        
        # Create job ID
        content = f"{job_json['title']}{job_json['company']}{job_json['description'][:100]}"
        job_id = hashlib.md5(content.encode()).hexdigest()
        job_json['job_id'] = job_id
        
        # Save job details
        job_file = JOBS_DIR / f"{job_id}.json"
        with open(job_file, 'w', encoding='utf-8') as f:
            json.dump(job_json, f, indent=2)
        
        # Generate resume
        handler = ResumeHandler()
        resume_path = handler.generate_resume(job_json)
        
        if not resume_path:
            return jsonify({
                'success': False,
                'message': 'Failed to generate resume'
            }), 500
        
        # Copy to generated directory
        resume_filename = Path(resume_path).name
        generated_path = GENERATED_DIR / resume_filename
        import shutil
        shutil.copy2(resume_path, generated_path)
        
        # Update statistics
        update_stats(job_json)
        
        return jsonify({
            'success': True,
            'message': 'Resume generated successfully',
            'job_id': job_id,
            'resume_filename': resume_filename,
            'job_data': {
                'title': job_json['title'],
                'company': job_json['company'],
                'skills': job_json.get('skills', [])[:15]
            }
        })
        
    except Exception as e:
        print(f"Error generating resume: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/download/<filename>')
def api_download(filename):
    """Download generated resume"""
    try:
        # Check in both directories
        file_path = GENERATED_DIR / filename
        if not file_path.exists():
            file_path = RESUME_DIR / filename
        
        if not file_path.exists():
            return jsonify({
                'success': False,
                'message': 'File not found'
            }), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/clear-history', methods=['POST'])
def api_clear_history():
    """Clear generation history"""
    try:
        stats = {
            'total_generated': 0,
            'total_today': 0,
            'last_date': None,
            'history': []
        }
        save_stats(stats)
        
        return jsonify({
            'success': True,
            'message': 'History cleared successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

if __name__ == '__main__':
    print("=" * 80)
    print("🎯 SmartApplyPro - Standalone Resume Generator")
    print("=" * 80)
    print("\n💡 Lightweight resume generation without bot dependencies")
    print(f"\n📄 Resume Generator: http://localhost:5001")
    print(f"📊 Generation History: http://localhost:5001/history")
    print(f"ℹ️  About: http://localhost:5001/about")
    print(f"\n📁 Generated Resumes: {GENERATED_DIR}")
    print(f"📋 Job Descriptions: {JOBS_DIR}")
    print("=" * 80)
    print("\n✨ Features:")
    print("   • Paste job descriptions or upload files")
    print("   • AI-powered resume generation")
    print("   • Track generation history")
    print("   • Download all resumes")
    print("   • Simple, focused interface")
    print("\n🚀 Starting server on port 5001...\n")
    
    app.run(debug=False, host='0.0.0.0', port=5001, threaded=True)
