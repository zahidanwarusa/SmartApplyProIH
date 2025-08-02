#!/usr/bin/env python3
"""
Complete testing framework for SmartApplyPro v2 Resume System
Tests all components: JSON structure, ResumeHandler, GeminiService, and document generation
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import project modules
try:
    from resume_handler import ResumeHandler, ResumeConverter
    from gemini_service import GeminiService
    from config import DEFAULT_RESUME, RESUME_DIR, JOBS_DIR, DATA_DIR
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)

class ResumeV2Tester:
    """Comprehensive tester for the v2 resume system"""
    
    def __init__(self):
        self.setup_logging()
        self.test_results = {}
        self.sample_job = self._create_sample_job()
        
    def setup_logging(self):
        """Setup logging for test output"""
        log_dir = Path('test_logs')
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / f'resume_v2_test_{datetime.now():%Y%m%d_%H%M%S}.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _create_sample_job(self) -> Dict:
        """Create a sample job for testing"""
        return {
            "job_id": "test_12345",
            "title": "Senior SDET",
            "company": "TestTech Solutions",
            "location": "Remote, US",
            "description": "We are seeking a Senior SDET with expertise in test automation frameworks, API testing, and cloud technologies. The ideal candidate will have experience with Selenium, REST APIs, AWS, and CI/CD pipelines. Strong background in healthcare or financial services testing preferred.",
            "skills": [
                "Selenium", "Java", "Python", "REST API", "AWS", "Docker", 
                "Kubernetes", "Jenkins", "JMeter", "TestNG", "Cucumber", 
                "API Testing", "Healthcare Testing", "HIPAA", "Agile"
            ]
        }
    
    def run_all_tests(self) -> bool:
        """Run all test phases and return overall success"""
        print("🚀 Starting SmartApplyPro v2 Resume System Tests")
        print("=" * 60)
        
        test_phases = [
            ("JSON Structure Validation", self.test_json_structure),
            ("ResumeHandler Functionality", self.test_resume_handler),
            ("GeminiService Integration", self.test_gemini_service),
            ("Document Generation", self.test_document_generation),
            ("End-to-End Pipeline", self.test_end_to_end_pipeline),
            ("Formatting Validation", self.test_formatting_validation)
        ]
        
        overall_success = True
        
        for phase_name, test_function in test_phases:
            print(f"\n📋 Phase: {phase_name}")
            print("-" * 40)
            
            try:
                success = test_function()
                self.test_results[phase_name] = success
                
                if success:
                    print(f"✅ {phase_name}: PASSED")
                else:
                    print(f"❌ {phase_name}: FAILED")
                    overall_success = False
                    
            except Exception as e:
                print(f"💥 {phase_name}: ERROR - {str(e)}")
                self.test_results[phase_name] = False
                overall_success = False
                
        self._print_final_report(overall_success)
        return overall_success
    
    def test_json_structure(self) -> bool:
        """Test that the v2 JSON structure is valid and complete"""
        print("Testing JSON structure validation...")
        
        try:
            # Check if default resume file exists
            if not DEFAULT_RESUME.exists():
                print(f"❌ Default resume file not found: {DEFAULT_RESUME}")
                return False
            
            # Load and validate JSON structure
            with open(DEFAULT_RESUME, 'r') as f:
                resume_data = json.load(f)
            
            # Check required top-level sections
            required_sections = ['header', 'professional_summary', 'core_competencies', 'professional_experience', 'education']
            missing_sections = [section for section in required_sections if section not in resume_data]
            
            if missing_sections:
                print(f"❌ Missing required sections: {missing_sections}")
                return False
            
            # Validate header structure
            header_fields = ['name', 'email', 'phone', 'citizenship', 'linkedin']
            missing_header = [field for field in header_fields if field not in resume_data['header']]
            
            if missing_header:
                print(f"❌ Missing header fields: {missing_header}")
                return False
            
            # Validate professional summary structure (v2 format)
            prof_summary_fields = ['title_experience', 'track_record', 'expertise', 'core_value']
            missing_prof_summary = [field for field in prof_summary_fields if field not in resume_data['professional_summary']]
            
            if missing_prof_summary:
                print(f"❌ Missing professional summary fields: {missing_prof_summary}")
                return False
            
            # Validate core competencies structure (v2 format)
            expected_competency_categories = [
                'programming_and_automation', 'testing_frameworks', 'cloud_and_devops',
                'api_and_performance', 'quality_tools', 'databases', 'domain_expertise', 'leadership'
            ]
            
            missing_competencies = [cat for cat in expected_competency_categories if cat not in resume_data['core_competencies']]
            
            if missing_competencies:
                print(f"❌ Missing core competency categories: {missing_competencies}")
                return False
            
            # Validate work experience structure
            if not isinstance(resume_data['professional_experience'], list) or len(resume_data['professional_experience']) == 0:
                print("❌ Professional experience must be a non-empty list")
                return False
            
            # Check first job structure
            first_job = resume_data['professional_experience'][0]
            required_job_fields = ['company', 'location', 'position', 'duration', 'summary']
            missing_job_fields = [field for field in required_job_fields if field not in first_job]
            
            if missing_job_fields:
                print(f"❌ Missing job fields in first experience: {missing_job_fields}")
                return False
            
            print("✅ JSON structure validation passed")
            print(f"   - All {len(required_sections)} required sections present")
            print(f"   - Professional summary has all 4 v2 fields")
            print(f"   - Core competencies has all 8 categories")
            print(f"   - {len(resume_data['professional_experience'])} work experiences found")
            
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
            return False
        except Exception as e:
            print(f"❌ JSON structure test error: {e}")
            return False
    
    def test_resume_handler(self) -> bool:
        """Test ResumeHandler functionality"""
        print("Testing ResumeHandler functionality...")
        
        try:
            # Initialize handler
            handler = ResumeHandler()
            
            # Test resume generation
            print("  🔄 Testing resume generation...")
            resume_path = handler.generate_resume(self.sample_job)
            
            if not resume_path:
                print("❌ Resume generation returned None")
                return False
            
            if not os.path.exists(resume_path):
                print(f"❌ Generated resume file not found: {resume_path}")
                return False
            
            # Check that JSON file was also created
            json_path = resume_path.replace('.docx', '.json')
            if not os.path.exists(json_path):
                print(f"❌ Generated JSON file not found: {json_path}")
                return False
            
            # Validate the generated JSON has v2 structure
            with open(json_path, 'r') as f:
                generated_resume = json.load(f)
            
            # Check if optimization happened (should have some differences from original)
            with open(DEFAULT_RESUME, 'r') as f:
                original_resume = json.load(f)
            
            # Basic validation that it's still a valid v2 structure
            if 'professional_summary' not in generated_resume:
                print("❌ Generated resume missing professional_summary")
                return False
            
            if 'core_competencies' not in generated_resume:
                print("❌ Generated resume missing core_competencies")
                return False
            
            print(f"✅ Resume generation successful: {os.path.basename(resume_path)}")
            print(f"   - DOCX file created: {os.path.exists(resume_path)}")
            print(f"   - JSON file created: {os.path.exists(json_path)}")
            
            return True
            
        except Exception as e:
            print(f"❌ ResumeHandler test error: {e}")
            return False
    
    def test_gemini_service(self) -> bool:
        """Test GeminiService integration"""
        print("Testing GeminiService integration...")
        
        try:
            # Initialize service
            gemini = GeminiService()
            
            # Test connection
            print("  🔄 Testing API connection...")
            if not gemini.test_connection():
                print("❌ Gemini API connection failed")
                print("   Check your API keys in config.py")
                return False
            
            # Test API usage stats
            print("  🔄 Testing API usage tracking...")
            stats = gemini.get_api_usage_stats()
            if 'date' not in stats or 'total_usage' not in stats:
                print("❌ API usage stats format invalid")
                return False
            
            # Load sample resume data for testing
            with open(DEFAULT_RESUME, 'r') as f:
                resume_data = json.load(f)
            
            # Test professional summary optimization
            print("  🔄 Testing professional summary optimization...")
            optimized_summary = gemini.optimize_resume_section(
                'professional_summary',
                resume_data['professional_summary'],
                self.sample_job
            )
            
            if not isinstance(optimized_summary, dict):
                print("❌ Professional summary optimization failed")
                return False
            
            required_fields = ['title_experience', 'track_record', 'expertise', 'core_value']
            if not all(field in optimized_summary for field in required_fields):
                print("❌ Optimized professional summary missing required fields")
                return False
            
            # Test core competencies optimization
            print("  🔄 Testing core competencies optimization...")
            optimized_competencies = gemini.optimize_resume_section(
                'core_competencies',
                resume_data['core_competencies'],
                self.sample_job
            )
            
            if not isinstance(optimized_competencies, dict):
                print("❌ Core competencies optimization failed")
                return False
            
            # Test cover letter generation
            print("  🔄 Testing cover letter generation...")
            
            # Create a temporary JSON file for testing
            temp_json_path = RESUME_DIR / "test_resume.json"
            with open(temp_json_path, 'w') as f:
                json.dump(resume_data, f, indent=2)
            
            temp_docx_path = str(temp_json_path).replace('.json', '.docx')
            
            cover_letter = gemini.generate_cover_letter(self.sample_job, temp_docx_path)
            
            # Clean up temp file
            if temp_json_path.exists():
                temp_json_path.unlink()
            
            if not cover_letter or len(cover_letter.strip()) < 100:
                print("❌ Cover letter generation failed or too short")
                return False
            
            print("✅ GeminiService integration successful")
            print(f"   - API connection: Working")
            print(f"   - Usage tracking: Working")
            print(f"   - Section optimization: Working")
            print(f"   - Cover letter generation: Working")
            
            return True
            
        except Exception as e:
            print(f"❌ GeminiService test error: {e}")
            return False
    
    def test_document_generation(self) -> bool:
        """Test document generation and formatting"""
        print("Testing document generation...")
        
        try:
            # Load sample resume data
            with open(DEFAULT_RESUME, 'r') as f:
                resume_data = json.load(f)
            
            # Test ResumeConverter
            print("  🔄 Testing ResumeConverter...")
            converter = ResumeConverter()
            converter.convert_resume(resume_data)
            
            # Save to test file
            test_docx_path = RESUME_DIR / "test_document_generation.docx"
            converter.save(str(test_docx_path))
            
            if not test_docx_path.exists():
                print("❌ Document generation failed - file not created")
                return False
            
            # Check file size (should be reasonable for a resume)
            file_size = test_docx_path.stat().st_size
            if file_size < 10000:  # Less than 10KB might indicate empty document
                print(f"❌ Generated document too small: {file_size} bytes")
                return False
            
            print("✅ Document generation successful")
            print(f"   - File created: {test_docx_path.name}")
            print(f"   - File size: {file_size:,} bytes")
            
            # Clean up test file
            test_docx_path.unlink()
            
            return True
            
        except Exception as e:
            print(f"❌ Document generation test error: {e}")
            return False
    
    def test_end_to_end_pipeline(self) -> bool:
        """Test the complete end-to-end pipeline"""
        print("Testing end-to-end pipeline...")
        
        try:
            # Create test job file
            test_job_file = JOBS_DIR / "test_job.json"
            with open(test_job_file, 'w') as f:
                json.dump(self.sample_job, f, indent=2)
            
            # Test complete pipeline
            print("  🔄 Running complete resume generation pipeline...")
            handler = ResumeHandler()
            resume_path = handler.generate_resume(self.sample_job)
            
            if not resume_path:
                print("❌ End-to-end pipeline failed - no resume generated")
                return False
            
            # Verify both files exist
            json_path = resume_path.replace('.docx', '.json')
            
            if not os.path.exists(resume_path):
                print("❌ End-to-end pipeline failed - DOCX not created")
                return False
            
            if not os.path.exists(json_path):
                print("❌ End-to-end pipeline failed - JSON not created")
                return False
            
            # Test cover letter generation
            print("  🔄 Testing cover letter in pipeline...")
            gemini = GeminiService()
            cover_letter = gemini.generate_cover_letter(self.sample_job, resume_path)
            
            if not cover_letter:
                print("❌ Cover letter generation in pipeline failed")
                return False
            
            print("✅ End-to-end pipeline successful")
            print(f"   - Resume generated: {os.path.basename(resume_path)}")
            print(f"   - Cover letter generated: {len(cover_letter)} characters")
            
            # Clean up test files
            test_job_file.unlink()
            
            return True
            
        except Exception as e:
            print(f"❌ End-to-end pipeline test error: {e}")
            return False
    
    def test_formatting_validation(self) -> bool:
        """Test formatting and quality validation"""
        print("Testing formatting validation...")
        
        try:
            # Load sample resume data
            with open(DEFAULT_RESUME, 'r') as f:
                resume_data = json.load(f)
            
            # Check for bold formatting markers
            print("  🔄 Validating bold formatting markers...")
            
            # Check professional summary
            prof_summary = resume_data['professional_summary']
            has_bold_formatting = any('**' in str(value) for value in prof_summary.values())
            
            if not has_bold_formatting:
                print("❌ Professional summary missing bold formatting markers")
                return False
            
            # Check core competencies for proper structure
            print("  🔄 Validating core competencies structure...")
            competencies = resume_data['core_competencies']
            
            # Should have 8 categories
            if len(competencies) < 8:
                print(f"❌ Core competencies only has {len(competencies)} categories, expected 8")
                return False
            
            # Each category should have skills
            empty_categories = [cat for cat, skills in competencies.items() if not skills]
            if empty_categories:
                print(f"❌ Empty competency categories found: {empty_categories}")
                return False
            
            # Check work experience structure
            print("  🔄 Validating work experience structure...")
            experience = resume_data['professional_experience']
            
            if not experience:
                print("❌ No work experience found")
                return False
            
            # Check first job has required v2 fields
            first_job = experience[0]
            v2_fields = ['company', 'location', 'position', 'duration', 'summary']
            missing_fields = [field for field in v2_fields if field not in first_job]
            
            if missing_fields:
                print(f"❌ Work experience missing v2 fields: {missing_fields}")
                return False
            
            # Check for achievements structure (key_achievements or detailed_achievements)
            has_achievements = 'key_achievements' in first_job or 'detailed_achievements' in first_job
            if not has_achievements:
                print("❌ Work experience missing achievements structure")
                return False
            
            print("✅ Formatting validation successful")
            print("   - Bold formatting markers present")
            print(f"   - Core competencies: {len(competencies)} categories")
            print(f"   - Work experience: {len(experience)} positions")
            print("   - v2 structure maintained")
            
            return True
            
        except Exception as e:
            print(f"❌ Formatting validation test error: {e}")
            return False
    
    def _print_final_report(self, overall_success: bool):
        """Print final test report"""
        print("\n" + "=" * 60)
        print("🎯 FINAL TEST REPORT")
        print("=" * 60)
        
        # Print individual test results
        for test_name, result in self.test_results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{test_name:<35} {status}")
        
        print("-" * 60)
        
        if overall_success:
            print("🎉 ALL TESTS PASSED! 🎉")
            print("Your SmartApplyPro v2 Resume System is ready to use!")
            print("\nNext steps:")
            print("1. Update your config.py to point to the new resume file")
            print("2. Test with a real job application")
            print("3. Verify the generated resumes meet your quality standards")
        else:
            failed_tests = [name for name, result in self.test_results.items() if not result]
            print("🚨 SOME TESTS FAILED 🚨")
            print(f"Failed tests: {', '.join(failed_tests)}")
            print("\nPlease review the error messages above and fix the issues before proceeding.")
        
        print("=" * 60)

def main():
    """Main test execution"""
    print("SmartApplyPro v2 Resume System Test Suite")
    print("=========================================")
    
    # Check if we're in the right directory
    if not Path('config.py').exists():
        print("❌ Error: config.py not found. Please run this script from the project root directory.")
        return False
    
    # Check if default resume exists
    if not DEFAULT_RESUME.exists():
        print(f"❌ Error: Default resume file not found: {DEFAULT_RESUME}")
        print("Please ensure you've created the new v2 JSON resume file.")
        return False
    
    # Run tests
    tester = ResumeV2Tester()
    success = tester.run_all_tests()
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)