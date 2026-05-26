import io
import os
import socket
import qrcode
from flask import Flask, request, send_from_directory, send_file, render_template_string, jsonify, abort
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB limit
UPLOAD_FOLDER = "received_files"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

HTML = '''
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>🚀 Advanced WiFi File Transfer</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .upload-zone { border: 3px dashed #007bff; border-radius: 15px; transition: all 0.3s; }
        .upload-zone.dragover { border-color: #28a745; background: rgba(40, 167, 69, 0.1); }
        .file-item { transition: all 0.2s; }
        .file-item:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        .preview-img { max-width: 80px; max-height: 80px; object-fit: cover; }
        .progress { height: 8px; }
    </style>
</head>
<body class="d-flex align-items-center min-vh-100">
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-lg-10 col-xl-8">
                <div class="card shadow-lg border-0">
                    <div class="card-header bg-primary text-white text-center py-4">
                        <h1 class="mb-0"><i class="bi bi-wifi"></i> Advanced WiFi File Transfer</h1>
                        <small>Drag & Drop or Select • Multi-File • Preview • Delete</small>
                    </div>
                    <div class="card-body p-5">
                        <!-- Upload Zone -->
                        <div id="uploadZone" class="upload-zone text-center p-5 mb-4">
                            <i class="bi bi-cloud-arrow-up-fill fs-1 text-muted mb-3"></i>
                            <h4>Drop files here or click to select</h4>
                            <p class="text-muted">Supports multiple files (Max 32MB total)</p>
                            <input type="file" id="fileInput" multiple class="d-none">
                            <button class="btn btn-primary btn-lg px-5" onclick="document.getElementById('fileInput').click()">
                                <i class="bi bi-folder-plus"></i> Choose Files
                            </button>
                            <div class="progress mt-4 d-none" id="progressDiv">
                                <div class="progress-bar" id="progressBar" role="progressbar"></div>
                            </div>
                        </div>

                        <div class="text-center mb-4">
                            <p class="mb-2 text-white-50">Open this app on a phone or another device:</p>
                            <div class="d-flex flex-column flex-sm-row justify-content-center align-items-center gap-2">
                                <a id="serverLink" href="#" target="_blank" class="btn btn-light btn-sm text-truncate" style="max-width:320px;"></a>
                                <button class="btn btn-outline-light btn-sm" onclick="copyLink()"><i class="bi bi-clipboard"></i> Copy Link</button>
                                <button class="btn btn-danger btn-sm" onclick="deleteAllFiles()"><i class="bi bi-trash-fill"></i> Delete All</button>
                            </div>
                            <img src="/qr.png" alt="Scan to connect" class="img-fluid rounded shadow-sm mt-3" style="max-width:220px;">
                        </div>

                        <!-- Files List -->
                        <h3 class="mb-4"><i class="bi bi-folder-fill"></i> Files on PC <span class="badge bg-secondary" id="fileCount">0</span></h3>
                        <div id="fileList" class="row g-3"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        const uploadZone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('fileInput');
        const progressBar = document.getElementById('progressBar');
        const progressDiv = document.getElementById('progressDiv');
        const fileList = document.getElementById('fileList');
        const fileCount = document.getElementById('fileCount');
        const serverLink = document.getElementById('serverLink');

        // Drag & Drop
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(event => {
            uploadZone.addEventListener(event, e => e.preventDefault());
            uploadZone.addEventListener(event, e => {
                if (event === 'dragenter' || event === 'dragover') uploadZone.classList.add('dragover');
                else if (event === 'dragleave') uploadZone.classList.remove('dragover');
                else if (event === 'drop') {
                    uploadZone.classList.remove('dragover');
                    handleFiles(e.dataTransfer.files);
                }
            });
        });

        fileInput.addEventListener('change', e => handleFiles(e.target.files));

        function handleFiles(files) {
            Array.from(files).forEach(uploadFile);
        }

        function uploadFile(file) {
            const formData = new FormData();
            formData.append('file', file);

            const xhr = new XMLHttpRequest();
            xhr.upload.addEventListener('progress', e => {
                if (e.lengthComputable) {
                    const percent = (e.loaded / e.total) * 100;
                    progressBar.style.width = percent + '%';
                    progressDiv.classList.remove('d-none');
                }
            });

            xhr.addEventListener('load', () => {
                progressDiv.classList.add('d-none');
                progressBar.style.width = '0%';
                if (xhr.status === 200) {
                    loadFiles();
                } else {
                    alert('Upload failed. Please try again.');
                }
            });

            xhr.open('POST', '/');
            xhr.send(formData);
        }

        function loadFiles() {
            updateServerLink();
            fetch('/api/files')
                .then(r => r.json())
                .then(files => {
                    fileCount.textContent = files.length;
                    fileList.innerHTML = files.map(f => `
                        <div class="col-md-6 col-lg-4">
                            <div class="card file-item h-100">
                                <div class="card-body d-flex flex-column">
                                    ${isImage(f.name) ? `<img src="/preview/${f.name}" class="preview-img rounded mb-2 mx-auto d-block" onerror="this.style.display='none'">` : ''}
                                    <h6 class="card-title text-truncate">${f.name}</h6>
                                    <small class="text-muted">${formatSize(f.size)}</small>
                                    <div class="mt-auto">
                                        <a href="/download/${f.name}" class="btn btn-success btn-sm me-1" title="Download"><i class="bi bi-download"></i></a>
                                        <button onclick="deleteFile('${f.name}')" class="btn btn-danger btn-sm" title="Delete"><i class="bi bi-trash"></i></button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `).join('');
                });
        }

        function copyLink() {
            const url = window.location.origin + '/';
            navigator.clipboard.writeText(url).then(() => {
                alert('Link copied!');
            }).catch(() => {
                prompt('Copy this link:', url);
            });
        }

        function deleteAllFiles() {
            if (!confirm('Delete all files from the transfer folder?')) return;
            fetch('/delete/all', {method: 'DELETE'})
                .then(() => loadFiles());
        }

        function updateServerLink() {
            const url = window.location.origin + '/';
            serverLink.href = url;
            serverLink.textContent = url;
        }


        function isImage(name) { return /\\.(jpg|jpeg|png|gif|webp)$/i.test(name); }
        function formatSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024**2) return (bytes/1024).toFixed(1) + ' KB';
            return (bytes/1024**2).toFixed(1) + ' MB';
        }

        // Load files on start
        loadFiles();
        setInterval(loadFiles, 5000);  // Refresh every 5s
    </script>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        files = request.files.getlist('file')
        success = 0
        for file in files:
            if file.filename:
                filename = secure_filename(file.filename)
                if '..' not in filename and os.path.sep not in filename:
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    success += 1
        return f"✅ {success} file(s) uploaded!", 200
    return render_template_string(HTML)

@app.route('/api/files')
def api_files():
    try:
        all_items = os.listdir(UPLOAD_FOLDER)
        files = []
        for f in all_items:
            path = os.path.join(UPLOAD_FOLDER, f)
            if os.path.isfile(path):
                stat = os.stat(path)
                files.append({'name': f, 'size': stat.st_size})
        files.sort(key=lambda x: x['name'].lower())
        return jsonify(files)
    except:
        return jsonify([])


def safe_path(filename):
    filename = secure_filename(filename)
    if not filename:
        return None
    return os.path.join(app.config['UPLOAD_FOLDER'], filename)

@app.route('/preview/<filename>')
def preview_file(filename):
    filepath = safe_path(filename)
    if not filepath or not os.path.isfile(filepath):
        return '', 404
    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, max_age=0)
    return '', 404

@app.route('/delete/<filename>', methods=['DELETE', 'POST'])
def delete_file(filename):
    filepath = safe_path(filename)
    if filepath and os.path.isfile(filepath):
        os.remove(filepath)
        return '', 200
    return '', 404

@app.route('/delete/all', methods=['DELETE', 'POST'])
def delete_all_files():
    deleted = 0
    for name in os.listdir(app.config['UPLOAD_FOLDER']):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], name)
        if os.path.isfile(filepath):
            os.remove(filepath)
            deleted += 1
    return jsonify({'deleted': deleted}), 200

@app.route('/qr.png')
def qr_code():
    url = request.host_url.rstrip('/')
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return send_file(buffer, mimetype='image/png', cache_timeout=0)

@app.route('/download/<filename>')
def download_file(filename):
    filepath = safe_path(filename)
    if not filepath or not os.path.isfile(filepath):
        return "File not found!", 404
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except:
            ip = "localhost"
    finally:
        s.close()
    return ip

if __name__ == '__main__':
    ip = get_ip()
    print(f"\n🚀 Advanced GUI ready! Open on mobile: http://{ip}:5000")
    print("Changes require server restart (Ctrl+C then rerun).")
    app.run(host='0.0.0.0', port=5000, debug=True)
