// Small frontend app for LabAssist
const $ = s => document.querySelector(s)
const $$ = s => Array.from(document.querySelectorAll(s))

let historyList = []; // Global history list

function show(page){
  $$('.page').forEach(p=>p.classList.add('hidden'))
  $(`#page-${page}`).classList.remove('hidden')
}

// Navigation
$('#nav-home').onclick = ()=> show('home')
$('#nav-upload').onclick = ()=> show('upload')
$('#nav-history').onclick = ()=> {
  show('history');
  renderHistory();
}

// Home page actions
$('#goto-upload').onclick = ()=> show('upload')
$('#dna-upload-shortcut').onclick = ()=> show('upload')
$('#image-upload-shortcut').onclick = ()=> show('upload')

// Chat modal
$('#chatIcon').onclick = ()=> $('#chatModal').classList.toggle('hidden')
$('#closeChat').onclick = ()=> $('#chatModal').classList.add('hidden')

// Simple history storage
function saveReport(report){
  const id = 'rep_'+Date.now()
  historyList.unshift({id, ts: Date.now(), report})
  if(historyList.length > 50) historyList.pop() // limit history
  localStorage.setItem('lab_history', JSON.stringify(historyList))
  renderHistory()
}

function renderHistory(){
  const el = $('#historyList')
  if (!el) {
    console.error('ERROR: historyList element not found!');
    return;
  }
  el.innerHTML = ''
  historyList = JSON.parse(localStorage.getItem('lab_history') || '[]')
  if(historyList.length === 0){
    el.innerHTML = '<p>No history yet.</p>'
    // Ensure the clear button is handled even with no history
    const clearBtn = $('#clearHistoryBtn');
    if (clearBtn) {
      clearBtn.onclick = clearAllHistory;
    }
    return
  }
  historyList.forEach(item=>{
    const li = document.createElement('li')
    li.innerHTML = `
      <button class="delete-item" data-id="${item.id}" title="Delete this report">X</button>
      <strong>Report ID: ${item.id}</strong>
      <p>Date: ${new Date(item.ts).toLocaleString()}</p>
      <button class="download-item" data-id="${item.id}">Download Report</button>
    `;
    li.querySelector('.download-item').onclick = ()=> downloadReportHTML(item.report)
    li.querySelector('.delete-item').onclick = (e)=> {
      e.stopPropagation()
      const id = item.id
      if(confirm('Delete report '+id+'? This cannot be undone.')){
        deleteHistoryItem(id);
      };
    }
    el.appendChild(li)
  })
  // Attach event listener for the clear all button
  const clearBtn = $('#clearHistoryBtn');
  if (clearBtn) {
    clearBtn.onclick = clearAllHistory;
  }
}

function deleteHistoryItem(id) {
  historyList = historyList.filter(item => item.id !== id)
  localStorage.setItem('lab_history', JSON.stringify(historyList))
  renderHistory()
}

function clearAllHistory() {
  console.log('clearAllHistory function triggered');
  if (confirm('Are you sure you want to delete all history? This cannot be undone.')) {
    localStorage.removeItem('lab_history');
    historyList = [];
    console.log('History cleared from localStorage');
    renderHistory();
  }
}

function downloadJSON(obj, name){
  const blob = new Blob([JSON.stringify(obj,null,2)], {type:'application/json'})
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url)
}

