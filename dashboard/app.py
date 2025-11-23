"""
Web dashboard for monitoring copy trading bot
"""
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import json
import asyncio
from typing import Dict

app = FastAPI(title="Copy Trading Bot Dashboard")

# Store bot stats (in production, use Redis or database)
bot_stats: Dict = {
    "total_copies": 0,
    "successful_copies": 0,
    "failed_copies": 0,
    "avg_latency_ms": 0.0,
    "last_trade_time": None,
    "is_running": False
}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve dashboard HTML"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Copy Trading Bot Dashboard</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                background: #1a1a1a;
                color: #fff;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 20px 0;
            }
            .stat-card {
                background: #2a2a2a;
                padding: 20px;
                border-radius: 8px;
                border: 1px solid #3a3a3a;
            }
            .stat-value {
                font-size: 2em;
                font-weight: bold;
                color: #4CAF50;
            }
            .stat-label {
                color: #aaa;
                margin-top: 5px;
            }
            .status {
                display: inline-block;
                padding: 5px 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            .status.running {
                background: #4CAF50;
            }
            .status.stopped {
                background: #f44336;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Copy Trading Bot Dashboard</h1>
            <div id="status" class="status stopped">Stopped</div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="total-copies">0</div>
                    <div class="stat-label">Total Copies</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="successful-copies">0</div>
                    <div class="stat-label">Successful</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="failed-copies">0</div>
                    <div class="stat-label">Failed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="avg-latency">0.0ms</div>
                    <div class="stat-label">Avg Latency</div>
                </div>
            </div>
        </div>
        
        <script>
            const ws = new WebSocket('ws://localhost:8000/ws');
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            };
            
            function updateDashboard(stats) {
                document.getElementById('total-copies').textContent = stats.total_copies || 0;
                document.getElementById('successful-copies').textContent = stats.successful_copies || 0;
                document.getElementById('failed-copies').textContent = stats.failed_copies || 0;
                document.getElementById('avg-latency').textContent = (stats.avg_latency_ms || 0).toFixed(2) + 'ms';
                
                const statusEl = document.getElementById('status');
                if (stats.is_running) {
                    statusEl.textContent = 'Running';
                    statusEl.className = 'status running';
                } else {
                    statusEl.textContent = 'Stopped';
                    statusEl.className = 'status stopped';
                }
            }
        </script>
    </body>
    </html>
    """
    return html

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    try:
        while True:
            # Send current stats
            await websocket.send_json(bot_stats)
            await asyncio.sleep(1)  # Update every second
    except:
        pass

@app.get("/api/stats")
async def get_stats():
    """Get current bot statistics"""
    return bot_stats

def update_stats(stats: Dict):
    """Update bot statistics (called from main bot)"""
    global bot_stats
    bot_stats.update(stats)

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    import time
    
    def open_browser():
        """Open browser after a short delay"""
        time.sleep(1.5)  # Wait for server to start
        webbrowser.open("http://localhost:8000")
    
    # Start browser in background thread
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    print("=" * 50)
    print("🚀 Starting Dashboard Server...")
    print("📊 Dashboard will open automatically in browser")
    print("🌐 Or manually visit: http://localhost:8000")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

