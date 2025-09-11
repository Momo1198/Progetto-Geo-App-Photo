/**
 * GeoPhoto Enhanced JavaScript Module
 * Version: 2.0.0
 * 
 * Enhanced Features:
 * - Complete EXIF data display with tabs
 * - GPS coordinate editing and adding
 * - Modal dialogs for coordinate input
 * - Download images with updated GPS data
 */

class GeoPhotoApp {
    constructor() {
        // Element Selectors
        this.themeToggle = document.getElementById('theme-toggle');
        this.fileInput = document.getElementById('photo');
        this.fileInfo = document.getElementById('file-info');
        this.uploadForm = document.getElementById('upload-form');
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.toast = document.getElementById('toast');
        
        // GPS Modal Elements
        this.gpsModal = document.getElementById('gps-modal');
        this.modalTitle = document.getElementById('modal-title');
        this.latitudeInput = document.getElementById('latitude-input');
        this.longitudeInput = document.getElementById('longitude-input');
        
        // State
        this.isEditMode = false;
        this.originalCoords = null;
        
        // Initialize
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.setupThemeToggle();
            this.setupFileInput();
            this.setupFormSubmission();
            this.loadSavedTheme();
            this.setupClipboard();
            this.setupModalListeners();
            
            // Smooth entry animation
            document.body.style.opacity = '0';
            window.addEventListener('load', () => {
                document.body.style.transition = 'opacity 0.5s ease';
                document.body.style.opacity = '1';
            });
        });
    }

    // ===== Theme Management =====
    setupThemeToggle() {
        if (!this.themeToggle) return;
        
        this.themeToggle.addEventListener('click', () => this.toggleTheme());
        this.themeToggle.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.toggleTheme();
            }
        });
    }

    toggleTheme() {
        const body = document.body;
        const isDarkMode = body.classList.contains('dark-mode');
        
        if (isDarkMode) {
            body.classList.remove('dark-mode');
            this.saveThemePreference('light');
        } else {
            body.classList.add('dark-mode');
            this.saveThemePreference('dark');
        }

        this.themeToggle.style.transform = 'scale(0.9)';
        setTimeout(() => {
            this.themeToggle.style.transform = '';
        }, 150);
    }

    saveThemePreference(theme) {
        try {
            localStorage.setItem('geoPhotoTheme', theme);
        } catch (error) {
            console.warn('Unable to save theme preference:', error);
        }
    }

    loadSavedTheme() {
        try {
            const savedTheme = localStorage.getItem('geoPhotoTheme');
            if (savedTheme === 'dark') {
                document.body.classList.add('dark-mode');
            } else if (savedTheme === 'light') {
                document.body.classList.remove('dark-mode');
            } else {
                document.body.classList.add('dark-mode');
                this.saveThemePreference('dark');
            }
        } catch (error) {
            console.warn('Unable to load theme preference:', error);
            document.body.classList.add('dark-mode');
        }
    }

    // ===== File Input Enhancement =====
    setupFileInput() {
        if (!this.fileInput || !this.fileInfo) return;

        this.fileInput.addEventListener('change', (e) => this.handleFileSelection(e));
        
        const fileLabel = document.querySelector('.file-input-label');
        if (fileLabel) {
            this.setupDragAndDrop(fileLabel);
        }
    }

    handleFileSelection(event) {
        const file = event.target.files[0];
        
        if (file) {
            this.displayFileInfo(file);
            this.validateFile(file);
        } else {
            this.clearFileInfo();
        }
    }

    displayFileInfo(file) {
        const fileSize = this.formatFileSize(file.size);
        const fileType = file.type || 'Unknown';
        
        this.fileInfo.innerHTML = `
            <div class="file-details">
                <div class="file-name">
                    <i class="fas fa-file-image">📷</i>
                    <strong>${file.name}</strong>
                </div>
                <div class="file-meta">
                    <span class="file-size">${fileSize}</span>
                    <span class="file-type">${fileType}</span>
                </div>
            </div>
        `;
        
        this.fileInfo.classList.add('visible');
    }

    clearFileInfo() {
        this.fileInfo.classList.remove('visible');
        setTimeout(() => {
            this.fileInfo.innerHTML = '';
        }, 300);
    }

    validateFile(file) {
        const maxSize = 16 * 1024 * 1024;
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/bmp', 'image/tiff', 'image/webp'];
        
        let isValid = true;
        let errorMessage = '';

        if (file.size > maxSize) {
            isValid = false;
            errorMessage = 'File size exceeds the 16MB limit.';
        } else if (!allowedTypes.includes(file.type.toLowerCase())) {
            isValid = false;
            errorMessage = 'Invalid file type. Please select an image.';
        }

        if (!isValid) {
            this.showFileError(errorMessage);
        } else {
            this.clearFileError();
        }

        return isValid;
    }

    showFileError(message) {
        this.fileInfo.innerHTML = `
            <div class="file-error">
                <i class="fas fa-exclamation-triangle">⚠️</i>
                <span>${message}</span>
            </div>
        `;
        this.fileInfo.classList.add('visible');
        this.fileInfo.style.color = 'var(--error-color)';
    }

    clearFileError() {
        this.fileInfo.style.color = '';
    }

    setupDragAndDrop(dropZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, this.preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => this.highlight(dropZone), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => this.unhighlight(dropZone), false);
        });

        dropZone.addEventListener('drop', (e) => this.handleDrop(e), false);
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    highlight(element) {
        element.style.borderColor = 'var(--accent-color)';
        element.style.backgroundColor = 'var(--container-bg)';
    }

    unhighlight(element) {
        element.style.borderColor = '';
        element.style.backgroundColor = '';
    }

    handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length > 0) {
            this.fileInput.files = files;
            this.handleFileSelection({ target: { files: files } });
        }
    }

    // ===== Form Submission =====
    setupFormSubmission() {
        if (!this.uploadForm) return;

        this.uploadForm.addEventListener('submit', (e) => {
            if (!this.validateFormSubmission()) {
                e.preventDefault();
                return;
            }
            this.showLoadingState();
        });
    }

    validateFormSubmission() {
        const file = this.fileInput.files[0];
        
        if (!file) {
            this.showToast('Please select a photo before submitting.', 'error');
            return false;
        }

        return this.validateFile(file);
    }

    showLoadingState() {
        if (this.loadingOverlay) {
            this.loadingOverlay.classList.add('active');
            
            const submitBtn = document.querySelector('.submit-btn');
            if (submitBtn) {
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin">⏳</i> Processing...';
                submitBtn.disabled = true;
            }
        }
    }

    // ===== Clipboard Functionality =====
    setupClipboard() {
        document.body.addEventListener('click', (e) => {
            const copyBtn = e.target.closest('.copy-btn');
            if (copyBtn) {
                const textToCopy = copyBtn.dataset.clipboardText;
                if (textToCopy) {
                    this.copyToClipboard(textToCopy, copyBtn);
                }
            }
            
            // Handle GPS edit button
            const editGpsBtn = e.target.closest('.edit-gps-btn');
            if (editGpsBtn) {
                const lat = parseFloat(editGpsBtn.dataset.lat);
                const lon = parseFloat(editGpsBtn.dataset.lon);
                if (!isNaN(lat) && !isNaN(lon)) {
                    this.openGPSEditModal(lat, lon);
                }
            }
            
            // Handle GPS add button
            const addGpsBtn = e.target.closest('.add-gps-btn');
            if (addGpsBtn && addGpsBtn.dataset.action === 'add-gps') {
                this.openGPSAddModal();
            }
        });
    }

    copyToClipboard(text, buttonElement) {
        navigator.clipboard.writeText(text).then(() => {
            this.showToast('Coordinates copied to clipboard!');
            
            const originalText = buttonElement.innerHTML;
            buttonElement.innerHTML = '<i class="fas fa-check">✅</i> Copied!';
            setTimeout(() => {
                buttonElement.innerHTML = originalText;
            }, 2000);

        }).catch(err => {
            console.error('Failed to copy text: ', err);
            this.showToast('Could not copy text.', 'error');
        });
    }

    // ===== GPS Modal Functions =====
    setupModalListeners() {
        window.onclick = (event) => {
            if (event.target === this.gpsModal) {
                this.closeGPSModal();
            }
        };

        // Close modal on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.gpsModal && this.gpsModal.style.display === 'block') {
                this.closeGPSModal();
            }
        });
    }

    openGPSEditModal(lat, lon) {
        this.isEditMode = true;
        this.originalCoords = { lat, lon };
        this.modalTitle.textContent = 'Edit GPS Coordinates';
        this.latitudeInput.value = lat;
        this.longitudeInput.value = lon;
        this.gpsModal.style.display = 'block';
    }

    openGPSAddModal() {
        this.isEditMode = false;
        this.originalCoords = null;
        this.modalTitle.textContent = 'Add GPS Coordinates';
        this.latitudeInput.value = '';
        this.longitudeInput.value = '';
        this.gpsModal.style.display = 'block';
    }

    closeGPSModal() {
        this.gpsModal.style.display = 'none';
        this.latitudeInput.value = '';
        this.longitudeInput.value = '';
    }

    async saveGPSCoordinates() {
        const lat = parseFloat(this.latitudeInput.value);
        const lon = parseFloat(this.longitudeInput.value);

        // Validate coordinates
        if (isNaN(lat) || isNaN(lon)) {
            this.showToast('Please enter valid numeric coordinates', 'error');
            return;
        }

        if (lat < -90 || lat > 90) {
            this.showToast('Latitude must be between -90 and 90', 'error');
            return;
        }

        if (lon < -180 || lon > 180) {
            this.showToast('Longitude must be between -180 and 180', 'error');
            return;
        }

        // Check if we have image data
        if (!window.tempImageData) {
            this.showToast('No image data available. Please upload an image first.', 'error');
            return;
        }

        try {
            // Show loading state
            this.showLoadingState();

            // Send request to update GPS
            const response = await fetch('/update-gps', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    image: window.tempImageData,
                    latitude: lat,
                    longitude: lon,
                    filename: window.currentFilename || 'image.jpg'
                })
            });

            if (response.ok) {
                // Download the updated image
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `gps_updated_${window.currentFilename || 'image.jpg'}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);

                this.showToast('GPS coordinates updated successfully! Image downloaded.', 'success');
                this.closeGPSModal();

                // Update displayed coordinates
                if (document.getElementById('current-lat')) {
                    document.getElementById('current-lat').textContent = lat.toFixed(6);
                }
                if (document.getElementById('current-lon')) {
                    document.getElementById('current-lon').textContent = lon.toFixed(6);
                }
            } else {
                throw new Error('Failed to update GPS coordinates');
            }
        } catch (error) {
            console.error('Error updating GPS:', error);
            this.showToast('Failed to update GPS coordinates. Please try again.', 'error');
        } finally {
            // Hide loading state
            if (this.loadingOverlay) {
                this.loadingOverlay.classList.remove('active');
            }
        }
    }

    // ===== Utility Functions =====
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    showToast(message, type = 'success') {
        if (!this.toast) return;

        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle'
        };

        this.toast.className = `toast ${type}`;
        this.toast.innerHTML = `<i class="${icons[type]}">${type === 'success' ? '✅' : type === 'error' ? '⚠️' : 'ℹ️'}</i> ${message}`;
        this.toast.classList.add('show');

        setTimeout(() => {
            this.toast.classList.remove('show');
        }, 3000);
    }
}

// ===== EXIF Tab Management =====
function switchExifTab(tabName) {
    // Remove active class from all tabs and contents
    document.querySelectorAll('.exif-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.exif-tab-content').forEach(content => {
        content.classList.remove('active');
    });

    // Add active class to selected tab and content
    const selectedTab = Array.from(document.querySelectorAll('.exif-tab')).find(
        tab => tab.textContent.toLowerCase() === tabName.toLowerCase() ||
               (tabName === 'datetime' && tab.textContent === 'Date/Time')
    );
    if (selectedTab) {
        selectedTab.classList.add('active');
    }

    const selectedContent = document.getElementById(`${tabName}-tab`);
    if (selectedContent) {
        selectedContent.classList.add('active');
    }
}

// ===== Global GPS Modal Functions =====
window.openGPSEditModal = function(lat, lon) {
    if (window.geoPhotoApp) {
        window.geoPhotoApp.openGPSEditModal(lat, lon);
    }
};

window.openGPSAddModal = function() {
    if (window.geoPhotoApp) {
        window.geoPhotoApp.openGPSAddModal();
    }
};

window.closeGPSModal = function() {
    if (window.geoPhotoApp) {
        window.geoPhotoApp.closeGPSModal();
    }
};

window.saveGPSCoordinates = function() {
    if (window.geoPhotoApp) {
        window.geoPhotoApp.saveGPSCoordinates();
    }
};

// Instantiate the app
window.geoPhotoApp = new GeoPhotoApp();