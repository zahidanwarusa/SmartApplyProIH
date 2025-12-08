"""
SmartApplyPro Web Interface - FIXED VERSION
Flask application for job description input and resume generation
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
import PyPDF2
from docx import Document as DocxDocument

# Import your existing modules
from resume_handler import ResumeHandler
from gemini_service import GeminiService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = Path('uploads')
app.config['GENERATED_RESUMES_FOLDER'] = Path('data/resumes')

# Create necessary directories
app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)
app.config['GENERATED_RESUMES_FOLDER'].mkdir(parents=True, exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

# Initialize services
resume_handler = ResumeHandler()
gemini_service = GeminiService()


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
    except Exception as e:
        logger.error(f"Error extracting PDF text: {str(e)}")
        return None


def extract_text_from_docx(file_path):
    """Extract text from DOCX file"""
    try:
        doc = DocxDocument(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text
    except Exception as e:
        logger.error(f"Error extracting DOCX text: {str(e)}")
        return None


def extract_text_from_txt(file_path):
    """Extract text from TXT file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error(f"Error reading TXT file: {str(e)}")
        return None


def call_gemini_api(prompt):
    """
    Wrapper function to call Gemini API using your GeminiService's make_api_call method
    """
    try:
        # Your GeminiService uses make_api_call() method
        response = gemini_service.make_api_call(
            prompt,
            max_retries=2
        )
        
        if response and hasattr(response, 'text'):
            return response.text
        else:
            logger.error("No valid response from Gemini API")
            return None
    except Exception as e:
        logger.error(f"Error calling Gemini API: {str(e)}")
        raise


