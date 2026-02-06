// Global state
let selectedModelType = 'autoencoder';
let uploadedTrainFile = null;
let uploadedPredictFile = null;
let liveMonitoring = false;
let chartInstance = null;
let socket = null;
let anomalyStats = {
    total: 0,
    recent: []
};

const API_BASE = 'http://localhost:5000/api';
const SOCKET_URL = 'http://localhost:5000';

// Initialize WebSocket connection
function initializeWebSocket() {
    if (socket !== null) {
        return; // Already connected
    }
    
    try {
        socket = io(SOCKET_URL, {
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: 5,
            transports: ['websocket', 'polling']
        });
        
        socket.on('connect', () => {
            console.log('WebSocket connected');
            updateStatus('systemStatus', 'systemText', true, 'Online');
        });
        
        socket.on('disconnect', () => {
            console.log('WebSocket disconnected');
            updateStatus('systemStatus', 'systemText', false, 'Offline');
        });
        
        socket.on('anomaly_detected', (data) => {
            console.log('Anomaly detected:', data);
            addLiveFeedItem({
                timestamp: new Date(data.timestamp).toLocaleTimeString(),
                message: `${data.protocol} traffic: ${data.src_ip}:${data.src_port} → ${data.dst_ip}:${data.dst_port}`,
                isAnomaly: true,
                anomalyScore: data.anomaly_score,
                details: data
            });
            
            anomalyStats.total++;
            anomalyStats.recent.push(data);
            if (anomalyStats.recent.length > 20) {
                anomalyStats.recent.shift();
            }
        });
        
        socket.on('connection_response', (data) => {
            console.log('Server response:', data);
        });
        
    } catch (error) {
        console.error('WebSocket initialization error:', error);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeWebSocket();
    checkSystemStatus();
    loadSavedModels();
    
    // File upload handlers
    document.getElementById('trainFile').addEventListener('change', handleTrainFileUpload);
    document.getElementById('predictFile').addEventListener('change', handlePredictFileUpload);
    
    // Auto-refresh status
    setInterval(checkSystemStatus, 5000);
});

// Tab switching
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active from all tab buttons
    document.querySelectorAll('.tab').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(tabName).classList.add('active');
    
    // Activate button
    event.target.classList.add('active');
}