function downloadReportHTML(json) {
  const summary = json.results || {};
  const full = json.full_results || {};
  const reportId = 'rep_' + Date.now();
  const dateStr = new Date().toLocaleString();
  
  const isDna = summary.type === 'dna' || (summary.model_used && summary.model_used.includes('dna'));
  
  let resultSection = '';
  if (isDna) {
    const fullResult = full && Object.keys(full).length > 0 ? full[Object.keys(full)[0]] : null;
    let tableRows = '';
    if (fullResult && fullResult.percentages_by_pathogen) {
      const sorted = Object.entries(fullResult.percentages_by_pathogen).sort((a,b) => b[1] - a[1]);
      sorted.forEach(([pathogen, percent]) => {
        tableRows += `<tr>
          <td><strong>${pathogen}</strong></td>
          <td>${percent.toFixed(2)}%</td>
        </tr>`;
      });
    } else if (fullResult && fullResult.probabilities_by_label) {
      const sorted = Object.entries(fullResult.probabilities_by_label).sort((a,b) => b[1] - a[1]);
      sorted.forEach(([pathogen, prob]) => {
        const percent = prob <= 1.0 ? prob * 100 : prob;
        tableRows += `<tr>
          <td><strong>${pathogen}</strong></td>
          <td>${percent.toFixed(2)}%</td>
        </tr>`;
      });
    }
    
    resultSection = `
      <div class="card">
        <h3>Genomic DNA Analysis Result</h3>
        <p><strong>Primary Prediction:</strong> <span class="badge ${summary.detection === 'DETECTED' ? 'badge-danger' : 'badge-success'}">${summary.label || 'Unknown'}</span></p>
        <p><strong>Pathogen:</strong> ${summary.pathogen || 'Unknown'}</p>
        <p><strong>Disease Name:</strong> ${summary.disease || 'Unknown'}</p>
        <p><strong>Notes:</strong> ${summary.notes || 'None'}</p>
        <div style="margin-top: 15px;">
          <h4>Sequence Probability Distribution</h4>
          <table>
            <thead>
              <tr>
                <th>Pathogen / Species</th>
                <th>Matched Percentage</th>
              </tr>
            </thead>
            <tbody>
              ${tableRows || `<tr><td>${summary.label}</td><td>${summary.probability}</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>
    `;
  } else {
    resultSection = `
      <div class="card">
        <h3>Microscopy/Image Classification Result</h3>
        <p><strong>Detection Status:</strong> <span class="badge ${summary.detection === 'DETECTED' ? 'badge-danger' : 'badge-success'}">${summary.detection}</span></p>
        <p><strong>Identified Pathogen:</strong> ${summary.label || 'Unknown'}</p>
        <p><strong>Disease Name:</strong> ${summary.disease || 'Unknown'}</p>
        <p><strong>Classification Probability:</strong> ${summary.probability || 'N/A'}</p>
        <p><strong>Clinical Notes:</strong> ${summary.notes || 'None'}</p>
      </div>
      
      ${summary.image_url ? `
      <div class="card text-center">
        <h3>Analyzed Image Sample</h3>
        <img class="img-preview" src="${summary.image_url}" alt="Analyzed Sample Image" />
      </div>` : ''}
    `;
  }
  
  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>LabAssist Clinical Diagnostic Report — ${reportId}</title>
  <style>
    body {
      font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #2c3e50;
      background-color: #f8f9fa;
      margin: 0;
      padding: 40px 20px;
    }
    .container {
      max-width: 800px;
      margin: 0 auto;
      background: #ffffff;
      padding: 40px;
      border-radius: 12px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.08);
      border: 1px solid #e9ecef;
    }
    header {
      border-bottom: 2px solid #3498db;
      padding-bottom: 20px;
      margin-bottom: 30px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    header h1 {
      margin: 0;
      font-size: 28px;
      color: #2c3e50;
    }
    .logo {
      color: #3498db;
      font-weight: bold;
    }
    .meta-info {
      font-size: 14px;
      color: #7f8c8d;
      text-align: right;
    }
    .card {
      background: #fdfdfd;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 24px;
      margin-bottom: 25px;
    }
    .card h3 {
      margin-top: 0;
      margin-bottom: 15px;
      color: #2c3e50;
      border-bottom: 1px dashed #e2e8f0;
      padding-bottom: 8px;
    }
    h4 {
      margin-top: 20px;
      margin-bottom: 10px;
      color: #34495e;
    }
    .badge {
      display: inline-block;
      padding: 6px 12px;
      border-radius: 20px;
      font-weight: bold;
      font-size: 13px;
      text-transform: uppercase;
    }
    .badge-danger {
      background-color: #fadbd8;
      color: #c0392b;
      border: 1px solid #f5b7b1;
    }
    .badge-success {
      background-color: #d4efdf;
      color: #27ae60;
      border: 1px solid #a9dfbf;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 10px;
    }
    table th, table td {
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid #e2e8f0;
    }
    table th {
      background-color: #f1f5f9;
      color: #475569;
    }
    .img-preview {
      max-width: 100%;
      max-height: 400px;
      border-radius: 6px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      margin-top: 10px;
    }
    .text-center {
      text-align: center;
    }
    footer {
      margin-top: 40px;
      border-top: 1px solid #e2e8f0;
      padding-top: 20px;
      font-size: 12px;
      color: #94a3b8;
      line-height: 1.6;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1><span class="logo">🧬 LabAssist</span> Clinical Report</h1>
      </div>
      <div class="meta-info">
        <div><strong>Report ID:</strong> ${reportId}</div>
        <div><strong>Date:</strong> ${dateStr}</div>
      </div>
    </header>
    
    <div class="card">
      <h3>Sample Metadata</h3>
      <table>
        <tr>
          <td><strong>Subject/Patient:</strong> Anonymous Sample</td>
          <td><strong>Analyst:</strong> LabAssist Automated System</td>
        </tr>
        <tr>
          <td><strong>Diagnostic Modality:</strong> ${isDna ? 'Genomic DNA Classification' : 'Microscopy/Cellular Image Analysis'}</td>
          <td><strong>System Version:</strong> v1.1.0 (Offline Fallback Enabled)</td>
        </tr>
      </table>
    </div>
    
    ${resultSection}
    
    <footer>
      <p><strong>Disclaimer:</strong> This is a computer-generated diagnostic screening aid produced by the LabAssist Multimodal Pathogen Screening AI framework. It is intended for laboratory assistance and research workflows. It does not replace professional clinical evaluation or confirmatory microbiological tests.</p>
    </footer>
  </div>
</body>
</html>`;

  const blob = new Blob([html], {type: 'text/html'})
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `labassist-report-${reportId}.html`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

// Analysis flow
$('#analyzeBtn').onclick = async ()=>{
  const imgFile = $('#imageFile').files[0]
  const dnaFile = $('#dnaFile').files[0]
  if(!imgFile && !dnaFile){ alert('Select an image or DNA file first'); return }
  show('processing')
  setProgress(5,'Starting multi-modal analysis...')

  const fd = new FormData()
  if(imgFile) fd.append('image_file', imgFile)
  if(dnaFile) fd.append('dna_file', dnaFile)

  setProgress(15,'Uploading files and running analysis...')
  try{
    const resp = await fetch('/analyze_multi', { method:'POST', body: fd })
    if (!resp.ok) {
        const errorText = await resp.text();
        throw new Error(`Network response was not ok: ${resp.statusText} - ${errorText}`);
    }
    const contentType = resp.headers.get('content-type') || '';
    let result;
    if (contentType.includes('application/json')) {
      result = await resp.json();
      console.log('analyze_multi response (JSON)', result);
      setProgress(80,'Running AI models and mapping data...')
      show('results');
      renderResults(result);
      saveReport(result);
      setProgress(100,'Done');
    } else {
      // Plain text response (DNA result)
      result = await resp.text();
      console.log('analyze_multi response (text)', result);
      setProgress(80,'DNA analysis complete.');
      show('results');
      // Format and display DNA result in results container
      const container = document.getElementById('resultsContainer');
      container.dataset.raw = result;
      // Try to parse the DNA result into sections
      const lines = result.split(/\r?\n/).filter(l => l.trim() !== '');
      let html = '<div class="dna-result">';
      lines.forEach(line => {
        if (line.startsWith('DNA Analysis Result')) {
          html += `<h2>${line}</h2>`;
        } else if (line.startsWith('Pathogen:')) {
          html += `<p><strong>${line}</strong></p>`;
        } else if (line.startsWith('Disease:')) {
          html += `<p><strong>${line}</strong></p>`;
        } else if (line.startsWith('Probability:')) {
          html += `<p style='color: #007bff;'><strong>${line}</strong></p>`;
        } else if (line.startsWith('Notes:')) {
          html += `<p><em>${line}</em></p>`;
        } else {
          html += `<p>${line}</p>`;
        }
      });
      html += '</div>';
      container.innerHTML = html;
      setProgress(100,'Done');
    }
  }catch(err){
    console.error('Analysis failed:', err); // Log the full error
    setProgress(0,'Error: '+err)
    alert('Analysis failed: '+err)
    show('upload')
  }
}

function setProgress(p, status){
  $('#progressFill').style.width = p+'%'
  $('#statusText').textContent = status
}

$('#backToUpload').onclick = ()=> show('upload')
$('#downloadReport').onclick = ()=> {
  const text = document.getElementById('resultsContainer').dataset.raw
  if(!text) return alert('No report available')
  downloadReportHTML(JSON.parse(text))
}

// --- Modified renderResults to fit new structure ---
function renderResults(json){
  console.log('renderResults called with:', json);
  
  const c = $('#resultsContainer')
  if (!c) {
    console.error('ERROR: resultsContainer not found!');
    return;
  }
  c.dataset.raw = JSON.stringify(json)

  const defaultData = {
    detection: 'NOT DETECTED',
    label: 'Unknown',
    probability: '0%',
    dnaRegions: 'No pathogenic regions found.',
    treatment: 'No specific guidance available. Consult a specialist.',
    notes: 'No issues found on initial scan.',
  }

  // Backend returns { results: <summary>, full_results: <per-model dict> }
  const summary = json.results || defaultData
  const full = json.full_results || {}

  console.log('Summary:', summary);
  console.log('Full results:', full);

  // 1. Detection & Probability - with null checks
  const detectionCard = $('#result-detection').closest('.result-section');
  const detectionEl = $('#result-detection');
  const labelEl = $('#result-label');

  if (detectionCard) detectionCard.style.display = '';
  if (detectionEl) {
    const isDetected = (summary.detection || '').toUpperCase() === 'DETECTED';
    const badgeStyle = isDetected 
      ? 'background: #fadbd8; color: #c0392b; border: 1px solid #f5b7b1; padding: 4px 10px; border-radius: 12px; font-weight: bold;'
      : 'background: #d4efdf; color: #27ae60; border: 1px solid #a9dfbf; padding: 4px 10px; border-radius: 12px; font-weight: bold;';
    detectionEl.innerHTML = `Detection Status: <span style="${badgeStyle}">${summary.detection || defaultData.detection}</span> (${summary.probability || 'N/A'})`;
  } else {
    console.error('ERROR: result-detection element not found!');
  }
  if (labelEl) {
    const organism = summary.pathogen && summary.pathogen !== 'Unknown' ? summary.pathogen : (summary.label || defaultData.label);
    const diseaseName = summary.disease && summary.disease !== 'Unknown' ? ` (${summary.disease})` : '';
    labelEl.innerHTML = `Identified Pathogen / Organism: <strong>${organism}</strong>${diseaseName}`;
  } else {
    console.error('ERROR: result-label element not found!');
  }

  // 2. Image and DNA Analysis
  const imageView = $('#image-view');
  const dnaEl = $('#dna-match-regions');
  if (summary.type === 'dna') {
    // Show DNA result in DNA analysis section
    if (dnaEl) {
      let html = `<div class="dna-result">`;
      html += `<h2>DNA Analysis Result</h2>`;
      // Add Human DNA Sequence percentage from 'human' entry in probabilities
      const fullResult = full && Object.keys(full).length > 0 ? full[Object.keys(full)[0]] : null;
      let humanPercent = null;
      if (fullResult && fullResult.probabilities_by_label && fullResult.probabilities_by_label['human'] !== undefined) {
        const total = Object.values(fullResult.probabilities_by_label).reduce((a, b) => a + b, 0);
        const prob = fullResult.probabilities_by_label['human'];
        humanPercent = total > 0 ? (prob / total) * 100 : 0;
        html += `<p><strong>Human DNA Sequence:</strong> ${humanPercent.toFixed(2)}%</p>`;
      } else {
        html += `<p><strong>Human DNA Sequence:</strong> N/A</p>`;
      }
      // Show probability for each pathogen (unchanged)
      if (fullResult && fullResult.probabilities_by_label) {
        html += `<h3>Probability by Pathogen:</h3><ul>`;
        const total = Object.values(fullResult.probabilities_by_label).reduce((a, b) => a + b, 0);
        Object.entries(fullResult.probabilities_by_label).forEach(([pathogen, prob]) => {
          const percent = total > 0 ? (prob / total) * 100 : 0;
          html += `<li><strong>${pathogen}:</strong> ${percent.toFixed(2)}%</li>`;
        });
        html += `</ul>`;
      } else {
        html += `<p style='color: #007bff;'><strong>Probability:</strong> ${summary.probability || 'N/A'}</p>`;
      }
      html += `<p><em>${summary.notes || ''}</em></p>`;
      html += `</div>`;
      dnaEl.innerHTML = html;
    } else {
      console.error('ERROR: dna-match-regions element not found!');
    }
    // Clear image analysis section for DNA results
    if (imageView) {
      imageView.innerHTML = '';
    }
  } else {
    // Show image result in image analysis section
    if (imageView) {
      imageView.innerHTML = summary.image_url ? 
        `<img src="${summary.image_url}" alt="Analyzed Sample Image" style="max-width: 100%; border-radius: 6px;">` :
        `<p class="hint">${summary.notes || defaultData.notes}</p>`;
      // Optional: expose full_results for debugging (first model)
      if(Object.keys(full).length > 0){
        const firstKey = Object.keys(full)[0]
        const first = full[firstKey]
        if (first && !first.error) { // Only show debug for successful results
            const dbg = document.createElement('pre')
            dbg.style.fontSize = '12px'
            dbg.textContent = 'Full result ('+firstKey+'): ' + JSON.stringify(first, null, 2)
            imageView.appendChild(dbg)
        }
      }
    } else {
      console.error('ERROR: image-view element not found!');
    }
    // Clear DNA analysis section for image results
    if (dnaEl) {
      dnaEl.textContent = '';
    }
  }

  // 4. Treatment Guidance
  const treatmentEl = $('#treatment-notes');
  if (treatmentEl) {
    treatmentEl.textContent = summary.treatment || defaultData.treatment
  } else {
    console.error('ERROR: treatment-notes element not found!');
  }
  
  console.log('renderResults completed successfully');
}


// Chat (Kept from original LabAssist)
$('#sendChat').onclick = async ()=>{
  const prompt = $('#chatPrompt').value.trim()
  if(!prompt) return
  const chatLog = $('#chatLog');
  chatLog.innerHTML += `<div class="bubble user">${escapeHtml(prompt)}</div>`
  $('#chatPrompt').value = ''
  // Add a placeholder and scroll to it
  const placeholder = document.createElement('div');
  placeholder.className = 'bubble system';
  placeholder.textContent = '...';
  chatLog.appendChild(placeholder);
  chatLog.scrollTop = chatLog.scrollHeight;

  try{
    const resp = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({prompt, history:[]})})
    if (!resp.ok) {
        throw new Error(`Chat API error: ${resp.statusText}`);
    }
    const reader = resp.body.getReader();
    const dec = new TextDecoder()
    let done=false, txt=''
    while(!done){
      const { value, done: d } = await reader.read();
      done = d
      if(value){ 
        txt += dec.decode(value, {stream: true});
        placeholder.innerHTML = escapeHtml(txt); // Update placeholder with streamed text
        chatLog.scrollTop = chatLog.scrollHeight;
      }
    }
    placeholder.className = 'bubble bot'; // Finalize bubble style
  }catch(e){
    placeholder.className = 'bubble bot';
    placeholder.innerHTML = `Error: ${e.message}`;
    chatLog.scrollTop = chatLog.scrollHeight;
  }
}

function escapeHtml(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') }

// init
show('home')
renderHistory()

// Clear other input when one is selected to enforce single-modality
const imageInput = $('#imageFile');
const dnaInput = $('#dnaFile');
if (imageInput && dnaInput) {
  imageInput.addEventListener('change', () => {
    if (imageInput.files.length > 0) {
      dnaInput.value = '';
    }
  });
  dnaInput.addEventListener('change', () => {
    if (dnaInput.files.length > 0) {
      imageInput.value = '';
    }
  });
}