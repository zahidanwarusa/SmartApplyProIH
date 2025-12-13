// SmartApplyPro - Main JavaScript

// Global variables
let generatedFilename = null;
let currentJobData = null;

// DOM Ready
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Tab switching
    setupTabSwitching();
    
    // File upload
    setupFileUpload();
    
    // Form submissions
    setupForms();
    
    // Start over button
    const startOverBtn = document.getElementById('start-over-btn');
    if (startOverBtn) {
        startOverBtn.addEventListener('click', startOver);
    }
}

// Tab Switching
function setupTabSwitching() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');
}

// File Upload
function setupFileUpload() {
    const fileInput = document.getElementById('job_description_file');
    const fileUploadBtn = document.getElementById('file-upload-btn');
    const fileNameDisplay = document.getElementById('file-name');
    
    if (fileUploadBtn && fileInput) {
        fileUploadBtn.addEventListener('click', function() {
            fileInput.click();
        });
        
        fileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                const fileName = this.files[0].name;
                const fileSize = formatFileSize(this.files[0].size);
                fileNameDisplay.textContent = `${fileName} (${fileSize})`;
                fileNameDisplay.style.fontStyle = 'normal';
                fileNameDisplay.style.color = '#36B37E';
            } else {
                fileNameDisplay.textContent = 'No file selected';
                fileNameDisplay.style.fontStyle = 'italic';
                fileNameDisplay.style.color = '#6C757D';
            }
        });
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Form Setup
function setupForms() {
    const pasteForm = document.getElementById('paste-form');
    const uploadForm = document.getElementById('upload-form');
    
    if (pasteForm) {
        pasteForm.addEventListener('submit', handlePasteSubmit);
    }
    
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUploadSubmit);
    }
}

// Handle Paste Form Submission
async function handlePasteSubmit(e) {
    e.preventDefault();
    
    const jobTitle = document.getElementById('job_title').value.trim();
    const companyName = document.getElementById('company_name').value.trim();
    const jobDescription = document.getElementById('job_description_text').value.trim();
    
    if (!jobTitle || !companyName || !jobDescription) {
        showAlert('Please fill in all fields', 'error');
        return;
    }
    
    const data = {
        job_title: jobTitle,
        company_name: companyName,
        job_description: jobDescription
    };
    
    await generateResume(data, 'text');
}

