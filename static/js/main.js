// SmartApplyPro - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    
    // Global variables
    let currentJobId = null;
    let currentJobData = null;

    // DOM Elements
    const pasteForm = document.getElementById('paste-form');
    const uploadForm = document.getElementById('upload-form');
    const fileUploadBtn = document.getElementById('file-upload-btn');
    const fileInput = document.getElementById('job_description_file');
    const fileName = document.getElementById('file-name');
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    const inputSection = document.getElementById('input-section');
    const reviewSection = document.getElementById('review-section');
    const resultSection = document.getElementById('result-section');
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');
    const generateBtn = document.getElementById('generate-btn');
    const editBtn = document.getElementById('edit-btn');
    const startOverBtn = document.getElementById('start-over-btn');
    const downloadBtn = document.getElementById('download-btn');
    const alertContainer = document.getElementById('alert-container');

    // Tab Switching
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetTab = this.getAttribute('data-tab');
            
            // Update tab buttons
            tabButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            // Update tab content
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.id === `${targetTab}-tab`) {
                    content.classList.add('active');
                }
            });
        });
    });

    // File Upload Button
    fileUploadBtn.addEventListener('click', function() {
        fileInput.click();
    });

    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            fileName.textContent = this.files[0].name;
        } else {
            fileName.textContent = 'No file selected';
        }
    });

    // Paste Form Submission
    pasteForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const jobDescriptionText = document.getElementById('job_description_text').value.trim();
        
        if (!jobDescriptionText) {
            showAlert('Please paste a job description before submitting.', 'error');
            return;
        }

        submitJobDescription({ job_description_text: jobDescriptionText });
    });

    // Upload Form Submission
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (fileInput.files.length === 0) {
            showAlert('Please select a file before submitting.', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('job_description_file', fileInput.files[0]);
        
        submitJobDescription(formData);
    });

    // Submit Job Description
    function submitJobDescription(data) {
        showLoading('Processing your job description...');

        const isFormData = data instanceof FormData;
        const options = {
            method: 'POST',
            body: isFormData ? data : JSON.stringify(data)
        };

        if (!isFormData) {
            options.headers = {
                'Content-Type': 'application/json'
            };
        }

        fetch('/upload', options)
            .then(response => response.json())
            .then(data => {
                hideLoading();
                
                if (data.success) {
                    currentJobId = data.job_id;
                    currentJobData = data.job_data;
                    
                    showAlert(data.message, 'success');
                    displayJobDetails(data.job_data);
                    moveToStep(2);
                } else {
                    showAlert(data.error || 'An error occurred while processing the job description.', 'error');
                }
            })
            .catch(error => {
                hideLoading();
                showAlert('Network error: ' + error.message, 'error');
                console.error('Error:', error);
            });
    }

    // Display Job Details
    function displayJobDetails(jobData) {
        const jobDetailsContainer = document.getElementById('job-details');
        
        let html = '';

        // Job Title
        if (jobData.title) {
            html += `
                <div class="job-detail-item">
                    <div class="job-detail-label">
                        <i class="fas fa-briefcase"></i> Job Title
                    </div>
                    <div class="job-detail-value">${escapeHtml(jobData.title)}</div>
                </div>
            `;
        }

        // Company
        if (jobData.company) {
            html += `
                <div class="job-detail-item">
                    <div class="job-detail-label">
                        <i class="fas fa-building"></i> Company
                    </div>
                    <div class="job-detail-value">${escapeHtml(jobData.company)}</div>
                </div>
            `;
        }

        // Location
        if (jobData.location) {
            html += `
                <div class="job-detail-item">
                    <div class="job-detail-label">
                        <i class="fas fa-map-marker-alt"></i> Location
                    </div>
                    <div class="job-detail-value">${escapeHtml(jobData.location)}</div>
                </div>
            `;
        }

        // Experience Level
        if (jobData.experience_level) {
            html += `
                <div class="job-detail-item">
                    <div class="job-detail-label">
                        <i class="fas fa-chart-line"></i> Experience Level
                    </div>
                    <div class="job-detail-value">${escapeHtml(jobData.experience_level)}</div>
                </div>
            `;
        }

        // Job Type
        if (jobData.job_type) {
            html += `
                <div class="job-detail-item">
                    <div class="job-detail-label">
                        <i class="fas fa-clock"></i> Job Type
                    </div>
                    <div class="job-detail-value">${escapeHtml(jobData.job_type)}</div>
                </div>
            `;
        }

        // Requirements
        if (jobData.requirements && jobData.requirements.length > 0) {
            html += `
                <div class="job-detail-item">
                    <div class="job-detail-label">
                        <i class="fas fa-list-check"></i> Key Requirements
                    </div>
                    <ul class="job-detail-list">
                        ${jobData.requirements.map(req => `<li>${escapeHtml(req)}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        // Skills
        if (jobData.skills && jobData.skills.length > 0) {
            html += `
                <div class="job-detail-item">
                    <div class="job-detail-label">
                        <i class="fas fa-tools"></i> Required Skills
                    </div>
                    <ul class="job-detail-list">
                        ${jobData.skills.map(skill => `<li>${escapeHtml(skill)}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        jobDetailsContainer.innerHTML = html;
    }

    // Generate Resume
    generateBtn.addEventListener('click', function() {
        if (!currentJobId) {
            showAlert('Job ID is missing. Please start over.', 'error');
            return;
        }

        showLoading('Generating your optimized resume...<br>This may take a minute...');

        fetch('/generate-resume', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ job_id: currentJobId })
        })
            .then(response => response.json())
            .then(data => {
                hideLoading();
                
                if (data.success) {
                    showAlert(data.message, 'success');
                    downloadBtn.href = data.download_url;
                    moveToStep(3);
                } else {
                    showAlert(data.error || 'Failed to generate resume.', 'error');
                }
            })
            .catch(error => {
                hideLoading();
                showAlert('Network error: ' + error.message, 'error');
                console.error('Error:', error);
            });
    });

    // Edit Button
    editBtn.addEventListener('click', function() {
        moveToStep(1);
        showAlert('You can now edit the job description.', 'info');
    });

    // Start Over Button
    startOverBtn.addEventListener('click', function() {
        resetForm();
        moveToStep(1);
        showAlert('Ready to create a new resume!', 'info');
    });

    // Helper Functions
    function moveToStep(step) {
        // Update progress steps
        document.querySelectorAll('.step').forEach((stepEl, index) => {
            if (index + 1 <= step) {
                stepEl.classList.add('active');
            } else {
                stepEl.classList.remove('active');
            }
        });

        // Show/hide sections
        inputSection.classList.add('hidden');
        reviewSection.classList.add('hidden');
        resultSection.classList.add('hidden');

        if (step === 1) {
            inputSection.classList.remove('hidden');
        } else if (step === 2) {
            reviewSection.classList.remove('hidden');
        } else if (step === 3) {
            resultSection.classList.remove('hidden');
        }

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function showLoading(message) {
        loadingText.innerHTML = message;
        loadingOverlay.classList.remove('hidden');
    }

    function hideLoading() {
        loadingOverlay.classList.add('hidden');
    }

    function showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type}`;
        
        let icon = 'info-circle';
        if (type === 'success') icon = 'check-circle';
        if (type === 'error') icon = 'exclamation-circle';
        
        alertDiv.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <span>${message}</span>
        `;
        
        alertContainer.innerHTML = '';
        alertContainer.appendChild(alertDiv);

        // Auto-hide after 5 seconds
        setTimeout(() => {
            alertDiv.style.opacity = '0';
            setTimeout(() => alertDiv.remove(), 300);
        }, 5000);
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function resetForm() {
        // Reset forms
        pasteForm.reset();
        uploadForm.reset();
        fileName.textContent = 'No file selected';
        
        // Clear job data
        currentJobId = null;
        currentJobData = null;
        
        // Clear alerts
        alertContainer.innerHTML = '';
    }

    // Initialize
    moveToStep(1);
});