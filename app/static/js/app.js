// Utility Functions
function formatTime(seconds) {
    if (!seconds) return "00:00";
    seconds = Math.round(seconds);
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    
    const pad = num => num.toString().padStart(2, '0');
    
    if (h > 0) {
        return `${pad(h)}:${pad(m)}:${pad(s)}`;
    } else {
        return `${pad(m)}:${pad(s)}`;
    }
}

// Expose for manual verification
if (typeof window !== 'undefined') {
    window.formatTime = formatTime;
}

// --- Pollinations BYOP Auth ---
const PollinationsAuth = (() => {
    const STORAGE_KEY = 'pollinations_api_key';

    function getKey() {
        return localStorage.getItem(STORAGE_KEY);
    }

    function setKey(key) {
        localStorage.setItem(STORAGE_KEY, key);
    }

    function clearKey() {
        localStorage.removeItem(STORAGE_KEY);
    }

    function getAuthHeaders() {
        const key = getKey();
        return key ? { 'Authorization': `Bearer ${key}` } : {};
    }

    async function fetchAppConfig() {
        try {
            const res = await fetch('/config/pollinations');
            if (!res.ok) return null;
            return await res.json();
        } catch (e) {
            return null;
        }
    }

    function handleCallback() {
        // URL fragment: #api_key=sk_abc123
        const fragment = window.location.hash;
        if (fragment.includes('api_key=')) {
            const key = fragment.split('api_key=')[1].split('&')[0];
            if (key) {
                setKey(key);
                // Clean URL without reloading
                history.replaceState(null, '', window.location.pathname);
                return true;
            }
        }
        return false;
    }

    async function init(btnConnect, statusEl) {
        // Check if returning from OAuth
        handleCallback();

        const config = await fetchAppConfig();
        const appKey = config ? config.app_key : '';
        const authUrl = config ? config.auth_url : 'https://enter.pollinations.ai/authorize';

        function updateUI() {
            const key = getKey();
            if (key) {
                btnConnect.textContent = 'Reconnect';
                btnConnect.className = 'auth-btn connected';
                statusEl.textContent = 'Connected';
                statusEl.className = 'auth-status connected';
            } else {
                btnConnect.textContent = 'Connect with Pollinations';
                btnConnect.className = 'auth-btn';
                statusEl.textContent = 'Not connected';
                statusEl.className = 'auth-status disconnected';
            }
        }

        btnConnect.addEventListener('click', () => {
            const redirectUrl = encodeURIComponent(window.location.href.split('#')[0]);
            const url = `${authUrl}?redirect_url=${redirectUrl}&app_key=${appKey}`;
            window.location.href = url;
        });

        updateUI();
    }

    function showReconnectToast() {
        if (window.showToast) {
            window.showToast('Pollinations key expired. Please reconnect.', 'error', 8000);
        }
        clearKey();
        // Update UI if elements still in DOM
        const btnConnect = document.getElementById('btn-connect-pollinations');
        const statusEl = document.getElementById('pollinations-status');
        if (btnConnect && statusEl) {
            btnConnect.textContent = 'Connect with Pollinations';
            btnConnect.className = 'auth-btn';
            statusEl.textContent = 'Not connected';
            statusEl.className = 'auth-status disconnected';
        }
    }

    function showBalanceToast() {
        if (window.showToast) {
            window.showToast(
                'Insufficient Pollinations balance. <a href="https://pollinations.ai/pricing" target="_blank" style="color:#fff;text-decoration:underline">Top up here</a>',
                'error',
                10000
            );
        }
    }

    return { getKey, setKey, clearKey, getAuthHeaders, init, showReconnectToast, showBalanceToast };
})();
document.addEventListener('DOMContentLoaded', () => {
    const videoUpload = document.getElementById('video-upload');
    const projectList = document.getElementById('project-list');
    const workspace = document.getElementById('workspace');
    const noProjectMsg = document.getElementById('no-project-msg');
    const projectDetails = document.getElementById('project-details');
    const errorBanner = document.getElementById('error-banner');
    const mainVideo = document.getElementById('main-video');
    const transcriptContent = document.getElementById('transcript-content');
    const clipsList = document.getElementById('clips-list');
    const timelineContainer = document.getElementById('timeline-container');
    const progressOverlay = document.getElementById('progress-overlay');
    const progressText = document.getElementById('progress-text');

    const btnTranscribe = document.getElementById('btn-transcribe');
    const btnGenerateAss = document.getElementById('btn-generate-ass');
    const btnAnalyze = document.getElementById('btn-analyze');
    const analysisControls = document.getElementById('analysis-controls');
    const clipCountInput = document.getElementById('clip-count');
    const customPromptInput = document.getElementById('custom-prompt');
    const notificationArea = document.getElementById('notification-area');
    const clipSortSelect = document.getElementById('clip-sort');

    const assConfigModal = document.getElementById('ass-config-modal');
    const btnAssCancel = document.getElementById('btn-ass-cancel');
    const btnAssGenerate = document.getElementById('btn-ass-generate');

    // Init Pollinations Auth
    const btnConnectPollinations = document.getElementById('btn-connect-pollinations');
    const pollinationsStatus = document.getElementById('pollinations-status');
    PollinationsAuth.init(btnConnectPollinations, pollinationsStatus);

    let projects = [];
    let selectedProjectId = null;
    let activeClipEndTime = null;
    let currentClips = [];

    function renderNotifications(activeProjects) {
        notificationArea.innerHTML = '';
        
        activeProjects.forEach(p => {
            const op = p.active_operation;
            if (!op) return;
            
            const div = document.createElement('div');
            div.className = 'notification-card';
            
            const typeMap = {
                'upload': 'Uploading Video',
                'transcribe': 'Transcribing Audio',
                'find_clips': 'Analyzing Content'
            };
            
            const title = typeMap[op.type] || 'Processing';
            const message = op.message || op.status;
            
            div.innerHTML = `
                <div class="notification-content">
                    <div class="notification-title">${p.name}</div>
                    <div class="notification-status">
                        <span class="mini-spinner"></span> ${title}: ${message}
                    </div>
                </div>
            `;
            notificationArea.appendChild(div);
        });
    }

    const toastContainer = document.getElementById('toast-container');

    function showToast(message, type = 'success', duration = 5000) {
        const div = document.createElement('div');
        div.className = `toast ${type}`;
        div.innerHTML = `
            <span>${message}</span>
            <span style="cursor:pointer;margin-left:10px" onclick="this.parentElement.remove()">×</span>
        `;
        toastContainer.appendChild(div);
        
        setTimeout(() => {
            div.style.animation = 'fadeOut 0.3s ease-out';
            div.addEventListener('animationend', () => div.remove());
        }, duration);
    }

    // Expose showToast globally if needed, or just use internally
    window.showToast = showToast;

    // --- Polling Logic ---
    
    function startOperationsPolling() {
        PollingManager.start('active-ops', async () => {
            try {
                // Fetch active operations (prevent cache)
                const res = await fetch(`/projects/active-operations?t=${Date.now()}`);
                if (!res.ok) return;
                const activeProjects = await res.json();
                console.log(activeProjects);
                if (activeProjects.length > 0) {
                    await fetchProjects(); // Simplest approach: refresh list
                    // Update Notifications
                    renderNotifications(activeProjects);
                    // If current selected project was active, refresh detail view
                    if (selectedProjectId) {
                        // Always refresh current view if polling is active.
                        // This handles cases where:
                        // 1. Current project is active (show progress)
                        // 2. Current project JUST finished but polling is kept alive by another project
                        // 3. Current project status changed externally
                        selectProject(selectedProjectId);
                    }
                } else {
                    // Optimization: If no operations running, slow down polling? 
                    // Or stop it until user does something?
                    // Requirement: "Stop polling when no active operations exist (optimization)"
                    // "Resume polling when new operation starts"
                    
                    // IMPORTANT: Before stopping, we must do ONE final refresh to ensure 
                    // the "Completed" state is reflected in UI.
                    // Otherwise, we stop polling while UI still shows "Running".
                    await fetchProjects();
                    if (selectedProjectId) {
                        selectProject(selectedProjectId);
                    }
                    
                    // Clear notifications
                    renderNotifications([]);
                    
                    PollingManager.stop('active-ops');
                }
            } catch (err) {
                console.error("Polling error:", err);
            }
        }, 1500); // Reduced to 1.5s for better responsiveness
    }
    
    // Call this when we know an operation started
    function triggerPolling() {
        startOperationsPolling();
    }

    // Also start on load to check for any persistent operations
    startOperationsPolling();

    // --- API Calls ---

    async function fetchProjects() {
        // Add timestamp to prevent caching
        const res = await fetch(`/projects?t=${Date.now()}`);
        if (!res.ok) {
            console.error("Failed to fetch projects");
            return;
        }
        projects = await res.json();
        renderProjectList();
    }

    async function createProject(name) {
        const res = await fetch('/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        return await res.json();
    }

    async function uploadVideo(projectId, file) {
        const formData = new FormData();
        formData.append('file', file);
        
        // Use asyncOperation for non-blocking upload
        // Note: For upload, we usually want to know if the upload request *started* successfully
        // but for now we follow the pattern "fire and forget".
        // HOWEVER: Standard upload needs waiting for the file to reach the server.
        // The endpoint returns immediately after receiving the file? No, endpoint waits for file.read().
        // So the "Upload" request itself takes time proportional to file size.
        // If we make it purely async, the UI will say "Uploading..." but we won't know if it failed 5s later.
        // But the requirement says: "Modify upload form submission to use async pattern"
        // and "Immediately add project to sidebar with 'Uploading...' status".
        
        // We still need to await the request to get the 'project_id' or confirmation?
        // Wait, 'createProject' is separate.
        // 'uploadVideo' is `POST /projects/{id}/upload`.
        // The server processes upload in background? 
        // No, `await file.read()` is awaited. So the client MUST wait for bytes to send.
        
        // The "Async Pattern" here effectively means:
        // 1. Trigger the upload fetch
        // 2. Do NOT await the *completion* of the fetch in the UI thread blocking way (no full screen spinner).
        // 3. Instead, let it run in background and rely on polling to see status?
        // BUT: Fetch itself is async. If we don't await it, we don't know when it finishes sending.
        // Browser handles the upload in background if we just call fetch.
        
        // Let's use asyncOperation logic: call fetch but don't await the promise in the main flow.
        asyncOperation(`/projects/${projectId}/upload`, {
            method: 'POST',
            body: formData
        });
    }

    async function startTranscription(projectId) {
        // Use asyncOperation
        asyncOperation(`/projects/${projectId}/transcribe`, {
            method: 'POST',
            headers: PollinationsAuth.getAuthHeaders()
        });
        // We can optimistically assume it started and just update UI via fetchProjects
        // But fetchProjects might be too fast and backend hasn't updated status yet.
        // However, asyncOperation is also "fast" (just triggers fetch).
        // Let's rely on polling later. For now, we just don't block.
    }

    async function startAnalysis(projectId, customPrompt, clipCount) {
        const params = new URLSearchParams();
        if (customPrompt) params.append('custom_prompt', customPrompt);
        if (clipCount) params.append('clip_count', clipCount);

        // Use asyncOperation
        asyncOperation(`/projects/${projectId}/analyze?${params.toString()}`, {
            method: 'POST',
            headers: PollinationsAuth.getAuthHeaders()
        });
    }

    async function deleteProject(projectId) {
        if (!confirm('Are you sure you want to delete this project?')) return;
        await fetch(`/projects/${projectId}`, { method: 'DELETE' });
        
        if (selectedProjectId === projectId) {
            selectedProjectId = null;
            projectDetails.classList.add('hidden');
            noProjectMsg.classList.remove('hidden');
        }
        await fetchProjects();
    }

    // --- UI Logic ---

    function renderProjectList() {
        projectList.innerHTML = '';
        projects.forEach(p => {
            const div = document.createElement('div');
            div.className = `project-item ${selectedProjectId === p.project_id ? 'active' : ''}`;
            
            // Determine display status
            let displayStatus = p.status;
            let statusClass = '';
            let showSpinner = false;
            
            if (p.active_operation && p.active_operation.status === 'running') {
                // ...
                statusClass = 'status-running';
                showSpinner = true;
            } else if (p.status === 'error') {
                statusClass = 'status-error';
            } else if (['completed', 'uploaded', 'transcribed'].includes(p.status)) {
                statusClass = 'status-completed';
            }

            const spinnerHtml = showSpinner ? '<span class="mini-spinner"></span>' : '';

            div.innerHTML = `
                <div class="project-info">
                    <span class="project-name">${p.name}</span>
                    <span class="project-status ${statusClass}">
                        ${spinnerHtml} ${displayStatus}
                    </span>
                </div>
                <button class="delete-btn" data-id="${p.project_id}">×</button>
            `;
            
            div.onclick = (e) => {
                if (e.target.classList.contains('delete-btn')) {
                    e.stopPropagation();
                    deleteProject(e.target.dataset.id);
                } else {
                    selectProject(p.project_id);
                }
            };
            projectList.appendChild(div);
        });
    }

    function selectProject(id) {
        selectedProjectId = id;
        const project = projects.find(p => p.project_id === id);
        if (!project) return;

        renderProjectList();
        noProjectMsg.classList.add('hidden');
        projectDetails.classList.remove('hidden');

        // Setup Error Banner
        if (project.error) {
            errorBanner.innerText = project.error;
            errorBanner.classList.remove('hidden');
        } else {
            errorBanner.classList.add('hidden');
        }

        // Setup Video
        // Only update source if it changed to prevent reloading
        let targetSrc = '';
        if (project.status !== 'created' && project.status !== 'uploading' && project.status !== 'compressing') {
            targetSrc = `/media/${project.project_id}/processed.mp4`;
        }
        
        // Decode URI component to handle potential encoding differences or just check end
        if (mainVideo.getAttribute('src') !== targetSrc) {
             mainVideo.src = targetSrc;
        }

        // Setup Buttons State
        const op = project.active_operation;
        const status = project.status;
        
        const videoReady = status !== 'created' && status !== 'uploading' && status !== 'compressing';
        const isTranscribing = (op && op.type === 'transcribe') || status === 'transcribing';
        const isAnalyzing = (op && op.type === 'find_clips') || status === 'analyzing';
        const hasTranscript = !!project.transcript;

        // Transcribe Button
        // Disable if video not ready OR transcribing OR analyzing (as requested)
        btnTranscribe.disabled = !videoReady || isTranscribing || isAnalyzing;
        btnTranscribe.innerText = isTranscribing ? "Transcribing..." : "Transcribe";
        if (!videoReady) btnTranscribe.title = "Upload video first";
        else if (isTranscribing) btnTranscribe.title = "Transcription in progress";
        else if (isAnalyzing) btnTranscribe.title = "Analysis in progress";
        else btnTranscribe.title = "";

        // Analyze Button
        // Disable if no transcript OR if transcription is running OR if analysis is running
        btnAnalyze.disabled = !hasTranscript || isTranscribing || isAnalyzing;
        btnAnalyze.innerText = isAnalyzing ? "Finding Clips..." : "Find Clips";
        if (!hasTranscript) btnAnalyze.title = "Transcribe video first";
        else if (isTranscribing) btnAnalyze.title = "Waiting for transcription to finish";
        else if (isAnalyzing) btnAnalyze.title = "Analysis in progress";
        else btnAnalyze.title = "";

        // Setup Buttons - Always show them as requested
        btnTranscribe.classList.remove('hidden');
        analysisControls.classList.remove('hidden');

        // ASS Button visibility
        if (hasTranscript) {
            btnGenerateAss.classList.remove('hidden');
        } else {
            btnGenerateAss.classList.add('hidden');
        }
        btnGenerateAss.disabled = !hasTranscript;

        // Populate Controls
        // Only update input value if user is not currently focusing it? 
        // Or if it differs? Assuming simple refresh for now.
        if (document.activeElement !== clipCountInput) {
             clipCountInput.value = project.clip_count !== undefined && project.clip_count !== null ? project.clip_count : '';
        }
        if (document.activeElement !== customPromptInput) {
             customPromptInput.value = project.custom_prompt || '';
        }

        // Render Data
        renderTranscript(project.transcript);
        renderClips(project.clips, project.project_id);
    }

    function renderTranscript(transcript) {
        transcriptContent.innerHTML = '';
        if (!transcript || !transcript.segments) return;

        transcript.segments.forEach(seg => {
            const div = document.createElement('div');
            div.className = 'transcript-segment';
            div.innerText = `[${seg.start.toFixed(1)}s] ${seg.text}`;
            div.dataset.start = seg.start;
            div.dataset.end = seg.end;
            div.onclick = () => {
                mainVideo.currentTime = seg.start;
                activeClipEndTime = null; // Clear auto-stop for transcript navigation
                mainVideo.play();
            };
            transcriptContent.appendChild(div);
        });
    }

    function renderClips(clips, projectId) {
        currentClips = clips || [];
        
        // Apply Sorting
        const sortType = clipSortSelect.value;
        const sortedClips = [...currentClips].sort((a, b) => {
            if (sortType === 'score') {
                return (b.score || 0) - (a.score || 0);
            } else if (sortType === 'time') {
                return (a.start_time || 0) - (b.start_time || 0);
            }
            return 0;
        });

        clipsList.innerHTML = '';
        renderTimeline();
        if (!sortedClips.length) return;

        sortedClips.forEach((clip) => {
            // Find original index for the editor link
            const originalIndex = currentClips.indexOf(clip);
            const startTime = clip.start_time || 0;
            const endTime = clip.end_time || 0;
            const duration = endTime - startTime;

            const card = document.createElement('div');
            card.className = 'clip-card';
            card.innerHTML = `
                <img class="clip-thumbnail" src="/media/${projectId}/thumbnails/${startTime.toFixed(1)}.jpg">
                <div class="clip-info">
                    <div class="clip-header">
                        <span class="clip-score">${clip.score}/10</span>
                        <span class="clip-title">${clip.title}</span>
                    </div>
                    <div class="clip-meta">
                        <span>${formatTime(startTime)} - ${formatTime(endTime)}</span>
                        <span>Duration: ${formatTime(duration)}</span>
                    </div>
                    <small>${clip.reason}</small>
                    <button class="action-btn small btn-select-clip" data-index="${originalIndex}">Select & Edit</button>
                </div>
            `;
            
            // Card click plays video
            card.onclick = (e) => {
                // Prevent playing if button clicked
                if (e.target.classList.contains('btn-select-clip')) {
                    e.stopPropagation();
                    const url = `/static/editor.html?project=${projectId}&clip=${originalIndex}`;
                    window.open(url, '_blank');
                    return;
                }
                
                mainVideo.currentTime = startTime;
                activeClipEndTime = endTime; // Set auto-stop
                mainVideo.play();
            };
            clipsList.appendChild(card);
        });
    }

    // --- Event Handlers ---

    clipSortSelect.onchange = () => {
        if (selectedProjectId) {
            const project = projects.find(p => p.project_id === selectedProjectId);
            if (project) {
                renderClips(project.clips, selectedProjectId);
            }
        }
    };

    videoUpload.onchange = async () => {
        if (!videoUpload.files.length) return;
        const file = videoUpload.files[0];
        
        try {
            // Create project first (this is fast and sync-ish)
            const project = await createProject(file.name);
            
            // OPTIMISTIC UPDATE: Manually set status to "uploading" locally
            // This ensures instant feedback before first poll
            project.status = "uploading";
            project.active_operation = {
                type: 'upload',
                status: 'running',
                message: 'Starting upload...'
            };
            
            // Add to list manually or via fetch (we use fetch for now, but modify it after?)
            // Actually, we can just push to 'projects' and render, then start upload
            projects.unshift(project); // Add to top
            renderProjectList();
            selectProject(project.project_id);
            
            // Start upload (async/non-blocking)
            uploadVideo(project.project_id, file);
            
            triggerPolling(); // Start polling for completion
            
            // Reset the input so that choosing the same file again works (e.g. after deletion)
            videoUpload.value = '';
            
        } catch (err) {
            alert('Creation failed: ' + err.message);
        }
    };

    btnTranscribe.onclick = async () => {
        try {
            startTranscription(selectedProjectId);
            
            // Immediate UI update - optimistically show it started?
            // Actually, since we don't await, we should just inform user or let polling handle it.
            // For now, let's just log and maybe refresh list to see if status changed (it should change to 'transcribing')
            
            // Wait a tiny bit to allow server to set status
            setTimeout(async () => {
               await fetchProjects();
               // We might want to disable the button manually here until refresh confirms status
               btnTranscribe.disabled = true; 
               btnTranscribe.innerText = "Starting...";
               
               triggerPolling(); // Start polling
            }, 500);

        } catch (err) {
            alert('Transcription trigger failed: ' + err.message);
        }
    };

    btnAnalyze.onclick = async () => {
        try {
            const prompt = customPromptInput.value;
            const count = clipCountInput.value;
            startAnalysis(selectedProjectId, prompt, count);
            
            setTimeout(async () => {
                await fetchProjects();
                btnAnalyze.disabled = true;
                btnAnalyze.innerText = "Analyzing...";
                triggerPolling();
            }, 500);

        } catch (err) {
            alert('Analysis trigger failed: ' + err.message);
        }
    };

    btnGenerateAss.onclick = () => {
        assConfigModal.classList.remove('hidden');
    };

    btnAssCancel.onclick = () => {
        assConfigModal.classList.add('hidden');
    };

    function convertHexToASS(hex) {
        // #RRGGBB -> &H00BBGGRR
        const r = hex.substring(1, 3).toUpperCase();
        const g = hex.substring(3, 5).toUpperCase();
        const b = hex.substring(5, 7).toUpperCase();
        return `&H00${b}${g}${r}`;
    }

    btnAssGenerate.onclick = async () => {
        const options = {
            bg_color: convertHexToASS(document.getElementById('ass-bg-color').value),
            text_color: convertHexToASS(document.getElementById('ass-text-color').value),
            font_size: parseInt(document.getElementById('ass-font-size').value),
            pulse_scale: parseFloat(document.getElementById('ass-pulse-scale').value),
            alignment: parseInt(document.getElementById('ass-alignment').value)
        };

        assConfigModal.classList.add('hidden');
        showProgress("Generating Subtitles...");

        try {
            const res = await fetch(`/projects/${selectedProjectId}/generate-ass`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(options)
            });

            if (!res.ok) throw new Error("Generation failed");

            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `subtitles_${selectedProjectId}.ass`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            showToast("Subtitles downloaded successfully!");
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            hideProgress();
        }
    };

    function showProgress(text) {
        progressText.innerText = text;
        progressOverlay.classList.remove('hidden');
    }

    function hideProgress() {
        progressOverlay.classList.add('hidden');
    }

    // Video Sync
    mainVideo.onloadedmetadata = renderTimeline;
    
    mainVideo.ontimeupdate = () => {
        const time = mainVideo.currentTime;

        // Auto-stop logic
        if (activeClipEndTime && time >= activeClipEndTime) {
            mainVideo.pause();
            activeClipEndTime = null;
        }

        document.querySelectorAll('.transcript-segment').forEach(el => {
            const start = parseFloat(el.dataset.start);
            const end = parseFloat(el.dataset.end);
            if (time >= start && time <= end) {
                el.classList.add('active');
            } else {
                el.classList.remove('active');
            }
        });
    };

    function renderTimeline() {
        timelineContainer.innerHTML = '';
        const duration = mainVideo.duration;
        if (!duration || !currentClips.length) return;

        currentClips.forEach(clip => {
            const start = clip.start_time || 0;
            const end = clip.end_time || 0;
            
            // Sanity check to avoid bad math
            if (end <= start) return;
            
            const left = (start / duration) * 100;
            const width = ((end - start) / duration) * 100;

            const marker = document.createElement('div');
            marker.className = 'timeline-clip-marker';
            marker.style.left = `${left}%`;
            marker.style.width = `${width}%`;
            marker.title = `${clip.title} (${formatTime(start)} - ${formatTime(end)})`;
            
            timelineContainer.appendChild(marker);
        });
    }

    // Init
    fetchProjects();
});

if (typeof module !== 'undefined') {
    module.exports = { formatTime };
}