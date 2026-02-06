// Global state
let currentModel = null;
let currentModelType = 'autoencoder';
let uploadedPredictFile = null;
let liveMonitoring = false;
let chartInstance = null;

const API_BASE = 'http://127.0.0.1:5000/api';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM Content Loaded');
    checkSystemStatus();
    
    // File upload handlers - with null checks
    const trainFile = document.getElementById('trainFile');
    const predictFile = document.getElementById('predictFile');
    
    if (trainFile) trainFile.addEventListener('change', handleTrainFileUpload);
    if (predictFile) predictFile.addEventListener('change', handlePredictFileUpload);
    
    // Auto-refresh status
    setInterval(checkSystemStatus, 5000);
    
    console.log('Initialization complete');
});

// Tab switching
function switchTab(tabName) {
    console.log('Switching to tab:', tabName);
    
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active from all tab buttons
    document.querySelectorAll('.tab').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const tabElement = document.getElementById(tabName);
    if (tabElement) {
        tabElement.classList.add('active');
        console.log('Tab activated:', tabName);
    } else {
        console.error('Tab not found:', tabName);
    }
    
    // Activate button - find the button that was clicked
    if (event && event.target) {
        event.target.classList.add('active');
        console.log('Button activated');
    }
}

// Model selection
function selectDefaultModel(modelType) {
    console.log('Selecting default model:', modelType);
    currentModelType = modelType;
    currentModel = { type: 'default', model_type: modelType };
    
    // Remove selected class from all cards
    document.querySelectorAll('.model-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Add selected class to clicked card
    if (event && event.currentTarget) {
        event.currentTarget.classList.add('selected');
        console.log('Model card selected:', modelType);
    }
    showAlert(`Using ${modelType} model for analysis`, 'success');
}

async function uploadCustomModel() {
    console.log('Upload custom model called');
    const fileInput = document.getElementById('modelFile');
    const file = fileInput.files[0];
    
    if (!file) {
        showAlert('Please select a model file (.pkl or .h5)', 'error');
        return;
    }
    
    console.log('File selected:', file.name);
    
    // Check file extension
    if (!file.name.endsWith('.pkl') && !file.name.endsWith('.h5')) {
        showAlert('Please upload a .pkl or .h5 model file', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        showAlert(`Loading ${file.name}...`, 'warning');
        console.log('Uploading file to /api/load_model');
        
        const response = await fetch(`${API_BASE}/load_model`, {
            method: 'POST',
            body: formData
        });
        
        console.log('Response status:', response.status);
        const data = await response.json();
        console.log('Response data:', data);
        
        if (data.success) {
            currentModel = data;
            currentModelType = data.model_type;
            showAlert(`Model loaded: ${data.model_type}`, 'success');
            
            // Remove selected class from all cards and update
            document.querySelectorAll('.model-card').forEach(card => {
                card.classList.remove('selected');
            });
            
            checkSystemStatus();
        } else {
            showAlert(data.error || 'Failed to load model', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showAlert('Failed to load model: ' + error.message, 'error');
    }
}

async function startTraining() {
    const fileInput = document.getElementById('trainFile');
    const file = fileInput.files[0];
    
    if (!file) {
        showAlert('Please select a training dataset', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        showAlert('Uploading dataset...', 'warning');
        const uploadRes = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });
        
        const uploadData = await uploadRes.json();
        
        if (!uploadData.success) {
            showAlert(uploadData.error, 'error');
            return;
        }
        
        showAlert('Training model...', 'warning');
        const btn = document.getElementById('trainBtnText');
        const originalText = btn.textContent;
        btn.innerHTML = '<span class="loading"></span> Training...';
        
        const response = await fetch(`${API_BASE}/train`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filepath: uploadData.filepath,
                model_type: currentModelType
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentModel = data;
            showAlert('Model trained successfully!', 'success');
            displayTrainingResults(data);
            checkSystemStatus();
        } else {
            showAlert(data.error || 'Training failed', 'error');
        }
        
        btn.textContent = originalText;
    } catch (error) {
        showAlert('Training error: ' + error.message, 'error');
    }
}

function displayTrainingResults(data) {
    const resultsDiv = document.getElementById('trainResults');
    resultsDiv.style.display = 'block';
    
    let html = `
        <div class="metric">
            <span class="metric-label">Model Type</span>
            <span class="metric-value">${data.model_type}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Training Samples</span>
            <span class="metric-value">${data.training_samples.toLocaleString()}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Test Samples</span>
            <span class="metric-value">${data.test_samples.toLocaleString()}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Threshold</span>
            <span class="metric-value">${data.threshold.toFixed(4)}</span>
        </div>
    `;
    
    if (data.metrics) {
        html += `
            <div class="metric">
                <span class="metric-label">Accuracy</span>
                <span class="metric-value">${(data.metrics.accuracy * 100).toFixed(2)}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Precision</span>
                <span class="metric-value">${(data.metrics.precision * 100).toFixed(2)}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Recall</span>
                <span class="metric-value">${(data.metrics.recall * 100).toFixed(2)}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">F1 Score</span>
                <span class="metric-value">${(data.metrics.f1_score * 100).toFixed(2)}%</span>
            </div>
        `;
    }
    
    resultsDiv.innerHTML = html;
}

// Check system status
async function checkSystemStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();
        
        // Update system status
        updateStatus('systemStatus', 'systemText', true, 'Online');
        
        // Update model status - check currentModel first
        if (currentModel || data.model_loaded) {
            const modelType = currentModel?.model_type || data.model_type || 'Unknown';
            updateStatus('modelStatus', 'modelText', true, modelType);
        } else {
            updateStatus('modelStatus', 'modelText', false, 'Select a Model');
        }
        
        // Update Kafka status
        if (data.kafka_available) {
            updateStatus('kafkaStatus', 'kafkaText', true, 'Connected');
        } else {
            updateStatus('kafkaStatus', 'kafkaText', false, 'Unavailable');
        }
        
        // Update capture status
        if (data.live_capture_active) {
            updateStatus('captureStatus', 'captureText', true, 'Active');
            liveMonitoring = true;
        } else {
            updateStatus('captureStatus', 'captureText', false, 'Inactive');
            liveMonitoring = false;
        }
        
    } catch (error) {
        console.error('Status check failed:', error);
        updateStatus('systemStatus', 'systemText', false, 'Offline');
    }
}

function updateStatus(indicatorId, textId, active, text) {
    const indicator = document.getElementById(indicatorId);
    const textElement = document.getElementById(textId);
    
    if (active) {
        indicator.classList.add('active');
    } else {
        indicator.classList.remove('active');
    }
    
    textElement.textContent = text;
}

// File upload handlers
async function handleTrainFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        showAlert('Uploading file...', 'warning');
        
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            uploadedTrainFile = data.filepath;
            showAlert(`File uploaded: ${data.rows} rows, ${data.columns} columns`, 'success');
        } else {
            showAlert(data.error, 'error');
        }
    } catch (error) {
        showAlert('Upload failed: ' + error.message, 'error');
    }
}

