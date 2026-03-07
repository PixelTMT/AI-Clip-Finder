// polling.js - Polling Manager

const PollingManager = {
    intervals: {},
    
    /**
     * Start a polling task.
     * @param {string} name - Unique name for the task
     * @param {function} callback - Function to execute
     * @param {number} ms - Interval in milliseconds (default 3000)
     */
    start(name, callback, ms = 3000) {
        if (this.intervals[name]) {
            console.warn(`Polling task '${name}' already running. Restarting.`);
            this.stop(name);
        }
        
        // Execute immediately once? No, typical polling waits first interval.
        // But for UI responsiveness, usually we want immediate check then interval.
        // Let's assume the caller does an immediate check if needed.
        
        console.log(`Starting polling: ${name} (${ms}ms)`);
        this.intervals[name] = setInterval(async () => {
            try {
                await callback();
            } catch (err) {
                console.error(`Error in polling task '${name}':`, err);
            }
        }, ms);
    },
    
    /**
     * Stop a polling task.
     * @param {string} name - Unique name for the task
     */
    stop(name) {
        if (this.intervals[name]) {
            console.log(`Stopping polling: ${name}`);
            clearInterval(this.intervals[name]);
            delete this.intervals[name];
        }
    },
    
    /**
     * Stop all polling tasks.
     */
    stopAll() {
        Object.keys(this.intervals).forEach(key => this.stop(key));
    }
};

// Export
if (typeof module !== 'undefined' && typeof module.exports !== 'undefined') {
    module.exports = PollingManager;
} else {
    window.PollingManager = PollingManager;
}
