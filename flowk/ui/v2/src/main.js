import './style.css';

/** @type {import('flowk').GraphInfo} */
let graphData = { nodes: [], edges: [], entrypoint: null };
let sessions = {};
let currentSessionId = null;
let currentRunTrace = [];

// DOM Elements
const sessionList = document.getElementById('session-list');
const nodesLayer = document.getElementById('nodes-layer');
const edgesLayer = document.getElementById('edges-layer');
const traceList = document.getElementById('trace-list');
const diffContent = document.getElementById('diff-content');
const currentSessionTitle = document.getElementById('current-session-id');
const nodeCountStat = document.getElementById('node-count');
const runTimeStat = document.getElementById('run-time');

// ------------------------------------------------------------------
// API Interaction
// ------------------------------------------------------------------

async function fetchData(endpoint) {
  try {
    const response = await fetch(endpoint);
    return await response.json();
  } catch (err) {
    console.error(`Error fetching ${endpoint}:`, err);
    return null;
  }
}

async function init() {
  graphData = await fetchData('/ui/graph') || graphData;
  sessions = await fetchData('/ui/sessions') || {};
  
  renderGraph();
  renderSessionList();
}

// ------------------------------------------------------------------
// Rendering: Sessions
// ------------------------------------------------------------------

function renderSessionList() {
  sessionList.innerHTML = '';
  Object.keys(sessions).forEach(id => {
    const item = document.createElement('div');
    item.className = `session-item ${id === currentSessionId ? 'active' : ''}`;
    item.onclick = () => selectSession(id);
    
    item.innerHTML = `
      <span class="session-id">${id}</span>
      <span class="session-meta">Nodes: ${Object.keys(sessions[id]).length} keys in state</span>
    `;
    sessionList.appendChild(item);
  });
}

async function selectSession(id) {
  currentSessionId = id;
  currentSessionTitle.innerText = id;
  renderSessionList();
  
  // Fetch runs specifically for THIS session
  const runs = await fetchData(`/ui/session/${id}/runs`);
  if (runs && runs.length > 0) {
    // Picking the latest run for this session
    const runId = runs[runs.length - 1];
    const trace = await fetchData(`/ui/run/${runId}`);
    if (trace) {
      currentRunTrace = trace;
      renderTrace();
      updateStats();
      
      // Auto-select latest step
      selectStep(currentRunTrace.length - 1);
    }
  } else {
    currentRunTrace = [];
    renderTrace();
    updateStats();
    diffContent.innerHTML = '<div class="text-secondary">No traces found for this session</div>';
  }
}

function updateStats() {
  nodeCountStat.innerText = graphData.nodes.length;
  if (currentRunTrace.length > 0) {
    const totalDuration = currentRunTrace.reduce((acc, step) => acc + (step.duration || 0), 0);
    runTimeStat.innerText = (totalDuration * 1000).toFixed(0) + 'ms';
  }
}

// ------------------------------------------------------------------
// Rendering: Graph (Simple Circular Layout)
// ------------------------------------------------------------------

function renderGraph() {
  nodesLayer.innerHTML = '';
  edgesLayer.innerHTML = '';
  
  const width = document.getElementById('graph-container').clientWidth;
  const height = document.getElementById('graph-container').clientHeight;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) / 3;
  
  const nodePositions = {};
  
  graphData.nodes.forEach((node, i) => {
    const angle = (i / graphData.nodes.length) * 2 * Math.PI;
    const x = centerX + radius * Math.cos(angle);
    const y = centerY + radius * Math.sin(angle);
    nodePositions[node.id] = { x, y };
    
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('class', 'node');
    g.setAttribute('id', `node-${node.id}`);
    
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', x);
    circle.setAttribute('cy', y);
    circle.setAttribute('r', node.type === 'llm_router' ? 40 : 35);
    
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', x);
    text.setAttribute('y', y + 5);
    text.setAttribute('text-anchor', 'middle');
    text.textContent = node.id.length > 10 ? node.id.substring(0, 8) + '..' : node.id;
    
    g.appendChild(circle);
    g.appendChild(text);
    nodesLayer.appendChild(g);
  });
  
  graphData.edges.forEach(edge => {
    const start = nodePositions[edge.source];
    const end = nodePositions[edge.target];
    if (!start || !end) return;
    
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const d = `M ${start.x} ${start.y} L ${end.x} ${end.y}`;
    line.setAttribute('d', d);
    line.setAttribute('class', 'edge');
    line.setAttribute('id', `edge-${edge.source}-${edge.target}`);
    edgesLayer.appendChild(line);
  });
}

// ------------------------------------------------------------------
// Rendering: Trace & Diffs
// ------------------------------------------------------------------

function renderTrace() {
  traceList.innerHTML = '';
  currentRunTrace.forEach((step, i) => {
    const item = document.createElement('div');
    item.className = 'trace-step';
    item.onclick = () => selectStep(i);
    
    item.innerHTML = `
      <div class="step-header">
        <span class="step-node">${step.node}</span>
        <span class="step-status ${step.status === 'error' ? 'error' : ''}">${step.status}</span>
      </div>
      <div style="font-size: 0.7rem; color: var(--text-secondary);">
        Duration: ${(step.duration * 1000).toFixed(1)}ms
      </div>
    `;
    traceList.appendChild(item);
  });
}

function selectStep(index) {
  // Highlight node in graph
  document.querySelectorAll('.node circle').forEach(c => c.style.stroke = 'var(--panel-border)');
  const step = currentRunTrace[index];
  const nodeEl = document.getElementById(`node-${step.node}`);
  if (nodeEl) {
    nodeEl.querySelector('circle').style.stroke = 'var(--accent)';
  }
  
  // Build Diff
  const prevStep = index > 0 ? currentRunTrace[index - 1] : null;
  const prevState = prevStep ? prevStep.state_snapshot : {};
  const currState = step.state_snapshot;
  
  renderDiff(prevState, currState);
}

function renderDiff(oldState, newState) {
  let diffHtml = '';
  const allKeys = new Set([...Object.keys(oldState), ...Object.keys(newState)]);
  
  allKeys.forEach(key => {
    const oldVal = JSON.stringify(oldState[key]);
    const newVal = JSON.stringify(newState[key]);
    
    if (!(key in oldState)) {
      diffHtml += `<div class="diff-added">+ ${key}: ${newVal}</div>`;
    } else if (!(key in newState)) {
      diffHtml += `<div class="diff-removed">- ${key}: ${oldVal}</div>`;
    } else if (oldVal !== newVal) {
      diffHtml += `<div class="diff-changed">~ ${key}: ${oldVal} -> ${newVal}</div>`;
    } else {
      diffHtml += `<div style="color: var(--text-secondary)">  ${key}: ${newVal}</div>`;
    }
  });
  
  diffContent.innerHTML = diffHtml || '<div class="text-secondary">No state changes</div>';
}

// Start
init();
window.onresize = renderGraph;
