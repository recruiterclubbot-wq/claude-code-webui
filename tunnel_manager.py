#!/usr/bin/env python3
"""
Microsoft VS Code Tunnel Manager & Web Control Portal
Runs on Render:
1. Starts the internal Google Gemini API bridge on port 8082.
2. Manages the official Microsoft `code tunnel` lifecycle.
3. Automatically captures GitHub device pairing codes and displays them in a sleek web portal on $PORT.
4. Provides direct 1-click access to vscode.dev/tunnel/<name>.
"""

import os
import sys
import re
import json
import time
import subprocess
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [TunnelManager] %(message)s")
logger = logging.getLogger("TunnelManager")

PORT = int(os.getenv("PORT", "10000"))
BRIDGE_PORT = int(os.getenv("BRIDGE_PORT", "8082"))
TUNNEL_NAME = os.getenv("TUNNEL_NAME", "claude-studio")

tunnel_state = {
    "status": "initializing",
    "login_url": None,
    "login_code": None,
    "vscode_url": f"https://vscode.dev/tunnel/{TUNNEL_NAME}/workspace",
    "logs": []
}


def start_gemini_bridge():
    logger.info("Starting Google Gemini Bridge on port %s...", BRIDGE_PORT)
    subprocess.Popen([sys.executable, "/app/bridge.py"], env=os.environ.copy())


def tunnel_worker():
    logger.info("Starting Microsoft Code Tunnel supervisor...")
    tunnel_state["status"] = "starting"

    # Step 1: Check login status or trigger login
    cmd = ["code", "tunnel", "--accept-server-license-terms", "--name", TUNNEL_NAME]
    env = os.environ.copy()
    env["HOME"] = "/root"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env
    )

    for line in iter(proc.stdout.readline, ""):
        clean_line = line.strip()
        if not clean_line:
            continue
        logger.info("[code tunnel] %s", clean_line)
        tunnel_state["logs"].append(clean_line)
        if len(tunnel_state["logs"]) > 50:
            tunnel_state["logs"].pop(0)

        # Detect pairing code
        # Example: "To grant access to the server, please open https://github.com/login/device and use code 1234-ABCD"
        if "github.com/login/device" in clean_line:
            tunnel_state["status"] = "waiting_auth"
            tunnel_state["login_url"] = "https://github.com/login/device"
            code_match = re.search(r'([A-Z0-9]{4}-[A-Z0-9]{4})', clean_line)
            if code_match:
                tunnel_state["login_code"] = code_match.group(1)
                logger.info("Captured GitHub Device Code: %s", tunnel_state["login_code"])

        # Detect active tunnel URL
        # Example: "Open this link in your browser https://vscode.dev/tunnel/claude-studio"
        if "vscode.dev/tunnel" in clean_line:
            tunnel_state["status"] = "active"
            url_match = re.search(r'(https://vscode\.dev/tunnel/\S+)', clean_line)
            if url_match:
                tunnel_state["vscode_url"] = url_match.group(1)
                logger.info("Tunnel is LIVE at: %s", tunnel_state["vscode_url"])

    proc.stdout.close()
    proc.wait()
    logger.warning("Code tunnel process exited with code %s", proc.returncode)
    tunnel_state["status"] = "exited"


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Reduce HTTP access log noise

    def do_GET(self):
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(tunnel_state).encode("utf-8"))
            return

        # Main HTML Dashboard
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        status = tunnel_state["status"]
        code = tunnel_state["login_code"] or "Ожидание кода..."
        login_url = tunnel_state["login_url"] or "https://github.com/login/device"
        vscode_url = tunnel_state["vscode_url"] or f"https://vscode.dev/tunnel/{TUNNEL_NAME}"

        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VS Code Tunnel — Claude Code Studio</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @keyframes pulse-slow {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.6; }} }}
    .pulse-slow {{ animation: pulse-slow 2s infinite; }}
  </style>
</head>
<body class="bg-[#0f1117] text-white min-h-screen flex flex-col items-center justify-center p-4 font-sans">
  <div class="max-w-xl w-full bg-[#181b24] border border-gray-800 rounded-3xl p-6 sm:p-8 shadow-2xl">
    
    <!-- Header -->
    <div class="flex items-center space-x-3 mb-6">
      <div class="w-12 h-12 rounded-2xl bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 text-2xl font-bold">
        ⚡
      </div>
      <div>
        <h1 class="text-xl sm:text-2xl font-semibold tracking-tight">VS Code Cloud Studio</h1>
        <p class="text-sm text-gray-400">Microsoft VS Code Tunnel + Claude Code (Gemini 3.5 Pro)</p>
      </div>
    </div>

    <!-- Status Card -->
    <div id="status-card">
