import './style.css';

/** @type {import('flowk').GraphInfo} */
let graphData = { nodes: [], edges: [], entrypoint: null };
let sessions = {};
let currentSessionId = null;
let currentRunId = null;
let currentRunTrace = [];
let currentEvents = [];

// DOM Elements
const sessionList = document.getElementById('session-list');
const runList = document.getElementById('run-list');
const nodesLayer = document.getElementById('nodes-layer');
const edgesLayer = document.getElementById('edges-layer');
const traceList = document.getElementById('trace-list');
const eventTimeline = document.getElementById('event-timeline');
const diffContent = document.getElementById('diff-content');
const currentSessionTitle = document.getElementById('current-session-id');
const currentRunTitle = document.getElementById('current-run-id');
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
  setupTabs();
  await refreshRegistry();
  
  // Refresh loop for dev mode
  setInterval(refreshRegistry, 5000);
}

async function refreshRegistry() {
  const oldSessionsCount = Object.keys(sessions).length;
  graphData = await fetchData('/ui/graph') || graphData;
  sessions = await fetchData('/ui/sessions') || {};
  
  renderGraph();
  renderSessionList();
  
  // If we just got our first session, auto-select it
  if (oldSessionsCount === 0 && Object.keys(sessions).length > 0) {
    selectSession(Object.keys(sessions)[0]);
  }
}

// ------------------------------------------------------------------
// Tabs
// ------------------------------------------------------------------

function setupTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      
      btn.classList.add('active');
      const tabId = `tab-${btn.dataset.tab}`;
      document.getElementById(tabId).classList.add('active');
      
      if (btn.dataset.tab === 'graph') renderGraph();
    };
  });
}

// ------------------------------------------------------------------
// Rendering: Sessions & Runs
// ------------------------------------------------------------------

function renderSessionList() {
  const activeId = currentSessionId;
  sessionList.innerHTML = '';
  Object.keys(sessions).sort((a,b) => b.localeCompare(a)).forEach(id => {
    const item = document.createElement('div');
    item.className = `session-item ${id === activeId ? 'active' : ''}`;
    item.onclick = () => selectSession(id);
    
    item.innerHTML = `
      <span class="session-id">${id}</span>
      <span class="session-meta">Global State Session</span>
    `;
    sessionList.appendChild(item);
  });
}

async function selectSession(id) {
  currentSessionId = id;
  currentSessionTitle.innerText = `Session: ${id}`;
  renderSessionList();
  
  const runs = await fetchData(`/ui/session/${id}/runs`);
  renderRunList(runs || []);
  
  if (runs && runs.length > 0) {
    selectRun(runs[runs.length - 1]);
  }
}

function renderRunList(runs) {
  runList.innerHTML = '';
  if (runs.length === 0) {
    runList.innerHTML = '<div class="session-item" style="opacity: 0.5;">No runs yet...</div>';
    return;
  }

  runs.slice().reverse().forEach(runId => {
    const item = document.createElement('div');
    item.className = `session-item ${runId === currentRunId ? 'active' : ''}`;
    item.onclick = () => selectRun(runId);
    
    item.innerHTML = `
      <span class="session-id" title="${runId}">${runId.substring(0, 18)}...</span>
      <span class="session-meta">Run Unit</span>
    `;
    runList.appendChild(item);
  });
}

async function selectRun(runId) {
  currentRunId = runId;
  currentRunTitle.innerText = `Run ID: ${runId}`;
  
  // Re-render run list to show active
  const runs = await fetchData(`/ui/session/${currentSessionId}/runs`);
  renderRunList(runs || []);

  const trace = await fetchData(`/ui/run/${runId}`);
  const events = await fetchData(`/ui/run/${runId}/events`);
  
  currentRunTrace = trace || [];
  currentEvents = events || [];
  
  renderTrace();
  renderEvents();
  updateStats();
  
  if (currentRunTrace.length > 0) {
    selectStep(currentRunTrace.length - 1);
  }
}

function updateStats() {
  nodeCountStat.innerText = graphData.nodes.length;
  if (currentRunTrace.length > 0) {
    const totalDuration = currentRunTrace.reduce((acc, step) => acc + (step.duration || 0), 0);
    runTimeStat.innerText = (totalDuration * 1000).toFixed(0) + 'ms';
  } else {
    runTimeStat.innerText = '0ms';
  }
}

// ------------------------------------------------------------------
// Rendering: Graph
// ------------------------------------------------------------------

function renderGraph() {
  nodesLayer.innerHTML = '';
  edgesLayer.innerHTML = '';
  
  const container = document.getElementById('graph-container');
  if (!container) return;
  const width = container.clientWidth;
  const height = container.clientHeight;
  if (width === 0) return;

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
    circle.setAttribute('r', 35);
    
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
// Rendering: Trace & Events
// ------------------------------------------------------------------

function renderTrace() {
  traceList.innerHTML = '';
  if (currentRunTrace.length === 0) {
    traceList.innerHTML = '<div class="text-secondary" style="padding: 2rem;">No trace data for this run.</div>';
    return;
  }
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

function renderEvents() {
    eventTimeline.innerHTML = '';
    if (currentEvents.length === 0) {
        eventTimeline.innerHTML = '<div class="text-secondary" style="padding: 2rem;">No event sourcing data.</div>';
        return;
    }
    currentEvents.forEach(event => {
        const item = document.createElement('div');
        item.className = 'event-item';
        const timeStr = new Date(event.timestamp * 1000).toLocaleTimeString();
        
        item.innerHTML = `
            <div class="event-time">${timeStr}</div>
            <div class="event-header">
                <span class="event-type">${event.type}</span>
                <span class="event-node">${event.node || ''}</span>
            </div>
            ${event.data ? `<pre>${JSON.stringify(event.data, null, 2)}</pre>` : ''}
        `;
        eventTimeline.appendChild(item);
    });
}

function selectStep(index) {
  // Reset highlights
  document.querySelectorAll('.node circle').forEach(c => c.style.stroke = 'var(--panel-border)');
  document.querySelectorAll('.trace-step').forEach(s => s.classList.remove('active'));
  
  if (index < 0 || index >= currentRunTrace.length) return;

  const step = currentRunTrace[index];
  const stepEls = document.querySelectorAll('.trace-step');
  if (stepEls[index]) stepEls[index].classList.add('active');

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
