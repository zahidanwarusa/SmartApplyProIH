// Common utility functions and global behavior

// Update global status indicator in navbar
function updateGlobalStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            const status = data.status.status || 'unknown';
            const indicator = document.getElementById('bot-status-indicator');
            const statusText = document.getElementById('status-text');
            
            if (indicator && statusText) {
                // Remove all status classes
                indicator.className = 'status-badge';
                
                // Add appropriate class
                indicator.classList.add(`status-${status}`);
                statusText.textContent = status.toUpperCase();
            }

            // Update last update time in footer
            const lastUpdateEl = document.getElementById('last-update-time');
            if (lastUpdateEl) {
                lastUpdateEl.textContent = formatDateTime(new Date().toISOString());
            }
        })
        .catch(error => {
            console.error('Error updating global status:', error);
        });
}

// Update status indicator based on bot status
function updateStatusIndicator(status) {
    const indicator = document.getElementById('bot-status-indicator');
    const statusText = document.getElementById('status-text');
    
    if (indicator && statusText) {
        // Remove all status classes
        indicator.className = 'status-badge';
        
        // Add appropriate class
        indicator.classList.add(`status-${status}`);
        statusText.textContent = status.toUpperCase();
    }
}

// Format datetime string
function formatDateTime(dateStr) {
    if (!dateStr || dateStr === 'N/A') return 'N/A';
    
    try {
        const date = new Date(dateStr);
        
        if (isNaN(date.getTime())) {
            return dateStr;
        }
        
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        // If within last hour, show "X minutes ago"
        if (diffMins < 60) {
            if (diffMins === 0) return 'Just now';
            return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
        }
        
        // If within last 24 hours, show "X hours ago"
        if (diffHours < 24) {
            return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
        }
        
        // If within last 7 days, show "X days ago"
        if (diffDays < 7) {
            return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
        }
        
        // Otherwise show full date
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (error) {
        console.error('Error formatting date:', error);
        return dateStr;
    }
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (typeof text !== 'string') {
        return text;
    }
    
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    
    return text.replace(/[&<>"']/g, m => map[m]);
}

// Show notification
function showNotification(message, type = 'info') {
    // Remove any existing notifications
    const existing = document.querySelector('.notification');
    if (existing) {
        existing.remove();
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Add to body
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Copy to clipboard
function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showNotification('Copied to clipboard', 'success');
        }).catch(err => {
            console.error('Failed to copy:', err);
            showNotification('Failed to copy to clipboard', 'error');
        });
    } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        document.body.appendChild(textArea);
        textArea.select();
        
        try {
            document.execCommand('copy');
            showNotification('Copied to clipboard', 'success');
        } catch (err) {
            console.error('Failed to copy:', err);
            showNotification('Failed to copy to clipboard', 'error');
        }
        
        document.body.removeChild(textArea);
    }
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Confirm action
function confirmAction(message) {
    return confirm(message);
}

// Initialize global status updates
document.addEventListener('DOMContentLoaded', function() {
    // Update global status immediately
    updateGlobalStatus();
    
    // Update global status every 5 seconds
    setInterval(updateGlobalStatus, 5000);
    
    // Handle visibility change to pause updates when tab is hidden
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            updateGlobalStatus();
        }
    });
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + K to focus search (if exists)
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('log-search') || 
                          document.getElementById('app-search');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // Escape to close modal
    if (e.key === 'Escape') {
        const modal = document.getElementById('app-modal');
        if (modal && modal.style.display === 'block') {
            modal.style.display = 'none';
        }
    }
});

// Handle errors globally
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
});

// Service worker for offline capability (optional)
if ('serviceWorker' in navigator) {
    // Uncomment to enable service worker
    // navigator.serviceWorker.register('/static/sw.js').catch(err => {
    //     console.log('Service worker registration failed:', err);
    // });
}

// Export functions for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatDateTime,
        escapeHtml,
        showNotification,
        copyToClipboard,
        formatFileSize,
        debounce,
        confirmAction,
        updateStatusIndicator,
        updateGlobalStatus
    };
}
