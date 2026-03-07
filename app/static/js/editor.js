document.addEventListener('DOMContentLoaded', initEditor);

// Global State
const state = {
    projectId: null,
    clipIndex: null,
    project: null,
    clip: null,
    transcript: null,
    sentences: [],
    video: document.getElementById('preview-video'),
    subtitleOverlay: document.getElementById('subtitle-overlay'),
    sentenceBuilder: new SentenceBuilder(),
    startTime: 0,
    endTime: 0,
    isPlaying: false,
    options: {
        startOffset: 0,
        endOffset: 0,
        fontFamily: 'Inter',
        fontSize: 'Medium',
        fontColor: '#FFFFFF',
        textStyle: 'Outline',
        subtitlePosition: 'Bottom'
    }
};

async function initEditor() {
    const urlParams = new URLSearchParams(window.location.search);
    state.projectId = urlParams.get('project');
    state.clipIndex = parseInt(urlParams.get('clip'));

    if (!state.projectId || isNaN(state.clipIndex)) {
        alert('Invalid project or clip parameters');
        return;
    }

    try {
        await loadClipData();
        setupVideo();
        setupControls();
        updateStyles(); // Apply defaults
    } catch (error) {
        console.error('Initialization error:', error);
        alert('Failed to load clip data: ' + error.message);
    }
}

async function loadClipData() {
    // 1. Fetch Project Status/Data
    const projectRes = await fetch(`/projects/${state.projectId}/status`);
    if (!projectRes.ok) throw new Error('Failed to fetch project');
    const projectData = await projectRes.json();
    
    // Fetch full project list
    const listRes = await fetch('/projects');
    const projects = await listRes.json();
    state.project = projects.find(p => p.project_id === state.projectId);
    
    if (!state.project) throw new Error('Project not found');
    if (!state.project.clips || !state.project.clips[state.clipIndex]) throw new Error('Clip not found');
    
    state.clip = state.project.clips[state.clipIndex];
    state.startTime = state.clip.start_time;
    state.endTime = state.clip.end_time;
    
    // 2. Fetch Transcript
    processTranscript();
    
    console.log('Loaded clip:', state.clip);
}

function processTranscript() {
    if (state.project.transcript && state.project.transcript.words) {
        state.transcript = state.project.transcript.words;
        
        // Apply offsets
        const finalStart = Math.max(0, state.startTime + state.options.startOffset);
        const finalEnd = state.endTime + state.options.endOffset;
        
        const clipWords = state.sentenceBuilder.filterWords(
            state.transcript, 
            finalStart, 
            finalEnd
        );
        
        state.sentences = state.sentenceBuilder.groupWords(clipWords);
    }
}

function setupVideo() {
    const videoSrc = `/media/${state.projectId}/processed.mp4`;
    state.video.src = videoSrc;
    state.video.currentTime = Math.max(0, state.startTime + state.options.startOffset);
    
    state.video.addEventListener('loadedmetadata', () => {
        state.video.currentTime = Math.max(0, state.startTime + state.options.startOffset);
    });
    
    state.video.addEventListener('timeupdate', handleTimeUpdate);
    state.video.addEventListener('ended', stopPlayback);
    
    updateTimeDisplay();
}

function setupControls() {
    document.getElementById('btn-play-pause').addEventListener('click', togglePlay);
    document.getElementById('btn-restart').addEventListener('click', restartClip);
    
    // Style Controls
    const styleInputs = ['font-family', 'font-size', 'font-color', 'text-style', 'subtitle-position'];
    styleInputs.forEach(id => {
        const elem = document.getElementById(id);
        elem.addEventListener('change', updateStyles);
        elem.addEventListener('input', updateStyles); // For color picker
    });
    
    // Offset Controls
    document.getElementById('start-offset').addEventListener('change', updateOffsets);
    document.getElementById('end-offset').addEventListener('change', updateOffsets);
    
    // Action Buttons
    document.getElementById('btn-create-clip').addEventListener('click', createClip);
    document.getElementById('btn-download').addEventListener('click', downloadFinal);
    document.getElementById('btn-back-edit').addEventListener('click', backToEdit);
}

