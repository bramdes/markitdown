from flask import Flask, render_template_string, request, jsonify
import os
import glob
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from datetime import datetime
import traceback
from convert_to_markdown import convert_file_to_markdown
import multiprocessing

app = Flask(__name__)

# Store conversion status
conversion_status = {}
conversion_lock = threading.Lock()

# Get number of CPU cores for parallel processing
MAX_WORKERS = max(1, ((multiprocessing.cpu_count()/2) - 1))  # Leave one core free
#MAX_WORKERS = 4  # Leave one core free

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File to Markdown Converter</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 800px;
            width: 100%;
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 2em;
        }
        
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 0.9em;
        }
        
        .input-section {
            margin-bottom: 30px;
        }
        
        label {
            display: block;
            margin-bottom: 10px;
            color: #555;
            font-weight: 500;
        }
        
        textarea {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 14px;
            font-family: 'Consolas', 'Monaco', monospace;
            resize: vertical;
            transition: border-color 0.3s;
        }
        
        textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .example {
            background: #f5f5f5;
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
            font-size: 12px;
            color: #666;
        }
        
        .button-group {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
        }
        
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
        }
        
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        
        button.secondary {
            background: #f0f0f0;
            color: #333;
        }
        
        button.secondary:hover {
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        
        .status-section {
            border-top: 2px solid #e0e0e0;
            padding-top: 30px;
        }
        
        .status-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .status-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .status-item {
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 10px;
            background: #f8f8f8;
            border-left: 4px solid #ccc;
            transition: all 0.3s;
        }
        
        .status-item.processing {
            border-left-color: #ffa726;
            background: #fff3e0;
        }
        
        .status-item.completed {
            border-left-color: #66bb6a;
            background: #e8f5e9;
        }
        
        .status-item.error {
            border-left-color: #ef5350;
            background: #ffebee;
        }
        
        .status-item.queued {
            border-left-color: #42a5f5;
            background: #e3f2fd;
        }
        
        .status-file {
            font-weight: 500;
            color: #333;
            word-break: break-all;
            margin-bottom: 5px;
        }
        
        .status-message {
            font-size: 12px;
            color: #666;
        }
        
        .status-time {
            font-size: 11px;
            color: #999;
            margin-top: 5px;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        
        .stats {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            padding: 15px;
            background: #f5f5f5;
            border-radius: 10px;
        }
        
        .stat {
            flex: 1;
            text-align: center;
        }
        
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        
        .stat-label {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📄 File to Markdown Converter</h1>
        <p class="subtitle">Convert PDFs, Word docs, and PowerPoints to Markdown format | Parallel Processing: Up to ''' + str(MAX_WORKERS) + ''' files simultaneously</p>
        
        <div class="input-section">
            <label for="paths">Enter file paths (one per line, supports wildcards):</label>
            <textarea id="paths" rows="8" placeholder="C:\\Users\\Documents\\file.pdf
C:\\Users\\Documents\\*.docx
C:\\Users\\**\\*.pptx"></textarea>
            <div class="example">
                <strong>Examples:</strong><br>
                • Single file: C:\\Users\\document.pdf<br>
                • All PDFs in folder: C:\\Users\\Documents\\*.pdf<br>
                • All files recursively: C:\\Users\\Documents\\**\\*.pdf
            </div>
        </div>
        
        <div class="button-group">
            <button onclick="convertFiles()" id="convertBtn">🚀 Start Conversion</button>
            <button onclick="clearPaths()" class="secondary">Clear</button>
            <button onclick="refreshStatus()" class="secondary">🔄 Refresh Status</button>
        </div>
        
        <div class="status-section">
            <div class="status-header">
                <h2>Conversion Status</h2>
                <button onclick="clearStatus()" class="secondary">Clear History</button>
            </div>
            
            <div class="stats" id="stats">
                <div class="stat">
                    <div class="stat-value" id="statQueued">0</div>
                    <div class="stat-label">Queued</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="statProcessing">0</div>
                    <div class="stat-label">Processing</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="statCompleted">0</div>
                    <div class="stat-label">Completed</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="statError">0</div>
                    <div class="stat-label">Errors</div>
                </div>
            </div>
            
            <div class="status-list" id="statusList">
                <div class="empty-state">No conversions yet. Add some files above to get started!</div>
            </div>
        </div>
    </div>
    
    <script>
        let statusUpdateInterval;
        
        function convertFiles() {
            const paths = document.getElementById('paths').value.trim();
            if (!paths) {
                alert('Please enter at least one file path');
                return;
            }
            
            const pathList = paths.split('\\n').filter(p => p.trim());
            document.getElementById('convertBtn').disabled = true;
            
            fetch('/convert', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({paths: pathList})
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert('Error: ' + data.error);
                } else {
                    document.getElementById('paths').value = '';
                    refreshStatus();
                }
                document.getElementById('convertBtn').disabled = false;
            })
            .catch(error => {
                alert('Error: ' + error);
                document.getElementById('convertBtn').disabled = false;
            });
        }
        
        function clearPaths() {
            document.getElementById('paths').value = '';
        }
        
        function refreshStatus() {
            fetch('/status')
            .then(response => response.json())
            .then(data => {
                updateStatusDisplay(data);
            });
        }
        
        function updateStatusDisplay(statusData) {
            const statusList = document.getElementById('statusList');
            
            if (Object.keys(statusData).length === 0) {
                statusList.innerHTML = '<div class="empty-state">No conversions yet. Add some files above to get started!</div>';
                updateStats({queued: 0, processing: 0, completed: 0, error: 0});
                return;
            }
            
            let html = '';
            let stats = {queued: 0, processing: 0, completed: 0, error: 0};
            
            // Sort by timestamp (newest first)
            const sortedEntries = Object.entries(statusData).sort((a, b) => 
                new Date(b[1].timestamp) - new Date(a[1].timestamp)
            );
            
            for (const [file, status] of sortedEntries) {
                const statusClass = status.status.toLowerCase();
                stats[statusClass] = (stats[statusClass] || 0) + 1;
                
                html += `
                    <div class="status-item ${statusClass}">
                        <div class="status-file">${file}</div>
                        <div class="status-message">${status.message || status.status}</div>
                        <div class="status-time">${new Date(status.timestamp).toLocaleString()}</div>
                    </div>
                `;
            }
            
            statusList.innerHTML = html;
            updateStats(stats);
        }
        
        function updateStats(stats) {
            document.getElementById('statQueued').textContent = stats.queued || 0;
            document.getElementById('statProcessing').textContent = stats.processing || 0;
            document.getElementById('statCompleted').textContent = stats.completed || 0;
            document.getElementById('statError').textContent = stats.error || 0;
        }
        
        function clearStatus() {
            fetch('/clear', {method: 'POST'})
            .then(() => refreshStatus());
        }
        
        // Auto-refresh status every 2 seconds
        setInterval(refreshStatus, 2000);
        
        // Initial status load
        refreshStatus();
        
        // Handle Enter key in textarea (Ctrl+Enter to submit)
        document.getElementById('paths').addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 'Enter') {
                convertFiles();
            }
        });
    </script>