// Model selection
function selectModel(modelType) {
    selectedModelType = modelType;
    
    // Remove selected class from all cards
    document.querySelectorAll('.model-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Add selected class to clicked card
    event.currentTarget.classList.add('selected');
}

// Check system status
async function checkSystemStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();
        
        // Update system status
        updateStatus('systemStatus', 'systemText', true, 'Online');
        
        // Update model status
        if (data.model_loaded) {
            updateStatus('modelStatus', 'modelText', true, data.model_type);
        } else {
            updateStatus('modelStatus', 'modelText', false, 'No Model Loaded');
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

// Train model
async function trainModel() {
    if (!uploadedTrainFile) {
        showAlert('Please upload a training dataset first', 'error');
        return;
    }
    
    const btn = document.getElementById('trainBtnText');
    const originalText = btn.textContent;
    btn.innerHTML = '<span class="loading"></span> Training...';
    
    try {
        const response = await fetch(`${API_BASE}/train`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                filepath: uploadedTrainFile,
                model_type: selectedModelType
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert('Model trained successfully!', 'success');
            displayTrainingResults(data);
            checkSystemStatus(); // Update status
        } else {
            showAlert(data.error, 'error');
        }
        
    } catch (error) {
        showAlert('Training failed: ' + error.message, 'error');
    } finally {
        btn.textContent = originalText;
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

// Predict
async function predictData() {
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
    
    const anomalyRate = (data.anomaly_rate * 100).toFixed(2);
    
    const html = `
        <div class="metric">
            <span class="metric-label">Total Samples Analyzed</span>
            <span class="metric-value">${data.total_samples.toLocaleString()}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Normal Traffic</span>
            <span class="metric-value" style="color: var(--primary);">${data.normal_traffic.toLocaleString()}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Anomalies Detected</span>
            <span class="metric-value" style="color: var(--danger);">${data.anomalies_detected.toLocaleString()}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Anomaly Rate</span>
            <span class="metric-value">${anomalyRate}%</span>
        </div>
    `;
    
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
                interface: interface_name,
                simulate: true  // Use simulated network traffic
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showAlert(`${data.message} (${data.mode})`, 'success');
            liveMonitoring = true;
            anomalyStats = { total: 0, recent: [] };
            
            // Clear the feed
            const feedDiv = document.getElementById('liveFeed');
            feedDiv.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 20px;">Waiting for network traffic...</p>';
            
            checkSystemStatus(); // Update capture status
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
            
            // Show summary
            const feedDiv = document.getElementById('liveFeed');
            if (anomalyStats.total > 0) {
                feedDiv.innerHTML += `
                    <div class="feed-item" style="border-left-color: var(--warning); background: rgba(255, 170, 0, 0.05);">
                        <div style="color: var(--warning); font-weight: bold;">Capture Complete</div>
                        <div class="timestamp">Total Anomalies Detected: ${anomalyStats.total}</div>
                    </div>
                `;
            }
        } else {
            showAlert(data.error, 'error');
        }
        
        checkSystemStatus(); // Update capture status
        
    } catch (error) {
        showAlert('Failed to stop capture: ' + error.message, 'error');
    }
}

function addLiveFeedItem(item) {
    const feedDiv = document.getElementById('liveFeed');
    
    // Clear "Waiting" message on first item
    if (feedDiv.children.length === 1 && feedDiv.textContent.includes('Waiting')) {
        feedDiv.innerHTML = '';
    }
    
    const itemDiv = document.createElement('div');
    itemDiv.className = `feed-item ${item.isAnomaly ? 'anomaly' : ''}`;
    
    let detailsHtml = '';
    if (item.isAnomaly && item.details) {
        const score = (item.anomalyScore * 100).toFixed(1);
        const threatLevel = item.anomalyScore > 0.7 ? 'Critical' : item.anomalyScore > 0.5 ? 'High' : 'Medium';
        const threatColor = item.anomalyScore > 0.7 ? 'var(--danger)' : item.anomalyScore > 0.5 ? '#ff6600' : 'var(--warning)';
        
        detailsHtml = `
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.1); font-size: 0.8rem;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                    <div><span style="color: var(--text-secondary);">Source:</span> ${item.details.src_ip}:${item.details.src_port}</div>
                    <div><span style="color: var(--text-secondary);">Destination:</span> ${item.details.dst_ip}:${item.details.dst_port}</div>
                    <div><span style="color: var(--text-secondary);">Protocol:</span> ${item.details.protocol}</div>
                    <div><span style="color: var(--text-secondary);">Threat Level:</span> <span style="color: ${threatColor}; font-weight: bold;">${threatLevel}</span></div>
                    <div><span style="color: var(--text-secondary);">Anomaly Score:</span> <span style="color: ${threatColor}; font-weight: bold;">${score}%</span></div>
                    <div><span style="color: var(--text-secondary);">Packet Size:</span> ${item.details.packet_size} bytes</div>
                </div>
            </div>
        `;
    }
    
    itemDiv.innerHTML = `
        <div class="timestamp">${item.timestamp}</div>
        <div>${item.message}</div>
        ${item.isAnomaly ? '<div style="color: var(--danger); font-weight: bold; margin-top: 4px;">⚠ INTRUSION DETECTED</div>' : ''}
        ${detailsHtml}
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
    // Remove existing alerts
    const existingAlerts = document.querySelectorAll('.alert');
    existingAlerts.forEach(alert => alert.remove());
    
    // Create new alert
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <span>${type === 'warning' ? '⚠' : type === 'error' ? '✖' : '✓'}</span>
        <span>${message}</span>
    `;
    
    // Insert at top of first card
    const firstCard = document.querySelector('.card');
    if (firstCard) {
        firstCard.insertBefore(alert, firstCard.firstChild);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            alert.remove();
        }, 5000);
    }
}