// Handle Upload Form Submission
async function handleUploadSubmit(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('job_description_file');
    
    if (!fileInput.files || fileInput.files.length === 0) {
        showAlert('Please select a file to upload', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    
    const jobTitle = document.getElementById('job_title_file').value.trim();
    const companyName = document.getElementById('company_name_file').value.trim();
    
    if (jobTitle) formData.append('job_title', jobTitle);
    if (companyName) formData.append('company_name', companyName);
    
    await generateResume(formData, 'file');
}

// Generate Resume
async function generateResume(data, type) {
    showLoading('Processing your job description with AI...');
    updateStep(2);
    
    try {
        const endpoint = type === 'text' ? '/api/generate-from-text' : '/api/generate-from-file';
        const options = {
            method: 'POST'
        };
        
        if (type === 'text') {
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify(data);
        } else {
            options.body = data;
        }
        
        const response = await fetch(endpoint, options);
        const result = await response.json();
        
        if (result.success) {
            currentJobData = result.job_data;
            generatedFilename = result.resume_filename;
            
            // Show review section
            updateStep(3);
            showReview(result.job_data);
            
            // Wait a bit, then show result
            setTimeout(() => {
                showResult(result.job_data);
                hideLoading();
            }, 1000);
            
        } else {
            hideLoading();
            showAlert(result.message || 'Failed to generate resume', 'error');
            updateStep(1);
        }
    } catch (error) {
        hideLoading();
        showAlert('Network error: ' + error.message, 'error');
        updateStep(1);
    }
}

// Show Review Section
function showReview(jobData) {
    const reviewSection = document.getElementById('review-section');
    const jobDetailsDiv = document.getElementById('job-details');
    
    let skillsHTML = '';
    if (jobData.skills && jobData.skills.length > 0) {
        skillsHTML = `
            <div class="skills-container">
                ${jobData.skills.slice(0, 15).map(skill => 
                    `<span class="skill-tag">${skill}</span>`
                ).join('')}
            </div>
        `;
    }
    
    jobDetailsDiv.innerHTML = `
        <div class="job-detail-item">
            <div class="job-detail-label">
                <i class="fas fa-briefcase"></i> Job Title
            </div>
            <div class="job-detail-value">${jobData.title}</div>
        </div>
        
        <div class="job-detail-item">
            <div class="job-detail-label">
                <i class="fas fa-building"></i> Company
            </div>
            <div class="job-detail-value">${jobData.company}</div>
        </div>
        
        ${jobData.skills && jobData.skills.length > 0 ? `
            <div class="job-detail-item">
                <div class="job-detail-label">
                    <i class="fas fa-check-circle"></i> Key Skills Matched
                </div>
                ${skillsHTML}
            </div>
        ` : ''}
    `;
    
    reviewSection.classList.remove('hidden');
    reviewSection.scrollIntoView({ behavior: 'smooth' });
}

// Show Result Section
function showResult(jobData) {
    const inputSection = document.getElementById('input-section');
    const reviewSection = document.getElementById('review-section');
    const resultSection = document.getElementById('result-section');
    
    inputSection.classList.add('hidden');
    reviewSection.classList.add('hidden');
    resultSection.classList.remove('hidden');
    
    // Setup download button
    const downloadBtn = document.getElementById('download-btn');
    downloadBtn.onclick = function() {
        if (generatedFilename) {
            window.location.href = `/api/download/${generatedFilename}`;
            showAlert('Resume download started!', 'success');
        }
    };
    
    resultSection.scrollIntoView({ behavior: 'smooth' });
    
    // Update stats
    updateStats();
}

// Start Over
function startOver() {
    // Reset forms
    document.getElementById('paste-form').reset();
    document.getElementById('upload-form').reset();
    
    // Reset file name display
    const fileNameDisplay = document.getElementById('file-name');
    fileNameDisplay.textContent = 'No file selected';
    fileNameDisplay.style.fontStyle = 'italic';
    fileNameDisplay.style.color = '#6C757D';
    
    // Hide sections
    document.getElementById('review-section').classList.add('hidden');
    document.getElementById('result-section').classList.add('hidden');
    document.getElementById('input-section').classList.remove('hidden');
    
    // Reset step
    updateStep(1);
    
    // Clear alerts
    document.getElementById('alert-container').innerHTML = '';
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Update Step Indicators
function updateStep(stepNumber) {
    // Remove active class from all steps
    document.querySelectorAll('.step').forEach(step => {
        step.classList.remove('active');
    });
    
    // Add active class to current and previous steps
    for (let i = 1; i <= stepNumber; i++) {
        const step = document.getElementById(`step-${i}`);
        if (step) {
            step.classList.add('active');
        }
    }
}

// Show Loading
function showLoading(message) {
    const overlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');
    
    if (loadingText) {
        loadingText.textContent = message;
    }
    
    overlay.classList.remove('hidden');
}

// Hide Loading
function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    overlay.classList.add('hidden');
}

// Show Alert
function showAlert(message, type) {
    const alertContainer = document.getElementById('alert-container');
    
    const iconMap = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'info': 'fa-info-circle'
    };
    
    const icon = iconMap[type] || iconMap['info'];
    
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.innerHTML = `
        <i class="fas ${icon}"></i>
        <span>${message}</span>
    `;
    
    alertContainer.innerHTML = '';
    alertContainer.appendChild(alertDiv);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        alertDiv.style.opacity = '0';
        setTimeout(() => alertDiv.remove(), 300);
    }, 5000);
    
    // Scroll to alert
    alertContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Update Stats
async function updateStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        // Update stat displays in header
        const statValues = document.querySelectorAll('.stat-value');
        if (statValues.length >= 2) {
            statValues[0].textContent = stats.total_generated || 0;
            statValues[1].textContent = stats.total_today || 0;
        }
    } catch (error) {
        console.error('Error updating stats:', error);
    }
}
