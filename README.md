# SmartApplyPro

*Your AI-Powered Career Accelerator*

SmartApplyPro is an intelligent job application automation system that leverages AI to streamline the job search and application process. It optimizes resumes, generates tailored cover letters, and automates applications on job platforms, saving professionals valuable time while increasing their chances of landing interviews.

## Features

- **Automated Job Search**: Searches for relevant job postings on Dice.com based on configured job titles
- **Resume Optimization**: Uses AI to tailor your resume for specific job descriptions
- **Cover Letter Generation**: Creates customized cover letters for each job application
- **Automated Application**: Handles the job application process including document uploads
- **Application Tracking**: Keeps records of applied jobs and generated documents

## Requirements

- Python 3.9+
- Chrome Browser
- ChromeDriver (compatible with your Chrome version)
- Google Gemini API Key

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/zahidanwarusa/SmartApplyPro.git
   cd job-application-automation
   ```

2. Install required packages:
   ```
   pip install selenium google-generativeai python-docx
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

## Usage

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

### List All Applications

```
python main.py --mode list
```

## Project Structure

- `main.py`: Main entry point for the application
- `bot.py`: Dice.com automation bot implementation
- `resume_handler.py`: Resume generation and optimization
- `gemini_service.py`: AI integration for content optimization
- `config.py`: Configuration settings
- `data/`: Directory for job and resume storage
  - `jobs/`: Job posting details
  - `resumes/`: Generated resumes

## Disclaimer

This tool is meant for personal use only. Please ensure you comply with the terms of service of any websites you interact with. The maintainers of this project are not responsible for any misuse of this tool.

## License

MIT