# SmartApplyPro

*Your AI-Powered Career Accelerator*

SmartApplyPro is an intelligent job application automation system that leverages AI to streamline the job search and application process. It optimizes resumes, generates tailored cover letters, and automates applications on job platforms, saving professionals valuable time while increasing their chances of landing interviews.

## 🚀 Key Features

- **Optimized Workflow**: Smart job assessment to efficiently identify relevant, easily applicable positions
- **Automated Job Search**: Searches for relevant job postings on Dice.com based on configured job titles
- **Resume Optimization**: Uses AI to tailor your resume for specific job descriptions
- **Cover Letter Generation**: Creates customized cover letters for each job application
- **Automated Application**: Handles the job application process including document uploads
- **Comprehensive Tracking**: Keeps detailed records of all application activities
- **Performance Analytics**: Generates statistics and reports on application success rates

## 📋 Requirements

- Python 3.9+
- Chrome Browser
- ChromeDriver (compatible with your Chrome version)
- Google Gemini API Key

## 🔧 Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/SmartApplyPro.git
   cd SmartApplyPro
   ```

2. Install required packages:
   ```
   pip install -r requirements.txt
   ```

3. Configure your Chrome profile in `config.py`:
   ```python
   CHROME_PROFILE = {
       'user_data_dir': 'C:\\Users\\YourUsername\\AppData\\Local\\Google\\Chrome\\User Data',
       'profile_directory': 'Profile 1'
   }
   ```

4. Set your Gemini API key in `config.py`:
   ```python
   GEMINI_API_KEY = 'your-api-key-here'
   ```

5. Customize job search parameters in `config.py` if needed.

## 📝 Usage

### Run Automatic Job Applications

```
python main.py --mode auto
```

### Generate Resume for a Specific Job

```
python main.py --mode resume --job-file data/jobs/example-job.json
```

### Generate Cover Letter

```
python main.py --mode cover --job-file data/jobs/example-job.json --resume data/resumes/your-resume.docx
```

### List Application Statistics and Recent Applications

```
python main.py --mode list
```

### Generate Comprehensive Application Report

```
python main.py --mode report
```

# Basic usage - generate resume
python main.py --mode process-description --job-description jobDescription.txt

# Generate both resume and cover letter
python main.py --mode process-description --job-description example-job.txt --output-type generate_both --job-title "Senior SDET" --company "HealthTech Solutions"

# Just create the JSON file (if you want to inspect it before generating a resume)
python main.py --mode process-description --job-description example-job.txt --output-type save_json_only

## 📊 Application Tracking

SmartApplyPro now includes a powerful application tracking system that:

- Tracks all application attempts (successful, failed, and skipped)
- Maintains detailed statistics on daily and overall performance
- Prevents duplicate applications to the same position
- Generates comprehensive reports on application activities
- Provides insights to optimize your job search strategy

The tracking system helps you:
1. **Monitor Progress**: See exactly how many applications you've submitted and their status
2. **Identify Patterns**: Understand which job types have the highest application success rates
3. **Save Resources**: Prevents wasting time on already applied jobs or those without Easy Apply
4. **Document Management**: Keeps track of which resume and cover letter were used for each position

## 📂 Project Structure

- `main.py`: Main entry point for the application
- `bot.py`: Dice.com automation bot implementation
- `resume_handler.py`: Resume generation and optimization
- `gemini_service.py`: AI integration for content optimization
- `application_tracker.py`: Tracks and manages application statistics
- `config.py`: Configuration settings
- `data/`: Directory for job and resume storage
  - `jobs/`: Job posting details
  - `resumes/`: Generated resumes
  - `tracking/`: Application tracking data
- `reports/`: Directory for application reports and statistics

## 🔄 Workflow Improvements

The application now follows a more efficient workflow:

1. **Pre-assessment**: Checks if a job is already applied to or lacks Easy Apply before wasting resources
2. **Document Generation**: Only generates optimized resumes and cover letters for viable job opportunities
3. **Smart Application**: Handles the entire application process with improved error handling
4. **Comprehensive Tracking**: Records all activity for later analysis and reporting
5. **Performance Analysis**: Provides insights into application success rates and opportunities for improvement

## ⚠️ Disclaimer

This tool is meant for personal use only. Please ensure you comply with the terms of service of any websites you interact with. The maintainers of this project are not responsible for any misuse of this tool.

## 📜 License

MIT