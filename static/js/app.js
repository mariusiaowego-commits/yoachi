/**
 * Yoachi JavaScript Utilities
 */

// Format date for display
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString('ja-JP', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

// Calculate progress percentage
function calculateProgress(current, threshold) {
    if (!threshold || threshold === 0) return 0;
    return Math.min(Math.round((current / threshold) * 100), 100);
}

// Show notification
function showNotification(message, type = 'success') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        z-index: 1000;
        animation: slideIn 0.3s ease-out;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// Alpine.js badgeWall component
function badgeWall() {
    return {
        selectedCategory: 'all',
        showModal: false,
        selectedBadge: null,

        init() {
            // Alpine.js initialization complete
        },

        async showDetail(badgeId) {
            try {
                const response = await fetch(`/api/badges/${badgeId}`);
                if (!response.ok) throw new Error('Badge not found');
                this.selectedBadge = await response.json();
                this.showModal = true;
            } catch (error) {
                console.error('Failed to load badge detail:', error);
                showNotification('加载勋章详情失败', 'error');
            }
        },

        closeModal() {
            this.showModal = false;
            this.selectedBadge = null;
        },

        formatDate(dateString) {
            return formatDate(dateString);
        }
    };
}

// Export for use in Alpine.js
window.YoachiUtils = {
    formatDate,
    calculateProgress,
    showNotification
};
