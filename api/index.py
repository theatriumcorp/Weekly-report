from flask import Flask

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Atrium Construction — Weekly Report</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f5f5f5;
      color: #333;
      min-height: 100vh;
    }
    header {
      background: #1a1a2e;
      color: white;
      padding: 2rem;
      text-align: center;
    }
    header h1 { font-size: 1.8rem; margin-bottom: 0.25rem; }
    header p { opacity: 0.7; font-size: 0.95rem; }
    main {
      max-width: 800px;
      margin: 2rem auto;
      padding: 0 1rem;
    }
    .generate-btn {
      display: block;
      margin: 0 auto 2rem;
      padding: 0.75rem 2rem;
      font-size: 1rem;
      background: #e94560;
      color: white;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      transition: background 0.2s;
    }
    .generate-btn:hover { background: #c73650; }
    .generate-btn:disabled { background: #999; cursor: not-allowed; }
    .report-container {
      background: white;
      border-radius: 8px;
      padding: 2rem;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      line-height: 1.7;
      display: none;
    }
    .report-container.visible { display: block; }
    .report-container h1, .report-container h2, .report-container h3 {
      color: #1a1a2e;
      margin-top: 1.5rem;
      margin-bottom: 0.5rem;
    }
    .report-container h1 { font-size: 1.5rem; }
    .report-container h2 { font-size: 1.25rem; }
    .report-container h3 { font-size: 1.1rem; }
    .report-container ul, .report-container ol {
      padding-left: 1.5rem;
      margin-bottom: 0.75rem;
    }
    .report-container li { margin-bottom: 0.3rem; }
    .report-container p { margin-bottom: 0.75rem; }
    .report-container strong { color: #1a1a2e; }
    .loading {
      text-align: center;
      padding: 2rem;
      color: #666;
      font-size: 1.1rem;
      display: none;
    }
    .loading.visible { display: block; }
    .spinner {
      display: inline-block;
      width: 24px;
      height: 24px;
      border: 3px solid #ddd;
      border-top-color: #e94560;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      vertical-align: middle;
      margin-right: 0.5rem;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .error {
      background: #ffe0e0;
      color: #c00;
      padding: 1rem;
      border-radius: 6px;
      text-align: center;
      display: none;
    }
    .error.visible { display: block; }
  </style>
</head>
<body>
  <header>
    <h1>Atrium Construction Corp</h1>
    <p>Weekly Status Report Generator</p>
  </header>
  <main>
    <button class="generate-btn" id="generateBtn" onclick="generateReport()">
      Generate Weekly Report
    </button>
    <div class="loading" id="loading">
      <span class="spinner"></span> Generating report with Claude...
    </div>
    <div class="error" id="error"></div>
    <div class="report-container" id="report"></div>
  </main>
  <script>
    async function generateReport() {
      const btn = document.getElementById('generateBtn');
      const loading = document.getElementById('loading');
      const report = document.getElementById('report');
      const error = document.getElementById('error');
      btn.disabled = true;
      loading.classList.add('visible');
      report.classList.remove('visible');
      error.classList.remove('visible');
      try {
        const res = await fetch('/api/generate', { method: 'POST' });
        if (!res.ok) throw new Error('Server error: ' + res.status);
        const data = await res.json();
        report.innerHTML = markdownToHtml(data.report);
        report.classList.add('visible');
      } catch (err) {
        error.textContent = 'Failed to generate report. Please check that the ANTHROPIC_API_KEY environment variable is set in Vercel.';
        error.classList.add('visible');
      } finally {
        btn.disabled = false;
        loading.classList.remove('visible');
      }
    }
    function markdownToHtml(md) {
      return md
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
        .replace(/^\\- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\\/li>\\n?)+/g, '<ul>$&</ul>')
        .replace(/\\n{2,}/g, '</p><p>')
        .replace(/\\n/g, '<br>');
    }
  </script>
</body>
</html>"""


@app.route("/")
def home():
    return HTML, 200, {"Content-Type": "text/html"}