async function handlePredictFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        showAlert('Uploading file...', 'warning');
        
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            uploadedPredictFile = data.filepath;
            showAlert(`File uploaded: ${data.rows} rows, ${data.columns} columns`, 'success');
        } else {
            showAlert(data.error, 'error');
        }
    } catch (error) {
        showAlert('Upload failed: ' + error.message, 'error');
    }
}


// Predict
async function predictData() {
    if (!currentModel) {
        showAlert('Please select or load a model first', 'error');
        return;
    }
    
    if (!uploadedPredictFile) {
        showAlert('Please upload traffic data first', 'error');
        return;
    }
    
    const btn = document.getElementById('predictBtnText');
    const originalText = btn.textContent;
    btn.innerHTML = '<span class="loading"></span> Analyzing...';
    
    try {
        const response = await fetch(`${API_BASE}/predict`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                filepath: uploadedPredictFile
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert('Analysis complete!', 'success');
            displayPredictionResults(data);
            displayPredictionChart(data);
        } else {
            showAlert(data.error, 'error');
        }
        
    } catch (error) {
        showAlert('Prediction failed: ' + error.message, 'error');
    } finally {
        btn.textContent = originalText;
    }
}

function displayPredictionResults(data) {
    const resultsDiv = document.getElementById('predictResults');
    resultsDiv.style.display = 'block';
    
    const anomalyRate = (data.anomaly_rate).toFixed(2);
    
    // Summary metrics
    let html = `
        <div style="margin-bottom: 30px;">
            <h3 style="color: var(--primary); margin-bottom: 15px;">📊 Summary Statistics</h3>
            <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
                <div class="metric">
                    <span class="metric-label">Total Samples</span>
                    <span class="metric-value">${data.total_samples.toLocaleString()}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Normal Traffic</span>
                    <span class="metric-value" style="color: var(--primary);">${data.normal_traffic.toLocaleString()}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Anomalies</span>
                    <span class="metric-value" style="color: var(--danger);">${data.anomalies_detected.toLocaleString()}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Anomaly Rate</span>
                    <span class="metric-value" style="color: var(--warning);">${anomalyRate}%</span>
                </div>
            </div>
        </div>
    `;
    
    // Score statistics
    if (data.scores_stats) {
        html += `
            <div style="margin-bottom: 30px;">
                <h3 style="color: var(--secondary); margin-bottom: 15px;">📈 Anomaly Score Statistics</h3>
                <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));">
                    <div class="metric">
                        <span class="metric-label">Min Score</span>
                        <span class="metric-value">${data.scores_stats.min.toFixed(3)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Max Score</span>
                        <span class="metric-value">${data.scores_stats.max.toFixed(3)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Mean Score</span>
                        <span class="metric-value">${data.scores_stats.mean.toFixed(3)}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Threshold</span>
                        <span class="metric-value" style="color: var(--warning);">${data.threshold.toFixed(3)}</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Top anomalies
    if (data.top_anomalies && data.top_anomalies.length > 0) {
        html += `
            <div style="margin-bottom: 30px;">
                <h3 style="color: var(--danger); margin-bottom: 15px;">🚨 Top Anomalous Flows (Most Suspicious)</h3>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
                        <thead>
                            <tr style="border-bottom: 2px solid var(--primary);">
                                <th style="padding: 10px; text-align: left; color: var(--primary);">Score</th>
                                <th style="padding: 10px; text-align: left; color: var(--primary);">Src IP</th>
                                <th style="padding: 10px; text-align: left; color: var(--primary);">Dst IP</th>
                                <th style="padding: 10px; text-align: left; color: var(--primary);">Port</th>
                                <th style="padding: 10px; text-align: left; color: var(--primary);">Protocol</th>
                                <th style="padding: 10px; text-align: left; color: var(--primary);">Pkts Fwd/Bwd</th>
                                <th style="padding: 10px; text-align: left; color: var(--primary);">Bytes/s</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        data.top_anomalies.forEach((anomaly, idx) => {
            const bgColor = idx % 2 === 0 ? 'rgba(0,255,157,0.05)' : 'transparent';
            html += `
                <tr style="border-bottom: 1px solid var(--border); background-color: ${bgColor};">
                    <td style="padding: 10px;"><strong style="color: var(--danger);">${anomaly.anomaly_score.toFixed(3)}</strong></td>
                    <td style="padding: 10px; font-size: 0.75rem;">${anomaly.src_ip}</td>
                    <td style="padding: 10px; font-size: 0.75rem;">${anomaly.dst_ip}</td>
                    <td style="padding: 10px;">${anomaly.dst_port}</td>
                    <td style="padding: 10px;">${anomaly.protocol}</td>
                    <td style="padding: 10px;">${anomaly.tot_fwd_pkts}/${anomaly.tot_bwd_pkts}</td>
                    <td style="padding: 10px;">${anomaly.flow_byts_s.toFixed(1)}</td>
                </tr>
            `;
        });
        
        html += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }
    
    // Protocol analysis
    if (data.protocol_analysis && Object.keys(data.protocol_analysis).length > 0) {
        html += `
            <div style="margin-bottom: 30px;">
                <h3 style="color: var(--secondary); margin-bottom: 15px;">🔌 Protocol Distribution</h3>
                <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));">
        `;
        
        for (const [protocol, stats] of Object.entries(data.protocol_analysis)) {
            html += `
                <div class="metric" style="background: rgba(0,153,255,0.1); border: 1px solid var(--secondary);">
                    <span class="metric-label">${protocol}</span>
                    <span class="metric-value" style="font-size: 0.9rem;">${stats.count.toLocaleString()}</span>
                    <span class="metric-label" style="font-size: 0.7rem;">${stats.percentage.toFixed(1)}%</span>
                </div>
            `;
        }
        
        html += `</div></div>`;
    }
    
    // Port analysis for anomalies
    if (data.port_analysis && Object.keys(data.port_analysis).length > 0) {
        html += `
            <div style="margin-bottom: 30px;">
                <h3 style="color: var(--warning); margin-bottom: 15px;">🌐 Top Anomalous Ports</h3>
                <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));">
        `;
        
        for (const [port, stats] of Object.entries(data.port_analysis)) {
            html += `
                <div class="metric" style="background: rgba(255,170,0,0.1); border: 1px solid var(--warning);">
                    <span class="metric-label">Port ${port}</span>
                    <span class="metric-value" style="font-size: 0.9rem;">${stats.count}</span>
                    <span class="metric-label" style="font-size: 0.7rem;">${stats.percentage.toFixed(1)}%</span>
                </div>
            `;
        }
        
        html += `</div></div>`;
    }
    
    // IP analysis
    if (data.ip_analysis && Object.keys(data.ip_analysis).length > 0) {
        html += `
            <div style="margin-bottom: 30px;">
                <h3 style="color: var(--danger); margin-bottom: 15px;">⚠️ Top Anomalous Source IPs</h3>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="border-bottom: 2px solid var(--danger);">
                                <th style="padding: 10px; text-align: left; color: var(--danger);">Source IP</th>
                                <th style="padding: 10px; text-align: left; color: var(--danger);">Count</th>
                                <th style="padding: 10px; text-align: left; color: var(--danger);">% of Anomalies</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        let ipIdx = 0;
        for (const [ip, stats] of Object.entries(data.ip_analysis)) {
            const bgColor = ipIdx % 2 === 0 ? 'rgba(255,0,85,0.05)' : 'transparent';
            html += `
                <tr style="border-bottom: 1px solid var(--border); background-color: ${bgColor};">
                    <td style="padding: 10px; font-weight: bold;">${ip}</td>
                    <td style="padding: 10px;">${stats.count}</td>
                    <td style="padding: 10px;">${stats.percentage.toFixed(1)}%</td>
                </tr>
            `;
            ipIdx++;
        }
        
        html += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }
    
    resultsDiv.innerHTML = html;
}

function displayPredictionChart(data) {
    const chartDiv = document.getElementById('predictChart');
    chartDiv.style.display = 'block';
    
    const ctx = document.getElementById('predictionChart').getContext('2d');
    
    // Destroy existing chart
    if (chartInstance) {
        chartInstance.destroy();
    }
    
    // Create new chart
    chartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Normal Traffic', 'Anomalies'],
            datasets: [{
                data: [data.normal_traffic, data.anomalies_detected],
                backgroundColor: [
                    'rgba(0, 255, 157, 0.8)',
                    'rgba(255, 0, 85, 0.8)'
                ],
                borderColor: [
                    'rgba(0, 255, 157, 1)',
                    'rgba(255, 0, 85, 1)'
                ],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    labels: {
                        color: '#e0e6f0',
                        font: {
                            family: 'JetBrains Mono',
                            size: 12
                        }
                    }
                },
                title: {
                    display: true,
                    text: 'Traffic Analysis Results',
                    color: '#00ff9d',
                    font: {
                        family: 'Orbitron',
                        size: 16,
                        weight: 'bold'
                    }
                }
            }
        }
    });
}

// Live capture
async function startLiveCapture() {
    const interface_name = document.getElementById('networkInterface').value;
    
    try {
        showAlert('Starting live capture...', 'warning');
        
        const response = await fetch(`${API_BASE}/live_capture/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                interface: interface_name
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert(data.message, 'success');
            liveMonitoring = true;
            startLiveFeedUpdates();
        } else {
            showAlert(data.error, 'error');
        }
        
    } catch (error) {
        showAlert('Failed to start capture: ' + error.message, 'error');
    }
}

