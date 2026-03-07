// api.js - Async Operation Utility

/**
 * Sends a request without waiting for the response (fire-and-forget style).
 * It sends the request and returns immediately.
 * 
 * NOTE: Since fetch is Promise-based, "returning immediately" effectively means 
 * we just start the fetch and don't await it in the main UI flow, 
 * OR we await it but don't block the UI with a full-screen overlay.
 * 
 * However, the requirement says "NOT await response". 
 * So we will trigger the fetch and attach a catch handler for logging.
 * 
 * @param {string} url - API endpoint
 * @param {object} options - Fetch options (method, body, etc.)
 * @returns {void}
 */
function asyncOperation(url, options = {}) {
    // We explicitly do NOT return the promise to the caller to prevent awaiting.
    fetch(url, options)
        .then(response => {
            if (response.status === 401) {
                if (typeof PollinationsAuth !== 'undefined') {
                    PollinationsAuth.showReconnectToast();
                }
                return;
            }
            if (response.status === 402) {
                if (typeof PollinationsAuth !== 'undefined') {
                    PollinationsAuth.showBalanceToast();
                }
                return;
            }
            if (!response.ok) {
                return response.text().then(text => {
                    console.error(`Async operation failed [${url}]: ${text}`);
                    if (window.showToast) window.showToast(`Operation failed: ${text}`, 'error');
                });
            }
            if (window.showToast) window.showToast('Operation started', 'success');
        })
        .catch(err => {
            console.error(`Network error in async operation [${url}]:`, err);
            if (window.showToast) window.showToast(`Network error: ${err.message}`, 'error');
        });
}

// Export for ES6 (Browser) and CommonJS (Node/Test)
if (typeof module !== 'undefined' && typeof module.exports !== 'undefined') {
    module.exports = { asyncOperation };
} else {
    // For browser without modules, attach to window or just let it be global
    window.asyncOperation = asyncOperation;
}
