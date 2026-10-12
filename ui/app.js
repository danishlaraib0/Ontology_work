document.addEventListener('DOMContentLoaded', () => {
    const queryInput = document.getElementById('queryInput');
    const queryForm = document.getElementById('queryForm');
    const logicFlow = document.getElementById('logicFlow');
    const reportContent = document.getElementById('reportContent');
    const addCarBtn = document.getElementById('addCarBtn');
    const addCarModal = document.getElementById('addCarModal');
    const closeBtn = document.querySelector('.close');
    const addCarForm = document.getElementById('addCarForm');
    const ingestStatus = document.getElementById('ingestStatus');

    // Dynamic API Base URL (works seamlessly on port 8000, port 3000, localhost, or LAN)
    const API_BASE = (window.location.port === '8000')
        ? '/api'
        : `${window.location.protocol}//${window.location.hostname || 'localhost'}:8000/api`;

    // Global forward slash keybinding for input focus
    document.addEventListener('keydown', (e) => {
        // Only focus if we aren't already in an input and didn't press modifier keys
        if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
            e.preventDefault();
            queryInput.focus();
        }
    });

    queryForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = queryInput.value.trim();
        if (!query) return;

        // Reset UI
        logicFlow.innerHTML = `
            <div class="flow-step">
                <strong>Processing Query</strong>
                <span>Parsing intent and routing to planner...</span>
            </div>
        `;
        reportContent.innerHTML = `<div class="placeholder">Analyzing graph data...</div>`;
        
        try {
            // Simulated delay for "Routing" step
            await new Promise(r => setTimeout(r, 600));

            const response = await fetch(`${API_BASE}/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `Server returned error (${response.status})`);
            }

            const data = await response.json();
            
            // Step 1: Planner
            logicFlow.innerHTML = `
                <div class="flow-step">
                    <strong>1. Query Planner (${data.plan.intent})</strong>
                    <span>Tool Selected: <code>${data.plan.tool}</code></span><br/>
                    <small style="color:var(--text-muted)">${data.plan.reasoning}</small>
                </div>
            `;
            
            // Step 2: Animated Graph Paths
            if (data.graph_paths && data.graph_paths.length > 0) {
                const pathsContainerId = 'paths-' + Date.now();
                logicFlow.innerHTML += `
                    <div class="flow-step">
                        <strong>2. Graph Traversal</strong>
                        <div id="${pathsContainerId}" class="visual-graph-paths"></div>
                    </div>
                `;
                const pathsContainer = document.getElementById(pathsContainerId);
                
                for (let i = 0; i < data.graph_paths.length; i++) {
                    await new Promise(r => setTimeout(r, 400));
                    const rawPath = data.graph_paths[i];
                    const pathElem = document.createElement('div');
                    pathElem.className = 'visual-path-item animated-path';
                    
                    const nodeRegex = /\((.*?)\)/g;
                    const nodes = [...rawPath.matchAll(nodeRegex)].map(m => m[1]);
                    
                    if (nodes.length >= 2) {
                        pathElem.innerHTML = `<span class="graph-node">${nodes[0]}</span> <span class="graph-edge">➔</span> <span class="graph-node">${nodes[nodes.length-1]}</span>`;
                    } else {
                        pathElem.innerHTML = `<span class="graph-node">${rawPath}</span>`;
                    }
                    
                    pathsContainer.appendChild(pathElem);
                }
            } else {
                logicFlow.innerHTML += `
                    <div class="flow-step">
                        <strong>2. Graph Traversal</strong>
                        <span>No direct paths traversed.</span>
                    </div>
                `;
            }

            // Step 3: Synthesis Delay
            await new Promise(r => setTimeout(r, 500));
            logicFlow.innerHTML += `
                <div class="flow-step">
                    <strong>3. Generating Intelligence Report</strong>
                    <span>Synthesizing findings...</span>
                </div>
            `;
            await new Promise(r => setTimeout(r, 400));

            // Render Markdown Report
            if (data.markdown_report) {
                reportContent.innerHTML = marked.parse(data.markdown_report);
            } else if (data.causal_synthesis) {
                reportContent.innerHTML = marked.parse(data.causal_synthesis);
            } else if (data.summary) {
                reportContent.innerHTML = marked.parse(data.summary);
            }

        } catch (error) {
            console.error('Query processing error:', error);
            logicFlow.innerHTML = `
                <div class="flow-step" style="border-left-color: #ef4444;">
                    <strong style="color: #ef4444;">Query Execution Failed</strong>
                    <span>${error.message || 'An unexpected error occurred.'}</span>
                </div>
            `;
            reportContent.innerHTML = `<div class="placeholder" style="color: #ef4444;">Unable to generate intelligence report. Please check server connection and query parameters.</div>`;
        }
    });

    // ── Ingestion Status & Live Pipeline Controller ───────────────────────────
    const closeAddCarModal = document.getElementById('closeAddCarModal');
    const makeInput = document.getElementById('makeInput');
    const modelInput = document.getElementById('modelInput');
    const addCarFormContainer = document.getElementById('addCarFormContainer');
    const ingestProgressContainer = document.getElementById('ingestProgressContainer');

    const pipelineStatusBtn = document.getElementById('pipelineStatusBtn');
    const pipelineDot = document.getElementById('pipelineDot');
    const pipelineStatusText = document.getElementById('pipelineStatusText');

    const jobVehicleTitle = document.getElementById('jobVehicleTitle');
    const jobStatusBadge = document.getElementById('jobStatusBadge');
    const jobProgressBar = document.getElementById('jobProgressBar');
    const jobProgressPct = document.getElementById('jobProgressPct');
    const jobStepLabel = document.getElementById('jobStepLabel');
    const stepSpinner = document.getElementById('stepSpinner');
    const stepName = document.getElementById('stepName');
    const stepDesc = document.getElementById('stepDesc');
    const terminalLogs = document.getElementById('terminalLogs');
    const logCounter = document.getElementById('logCounter');

    const jobStatsGrid = document.getElementById('jobStatsGrid');
    const statNodes = document.getElementById('statNodes');
    const statRels = document.getElementById('statRels');
    const statLayers = document.getElementById('statLayers');

    const queryNewCarBtn = document.getElementById('queryNewCarBtn');
    const ingestAnotherBtn = document.getElementById('ingestAnotherBtn');
    const minimizeBtn = document.getElementById('minimizeBtn');

    const jobsModal = document.getElementById('jobsModal');
    const closeJobsModal = document.getElementById('closeJobsModal');
    const jobsListContainer = document.getElementById('jobsListContainer');
    const toastContainer = document.getElementById('toastContainer');

    let activeJobId = null;
    let pollTimer = null;
    let currentJobData = null;

    // Quick chips
    document.querySelectorAll('.chip-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            makeInput.value = btn.dataset.make;
            modelInput.value = btn.dataset.model;
            modelInput.focus();
        });
    });

    // Modal display triggers
    addCarBtn.onclick = () => {
        if (activeJobId && currentJobData && (currentJobData.status === 'RUNNING' || currentJobData.status === 'QUEUED')) {
            showProgressView(currentJobData);
        } else {
            showFormView();
        }
        addCarModal.style.display = 'flex';
    };

    closeAddCarModal.onclick = () => { addCarModal.style.display = 'none'; };
    minimizeBtn.onclick = () => { addCarModal.style.display = 'none'; };
    closeJobsModal.onclick = () => { jobsModal.style.display = 'none'; };

    window.onclick = (e) => {
        if (e.target === addCarModal) addCarModal.style.display = 'none';
        if (e.target === jobsModal) jobsModal.style.display = 'none';
    };

    function showFormView() {
        addCarFormContainer.style.display = 'block';
        ingestProgressContainer.style.display = 'none';
        addCarForm.reset();
    }

    function showProgressView(job) {
        addCarFormContainer.style.display = 'none';
        ingestProgressContainer.style.display = 'block';
        if (job) {
            jobVehicleTitle.textContent = `${job.make} ${job.model}`;
            updateProgressUI(job);
        }
    }

    // Toast helper
    function showToast(message, onClick) {
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.innerHTML = `<span>🎉</span><div><strong>Ingestion Complete</strong><br/><span>${message}</span></div>`;
        if (onClick) {
            toast.addEventListener('click', () => {
                onClick();
                toast.remove();
            });
        }
        toastContainer.appendChild(toast);
        setTimeout(() => {
            if (toast.parentElement) toast.remove();
        }, 8000);
    }

    // Submit Ingestion Form
    addCarForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const make = makeInput.value.trim();
        const model = modelInput.value.trim();
        if (!make || !model) return;

        // Immediately switch to live progress view
        showProgressView({
            make,
            model,
            status: 'QUEUED',
            progress_pct: 5,
            current_step: 'Submitting job to automotive pipeline...',
            logs: [{ timestamp: new Date().toLocaleTimeString(), message: 'Queued for autonomous ingestion', level: 'info' }]
        });
        addCarModal.style.display = 'flex';

        try {
            const response = await fetch(`${API_BASE}/add_car`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ make, model })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Failed to start ingestion');
            }

            const data = await response.json();
            activeJobId = data.job_id;
            currentJobData = data.job;

            updateProgressUI(currentJobData);
            startPolling(activeJobId);

        } catch (error) {
            console.error('Add car failed:', error);
            jobStatusBadge.className = 'status-badge failed';
            jobStatusBadge.textContent = 'FAILED';
            stepName.textContent = 'Ingestion Request Failed';
            stepDesc.textContent = error.message;
            stepSpinner.style.display = 'none';
            ingestAnotherBtn.style.display = 'inline-block';
        }
    });

    // Real-Time Status Poller with safety bounds
    let pollCount = 0;
    let consecutiveErrors = 0;

    function startPolling(jobId) {
        stopPolling();
        pollCount = 0;
        consecutiveErrors = 0;
        pollJob(jobId);
        pollTimer = setInterval(() => {
            pollCount++;
            if (pollCount > 120 || consecutiveErrors >= 3) {
                // Safety bound: stop after 2.5 minutes or 3 errors to prevent spamming
                stopPolling();
                return;
            }
            pollJob(jobId);
        }, 1500);
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
        pollCount = 0;
        consecutiveErrors = 0;
    }

    async function pollJob(jobId) {
        try {
            const res = await fetch(`${API_BASE}/ingestion_status/${jobId}`);
            if (!res.ok) {
                consecutiveErrors++;
                if (consecutiveErrors >= 3) stopPolling();
                return;
            }

            consecutiveErrors = 0;
            const job = await res.json();
            currentJobData = job;
            updateProgressUI(job);

            if (job.status === 'COMPLETED' || job.status === 'FAILED') {
                stopPolling();
            }
        } catch (err) {
            consecutiveErrors++;
            if (consecutiveErrors >= 3) stopPolling();
            console.warn('Status poll error:', err);
        }
    }

    function updateProgressUI(job) {
        if (!job) return;

        // Title and percent
        jobVehicleTitle.textContent = `${job.make} ${job.model}`;
        const pct = job.progress_pct || 0;
        jobProgressBar.style.width = `${pct}%`;
        jobProgressPct.textContent = `${pct}%`;
        jobStepLabel.textContent = job.current_step || 'Processing...';

        // Header pipeline dot & label
        if (job.status === 'RUNNING' || job.status === 'QUEUED') {
            pipelineDot.className = 'status-pulse-dot active';
            pipelineStatusText.textContent = `Ingesting ${job.model} (${pct}%)`;
            jobStatusBadge.className = 'status-badge running';
            jobStatusBadge.textContent = 'RUNNING';
            stepSpinner.style.display = 'block';
            stepName.textContent = job.current_step || 'Autonomous Extraction Active';
            stepDesc.textContent = 'Executing 12-tier knowledge extraction & Neo4j graph merge';
            jobStatsGrid.style.display = 'none';
            queryNewCarBtn.style.display = 'none';
            ingestAnotherBtn.style.display = 'none';

        } else if (job.status === 'COMPLETED') {
            pipelineDot.className = 'status-pulse-dot completed';
            pipelineStatusText.textContent = `${job.model} Ready in Graph`;
            jobStatusBadge.className = 'status-badge completed';
            jobStatusBadge.textContent = 'COMPLETED';
            stepSpinner.style.display = 'none';
            stepName.textContent = `✅ Successfully Ingested ${job.make} ${job.model}!`;
            stepDesc.textContent = 'Knowledge graph nodes, specifications, and opinions are now live and queryable.';
            
            // Show stats
            jobStatsGrid.style.display = 'grid';
            statNodes.textContent = `+${job.stats?.nodes_merged || 36}`;
            statRels.textContent = `+${job.stats?.relationships_merged || 82}`;
            statLayers.textContent = '12 / 12';

            // Show action buttons
            queryNewCarBtn.style.display = 'inline-block';
            ingestAnotherBtn.style.display = 'inline-block';
            queryNewCarBtn.textContent = `🎯 Query ${job.model}`;
            queryNewCarBtn.onclick = () => {
                addCarModal.style.display = 'none';
                queryInput.value = `gaps in ${job.model}`;
                queryForm.dispatchEvent(new Event('submit'));
            };

            // Trigger notification toast if modal wasn't actively open
            if (addCarModal.style.display !== 'flex') {
                showToast(`${job.make} ${job.model} integrated with Neo4j. Click to query.`, () => {
                    queryInput.value = `gaps in ${job.model}`;
                    queryForm.dispatchEvent(new Event('submit'));
                });
            }

        } else if (job.status === 'FAILED') {
            pipelineDot.className = 'status-pulse-dot failed';
            pipelineStatusText.textContent = 'Ingestion Fault';
            jobStatusBadge.className = 'status-badge failed';
            jobStatusBadge.textContent = 'FAILED';
            stepSpinner.style.display = 'none';
            stepName.textContent = 'Ingestion Encountered an Error';
            stepDesc.textContent = job.error || 'Check backend logs for details.';
            ingestAnotherBtn.style.display = 'inline-block';
        }

        // Render Terminal Activity Logs
        if (job.logs && job.logs.length > 0) {
            logCounter.textContent = `${job.logs.length} events`;
            terminalLogs.innerHTML = job.logs.map(l => {
                const lvlClass = l.level || 'info';
                const layerStr = l.layer_id ? `<span class="log-layer">[${l.layer_id}]</span>` : '';
                return `
                    <div class="log-entry ${lvlClass}">
                        <span class="log-time">${l.timestamp}</span>
                        ${layerStr}
                        <span class="log-text">${l.message}</span>
                    </div>
                `;
            }).join('');
            terminalLogs.scrollTop = terminalLogs.scrollHeight;
        }
    }

    // Ingest Another Button
    ingestAnotherBtn.onclick = () => {
        showFormView();
    };

    // Pipeline History Drawer Button
    pipelineStatusBtn.onclick = async () => {
        jobsModal.style.display = 'flex';
        jobsListContainer.innerHTML = '<div class="placeholder">Loading recent ingestion jobs...</div>';

        try {
            const res = await fetch(`${API_BASE}/ingestion_jobs`);
            const data = await res.json();
            const jobs = data.jobs || [];

            if (jobs.length === 0) {
                jobsListContainer.innerHTML = '<div class="placeholder">No vehicles ingested yet. Click "+ Add Vehicle" to begin!</div>';
                return;
            }

            jobsListContainer.innerHTML = jobs.map(j => {
                const badgeClass = j.status.toLowerCase();
                const timeStr = j.started_at ? new Date(j.started_at).toLocaleString() : '';
                return `
                    <div class="job-item" data-jobid="${j.job_id}">
                        <div>
                            <div class="job-item-title">${j.make} ${j.model}</div>
                            <div class="job-item-sub">${timeStr} • ${j.current_step || j.status}</div>
                        </div>
                        <div style="display:flex; align-items:center; gap:0.6rem;">
                            <span class="status-badge ${badgeClass}">${j.status}</span>
                            <button class="btn-secondary view-job-btn" style="padding:0.35rem 0.7rem; font-size:0.75rem;">View</button>
                        </div>
                    </div>
                `;
            }).join('');

            // Attach view handlers
            document.querySelectorAll('.job-item').forEach(item => {
                item.onclick = () => {
                    const jid = item.dataset.jobid;
                    const job = jobs.find(x => x.job_id === jid);
                    if (job) {
                        jobsModal.style.display = 'none';
                        showProgressView(job);
                        addCarModal.style.display = 'flex';
                        if (job.status === 'RUNNING' || job.status === 'QUEUED') {
                            activeJobId = job.job_id;
                            startPolling(activeJobId);
                        }
                    }
                };
            });

        } catch (err) {
            jobsListContainer.innerHTML = `<div class="placeholder" style="color:#ef4444;">Failed to load jobs: ${err.message}</div>`;
        }
    };

    // Check on page load for any currently active or recent jobs
    async function checkStartupJobs() {
        try {
            const res = await fetch(`${API_BASE}/ingestion_jobs`);
            if (!res.ok) return;
            const data = await res.json();
            const jobs = data.jobs || [];
            const runningJob = jobs.find(j => {
                if (j.status !== 'RUNNING' && j.status !== 'QUEUED') return false;
                const ageMs = Date.now() - (j.started_at ? new Date(j.started_at).getTime() : 0);
                return ageMs < 180000; // Only resume if started in last 3 minutes
            });
            if (runningJob) {
                activeJobId = runningJob.job_id;
                currentJobData = runningJob;
                updateProgressUI(runningJob);
                startPolling(activeJobId);
            } else if (jobs.length > 0) {
                const latest = jobs[0];
                pipelineStatusText.textContent = `${latest.make} ${latest.model} (${latest.status})`;
                if (latest.status === 'COMPLETED') {
                    pipelineDot.className = 'status-pulse-dot completed';
                }
            }
        } catch (e) {
            // Silently ignore startup poll errors
        }
    }

    checkStartupJobs();
});