"""

        if status == "active":
            html += f"""
      <div class="bg-emerald-950/40 border border-emerald-500/40 rounded-2xl p-5 mb-6">
        <div class="flex items-center space-x-2 text-emerald-400 font-medium mb-1">
          <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping"></span>
          <span>Туннель активен и готов к работе 24/7!</span>
        </div>
        <p class="text-xs text-gray-300 mb-4">Нажмите кнопку ниже, чтобы открыть официальный VS Code в браузере.</p>
        <a href="{vscode_url}" target="_blank" class="block w-full py-3.5 px-4 bg-emerald-500 hover:bg-emerald-600 text-black font-semibold rounded-xl text-center shadow-lg transition duration-200">
          🚀 Открыть VS Code на vscode.dev
        </a>
      </div>
"""
        elif status == "waiting_auth":
            html += f"""
      <div class="bg-amber-950/40 border border-amber-500/40 rounded-2xl p-5 mb-6">
        <div class="flex items-center space-x-2 text-amber-400 font-medium mb-2">
          <span class="w-2.5 h-2.5 rounded-full bg-amber-400 pulse-slow"></span>
          <span>Шаг 1: Авторизуйте туннель через GitHub</span>
        </div>
        <p class="text-xs text-gray-300 mb-4">Скопируйте этот код и подтвердите доступ к туннелю:</p>
        
        <div class="bg-black/50 border border-amber-500/30 rounded-xl p-4 flex items-center justify-between mb-4">
          <span class="text-2xl sm:text-3xl font-mono tracking-widest text-amber-300 font-bold">{code}</span>
          <button onclick="navigator.clipboard.writeText('{code}'); this.innerText='Скопировано!';" class="px-3 py-1.5 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-xs font-medium rounded-lg border border-amber-500/40 transition">
            Копировать
          </button>
        </div>

        <a href="{login_url}" target="_blank" class="block w-full py-3.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-xl text-center shadow-lg transition duration-200">
          Ввести код на GitHub (github.com/login/device) &rarr;
        </a>
      </div>
"""
        else:
            html += f"""
      <div class="bg-blue-950/40 border border-blue-500/40 rounded-2xl p-5 mb-6">
        <div class="flex items-center space-x-2 text-blue-400 font-medium mb-2">
          <span class="w-2.5 h-2.5 rounded-full bg-blue-400 pulse-slow"></span>
          <span>Инициализация Microsoft VS Code туннеля...</span>
        </div>
        <p class="text-xs text-gray-400">Пожалуйста, подождите 5-10 секунд. Страница обновится автоматически.</p>
      </div>
"""

        html += f"""
    </div>

    <!-- Quick instructions -->
    <div class="bg-[#12141c] rounded-2xl p-4 border border-gray-800 text-xs text-gray-400 space-y-2">
      <div class="font-medium text-gray-300">Как работать с Claude Code в VS Code:</div>
      <ol class="list-decimal list-inside space-y-1">
        <li>В открывшемся окне <span class="text-blue-400">vscode.dev</span> откройте терминал (<code class="bg-gray-800 px-1 py-0.5 rounded">Ctrl + ~</code>).</li>
        <li>В терминале введите <code class="text-emerald-400 bg-gray-800 px-1.5 py-0.5 rounded font-mono">claude</code> и нажмите Enter.</li>
        <li>Claude Code запустится с безлимитным подключением к Google Gemini 3.5.</li>
      </ol>
    </div>

  </div>

  <script>
    // Auto-refresh page every 3 seconds while waiting for authorization
    const currentStatus = '{status}';
    if (currentStatus !== 'active') {{
      setInterval(async () => {{
        try {{
          const res = await fetch('/api/status');
          const data = await res.json();
          if (data.status !== currentStatus || data.login_code !== '{code}') {{
            window.location.reload();
          }}
        }} catch(e) {{}}
      }}, 3000);
    }}
  </script>
</body>
</html>
"""
        self.wfile.write(html.encode("utf-8"))


def run():
    start_gemini_bridge()
    t = threading.Thread(target=tunnel_worker, daemon=True)
    t.start()

    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, DashboardHandler)
    logger.info("Web Dashboard listening on http://0.0.0.0:%s", PORT)
    httpd.serve_forever()


if __name__ == "__main__":
    run()
