// SentinAI App Orchestrator
document.addEventListener('DOMContentLoaded', () => {
    // State management variables
    let targetsList = [];
    let activeSimId = null;
    let pollInterval = null;
    let acknowledgedEvaluationTurn = 0;

    // --- DOM Elements ---
    // Tabs
    const tabBtnSimulations = document.getElementById('tab-btn-simulations');
    const tabBtnTargets = document.getElementById('tab-btn-targets');
    const tabBtnMemory = document.getElementById('tab-btn-memory');
    const tabPanels = {
        simulations: document.getElementById('tab-simulations'),
        targets: document.getElementById('tab-targets'),
        memory: document.getElementById('tab-memory')
    };

    // Targets tab elements
    const targetTypeSelect = document.getElementById('target-type');
    const mockSettingsGroup = document.getElementById('mock-settings-group');
    const externalSettingsGroup = document.getElementById('external-settings-group');
    const fieldUseLlmGroup = document.getElementById('field-use-llm-group');
    const targetConfigForm = document.getElementById('target-config-form');
    const targetsListContainer = document.getElementById('targets-list-container');
    const resetTargetBtn = document.getElementById('reset-target-btn');
    const targetFormTitle = document.getElementById('target-form-title');

    // Simulation tab elements
    const launchSimForm = document.getElementById('launch-sim-form');
    const simObjectiveInput = document.getElementById('sim-objective');
    const simTargetSelect = document.getElementById('sim-target');
    const simTurnsInput = document.getElementById('sim-turns');
    const turnsValDisplay = document.getElementById('turns-val');
    const simsListContainer = document.getElementById('sims-list');
    const refreshSimsBtn = document.getElementById('refresh-sims-btn');

    // Simulation details elements
    const activeSimPanel = document.getElementById('active-sim-panel');
    const activeSimPlaceholder = document.getElementById('active-sim-placeholder');
    const detailSimId = document.getElementById('detail-sim-id');
    const detailSimObjective = document.getElementById('detail-sim-objective');
    const detailSimStatus = document.getElementById('detail-sim-status');
    const detailLogs = document.getElementById('detail-logs');

    // Details control panes
    const hitlControlBox = document.getElementById('hitl-control-box');
    const hitlPayloadText = document.getElementById('hitl-payload-text');
    const hitlApproveBtn = document.getElementById('hitl-approve-btn');
    const hitlRejectBtn = document.getElementById('hitl-reject-btn');

    const resultControlBox = document.getElementById('result-control-box');
    const riskDialFill = document.getElementById('risk-dial-fill');
    const riskScoreText = document.getElementById('risk-score-text');
    const resultCompromised = document.getElementById('result-compromised');
    const resultLeakedSecret = document.getElementById('result-leaked-secret');
    const exfiltratedSecretRow = document.getElementById('exfiltrated-secret-row');
    const resultVulns = document.getElementById('result-vulns');
    const resultReasoningText = document.getElementById('result-reasoning-text');
    const resultNextBtn = document.getElementById('result-next-btn');

    const idleControlBox = document.getElementById('idle-control-box');
    const idleControlMsg = document.getElementById('idle-control-msg');

    // Memory elements
    const memoryListContainer = document.getElementById('memory-list');
    const refreshMemoryBtn = document.getElementById('refresh-memory-btn');

    // --- Tab Navigation Setup ---
    function switchTab(tabName) {
        // Toggle Buttons
        tabBtnSimulations.classList.toggle('active', tabName === 'simulations');
        tabBtnTargets.classList.toggle('active', tabName === 'targets');
        tabBtnMemory.classList.toggle('active', tabName === 'memory');

        // Toggle Panels
        tabPanels.simulations.classList.toggle('active', tabName === 'simulations');
        tabPanels.targets.classList.toggle('active', tabName === 'targets');
        tabPanels.memory.classList.toggle('active', tabName === 'memory');

        // Fetch corresponding tab data
        if (tabName === 'targets') {
            fetchTargets();
        } else if (tabName === 'memory') {
            fetchMemoryExploits();
        }
    }

    tabBtnSimulations.addEventListener('click', () => switchTab('simulations'));
    tabBtnTargets.addEventListener('click', () => switchTab('targets'));
    tabBtnMemory.addEventListener('click', () => switchTab('memory'));

    // --- Slider listener ---
    simTurnsInput.addEventListener('input', (e) => {
        turnsValDisplay.textContent = e.target.value;
    });

    // --- Target Type form toggle ---
    targetTypeSelect.addEventListener('change', (e) => {
        const type = e.target.value;
        if (type === 'mock') {
            mockSettingsGroup.style.display = 'block';
            externalSettingsGroup.style.display = 'none';
            fieldUseLlmGroup.style.display = 'block';
        } else {
            mockSettingsGroup.style.display = 'none';
            externalSettingsGroup.style.display = 'block';
            fieldUseLlmGroup.style.display = 'none';
        }
    });

    // --- TARGETS REGISTRY LOGIC ---
    async function fetchTargets() {
        try {
            const response = await fetch('/api/v1/targets');
            targetsList = await response.json();
            renderTargetsList();
            populateSimulationTargetsDropdown();
        } catch (error) {
            console.error("Error fetching targets:", error);
        }
    }

    function renderTargetsList() {
        targetsListContainer.innerHTML = '';
        if (targetsList.length === 0) {
            targetsListContainer.innerHTML = '<div class="empty-state">No targets registered.</div>';
            return;
        }

        targetsList.forEach(target => {
            const item = document.createElement('div');
            item.className = 'target-item';
            
            const isDefault = target.id === 'default_mock';
            const actionButtons = isDefault ? 
                `<button class="btn btn-sm btn-secondary edit-target-btn" data-id="${target.id}">Edit</button>` :
                `<button class="btn btn-sm btn-secondary edit-target-btn" data-id="${target.id}">Edit</button>
                 <button class="btn btn-sm btn-danger delete-target-btn" data-id="${target.id}">Delete</button>`;

            item.innerHTML = `
                <div class="target-item-info">
                    <div class="target-item-header">
                        <h4>${escapeHTML(target.name)}</h4>
                        <span class="type-tag ${target.target_type}">${target.target_type}</span>
                        ${target.use_llm && target.target_type === 'mock' ? '<span class="type-tag mock" style="background-color:rgba(16,185,129,0.15);color:#10b981;border-color:rgba(16,185,129,0.3)">Live LLM</span>' : ''}
                    </div>
                    <p class="target-item-desc">${escapeHTML(target.description || 'No description provided')}</p>
                    <span class="target-item-meta">ID: ${target.id} ${target.target_type === 'external' ? `| URL: ${escapeHTML(target.url)}` : ''}</span>
                </div>
                <div class="target-item-actions">
                    ${actionButtons}
                </div>
            `;
            targetsListContainer.appendChild(item);
        });

        // Add event listeners for edit and delete buttons
        document.querySelectorAll('.edit-target-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.getAttribute('data-id');
                editTarget(id);
            });
        });

        document.querySelectorAll('.delete-target-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.getAttribute('data-id');
                if (confirm(`Are you sure you want to delete target "${id}"?`)) {
                    deleteTarget(id);
                }
            });
        });
    }

    function populateSimulationTargetsDropdown() {
        simTargetSelect.innerHTML = '';
        targetsList.forEach(target => {
            const opt = document.createElement('option');
            opt.value = target.id;
            opt.textContent = `${target.name} (${target.target_type})`;
            simTargetSelect.appendChild(opt);
        });
    }

    async function saveTarget(e) {
        e.preventDefault();
        
        const id = document.getElementById('target-id').value || null;
        const name = document.getElementById('target-name').value;
        const description = document.getElementById('target-desc').value;
        const target_type = targetTypeSelect.value;
        const use_llm = document.getElementById('target-use-llm').checked;
        const system_prompt = document.getElementById('target-sys-prompt').value;
        const secret_token = document.getElementById('target-secret').value;
        const url = document.getElementById('target-url').value;
        const payload_field_name = document.getElementById('target-field').value;
        const headersRaw = document.getElementById('target-headers').value || "{}";

        // Validate JSON headers
        try {
            JSON.parse(headersRaw);
        } catch (err) {
            alert("Custom headers must be a valid JSON object string. e.g. {} or {\"Auth\": \"Bearer key\"}");
            return;
        }

        const payload = {
            id, name, description, target_type, use_llm, system_prompt, secret_token, url, payload_field_name,
            headers: headersRaw
        };

        try {
            const response = await fetch('/api/v1/targets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                resetTargetForm();
                fetchTargets();
            } else {
                const errData = await response.json();
                alert(`Error saving target: ${errData.detail || 'Unknown error'}`);
            }
        } catch (error) {
            console.error("Error saving target:", error);
        }
    }

    function editTarget(id) {
        const target = targetsList.find(t => t.id === id);
        if (!target) return;

        document.getElementById('target-id').value = target.id;
        document.getElementById('target-name').value = target.name;
        document.getElementById('target-desc').value = target.description;
        targetTypeSelect.value = target.target_type;
        document.getElementById('target-use-llm').checked = target.use_llm;
        document.getElementById('target-sys-prompt').value = target.system_prompt || '';
        document.getElementById('target-secret').value = target.secret_token || '';
        document.getElementById('target-url').value = target.url || '';
        document.getElementById('target-field').value = target.payload_field_name || 'query';
        document.getElementById('target-headers').value = target.headers || '{}';

        // Trigger type change event to show correct inputs
        targetTypeSelect.dispatchEvent(new Event('change'));

        targetFormTitle.textContent = "Edit Target System";
        resetTargetBtn.style.display = 'inline-flex';
    }

    async function deleteTarget(id) {
        try {
            const response = await fetch(`/api/v1/targets/${id}`, { method: 'DELETE' });
            if (response.ok) {
                fetchTargets();
            } else {
                const err = await response.json();
                alert(err.detail || "Error deleting target");
            }
        } catch (error) {
            console.error("Error deleting target:", error);
        }
    }

    function resetTargetForm() {
        targetConfigForm.reset();
        document.getElementById('target-id').value = '';
        targetTypeSelect.value = 'mock';
        targetTypeSelect.dispatchEvent(new Event('change'));
        targetFormTitle.textContent = "Register Target System";
        resetTargetBtn.style.display = 'none';
    }

    targetConfigForm.addEventListener('submit', saveTarget);
    resetTargetBtn.addEventListener('click', resetTargetForm);

    // --- SIMULATIONS LOGIC ---
    let localSimsList = [];

    // Populate active simulations list
    async function loadSimulationsList() {
        // Since we don't have a database tracking simulations directly, we can read them from memory or the frontend state.
        // To make it persistent in the UI, we keep a local list in localStorage of launched sim IDs!
        let savedIds = [];
        try {
            savedIds = JSON.parse(localStorage.getItem('sentinai_sims') || '[]');
        } catch(e) {}

        simsListContainer.innerHTML = '';
        if (savedIds.length === 0) {
            simsListContainer.innerHTML = '<div class="empty-state">No simulation campaigns found.</div>';
            return;
        }

        localSimsList = [];
        for (const simId of savedIds) {
            try {
                const response = await fetch(`/api/v1/simulation/${simId}`);
                if (response.ok) {
                    const data = await response.json();
                    localSimsList.push(data);
                }
            } catch (err) {
                console.error(`Error loading sim details for ${simId}`, err);
            }
        }

        renderSimulationsList();
    }

    function renderSimulationsList() {
        simsListContainer.innerHTML = '';
        if (localSimsList.length === 0) {
            simsListContainer.innerHTML = '<div class="empty-state">No campaigns found.</div>';
            return;
        }

        // Sort: active/paused first, then by completed
        localSimsList.sort((a,b) => {
            if (a.status !== 'completed' && b.status === 'completed') return -1;
            if (a.status === 'completed' && b.status !== 'completed') return 1;
            return 0;
        });

        localSimsList.forEach(sim => {
            const item = document.createElement('div');
            item.className = `sim-item ${activeSimId === sim.simulation_id ? 'active' : ''}`;
            item.setAttribute('data-id', sim.simulation_id);

            let statusClass = 'running';
            let statusLabel = sim.status;
            if (sim.status === 'completed') {
                statusClass = 'completed';
                statusLabel = 'Done';
            } else if (sim.status === 'paused_for_hitl') {
                statusClass = 'paused';
                statusLabel = 'HITL Gate';
            }

            item.innerHTML = `
                <div class="sim-info">
                    <span class="sim-info-id">${sim.simulation_id}</span>
                    <span class="sim-info-obj" title="${escapeHTML(sim.objective)}">${escapeHTML(sim.objective)}</span>
                </div>
                <span class="status-badge ${statusClass}">${statusLabel}</span>
            `;

            item.addEventListener('click', () => {
                selectSimulation(sim.simulation_id);
            });
            simsListContainer.appendChild(item);
        });
    }

    async function launchSimulation(e) {
        e.preventDefault();
        
        const objective = simObjectiveInput.value;
        const target_id = simTargetSelect.value;
        const max_turns = parseInt(simTurnsInput.value);

        const launchBtn = document.getElementById('launch-btn');
        launchBtn.disabled = true;
        launchBtn.textContent = "Initializing Agents...";

        try {
            const response = await fetch('/api/v1/simulation/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ objective, target_id, max_turns })
            });

            if (response.ok) {
                const data = await response.json();
                
                // Save to localStorage list
                let savedIds = [];
                try { savedIds = JSON.parse(localStorage.getItem('sentinai_sims') || '[]'); } catch(e) {}
                savedIds.push(data.simulation_id);
                localStorage.setItem('sentinai_sims', JSON.stringify(savedIds));

                // Clear input objective
                simObjectiveInput.value = 'Exfiltrate the enterprise database secret key';

                // Select the new simulation
                await loadSimulationsList();
                selectSimulation(data.simulation_id);
            } else {
                const err = await response.json();
                alert(`Failed to launch campaign: ${err.detail || 'Unknown error'}`);
            }
        } catch (error) {
            console.error("Error launching simulation:", error);
        } finally {
            launchBtn.disabled = false;
            launchBtn.textContent = "Initialize Attack Campaign";
        }
    }

    // --- ACTIVE RUN SELECTION & POLLING ---
    function selectSimulation(simId) {
        activeSimId = simId;
        activeSimPlaceholder.style.display = 'none';
        activeSimPanel.style.display = 'flex';

        // Render selected class in list
        document.querySelectorAll('.sim-item').forEach(item => {
            const id = item.getAttribute('data-id');
            item.classList.toggle('active', id === simId);
        });

        // Reset details panel state
        detailLogs.innerHTML = '';
        hitlControlBox.style.display = 'none';
        resultControlBox.style.display = 'none';
        idleControlBox.style.display = 'flex';
        idleControlMsg.textContent = "Fetching simulation context...";
        
        // Reset cached state for new selection
        hitlPayloadText.value = '';
        hitlPayloadText.removeAttribute('data-sim-id');
        hitlPayloadText.removeAttribute('data-turn');
        acknowledgedEvaluationTurn = 0;

        // Set up active nodes highlight resetting
        resetGraphVisualization();

        // Clear active polling, set new one
        if (pollInterval) clearInterval(pollInterval);
        
        pollSimulationStatus();
        pollInterval = setInterval(pollSimulationStatus, 2000);
    }

    async function pollSimulationStatus() {
        if (!activeSimId) return;

        try {
            const response = await fetch(`/api/v1/simulation/${activeSimId}`);
            if (!response.ok) {
                clearInterval(pollInterval);
                return;
            }
            const data = await response.json();
            
            // Update local memory list with updated status
            const idx = localSimsList.findIndex(s => s.simulation_id === data.simulation_id);
            if (idx !== -1) {
                localSimsList[idx] = data;
                renderSimulationsList();
            }

            renderSimulationDetails(data);

            // Stop polling if completed
            if (data.status === 'completed') {
                clearInterval(pollInterval);
            }
        } catch (error) {
            console.error("Error polling simulation details:", error);
        }
    }

    function resetGraphVisualization() {
        const nodes = ['node-attacker', 'node-hitl', 'node-executor', 'node-evaluator', 'node-optimizer'];
        nodes.forEach(nodeId => {
            const wrapper = document.getElementById(nodeId);
            if (wrapper) {
                wrapper.className = 'node-wrapper';
                wrapper.querySelector('.node-status').textContent = 'Idle';
            }
        });
        
        const arrows = ['arrow-atk-hitl', 'arrow-hitl-exec', 'arrow-exec-eval', 'arrow-eval-opt'];
        arrows.forEach(arrowId => {
            const arrow = document.getElementById(arrowId);
            if (arrow) arrow.className = 'node-arrow';
        });
    }

    function renderSimulationDetails(sim) {
        detailSimId.textContent = sim.simulation_id;
        detailSimObjective.textContent = sim.objective;
        
        let statusText = "Active (Running)";
        let statusClass = "status-badge running";
        if (sim.status === 'paused_for_hitl') {
            statusText = "Paused (HITL Approval)";
            statusClass = "status-badge paused";
        } else if (sim.status === 'completed') {
            statusText = "Audit Campaign Completed";
            statusClass = "status-badge completed";
        }
        detailSimStatus.textContent = statusText;
        detailSimStatus.className = statusClass;

        // --- Formatting logs ---
        detailLogs.innerHTML = '';
        if (sim.history && sim.history.length > 0) {
            sim.history.forEach(line => {
                const logLine = document.createElement('div');
                logLine.className = 'log-line';
                
                // Colors based on content
                if (line.includes("Fired") || line.includes("Payload fired")) {
                    logLine.className += ' system';
                } else if (line.includes("Evaluation complete")) {
                    logLine.className += ' eval';
                } else if (line.includes("SECURITY ALERT") || line.includes("blocked")) {
                    logLine.className += ' fail';
                }
                
                logLine.innerHTML = `&gt; ${escapeHTML(line)}`;
                detailLogs.appendChild(logLine);
            });
            // Auto scroll to bottom
            detailLogs.scrollTop = detailLogs.scrollHeight;
        }

        // --- Render Graph Nodes & Arrows ---
        resetGraphVisualization();
        
        // Attacker is complete once initialized
        document.getElementById('node-attacker').classList.add('complete');
        document.getElementById('node-attacker').querySelector('.node-status').textContent = 'Done';
        
        const arrowAtkHitl = document.getElementById('arrow-atk-hitl');
        if (arrowAtkHitl) arrowAtkHitl.classList.add('complete');

        if (sim.status === 'paused_for_hitl') {
            document.getElementById('node-hitl').classList.add('waiting');
            document.getElementById('node-hitl').querySelector('.node-status').textContent = 'Awaiting';
            
            // Do we have an evaluation result to show first? (For turns > 1 before inspecting the new payload)
            if (sim.evaluation && sim.evaluation.score !== undefined && acknowledgedEvaluationTurn !== sim.turn_count) {
                // Show result box with the Next button, hide HITL and idle boxes
                hitlControlBox.style.display = 'none';
                resultControlBox.style.display = 'flex';
                idleControlBox.style.display = 'none';
                resultNextBtn.style.display = 'block';
                
                renderEvaluationResult(sim.evaluation);
            } else {
                // Show HITL Box, hide others
                hitlControlBox.style.display = 'flex';
                resultControlBox.style.display = 'none';
                idleControlBox.style.display = 'none';
                resultNextBtn.style.display = 'none';
                
                // If the textbox is empty, simulation ID changed, or turn count has increased, fetch the pending payload
                const cachedSimId = hitlPayloadText.getAttribute('data-sim-id');
                const cachedTurn = hitlPayloadText.getAttribute('data-turn');
                if (hitlPayloadText.value === '' || cachedSimId !== sim.simulation_id || cachedTurn !== String(sim.turn_count)) {
                    hitlPayloadText.setAttribute('data-turn', sim.turn_count);
                    fetchPendingPayload(sim.simulation_id);
                }
            }
        } else if (sim.status === 'running') {
            // Highlighting active execution phase
            document.getElementById('node-hitl').classList.add('complete');
            document.getElementById('node-hitl').querySelector('.node-status').textContent = 'Done';
            
            const arrowHitlExec = document.getElementById('arrow-hitl-exec');
            if (arrowHitlExec) arrowHitlExec.classList.add('active'); // pulsing beam
            
            document.getElementById('node-executor').classList.add('active');
            document.getElementById('node-executor').querySelector('.node-status').textContent = 'Firing';
            
            hitlControlBox.style.display = 'none';
            resultControlBox.style.display = 'none';
            idleControlBox.style.display = 'flex';
            resultNextBtn.style.display = 'none';
            idleControlMsg.textContent = `Turn ${sim.turn_count}: Exchanging payload with RAG target...`;
        } else if (sim.status === 'completed') {
            document.getElementById('node-hitl').classList.add('complete');
            document.getElementById('node-hitl').querySelector('.node-status').textContent = 'Done';
            
            const arrowHitlExec = document.getElementById('arrow-hitl-exec');
            if (arrowHitlExec) arrowHitlExec.classList.add('complete');
            
            document.getElementById('node-executor').classList.add('complete');
            document.getElementById('node-executor').querySelector('.node-status').textContent = 'Done';
            
            const arrowExecEval = document.getElementById('arrow-exec-eval');
            if (arrowExecEval) arrowExecEval.classList.add('complete');
            
            document.getElementById('node-evaluator').classList.add('complete');
            document.getElementById('node-evaluator').querySelector('.node-status').textContent = 'Done';
            
            // Show result card
            hitlControlBox.style.display = 'none';
            resultControlBox.style.display = 'flex';
            idleControlBox.style.display = 'none';
            resultNextBtn.style.display = 'none';

            renderEvaluationResult(sim.evaluation);
        }

        // Highlight mutation node if turn count has advanced and it loops
        if (sim.turn_count > 1) {
            const arrowEvalOpt = document.getElementById('arrow-eval-opt');
            if (arrowEvalOpt) arrowEvalOpt.classList.add('complete');
            
            document.getElementById('node-optimizer').classList.add('complete');
            document.getElementById('node-optimizer').querySelector('.node-status').textContent = 'Mutated';
        }
    }

    async function fetchPendingPayload(simId) {
        hitlPayloadText.value = 'Retrieving adversarial payload...';
        hitlPayloadText.setAttribute('data-sim-id', simId);
        
        try {
            const response = await fetch(`/api/v1/hitl/${simId}/pending`);
            if (response.ok) {
                const data = await response.json();
                if (data.pending_payload) {
                    hitlPayloadText.value = data.pending_payload.raw_prompt;
                }
            } else {
                hitlPayloadText.value = "Failed to load pending payload.";
            }
        } catch (error) {
            console.error("Error fetching HITL pending payload:", error);
            hitlPayloadText.value = "Connection error.";
        }
    }

    async function approvePayload() {
        if (!activeSimId) return;

        const edited_payload = hitlPayloadText.value;
        
        // Show loading spinner
        hitlControlBox.style.display = 'none';
        idleControlBox.style.display = 'flex';
        resultNextBtn.style.display = 'none';
        idleControlMsg.textContent = "Transmitting approved payload...";

        try {
            const response = await fetch(`/api/v1/hitl/${activeSimId}/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ edited_payload })
            });

            if (response.ok) {
                // Instantly query status
                pollSimulationStatus();
            } else {
                const err = await response.json();
                alert(`Error resuming simulation: ${err.detail || 'Unknown error'}`);
                // Restore HITL box
                hitlControlBox.style.display = 'flex';
                idleControlBox.style.display = 'none';
            }
        } catch (error) {
            console.error("Error approving payload:", error);
        }
    }

    async function rejectPayload() {
        if (!activeSimId) return;
        
        if (confirm("Rejecting will stop the current campaign. Are you sure?")) {
            // We can delete or terminate the simulation state by just ignoring it or clearing active id
            clearInterval(pollInterval);
            
            // Delete from UI list
            let savedIds = [];
            try { savedIds = JSON.parse(localStorage.getItem('sentinai_sims') || '[]'); } catch(e) {}
            savedIds = savedIds.filter(id => id !== activeSimId);
            localStorage.setItem('sentinai_sims', JSON.stringify(savedIds));
            
            activeSimId = null;
            activeSimPanel.style.display = 'none';
            activeSimPlaceholder.style.display = 'flex';
            
            loadSimulationsList();
        }
    }

    function renderEvaluationResult(evalData) {
        if (!evalData) {
            riskScoreText.textContent = "0.0";
            setGaugeOffset(0);
            resultCompromised.textContent = "Secure / Safety active";
            resultCompromised.className = "val"
            exfiltratedSecretRow.style.display = 'none';
            resultVulns.textContent = "None";
            resultReasoningText.textContent = "No evaluation metrics recorded.";
            return;
        }

        const score = evalData.score;
        riskScoreText.textContent = score.toFixed(1);
        setGaugeOffset(score);

        // Score colors
        let circleColor = "#10b981"; // green
        if (score > 0.3 && score <= 0.7) {
            circleColor = "#f59e0b"; // yellow
        } else if (score > 0.7) {
            circleColor = "#ef4444"; // red
        }
        riskDialFill.style.stroke = circleColor;

        if (evalData.is_compromised) {
            resultCompromised.textContent = "Vulnerable / Compromised";
            resultCompromised.className = "val status-red";
            
            if (evalData.leakage_detected) {
                exfiltratedSecretRow.style.display = 'flex';
                resultLeakedSecret.textContent = evalData.leakage_detected;
            } else {
                exfiltratedSecretRow.style.display = 'none';
            }
        } else {
            resultCompromised.textContent = "Secure / Blocked";
            resultCompromised.className = "val";
            resultCompromised.style.color = "#10b981";
            exfiltratedSecretRow.style.display = 'none';
        }

        resultVulns.textContent = evalData.vulnerabilities_detected && evalData.vulnerabilities_detected.length > 0 ?
            evalData.vulnerabilities_detected.join(', ') : 'None';
            
        resultReasoningText.textContent = evalData.reasoning;
    }

    function setGaugeOffset(score) {
        // radius = 40, circumference = 2 * pi * r = 251.2
        const circumference = 251.2;
        const offset = circumference - (score * circumference);
        riskDialFill.style.strokeDashoffset = offset;
    }

    hitlApproveBtn.addEventListener('click', approvePayload);
    hitlRejectBtn.addEventListener('click', rejectPayload);
    refreshSimsBtn.addEventListener('click', loadSimulationsList);
    launchSimForm.addEventListener('submit', launchSimulation);
    resultNextBtn.addEventListener('click', () => {
        if (activeSimId) {
            const idx = localSimsList.findIndex(s => s.simulation_id === activeSimId);
            if (idx !== -1) {
                const sim = localSimsList[idx];
                acknowledgedEvaluationTurn = sim.turn_count;
                renderSimulationDetails(sim);
            }
        }
    });

    // --- LONG-TERM EPISTEMIC MEMORY LOGIC ---
    async function fetchMemoryExploits() {
        memoryListContainer.innerHTML = '<div class="empty-state">Retrieving vector embeddings from ChromaDB...</div>';
        
        try {
            const response = await fetch('/api/v1/targets/memory/exploits');
            const data = await response.json();
            
            memoryListContainer.innerHTML = '';
            if (data.length === 0 || (data.length === 1 && data[0].id === 'error')) {
                const msg = data.length === 1 ? data[0].prompt : "No exploits recorded in vector memory yet.";
                memoryListContainer.innerHTML = `<div class="empty-state">${escapeHTML(msg)}</div>`;
                return;
            }

            data.forEach(exploit => {
                const card = document.createElement('div');
                card.className = 'memory-item';
                
                const attackType = exploit.metadata?.attack_type || 'Prompt Injection';

                card.innerHTML = `
                    <div class="memory-item-header">
                        <span class="memory-item-id">${exploit.id}</span>
                        <span class="type-tag mock" style="font-size:8px;">${escapeHTML(attackType)}</span>
                    </div>
                    <div class="memory-item-prompt">${escapeHTML(exploit.prompt)}</div>
                `;
                memoryListContainer.appendChild(card);
            });
        } catch (error) {
            console.error("Error fetching memory exploits:", error);
            memoryListContainer.innerHTML = '<div class="empty-state">Error connecting to memories store.</div>';
        }
    }

    refreshMemoryBtn.addEventListener('click', fetchMemoryExploits);

    // --- Helper Utilities ---
    function escapeHTML(str) {
        if (!str) return '';
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }

    // --- Initial Startup triggers ---
    fetchTargets();
    loadSimulationsList();
});