async function createClip() {
    // Show loading
    document.getElementById('progress-overlay').classList.remove('hidden');
    document.getElementById('progress-text').textContent = 'Starting preview render...';
    
    // Prepare payload
    const payload = {
        project_id: state.projectId,
        clip_index: state.clipIndex,
        start_offset: state.options.startOffset,
        end_offset: state.options.endOffset,
        font_family: state.options.fontFamily,
        font_size: state.options.fontSize,
        font_color: state.options.fontColor,
        text_style: state.options.textStyle,
        subtitle_position: state.options.subtitlePosition
    };
    
    try {
        const res = await fetch('/api/clips/render-preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error('Failed to start render');
        const data = await res.json();
        
        // Start polling
        pollRenderStatus(data.task_id, true);
        
    } catch (error) {
        console.error(error);
        alert('Error: ' + error.message);
        document.getElementById('progress-overlay').classList.add('hidden');
    }
}

async function pollRenderStatus(taskId, isPreview) {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/api/clips/render-status/${taskId}`);
            if (!res.ok) throw new Error('Status check failed');
            const status = await res.json();
            
            // Update progress text
            const pct = Math.round(status.progress * 100);
            document.getElementById('progress-text').textContent = `Rendering... ${pct}%`;
            
            if (status.status === 'completed') {
                clearInterval(interval);
                document.getElementById('progress-overlay').classList.add('hidden');
                
                if (isPreview) {
                    onPreviewReady(status.output_path); // Path might be relative or full
                } else {
                    // Trigger download
                    window.location.href = status.download_url;
                    alert('Download started!');
                }
            } else if (status.status === 'failed') {
                clearInterval(interval);
                throw new Error('Render failed on server');
            }
            
        } catch (error) {
            clearInterval(interval);
            console.error(error);
            alert('Render failed: ' + error.message);
            document.getElementById('progress-overlay').classList.add('hidden');
        }
    }, 1000);
}

function onPreviewReady(path) {
    // Switch to rendered video
    const filename = path.split(/[\\/]/).pop();
    const url = `/media/${state.projectId}/${filename}`;
    
    state.video.src = url;
    state.video.load();
    state.video.play();
    
    // Hide live overlay (burned in)
    state.subtitleOverlay.classList.add('hidden');
    
    // UI Updates
    document.getElementById('btn-create-clip').classList.add('hidden');
    document.getElementById('btn-download').classList.remove('hidden');
    document.getElementById('btn-back-edit').classList.remove('hidden');
    document.getElementById('controls-panel').classList.add('disabled-controls'); // Visual cue
    
    // Disable inputs
    const inputs = document.querySelectorAll('#controls-panel input, #controls-panel select');
    inputs.forEach(el => el.disabled = true);
    
    alert('Preview ready! Please review.');
}

function backToEdit() {
    // Switch video back to processed
    const videoSrc = `/media/${state.projectId}/processed.mp4`;
    state.video.src = videoSrc;
    
    // Restore time
    const finalStart = Math.max(0, state.startTime + state.options.startOffset);
    state.video.currentTime = finalStart;
    
    // Show live overlay
    state.subtitleOverlay.classList.remove('hidden');
    updateStyles(); // Ensure styles applied
    
    // UI Updates
    document.getElementById('btn-create-clip').classList.remove('hidden');
    document.getElementById('btn-download').classList.add('hidden');
    document.getElementById('btn-back-edit').classList.add('hidden');
    document.getElementById('controls-panel').classList.remove('disabled-controls');
    
    // Enable inputs
    const inputs = document.querySelectorAll('#controls-panel input, #controls-panel select');
    inputs.forEach(el => el.disabled = false);
}

async function downloadFinal() {
    // Show loading
    document.getElementById('progress-overlay').classList.remove('hidden');
    document.getElementById('progress-text').textContent = 'Rendering high-quality version...';
    
    const payload = {
        project_id: state.projectId,
        clip_index: state.clipIndex,
        start_offset: state.options.startOffset,
        end_offset: state.options.endOffset,
        font_family: state.options.fontFamily,
        font_size: state.options.fontSize,
        font_color: state.options.fontColor,
        text_style: state.options.textStyle,
        subtitle_position: state.options.subtitlePosition
    };
    
    try {
        const res = await fetch('/api/clips/render-final', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error('Failed to start final render');
        const data = await res.json();
        
        pollRenderStatus(data.task_id, false);
        
    } catch (error) {
        console.error(error);
        alert('Error: ' + error.message);
        document.getElementById('progress-overlay').classList.add('hidden');
    }
}

function updateStyles() {
    // Read values
    state.options.fontFamily = document.getElementById('font-family').value;
    state.options.fontSize = document.getElementById('font-size').value;
    state.options.fontColor = document.getElementById('font-color').value;
    state.options.textStyle = document.getElementById('text-style').value;
    state.options.subtitlePosition = document.getElementById('subtitle-position').value;
    
    // Update Color Hex
    document.getElementById('font-color-hex').textContent = state.options.fontColor;
    
    // Apply to Overlay Container
    const container = state.subtitleOverlay;
    
    // Position
    container.style.alignItems = 
        state.options.subtitlePosition === 'Top' ? 'flex-start' :
        state.options.subtitlePosition === 'Center' ? 'center' : 'flex-end';
        
    // Font
    container.style.fontFamily = state.options.fontFamily;
    
    // Font Size
    const sizeMap = { 'Small': '18px', 'Medium': '24px', 'Large': '32px' };
    container.style.fontSize = sizeMap[state.options.fontSize];
    
    // CSS Vars
    container.style.setProperty('--sub-color', state.options.fontColor);
    
    // Text Style (Shadow/Outline)
    let shadow = '';
    if (state.options.textStyle === 'Outline') {
        shadow = '-1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000';
    } else if (state.options.textStyle === 'Shadow') {
        shadow = '2px 2px 4px rgba(0,0,0,0.8)';
    } else {
        shadow = 'none';
    }
    container.style.setProperty('--sub-shadow', shadow);
    
    // Update current sentence styles manually if rendered
    const currentSentence = container.querySelector('.sentence-container');
    if (currentSentence) {
        currentSentence.style.color = state.options.fontColor;
        currentSentence.style.textShadow = shadow;
        currentSentence.style.fontFamily = state.options.fontFamily;
    }
}

function updateOffsets() {
    state.options.startOffset = parseFloat(document.getElementById('start-offset').value) || 0;
    state.options.endOffset = parseFloat(document.getElementById('end-offset').value) || 0;
    
    // Reprocess sentences
    processTranscript();
    updateTimeDisplay();
    
    // Seek to new start if current is before
    const finalStart = Math.max(0, state.startTime + state.options.startOffset);
    if (state.video.currentTime < finalStart) {
        state.video.currentTime = finalStart;
    }
}

function handleTimeUpdate() {
    const current = state.video.currentTime;
    
    // Update Subtitles
    updateSubtitleOverlay(current);
    
    // Auto-stop at end boundary
    const finalEnd = state.endTime + state.options.endOffset;
    if (current >= finalEnd) {
        stopPlayback();
        // state.video.currentTime = finalEnd; // Optional snap
    }
    
    updateTimeDisplay();
}

function updateTimeDisplay() {
    const current = state.video.currentTime;
    const finalEnd = state.endTime + state.options.endOffset;
    document.getElementById('time-display').textContent = 
        formatTime(current) + ' / ' + formatTime(finalEnd);
}

function updateSubtitleOverlay(currentTime) {
    if (!state.sentences || state.sentences.length === 0) return;
    
    const activeSentence = state.sentences.find(s => currentTime >= s.start && currentTime <= s.end);
    
    if (!activeSentence) {
        state.subtitleOverlay.innerHTML = '';
        return;
    }
    
    // Render words
    let html = '';
    activeSentence.words.forEach(w => {
        const isActive = currentTime >= w.start && currentTime <= w.end;
        const styleClass = isActive ? 'word-active' : 'word-inactive';
        html += `<span class="${styleClass}">${w.word} </span>`;
    });
    
    // Inline styles for immediate feedback
    const color = state.options.fontColor;
    const font = state.options.fontFamily;
    let shadow = 'none';
    if (state.options.textStyle === 'Outline') {
        shadow = '-1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000';
    } else if (state.options.textStyle === 'Shadow') {
        shadow = '2px 2px 4px rgba(0,0,0,0.8)';
    }
    
    state.subtitleOverlay.innerHTML = `<div class="sentence-container" style="color:${color}; text-shadow:${shadow}; font-family:${font}">${html}</div>`;
}

function togglePlay() {
    if (state.video.paused) {
        const finalStart = Math.max(0, state.startTime + state.options.startOffset);
        const finalEnd = state.endTime + state.options.endOffset;
        
        if (state.video.currentTime >= finalEnd) {
            state.video.currentTime = finalStart;
        }
        state.video.play();
        document.getElementById('btn-play-pause').textContent = 'Pause';
    } else {
        state.video.pause();
        document.getElementById('btn-play-pause').textContent = 'Play';
    }
}

function stopPlayback() {
    state.video.pause();
    document.getElementById('btn-play-pause').textContent = 'Play';
}

function restartClip() {
    const finalStart = Math.max(0, state.startTime + state.options.startOffset);
    state.video.currentTime = finalStart;
    state.video.play();
    document.getElementById('btn-play-pause').textContent = 'Pause';
}

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
}