</body>
</html>
'''

# Global thread pool executor for background conversions
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

def process_single_file(file_path):
    """Process a single file conversion"""
    try:
        # Update status to processing
        with conversion_lock:
            conversion_status[file_path] = {
                'status': 'Processing',
                'message': 'Converting to Markdown...',
                'timestamp': datetime.now().isoformat()
            }
        
        # Run the Python conversion function
        success, message = convert_file_to_markdown(file_path)
        
        # Update status based on result
        with conversion_lock:
            if success:
                conversion_status[file_path] = {
                    'status': 'Completed',
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                conversion_status[file_path] = {
                    'status': 'Error',
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                }
    except Exception as e:
        with conversion_lock:
            conversion_status[file_path] = {
                'status': 'Error',
                'message': f'Error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
        print(f"Conversion error for {file_path}: {e}")
        traceback.print_exc()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/convert', methods=['POST'])
def convert():
    try:
        data = request.json
        paths = data.get('paths', [])
        
        files_to_convert = []
        
        for path in paths:
            path = path.strip()
            if not path:
                continue
                
            # Handle glob patterns
            if '*' in path or '?' in path:
                # Convert Windows path to glob pattern
                if '**' in path:
                    # Recursive glob
                    matched_files = glob.glob(path, recursive=True)
                else:
                    # Normal glob
                    matched_files = glob.glob(path)
                    
                for file in matched_files:
                    if os.path.isfile(file):
                        files_to_convert.append(file)
            else:
                # Single file
                if os.path.isfile(path):
                    files_to_convert.append(path)
                elif os.path.isdir(path):
                    # If it's a directory, get all supported files
                    for ext in ['*.pdf', '*.docx', '*.pptx']:
                        matched = glob.glob(os.path.join(path, ext))
                        files_to_convert.extend(matched)
        
        # Submit files for parallel processing
        for file_path in files_to_convert:
            with conversion_lock:
                conversion_status[file_path] = {
                    'status': 'Queued',
                    'message': 'Waiting to be processed',
                    'timestamp': datetime.now().isoformat()
                }
            # Submit to thread pool for parallel processing
            executor.submit(process_single_file, file_path)
        
        return jsonify({
            'success': True,
            'queued': len(files_to_convert),
            'files': files_to_convert
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def status():
    with conversion_lock:
        return jsonify(dict(conversion_status))

@app.route('/clear', methods=['POST'])
def clear():
    global conversion_status
    with conversion_lock:
        conversion_status = {}
    return jsonify({'success': True})

if __name__ == '__main__':
    print("\nFile to Markdown Converter")
    print("=" * 50)
    print(f"Parallel Processing: {MAX_WORKERS} workers")
    print(f"CPU Cores Available: {multiprocessing.cpu_count()}")
    print("Open http://localhost:5555 in your browser")
    print("Tips:")
    print("   - Use wildcards: *.pdf, *.docx, *.pptx")
    print("   - Recursive search: C:\\path\\**\\*.pdf")
    print("   - Press Ctrl+Enter in the text area to convert")
    print("   - Multiple files convert in parallel!")
    print("=" * 50)
    print()
    
    app.run(debug=False, port=5555, host='0.0.0.0')