async function stopLiveCapture() {
    try {
        const response = await fetch(`${API_BASE}/live_capture/stop`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert(data.message, 'success');
            liveMonitoring = false;
        } else {
            showAlert(data.error, 'error');
        }
        
    } catch (error) {
        showAlert('Failed to stop capture: ' + error.message, 'error');
    }
}

function startLiveFeedUpdates() {
    const feedDiv = document.getElementById('liveFeed');
    feedDiv.innerHTML = '';
    
    // Simulated live feed (in production, use WebSocket or polling)
    const updateInterval = setInterval(() => {
        if (!liveMonitoring) {
            clearInterval(updateInterval);
            return;
        }
        
        addLiveFeedItem({
            timestamp: new Date().toLocaleTimeString(),
            message: 'Network packet analyzed',
            isAnomaly: Math.random() > 0.9
        });
        
    }, 2000);
}

function addLiveFeedItem(item) {
    const feedDiv = document.getElementById('liveFeed');
    
    const itemDiv = document.createElement('div');
    itemDiv.className = `feed-item ${item.isAnomaly ? 'anomaly' : ''}`;
    
    itemDiv.innerHTML = `
        <div class="timestamp">${item.timestamp}</div>
        <div>${item.message}</div>
        ${item.isAnomaly ? '<div style="color: var(--danger); font-weight: bold;">⚠ ANOMALY DETECTED</div>' : ''}
    `;
    
    feedDiv.insertBefore(itemDiv, feedDiv.firstChild);
    
    // Keep only last 20 items
    while (feedDiv.children.length > 20) {
        feedDiv.removeChild(feedDiv.lastChild);
    }
}