def parse_job_description(text):
    """Parse job description text and extract key information using Gemini AI"""
    try:
        logger.info(f"Parsing job description (length: {len(text)} chars)")
        
        prompt = f"""
        Analyze this job description and extract structured information in JSON format:
        
        Job Description:
        {text}
        
        Please provide a JSON response with the following structure:
        {{
            "title": "Job Title",
            "company": "Company Name",
            "location": "Location",
            "description": "Full job description",
            "requirements": ["requirement1", "requirement2", ...],
            "skills": ["skill1", "skill2", ...],
            "experience_level": "Entry/Mid/Senior level",
            "job_type": "Full-time/Part-time/Contract"
        }}
        
        Extract as much information as possible. If certain fields are not available, use "Not specified" or empty arrays.
        Return ONLY the JSON, no additional text.
        """
        
        logger.info("Calling Gemini API...")
        response = call_gemini_api(prompt)
        logger.info(f"Received response from Gemini")
        
        # Convert response to string if needed
        response_text = str(response).strip()
        logger.info(f"Response text length: {len(response_text)}")
        
        # Clean the response to ensure it's valid JSON
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        logger.info("Attempting to parse JSON...")
        job_data = json.loads(response_text)
        logger.info(f"Successfully parsed JSON with {len(job_data)} fields")
        
        return job_data
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        logger.error(f"Response text (first 500 chars): {response_text[:500]}")
        return None
    except Exception as e:
        logger.error(f"Error parsing job description: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


@app.route('/')
def index():
    """Main landing page"""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_job_description():
    """Handle job description upload or paste"""
    try:
        job_description_text = None
        
        logger.info(f"=== Upload Request Received ===")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Is JSON: {request.is_json}")
        logger.info(f"Form keys: {list(request.form.keys())}")
        logger.info(f"Files keys: {list(request.files.keys())}")
        
        # Handle JSON data (from JavaScript fetch)
        if request.is_json:
            data = request.get_json()
            logger.info(f"JSON data received: {list(data.keys()) if data else 'None'}")
            if data and 'job_description_text' in data:
                job_description_text = data.get('job_description_text', '').strip()
                if job_description_text:
                    logger.info(f"✅ Processing pasted job description (JSON) - Length: {len(job_description_text)}")
                else:
                    logger.warning("❌ job_description_text is empty in JSON")
        
        # Handle form data (traditional form submission)
        elif 'job_description_text' in request.form:
            job_description_text = request.form.get('job_description_text', '').strip()
            if job_description_text:
                logger.info(f"✅ Processing pasted job description (Form) - Length: {len(job_description_text)}")
            else:
                logger.warning("❌ job_description_text is empty in Form")
        
        # Check if file was uploaded
        elif 'job_description_file' in request.files:
            file = request.files['job_description_file']
            logger.info(f"File received: {file.filename if file else 'None'}")
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = app.config['UPLOAD_FOLDER'] / filename
                file.save(file_path)
                logger.info(f"File saved to: {file_path}")
                
                # Extract text based on file type
                ext = filename.rsplit('.', 1)[1].lower()
                logger.info(f"Extracting text from {ext} file...")
                
                if ext == 'pdf':
                    job_description_text = extract_text_from_pdf(file_path)
                elif ext == 'docx':
                    job_description_text = extract_text_from_docx(file_path)
                elif ext == 'txt':
                    job_description_text = extract_text_from_txt(file_path)
                
                if job_description_text:
                    logger.info(f"✅ Extracted text length: {len(job_description_text)}")
                else:
                    logger.error("❌ Failed to extract text from file")
                
                # Clean up uploaded file
                try:
                    file_path.unlink()
                    logger.info("Temporary file cleaned up")
                except:
                    pass
            else:
                logger.warning(f"Invalid or missing file: {file.filename if file else 'None'}")
        else:
            logger.warning("No data received in request")
        
        if not job_description_text:
            logger.error("❌ No job description text found")
            return jsonify({
                'success': False,
                'error': 'No job description provided. Please paste text or upload a file.'
            }), 400
        
        # Parse job description using AI
        logger.info("Parsing job description with AI...")
        job_data = parse_job_description(job_description_text)
        
        if not job_data:
            logger.error("❌ Failed to parse job description")
            return jsonify({
                'success': False,
                'error': 'Failed to parse job description. Please try again.'
            }), 500
        
        # Store job data in session or temporary storage
        job_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_file_path = app.config['UPLOAD_FOLDER'] / f"job_{job_id}.json"
        
        with open(job_file_path, 'w', encoding='utf-8') as f:
            json.dump(job_data, f, indent=2)
        
        logger.info(f"✅ Successfully processed job description. Job ID: {job_id}")
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'job_data': job_data,
            'message': 'Job description processed successfully!'
        })
        
    except Exception as e:
        logger.error(f"❌ Error in upload_job_description: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }), 500


@app.route('/generate-resume', methods=['POST'])
def generate_resume():
    """Generate optimized resume based on job description"""
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        
        if not job_id:
            return jsonify({
                'success': False,
                'error': 'Job ID is required'
            }), 400
        
        # Load job data
        job_file_path = app.config['UPLOAD_FOLDER'] / f"job_{job_id}.json"
        
        if not job_file_path.exists():
            return jsonify({
                'success': False,
                'error': 'Job data not found'
            }), 404
        
        with open(job_file_path, 'r', encoding='utf-8') as f:
            job_data = json.load(f)
        
        logger.info(f"Generating resume for job: {job_data.get('title', 'Unknown')}")
        
        # Generate resume using existing resume handler
        resume_path = resume_handler.generate_resume(job_data)
        
        if not resume_path:
            return jsonify({
                'success': False,
                'error': 'Failed to generate resume. Please check logs.'
            }), 500
        
        # Get relative path for download
        resume_filename = Path(resume_path).name
        
        return jsonify({
            'success': True,
            'message': 'Resume generated successfully!',
            'resume_filename': resume_filename,
            'download_url': url_for('download_resume', filename=resume_filename)
        })
        
    except Exception as e:
        logger.error(f"Error generating resume: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }), 500


@app.route('/download/<filename>')
def download_resume(filename):
    """Download generated resume"""
    try:
        file_path = app.config['GENERATED_RESUMES_FOLDER'] / filename
        
        if not file_path.exists():
            flash('Resume file not found', 'error')
            return redirect(url_for('index'))
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
    except Exception as e:
        logger.error(f"Error downloading resume: {str(e)}")
        flash(f'Error downloading resume: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    return jsonify({
        'success': False,
        'error': 'File too large. Maximum size is 16MB.'
    }), 413


@app.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'success': False,
        'error': 'An internal server error occurred. Please try again.'
    }), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("SmartApplyPro Web Interface Starting...")
    print("="*60)
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"Resume folder: {app.config['GENERATED_RESUMES_FOLDER']}")
    print("\nServer will start on: http://localhost:5000")
    print("="*60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)