#!/usr/bin/env python3
"""
app.py

Web 404 Fetcher - Improved
Web app that takes a base website something.com (and an optional path, if you want to test a specific
dir that causes a 404), requests a non-existent page, takes out the ugly stuff,
and proxies it so it can be displayed in-app via iframe or saved for archival purposes.
"""

import os
import uuid
import certifi
import requests
from urllib.parse import urljoin
from flask import Flask, request, render_template_string, Response
from bs4 import BeautifulSoup

# Ensure requests/openssl uses certifi’s CA bundle
os.environ.setdefault('SSL_CERT_FILE', certifi.where())

app = Flask(__name__)

# In-memory store of fetched pages: page_id -> HTML content
pages = {}

TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>404 Page Fetcher</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <!-- Bootstrap 5 CSS CDN -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {
      background: #f8fafc;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }
    .main-card {
      max-width: 900px;
      min-width: 320px;
      width: 100%;
      border-radius: 1rem;
      box-shadow: 0 6px 32px rgba(30, 41, 59, 0.14);
      background: #fff;
      padding: 2.5rem 2rem 2rem 2rem;
    }
    .fun-header {
      font-weight: 700;
      font-size: 2.3rem;
      letter-spacing: -.5px;
      /* No gradient, just a fun blue (pick your favorite) */
      color: #2563eb; /* Fun, professional blue */
    }
    .small {
      color: #64748b;
      font-size: 0.95rem;
    }
    .iframe-wrap {
      border-radius: 1rem;
      overflow: hidden;
      box-shadow: 0 2px 10px rgba(30,41,59,0.10);
      margin-bottom: 1rem;
      margin-top: .5rem;
    }
  </style>
</head>
<body>
  <div class="main-card mx-auto">
    <div class="text-center mb-4">
      <span class="fun-header">404 Page Fetcher</span>
      <div class="small mt-2"> Explore how creative (or not) different websites are with their 404 pages.
 </div>
    </div>
    <form method="post" autocomplete="off">
      <div class="mb-3">
        <label for="url" class="form-label">Site URL</label>
        <input type="text" name="url" id="url" class="form-control" value="{{ request.form.url or '' }}" placeholder="https://example.com" required>
      </div>
      <div class="mb-3">
        <label for="path" class="form-label">Optional path <span class="small">(leave blank for 404)</span></label>
        <input type="text" name="path" id="path" class="form-control" value="{{ request.form.path or '' }}">
      </div>
      <button type="submit" class="btn btn-primary w-100">Fetch 404 Page</button>
    </form>
    {% if error %}
      <div class="alert alert-danger mt-4" role="alert">
        <strong>Error:</strong> {{ error }}
      </div>
    {% endif %}

    {% if fetched_url %}
      <div class="alert alert-secondary mt-4">
        <div class="fw-bold mb-1">Fetched URL:</div>
        <a href="{{ fetched_url }}" target="_blank" style="word-break: break-all;">{{ fetched_url }}</a>
        <div>Status code: <strong>{{ status_code }}</strong></div>
      </div>
    {% endif %}

    {% if page_id %}
      <div class="mt-3 mb-2 fw-semibold">Rendered 404 page:</div>
      <div class="iframe-wrap">
        <iframe class="w-100" style="height: 480px; border: none;" src="/view/{{ page_id }}" sandbox></iframe>
      </div>
      <div class="text-center d-flex flex-column flex-md-row gap-2 justify-content-center">
        <a class="btn btn-outline-secondary btn-sm" href="{{ fetched_url }}" target="_blank">
          Open full 404 page (real site)
        </a>
        <a class="btn btn-outline-primary btn-sm" href="/view/{{ page_id }}" target="_blank">
          Open sanitized local copy
        </a>
      </div>
    {% endif %}
  </div>
  <footer class="text-center mt-4 small text-muted">
    Built with Flask & Bootstrap &mdash; v2025
  </footer>
</body>
</html>
"""


@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    fetched_url = None
    status_code = None
    page_id = None

    if request.method == 'POST':
        base = request.form.get('url', '').strip()
        path = request.form.get('path', '').strip()

        if not base:
            error = "You must enter a site URL."
        else:
            # Normalize URL
            if not base.startswith(('http://', 'https://')):
                base = 'http://' + base
            base = base.rstrip('/')

            # Determine or generate path
            if path:
                path = path.lstrip('/')
            else:
                path = f'404-collector-{uuid.uuid4().hex}'

            fetched_url = urljoin(base + '/', path)
            try:
                # Spoof browser User-Agent for better compatibility
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    )
                }
                resp = requests.get(fetched_url, timeout=10, verify=certifi.where(), headers=headers)
                status_code = resp.status_code

                if status_code == 404:
                    # Parse and proxy the HTML
                    soup = BeautifulSoup(resp.text, 'html.parser')

                    # Remove scripts for safety
                    for tag in soup(['script']):
                        tag.decompose()

                    # Prefix with base so relative resources resolve
                    html_content = f'<base href="{fetched_url}">\n' + str(soup)

                    # Store in memory and assign an ID
                    page_id = uuid.uuid4().hex
                    pages[page_id] = html_content
                else:
                    error = f"hey!!! that's not a 404, that's a {status_code} (working link)!!!"
            except Exception as e:
                error = str(e)

    return render_template_string(
        TEMPLATE,
        error=error,
        fetched_url=fetched_url,
        status_code=status_code,
        page_id=page_id
    )

@app.route('/view/<page_id>')
def view_page(page_id):
    html = pages.get(page_id)
    if html is None:
        return "Page not found", 404
    return Response(html, mimetype='text/html')

if __name__ == '__main__':
    # debug=True for dev; disable in production
    app.run(host='0.0.0.0', port=5000, debug=True)