// Model management
async function saveModel() {
    const modelName = document.getElementById('modelName').value;
    
    if (!modelName) {
        showAlert('Please enter a model name', 'error');
        return;
    }
    
    try {
        showAlert('Saving model...', 'warning');
        
        const response = await fetch(`${API_BASE}/save_model`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model_name: modelName
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert('Model saved successfully!', 'success');
            document.getElementById('modelName').value = '';
            loadSavedModels();
        } else {
            showAlert(data.error, 'error');
        }
        
    } catch (error) {
        showAlert('Save failed: ' + error.message, 'error');
    }
}

async function loadSavedModels() {
    try {
        const response = await fetch(`${API_BASE}/list_models`);
        const data = await response.json();
        
        const listDiv = document.getElementById('modelsList');
        
        if (data.models && data.models.length > 0) {
            let html = '';
            
            data.models.forEach(model => {
                html += `
                    <div class="metric" style="cursor: pointer;" onclick="loadModel('${model.name}')">
                        <div>
                            <div class="metric-label">${model.name}</div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary);">
                                ${model.type} • ${new Date(model.created_at).toLocaleDateString()}
                            </div>
                        </div>
                        <button class="btn btn-secondary" style="padding: 8px 16px; font-size: 0.8rem;">
                            Load
                        </button>
                    </div>
                `;
            });
            
            listDiv.innerHTML = html;
        } else {
            listDiv.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 20px;">No saved models found</p>';
        }
        
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

async function loadModel(modelName) {
    try {
        showAlert('Loading model...', 'warning');
        
        const response = await fetch(`${API_BASE}/load_model`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model_name: modelName
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert(`Model "${modelName}" loaded successfully!`, 'success');
            checkSystemStatus();
        } else {
            showAlert(data.error, 'error');
        }
        
    } catch (error) {
        showAlert('Load failed: ' + error.message, 'error');
    }
}

// Alert helper
function showAlert(message, type) {
    console.log(`Alert [${type}]:`, message);
    
    // Remove existing alerts
    const existingAlerts = document.querySelectorAll('.alert');
    existingAlerts.forEach(alert => alert.remove());
    
    // Create new alert
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    
    const icon = type === 'warning' ? '⚠️' : type === 'error' ? '❌' : '✅';
    alert.innerHTML = `
        <span style="font-size: 1.2em; margin-right: 10px;">${icon}</span>
        <span style="flex: 1;">${message}</span>
        <span style="cursor: pointer; font-weight: bold;" onclick="this.parentElement.remove()">×</span>
    `;
    alert.style.cssText = 'display: flex; align-items: center; padding: 15px 20px; margin-bottom: 20px; border-radius: 8px; z-index: 1000; position: relative;';
    
    // Insert at top of page
    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(alert, container.firstChild);
        
        // Auto-remove after 5 seconds
        const timeout = setTimeout(() => {
            if (alert && alert.parentElement) {
                alert.remove();
            }
        }, 5000);
        
        // Allow manual close to clear timeout
        alert.addEventListener('click', () => clearTimeout(timeout));
    }
}
