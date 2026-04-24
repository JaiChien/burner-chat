#!/usr/bin/env python3
"""
🔥 BurnerChat VSCode Extension Installer
自動安裝焚模式聊天室 VSCode 擴充套件並啟動伺服器

版本歷史請見同目錄的 CHANGELOG.md
"""

import os
import sys
import json

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import time
import shutil
import socket
import hashlib
import secrets
import zipfile
import tempfile
import platform
import threading
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime

# ─── 顏色輸出 ───────────────────────────────────────────────────────────────
class C:
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    MAGENTA= "\033[95m"
    WHITE  = "\033[97m"
    DIM    = "\033[2m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

def log(msg, color=C.WHITE):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{C.DIM}[{ts}]{C.RESET} {color}{msg}{C.RESET}")

def step(n, total, msg):
    bar = "█" * n + "░" * (total - n)
    print(f"\r{C.CYAN}[{bar}] {n}/{total}{C.RESET}  {C.BOLD}{msg}{C.RESET}", end="", flush=True)
    if n == total:
        print()

def banner():
    print(f"""
{C.RED}╔══════════════════════════════════════════════╗
║  🔥  B U R N E R  C H A T  I N S T A L L E R  ║
║       焚後即毀・端對端加密・零留存              ║
║       v1.5 — E2E 加密 🔒 (AES-256-GCM)         ║
╚══════════════════════════════════════════════╝{C.RESET}
""")


# ─── 系統檢查 ────────────────────────────────────────────────────────────────
def check_prerequisites():
    log("檢查系統需求...", C.CYAN)
    issues = []

    if sys.version_info < (3, 8):
        issues.append("需要 Python 3.8 以上版本")
    else:
        log(f"  ✓ Python {sys.version.split()[0]}", C.GREEN)

    node = shutil.which("node")
    if not node:
        issues.append("未找到 Node.js(請先安裝 https://nodejs.org)")
    else:
        try:
            ver = subprocess.check_output(["node", "--version"], text=True).strip()
            log(f"  ✓ Node.js {ver}", C.GREEN)
        except Exception:
            issues.append("無法執行 node 指令")

    code = shutil.which("code")
    if not code:
        log(f"  ⚠ 未找到 VSCode CLI — 將跳過 VSCode extension 安裝,只跑聊天 server", C.YELLOW)
        log(f"    (要裝 extension 的話:VSCode → Ctrl+Shift+P → Shell Command: Install 'code' command)", C.DIM)
    else:
        log(f"  ✓ VSCode CLI: {code}", C.GREEN)

    if issues:
        print()
        log("❌ 發現以下問題,請修正後重新執行:", C.RED)
        for i in issues:
            log(f"   • {i}", C.YELLOW)
        sys.exit(1)

    print()
    return code is not None  # 回傳 VSCode CLI 是否可用


# ─── 密碼生成 ────────────────────────────────────────────────────────────────
def generate_room_password(length=12):
    chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(chars) for _ in range(length))

def generate_admin_password(length=20):
    """Admin 密碼比較長,更安全"""
    chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(chars) for _ in range(length))

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


# ─── 取得本機 IP ─────────────────────────────────────────────────────────────
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def find_free_port(start=7788):
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
    return start


# ─── 建立 VSCode 擴充套件 ─────────────────────────────────────────────────────
EXTENSION_PACKAGE_JSON = {
    "name": "burner-chat",
    "displayName": "🔥 BurnerChat",
    "description": "焚後即毀的端對端加密即時聊天室",
    "version": "1.4.0",
    "publisher": "burner-chat",
    "engines": {"vscode": "^1.80.0"},
    "categories": ["Other"],
    "activationEvents": ["onCommand:burnerChat.openRoom"],
    "main": "./extension.js",
    "contributes": {
        "commands": [
            {"command": "burnerChat.openRoom", "title": "🔥 開啟 BurnerChat 聊天室", "category": "BurnerChat"},
            {"command": "burnerChat.joinRoom", "title": "🔥 加入 BurnerChat 聊天室", "category": "BurnerChat"}
        ],
        "keybindings": [
            {"command": "burnerChat.openRoom", "key": "ctrl+shift+b", "mac": "cmd+shift+b"}
        ]
    }
}

EXTENSION_JS = r"""
const vscode = require('vscode');

function activate(context) {
    let openCmd = vscode.commands.registerCommand('burnerChat.openRoom', async () => {
        const url = await vscode.window.showInputBox({
            prompt: '輸入 BurnerChat 伺服器 URL 或房間連結',
            placeHolder: 'http://localhost:7788 或 http://ip:7788/room/xxxx'
        });
        if (url === undefined) return;
        const serverUrl = url.trim() || 'http://localhost:7788';
        openPanel(context, serverUrl);
    });

    let joinCmd = vscode.commands.registerCommand('burnerChat.joinRoom', async () => {
        const url = await vscode.window.showInputBox({
            prompt: '輸入邀請 URL(包含 room ID)',
            placeHolder: 'http://192.168.x.x:7788/room/XXXXXXXX'
        });
        if (!url) return;
        openPanel(context, url);
    });

    context.subscriptions.push(openCmd, joinCmd);
}

function openPanel(context, serverUrl) {
    const panel = vscode.window.createWebviewPanel(
        'burnerChat', '🔥 BurnerChat',
        vscode.ViewColumn.Two,
        { enableScripts: true, retainContextWhenHidden: true }
    );
    panel.webview.onDidReceiveMessage(msg => {
        if (msg && msg.type === 'unread') {
            const n = parseInt(msg.count) || 0;
            panel.title = n > 0 ? '(' + n + ') 🔥 BurnerChat' : '🔥 BurnerChat';
        }
    });
    panel.webview.html = getWebviewContent(serverUrl);
}

function getWebviewContent(serverUrl) {
    return `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0d0d0d; color: #e0e0e0; font-family: 'Courier New', monospace;
         display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
  #header { background: #1a0a00; border-bottom: 1px solid #ff4500;
            padding: 12px 16px; display: flex; align-items: center; gap: 10px; }
  #header h1 { font-size: 14px; color: #ff6b35; font-weight: bold; }
  #header .me { font-size: 11px; color: #ff8c35; margin-left: 8px; }
  .sound-btn { font-size: 14px; cursor: pointer; opacity: .75; user-select: none;
               transition: opacity .2s, transform .1s; padding: 2px 6px; border-radius: 3px; }
  .sound-btn:hover { opacity: 1; transform: scale(1.15); background: rgba(255,69,0,.1); }
  #status { font-size: 11px; color: #666; margin-left: auto; }
  #roster { background: #0a0503; border-bottom: 1px solid #2a1a00;
            padding: 5px 16px; font-size: 11px; color: #888;
            display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  #roster .roster-toggle { cursor: pointer; color: #ff4500; user-select: none;
                           padding: 1px 6px; border: 1px solid #2a1a00; border-radius: 2px; }
  #roster .roster-toggle:hover { background: #1a0a00; }
  #roster .roster-list { flex: 1; line-height: 1.5; }
  #roster.collapsed .roster-list { display: none; }
  #sys-log { background: #080503; border-bottom: 1px solid #2a1a00;
             padding: 4px 16px; font-size: 11px; color: #888; font-style: italic; }
  #sys-log .sys-header { display: flex; align-items: center; gap: 8px; }
  #sys-log .sys-last { flex: 1; opacity: .85;
                       white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #sys-log .sys-toggle { cursor: pointer; color: #ff4500; user-select: none;
                         padding: 1px 6px; border: 1px solid #2a1a00; border-radius: 2px;
                         font-style: normal; font-size: 10px; flex-shrink: 0; }
  #sys-log .sys-toggle:hover { background: #1a0a00; }
  #sys-log .sys-full { max-height: 10vh; overflow-y: auto; margin-top: 4px; }
  #sys-log .sys-line { padding: 2px 0; opacity: .7; }
  #sys-log.collapsed .sys-full { display: none; }
  #sys-log:not(.collapsed) .sys-last { display: none; }
  #burn-bar { background: #0f0a05; border-bottom: 1px solid #2a1a00;
              padding: 6px 16px; display: flex; align-items: center; gap: 8px;
              font-size: 11px; color: #888; flex-wrap: wrap; }
  #burn-bar label { color: #ff8c35; }
  #burn-bar input[type=number] { background: #0a0a0a; border: 1px solid #333;
              color: #e0e0e0; padding: 3px 6px; width: 55px; border-radius: 2px;
              font-family: inherit; font-size: 11px; outline: none; }
  #burn-bar button { background: transparent; color: #ff4500; border: 1px solid #ff4500;
              padding: 3px 10px; border-radius: 2px; cursor: pointer; font-size: 10px; }
  #burn-bar button:hover { background: #ff4500; color: white; }
  #messages { flex: 1; overflow-y: auto; padding: 16px; display: flex;
              flex-direction: column; gap: 8px; }
  .msg { padding: 8px 12px; border-radius: 4px; max-width: 80%; font-size: 12px;
         transition: opacity .6s, transform .6s; }
  .msg.system { color: #666; font-style: italic; align-self: center; background: #111; }
  .msg.mine { align-self: flex-end; background: #1a0a00; color: #ff8c66; }
  .msg.other { align-self: flex-start; background: #0a1a0a; color: #88ffbb; }
  .msg .sender { font-size: 10px; opacity: 0.6; margin-bottom: 3px; }
  .msg .readby { font-size: 9px; color: #00ff88; opacity: .55; margin-top: 3px; }
  .msg.mine .readby { text-align: right; }
  .msg .countdown { font-size: 9px; opacity: .5; margin-top: 2px; }
  .msg.mine .countdown { text-align: right; }
  .msg.burning { animation: flicker .6s infinite; }
  .msg.unread { border-left: 3px solid #ff4500; padding-left: 9px; }
  /* 反黑遮罩:未 focus 或分頁背景時,訊息文字顯示為 █████ */
  #messages.redacted .msg:not(.system) .text-content { font-size: 0; }
  #messages.redacted .msg:not(.system) .text-content::before {
    content: attr(data-mask); font-size: 12px; color: #888; opacity: .6; letter-spacing: -2px;
  }
  @keyframes flicker { 0%,100%{opacity:1} 50%{opacity:.6} }
  #input-area { display: flex; gap: 8px; padding: 12px 16px; background: #111; }
  #input-area input { flex: 1; background: #1a1a1a; border: 1px solid #333; color: #e0e0e0;
                      padding: 8px 12px; border-radius: 3px; font-size: 12px; outline: none; }
  #input-area button { background: #ff4500; color: white; border: none;
                       padding: 8px 16px; border-radius: 3px; cursor: pointer; }
  #clean-toggle { background: transparent !important; border: 1px solid #333 !important;
                  cursor: pointer; padding: 4px 6px !important;
                  border-radius: 3px; flex-shrink: 0; transition: .15s;
                  display: flex; align-items: center; justify-content: center; }
  #clean-toggle img { width: 22px; height: 22px; display: block; opacity: .7; transition: opacity .15s; }
  #clean-toggle:hover img { opacity: 1; }
  #clean-toggle:hover { background: #1a0a00 !important; border-color: #ff4500 !important; }
  #clean-toggle.active { color: #ff4500 !important; border-color: #ff4500 !important;
                         background: rgba(255,69,0,.1) !important; }
  /* 乾淨版:隱藏 header/roster/sys-log/burn-bar,保留訊息區與輸入列 */
  body.clean-mode #header,
  body.clean-mode #roster,
  body.clean-mode #sys-log,
  body.clean-mode #burn-bar { display: none !important; }
  body.clean-mode #msg-input::placeholder { color: transparent; }
  body.clean-mode #send-btn { font-size: 0; padding: 8px 14px; }
  body.clean-mode #send-btn::after { content: '→'; font-size: 16px; }
  body.clean-mode .readby .names { display: none; }

  /* Emoji + 圖片按鈕 */
  #emoji-toggle,#img-attach { background: transparent !important; border: 1px solid #333 !important;
                              cursor: pointer; padding: 4px 8px !important; border-radius: 3px;
                              font-size: 16px; flex-shrink: 0; transition: .15s; color: #e0e0e0 !important; }
  #emoji-toggle:hover,#img-attach:hover { background: #1a0a00 !important; border-color: #ff4500 !important; }
  #emoji-toggle.active { color: #ff4500 !important; border-color: #ff4500 !important; background: rgba(255,69,0,.1) !important; }

  /* Emoji 面板 */
  #emoji-panel { position: fixed; bottom: 68px; left: 16px; width: 300px; max-width: 92vw;
                 background: #1a1a1a; border: 1px solid #333; border-radius: 6px; padding: 8px;
                 z-index: 999; box-shadow: 0 4px 20px rgba(0,0,0,.5); }
  #emoji-search { width: 100%; background: #0d0d0d; border: 1px solid #333; color: #e0e0e0;
                  padding: 6px 10px; border-radius: 4px; font-size: 12px; outline: none;
                  box-sizing: border-box; margin-bottom: 6px; }
  #emoji-search:focus { border-color: #ff4500; }
  #emoji-tabs { display: flex; gap: 4px; border-bottom: 1px solid #333; padding-bottom: 6px; margin-bottom: 6px; }
  #emoji-tabs .tab { cursor: pointer; padding: 3px 7px; border-radius: 3px; font-size: 15px; opacity: .5; }
  #emoji-tabs .tab:hover { opacity: .9; background: #0d0d0d; }
  #emoji-tabs .tab.active { opacity: 1; background: #0d0d0d; box-shadow: inset 0 -2px 0 #ff4500; }
  #emoji-grid { display: grid; grid-template-columns: repeat(8,1fr); gap: 2px; max-height: 220px; overflow-y: auto; }
  #emoji-grid .emoji-cell { cursor: pointer; padding: 4px; text-align: center; font-size: 20px; border-radius: 3px; user-select: none; }
  #emoji-grid .emoji-cell:hover { background: #ff4500; transform: scale(1.15); }

  /* 圖片預覽 */
  #img-preview { position: fixed; bottom: 68px; right: 16px; background: #1a1a1a; border: 1px solid #ff4500;
                 border-radius: 6px; padding: 8px; display: flex; align-items: center; gap: 8px; z-index: 999;
                 box-shadow: 0 4px 20px rgba(0,0,0,.5); }
  #img-preview #img-preview-thumb { max-width: 80px; max-height: 80px; border-radius: 3px; object-fit: cover; }
  #img-preview #img-preview-size { font-size: 10px; color: #888; }
  #img-preview button { background: transparent; border: 1px solid #333; color: #ff4444; cursor: pointer;
                        width: 24px; height: 24px; padding: 0; border-radius: 50%; font-size: 12px; }
  #img-preview button:hover { background: #ff4444; color: white; }

  /* 訊息內圖片 */
  .msg-image { width: 100%; max-width: 280px; aspect-ratio: 4/3; background-size: contain;
               background-position: left center; background-repeat: no-repeat; margin-top: 6px;
               border-radius: 4px; cursor: zoom-in; border: 1px solid #333; }
  .msg.mine .msg-image { background-position: right center; }
  #messages.redacted .msg:not(.system) .msg-image { filter: blur(18px); }

  /* 全螢幕 viewer */
  #img-viewer { position: fixed; inset: 0; background: rgba(0,0,0,.96); z-index: 9999; display: flex; flex-direction: column; }
  #img-viewer-stage { flex: 1; overflow: hidden; position: relative; cursor: grab;
                      display: flex; align-items: center; justify-content: center; }
  #img-viewer-stage.dragging { cursor: grabbing; }
  #img-viewer-content { width: 100%; height: 100%; background-size: contain; background-position: center;
                        background-repeat: no-repeat; transition: transform .1s ease-out; transform-origin: center; }
  #img-viewer-toolbar { padding: 10px 20px; display: flex; gap: 8px; align-items: center;
                        justify-content: center; background: rgba(0,0,0,.5); border-top: 1px solid #222; }
  #img-viewer-toolbar button { background: transparent; border: 1px solid #555; color: #ccc; cursor: pointer;
                               padding: 6px 14px; border-radius: 4px; font-size: 14px; min-width: 44px; }
  #img-viewer-toolbar button:hover { background: #333; color: white; border-color: #888; }
  #img-viewer-zoom { color: #ccc; font-size: 12px; min-width: 50px; text-align: center; }
  #img-viewer-warn { position: absolute; top: 20px; left: 50%; transform: translateX(-50%);
                     background: rgba(255,69,0,.15); border: 1px solid #ff4500; color: #ff4500;
                     padding: 6px 14px; border-radius: 20px; font-size: 11px; letter-spacing: .5px; }
  #auth-overlay { position: fixed; inset: 0; background: #0d0d0d;
                  display: flex; align-items: center; justify-content: center;
                  flex-direction: column; gap: 12px; z-index: 100; }
  #auth-overlay input { background: #1a1a1a; border: 1px solid #333; color: #e0e0e0;
                         padding: 10px 16px; width: 280px; border-radius: 4px;
                         font-size: 14px; outline: none; text-align: center; }
  #auth-overlay input[type=password] { letter-spacing: 2px; }
  #auth-overlay button { background: #ff4500; color: white; border: none; width: 280px;
                          padding: 10px; border-radius: 4px; cursor: pointer; font-size: 14px; }
  #auth-overlay .title { color: #ff6b35; font-size: 18px; font-weight: bold; }
  #auth-overlay .subtitle { color: #666; font-size: 12px; }
  #auth-err { color: #ff4444; font-size: 12px; min-height: 16px; }
</style></head>
<body>
<div id="auth-overlay">
  <div class="title">🔥 BurnerChat</div>
  <div class="subtitle">取個名字並輸入房間密碼</div>
  <input type="text" id="nick-input" placeholder="你的名字..." maxlength="20" autofocus />
  <input type="password" id="pwd-input" placeholder="房間密碼..." />
  <div id="auth-err"></div>
  <button onclick="authenticate()">進入房間</button>
</div>

<div id="header" style="display:none">
  <span>🔥</span><h1>BurnerChat</h1>
  <span class="me" id="me-label"></span>
  <span id="sound-btn" class="sound-btn" onclick="toggleSound()">🔔</span>
  <span id="status">●  連線中...</span>
</div>
<div id="roster" class="collapsed" style="display:none">
  <span class="roster-toggle" onclick="toggleRoster()"></span>
  <span class="roster-list"></span>
</div>
<div id="sys-log" class="collapsed" style="display:none">
  <div class="sys-header">
    <span class="sys-last"></span>
    <span class="sys-toggle" onclick="toggleSysLog()"></span>
  </div>
  <div class="sys-full"></div>
</div>
<div id="burn-bar" style="display:none">
  <label>🔥 訊息存活:</label>
  <input type="number" id="burn-sec" min="0" max="3600" value="30" />
  <span>秒</span>
  <button onclick="updateBurn()">套用</button>
</div>
<div id="messages" style="display:none"></div>
<div id="input-area" style="display:none">
  <button id="clean-toggle" class="clean-btn" onclick="toggleCleanMode()" title="切換乾淨版"><img src="data:image/png;base64,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" alt="toggle"/></button>
  <input type="text" id="msg-input" placeholder="輸入訊息..." />
  <button id="send-btn" onclick="sendMsg()">發送</button>
</div>
<div id="emoji-panel" style="display:none">
  <input type="text" id="emoji-search" placeholder="搜尋 emoji..." />
  <div id="emoji-tabs"></div>
  <div id="emoji-grid"></div>
</div>
<div id="img-preview" style="display:none">
  <img id="img-preview-thumb" />
  <span id="img-preview-size"></span>
  <button onclick="clearImagePreview()" title="取消">✕</button>
</div>
<div id="img-viewer" style="display:none">
  <div id="img-viewer-stage"><div id="img-viewer-content"></div></div>
  <div id="img-viewer-toolbar">
    <button onclick="viewerZoomOut()" title="縮小">−</button>
    <span id="img-viewer-zoom">100%</span>
    <button onclick="viewerZoomIn()" title="放大">+</button>
    <button onclick="viewerReset()" title="重設">重設</button>
    <button onclick="closeImageViewer()" title="關閉 (Esc)">✕</button>
  </div>
  <div id="img-viewer-warn" style="display:none">⚠ 請勿截圖或轉傳 · 訊息焚毀後圖片自動消失</div>
</div>
<input type="file" id="img-file-input" accept="image/jpeg,image/png,image/webp" style="display:none" />

<script>
const RAW_URL = '${serverUrl}';
const _u = new URL(RAW_URL);
const SERVER = _u.protocol + '//' + _u.host;
const _parts = _u.pathname.split('/').filter(Boolean);
const ROOM_ID_FROM_URL = (_parts[0] === 'room' && _parts[1]) ? _parts[1] : '';
const BASE_TITLE = '🔥 BurnerChat';
let authToken = null, nick = '', clientId = null;
let sinceSeq = 0;
let polling = false;
let pollAbortCtrl = null;
let burnDuration = 30, unreadCount = 0, soundEnabled = true, audioCtx = null;
let cryptoKey = null;
const msgReads = {}, sentReads = {};
// 訊息暫存:等 focus 輸入框(別人訊息)或湊齊所有讀者(自己訊息)才開始倒數
const pendingBurn = new Map();  // msgId -> { el, isMine, readersNeeded, readersGot }
// 線上名單 + UI 狀態
let roster = [];
let rosterExpanded = false;
const ROSTER_COLLAPSE_THRESHOLD = 6;
// 系統訊息獨立區:最新 10 則,預設折疊只顯示最後一則
const sysMsgs = [];
const MAX_SYS_MSGS = 10;
let sysExpanded = false;
let cleanMode = false;  // 乾淨版(本地狀態,不發給 server)
let inputFocused = false;
let heartbeatTimer = null;
const HEARTBEAT_INTERVAL = 15000;
const vscodeApi = (typeof acquireVsCodeApi === 'function') ? acquireVsCodeApi() : null;

// ─── Emoji Picker 資料 + 功能 ──────────────────────────────────
const EMOJI_DATA=[{"e":"😀","k":"grin smile happy 笑 開心"},{"e":"😃","k":"smile happy 開心 笑"},{"e":"😄","k":"laugh happy 大笑 開心"},{"e":"😁","k":"grin teeth 露齒 笑"},{"e":"😆","k":"laugh happy 哈哈"},{"e":"😅","k":"sweat laugh 尷尬 笑"},{"e":"🤣","k":"rofl laugh 笑翻 笑哭"},{"e":"😂","k":"joy laugh tears 笑哭"},{"e":"🙂","k":"slight smile 微笑"},{"e":"🙃","k":"upside flip 倒立 倒過來"},{"e":"😉","k":"wink 眨眼"},{"e":"😊","k":"blush smile 害羞 微笑"},{"e":"😇","k":"angel halo 天使"},{"e":"🥰","k":"love heart 愛心"},{"e":"😍","k":"heart eyes 愛心眼"},{"e":"🤩","k":"star eyes 星星眼 驚嘆"},{"e":"😘","k":"kiss 親親 飛吻"},{"e":"😗","k":"kiss 吻"},{"e":"☺️","k":"smile blush 微笑"},{"e":"😚","k":"kiss closed 閉眼親"},{"e":"😙","k":"kiss smile 親"},{"e":"🥲","k":"tear smile 含淚笑"},{"e":"😋","k":"yum tongue 好吃"},{"e":"😛","k":"tongue 吐舌"},{"e":"😜","k":"wink tongue 調皮"},{"e":"🤪","k":"zany crazy 瘋狂"},{"e":"😝","k":"tongue closed 扮鬼臉"},{"e":"🤑","k":"money mouth 錢 貪財"},{"e":"🤗","k":"hug 擁抱"},{"e":"🤭","k":"hand mouth 偷笑 驚"},{"e":"🤫","k":"shush quiet 噓 安靜"},{"e":"🤔","k":"thinking 思考"},{"e":"🤐","k":"zipper mouth 閉嘴"},{"e":"🤨","k":"raised eyebrow 懷疑"},{"e":"😐","k":"neutral 面無表情"},{"e":"😑","k":"expressionless 無奈"},{"e":"😶","k":"no mouth 無言"},{"e":"😏","k":"smirk 奸笑"},{"e":"😒","k":"unamused 無聊 不爽"},{"e":"🙄","k":"roll eyes 翻白眼"},{"e":"😬","k":"grimace 尷尬"},{"e":"🤥","k":"lying nose 說謊"},{"e":"😌","k":"relieved 放鬆"},{"e":"😔","k":"pensive 難過 沉思"},{"e":"😪","k":"sleepy 想睡"},{"e":"🤤","k":"drooling 流口水"},{"e":"😴","k":"sleeping 睡覺"},{"e":"😷","k":"mask 口罩 生病"},{"e":"🤒","k":"thermometer sick 發燒"},{"e":"🤕","k":"head bandage 受傷"},{"e":"🤢","k":"nauseated 想吐"},{"e":"🤮","k":"vomit 吐"},{"e":"🤧","k":"sneeze 打噴嚏"},{"e":"🥵","k":"hot 熱"},{"e":"🥶","k":"cold 冷"},{"e":"🥴","k":"woozy 醉"},{"e":"😵","k":"dizzy 暈"},{"e":"🤯","k":"exploding 爆炸 震驚"},{"e":"🤠","k":"cowboy 牛仔"},{"e":"🥳","k":"party 派對 慶生"},{"e":"😎","k":"sunglasses cool 酷 墨鏡"},{"e":"🤓","k":"nerd 書呆子"},{"e":"🧐","k":"monocle 單片眼鏡"},{"e":"😕","k":"confused 困惑"},{"e":"😟","k":"worried 擔心"},{"e":"🙁","k":"frown 皺眉"},{"e":"☹️","k":"frowning 難過"},{"e":"😮","k":"surprised 驚訝"},{"e":"😯","k":"hushed 驚"},{"e":"😲","k":"astonished 驚訝"},{"e":"😳","k":"flushed 臉紅"},{"e":"🥺","k":"pleading 拜託"},{"e":"😦","k":"frown open 驚慌"},{"e":"😧","k":"anguished 痛苦"},{"e":"😨","k":"fearful 害怕"},{"e":"😰","k":"cold sweat 冷汗"},{"e":"😥","k":"sad relieved 難過"},{"e":"😢","k":"cry 哭"},{"e":"😭","k":"loud cry 大哭"},{"e":"😱","k":"scream 尖叫"},{"e":"😖","k":"confounded 糾結"},{"e":"😣","k":"persevering 努力"},{"e":"😞","k":"disappointed 失望"},{"e":"😓","k":"downcast sweat 汗顏"},{"e":"😩","k":"weary 累"},{"e":"😫","k":"tired 疲累"},{"e":"🥱","k":"yawn 哈欠"},{"e":"😤","k":"triumph angry 生氣 哼"},{"e":"😡","k":"pout rage 憤怒"},{"e":"😠","k":"angry 生氣"},{"e":"🤬","k":"cursing 罵人 髒話"},{"e":"😈","k":"devil smile 壞笑"},{"e":"👿","k":"devil angry 惡魔"},{"e":"💀","k":"skull 骷髏 死"},{"e":"👻","k":"ghost 鬼 幽靈"},{"e":"👽","k":"alien 外星人"},{"e":"🤖","k":"robot 機器人"},{"e":"💩","k":"poop 便便"},{"e":"👋","k":"wave hi 揮手 你好"},{"e":"🤚","k":"raised back 舉手"},{"e":"🖐️","k":"hand spread 五指張開"},{"e":"✋","k":"raised 舉手 停"},{"e":"🖖","k":"vulcan 瓦肯"},{"e":"👌","k":"ok perfect 好 完美"},{"e":"🤌","k":"pinched 捏"},{"e":"🤏","k":"pinch small 一點點"},{"e":"✌️","k":"peace victory 勝利 二"},{"e":"🤞","k":"crossed fingers 祈禱 希望"},{"e":"🤟","k":"love you 我愛你"},{"e":"🤘","k":"rock horns 搖滾"},{"e":"🤙","k":"call me 打電話"},{"e":"👈","k":"point left 指左"},{"e":"👉","k":"point right 指右"},{"e":"👆","k":"point up 指上"},{"e":"🖕","k":"middle finger 中指"},{"e":"👇","k":"point down 指下"},{"e":"☝️","k":"point up 食指"},{"e":"👍","k":"thumbs up 讚 好"},{"e":"👎","k":"thumbs down 噓 差"},{"e":"✊","k":"fist 拳頭"},{"e":"👊","k":"punch 揍"},{"e":"🤛","k":"left fist 拳"},{"e":"🤜","k":"right fist 拳"},{"e":"👏","k":"clap 拍手 鼓掌"},{"e":"🙌","k":"praise 舉手 萬歲"},{"e":"👐","k":"open hands 雙手"},{"e":"🤲","k":"palms up 攤手"},{"e":"🤝","k":"handshake 握手"},{"e":"🙏","k":"pray please 拜託 祈禱"},{"e":"✍️","k":"writing 寫字"},{"e":"💅","k":"nail polish 指甲油"},{"e":"🤳","k":"selfie 自拍"},{"e":"💪","k":"muscle 肌肉 加油"},{"e":"🦾","k":"mechanical arm 機械手"},{"e":"🦿","k":"mechanical leg 機械腿"},{"e":"🦵","k":"leg 腿"},{"e":"🦶","k":"foot 腳"},{"e":"👂","k":"ear 耳朵"},{"e":"❤️","k":"red heart 愛心 紅色"},{"e":"🧡","k":"orange heart 橘色愛心"},{"e":"💛","k":"yellow heart 黃色愛心"},{"e":"💚","k":"green heart 綠色愛心"},{"e":"💙","k":"blue heart 藍色愛心"},{"e":"💜","k":"purple heart 紫色愛心"},{"e":"🖤","k":"black heart 黑色愛心"},{"e":"🤍","k":"white heart 白色愛心"},{"e":"🤎","k":"brown heart 棕色愛心"},{"e":"💔","k":"broken heart 心碎"},{"e":"❣️","k":"heart exclamation 愛心驚嘆"},{"e":"💕","k":"two hearts 雙愛心"},{"e":"💞","k":"revolving hearts 旋轉愛心"},{"e":"💓","k":"beating heart 愛心跳動"},{"e":"💗","k":"growing heart 愛心放大"},{"e":"💖","k":"sparkling heart 閃亮愛心"},{"e":"💘","k":"cupid arrow 丘比特之箭"},{"e":"💝","k":"heart gift 禮物愛心"},{"e":"💟","k":"heart decoration 愛心"},{"e":"♥️","k":"suit heart 愛心"},{"e":"💌","k":"love letter 情書"},{"e":"😻","k":"heart eyes cat 愛心貓"},{"e":"💑","k":"couple heart 情侶"},{"e":"💏","k":"kiss couple 接吻"},{"e":"🎉","k":"party popper 慶祝 派對"},{"e":"🎊","k":"confetti 彩紙"},{"e":"🎂","k":"cake 蛋糕 生日"},{"e":"🎁","k":"gift present 禮物"},{"e":"🎈","k":"balloon 氣球"},{"e":"🎆","k":"fireworks 煙火"},{"e":"🎇","k":"sparkler 仙女棒"},{"e":"✨","k":"sparkles 閃亮"},{"e":"⭐","k":"star 星星"},{"e":"🌟","k":"glowing star 閃亮星星"},{"e":"💫","k":"dizzy stars 星星"},{"e":"🎀","k":"ribbon 蝴蝶結"},{"e":"🎗️","k":"reminder ribbon 紀念緞帶"},{"e":"🏆","k":"trophy 獎盃"},{"e":"🥇","k":"gold medal 金牌"},{"e":"🥈","k":"silver medal 銀牌"},{"e":"🥉","k":"bronze medal 銅牌"},{"e":"🎖️","k":"military medal 勳章"},{"e":"👑","k":"crown 皇冠"},{"e":"💎","k":"diamond 鑽石"},{"e":"🥂","k":"clinking glasses 乾杯"},{"e":"🍾","k":"champagne 香檳"},{"e":"🎵","k":"music note 音符"},{"e":"🎶","k":"music notes 音符"},{"e":"🍎","k":"red apple 蘋果"},{"e":"🍊","k":"orange 柳橙"},{"e":"🍋","k":"lemon 檸檬"},{"e":"🍌","k":"banana 香蕉"},{"e":"🍉","k":"watermelon 西瓜"},{"e":"🍇","k":"grapes 葡萄"},{"e":"🍓","k":"strawberry 草莓"},{"e":"🫐","k":"blueberries 藍莓"},{"e":"🍈","k":"melon 哈密瓜"},{"e":"🍒","k":"cherries 櫻桃"},{"e":"🍑","k":"peach 桃子"},{"e":"🥭","k":"mango 芒果"},{"e":"🍍","k":"pineapple 鳳梨"},{"e":"🥝","k":"kiwi 奇異果"},{"e":"🥥","k":"coconut 椰子"},{"e":"🍅","k":"tomato 番茄"},{"e":"🥑","k":"avocado 酪梨"},{"e":"🍆","k":"eggplant 茄子"},{"e":"🌽","k":"corn 玉米"},{"e":"🥕","k":"carrot 紅蘿蔔"},{"e":"🍞","k":"bread 麵包"},{"e":"🥐","k":"croissant 可頌"},{"e":"🥖","k":"baguette 法國麵包"},{"e":"🥨","k":"pretzel 椒鹽脆餅"},{"e":"🧀","k":"cheese 起司"},{"e":"🍳","k":"egg fried 煎蛋"},{"e":"🥞","k":"pancakes 鬆餅"},{"e":"🥓","k":"bacon 培根"},{"e":"🥩","k":"steak 牛排"},{"e":"🍗","k":"chicken drumstick 雞腿"},{"e":"🍖","k":"meat bone 肉"},{"e":"🌭","k":"hotdog 熱狗"},{"e":"🍔","k":"hamburger 漢堡"},{"e":"🍟","k":"fries 薯條"},{"e":"🍕","k":"pizza 披薩"},{"e":"🌮","k":"taco 墨西哥捲餅"},{"e":"🌯","k":"burrito 墨西哥捲"},{"e":"🥗","k":"salad 沙拉"},{"e":"🍝","k":"spaghetti 義大利麵"},{"e":"🍜","k":"ramen 拉麵"},{"e":"🍱","k":"bento 便當"},{"e":"🍣","k":"sushi 壽司"},{"e":"🍤","k":"shrimp 炸蝦"},{"e":"🍙","k":"rice ball 飯糰"},{"e":"🍚","k":"rice 白飯"},{"e":"🍘","k":"rice cracker 仙貝"},{"e":"🍢","k":"oden 關東煮"},{"e":"🍡","k":"dango 糯米糰"},{"e":"🥟","k":"dumpling 餃子"},{"e":"🍦","k":"ice cream soft 霜淇淋"},{"e":"🍧","k":"shaved ice 剉冰"},{"e":"🍨","k":"ice cream 冰淇淋"},{"e":"🍩","k":"donut 甜甜圈"},{"e":"🍪","k":"cookie 餅乾"},{"e":"🎂","k":"birthday cake 生日蛋糕"},{"e":"🍰","k":"cake 蛋糕"},{"e":"🧁","k":"cupcake 杯子蛋糕"},{"e":"🥧","k":"pie 派"},{"e":"🍫","k":"chocolate 巧克力"},{"e":"🍬","k":"candy 糖果"},{"e":"🍭","k":"lollipop 棒棒糖"},{"e":"🍮","k":"pudding 布丁"},{"e":"🍯","k":"honey 蜂蜜"},{"e":"☕","k":"coffee 咖啡"},{"e":"🍵","k":"tea 茶"},{"e":"🧋","k":"bubble tea 珍珠奶茶"},{"e":"🍺","k":"beer 啤酒"},{"e":"🍻","k":"cheers beer 乾杯"},{"e":"🍷","k":"wine 紅酒"},{"e":"🍸","k":"cocktail 雞尾酒"},{"e":"🍹","k":"tropical 熱帶飲料"},{"e":"🥤","k":"cup drink 飲料"},{"e":"🐶","k":"dog face 小狗"},{"e":"🐱","k":"cat face 小貓"},{"e":"🐭","k":"mouse 老鼠"},{"e":"🐹","k":"hamster 倉鼠"},{"e":"🐰","k":"rabbit face 兔子"},{"e":"🦊","k":"fox 狐狸"},{"e":"🐻","k":"bear 熊"},{"e":"🐼","k":"panda 熊貓"},{"e":"🐨","k":"koala 無尾熊"},{"e":"🐯","k":"tiger 老虎"},{"e":"🦁","k":"lion 獅子"},{"e":"🐮","k":"cow 牛"},{"e":"🐷","k":"pig 豬"},{"e":"🐸","k":"frog 青蛙"},{"e":"🐵","k":"monkey face 猴子"},{"e":"🙈","k":"see no evil 猴子摀眼"},{"e":"🙉","k":"hear no evil 猴子摀耳"},{"e":"🙊","k":"speak no evil 猴子摀嘴"},{"e":"🐒","k":"monkey 猴子"},{"e":"🐔","k":"chicken 雞"},{"e":"🐧","k":"penguin 企鵝"},{"e":"🐦","k":"bird 鳥"},{"e":"🐤","k":"baby chick 小雞"},{"e":"🦆","k":"duck 鴨子"},{"e":"🦅","k":"eagle 老鷹"},{"e":"🦉","k":"owl 貓頭鷹"},{"e":"🦇","k":"bat 蝙蝠"},{"e":"🐺","k":"wolf 狼"},{"e":"🐗","k":"boar 野豬"},{"e":"🐴","k":"horse face 馬"},{"e":"🦄","k":"unicorn 獨角獸"},{"e":"🐝","k":"bee 蜜蜂"},{"e":"🐛","k":"bug 毛毛蟲"},{"e":"🦋","k":"butterfly 蝴蝶"},{"e":"🐌","k":"snail 蝸牛"},{"e":"🐞","k":"ladybug 瓢蟲"},{"e":"🐜","k":"ant 螞蟻"},{"e":"🕷️","k":"spider 蜘蛛"},{"e":"🐢","k":"turtle 烏龜"},{"e":"🐍","k":"snake 蛇"},{"e":"🐙","k":"octopus 章魚"},{"e":"🦑","k":"squid 魷魚"},{"e":"🦐","k":"shrimp 蝦"},{"e":"🐟","k":"fish 魚"},{"e":"🐬","k":"dolphin 海豚"},{"e":"🐳","k":"whale 鯨魚"},{"e":"🦈","k":"shark 鯊魚"},{"e":"⚽","k":"soccer 足球"},{"e":"🏀","k":"basketball 籃球"},{"e":"🏈","k":"football 美式足球"},{"e":"⚾","k":"baseball 棒球"},{"e":"🎾","k":"tennis 網球"},{"e":"🏐","k":"volleyball 排球"},{"e":"🎱","k":"billiards 撞球"},{"e":"🏓","k":"ping pong 桌球"},{"e":"🏸","k":"badminton 羽球"},{"e":"🎯","k":"dart 飛鏢 目標"},{"e":"🎲","k":"dice 骰子"},{"e":"🎮","k":"game 電動"},{"e":"🕹️","k":"joystick 搖桿"},{"e":"🎨","k":"palette 調色盤"},{"e":"🎬","k":"clapperboard 場記板"},{"e":"📷","k":"camera 相機"},{"e":"📹","k":"video camera 攝影機"},{"e":"🎥","k":"movie camera 電影"},{"e":"📺","k":"tv 電視"},{"e":"📱","k":"phone 手機"},{"e":"💻","k":"laptop 筆電"},{"e":"🖥️","k":"desktop 桌電"},{"e":"⌨️","k":"keyboard 鍵盤"},{"e":"🖱️","k":"mouse 滑鼠"},{"e":"💾","k":"floppy 磁碟片"},{"e":"💿","k":"cd CD"},{"e":"📀","k":"dvd DVD"},{"e":"🔋","k":"battery 電池"},{"e":"🔌","k":"plug 插頭"},{"e":"💡","k":"bulb 燈泡 想法"},{"e":"🔦","k":"flashlight 手電筒"},{"e":"🕯️","k":"candle 蠟燭"},{"e":"📚","k":"books 書本"},{"e":"📖","k":"open book 開書"},{"e":"📝","k":"memo 筆記"},{"e":"✏️","k":"pencil 鉛筆"},{"e":"✒️","k":"pen 鋼筆"},{"e":"📎","k":"paperclip 迴紋針"},{"e":"📌","k":"pushpin 圖釘"},{"e":"📍","k":"round pin 地點"},{"e":"🔑","k":"key 鑰匙"},{"e":"🔒","k":"lock 鎖"},{"e":"🔓","k":"unlock 開鎖"},{"e":"🔔","k":"bell 鈴鐺"},{"e":"🔕","k":"bell mute 靜音"},{"e":"⏰","k":"alarm 鬧鐘"},{"e":"⏳","k":"hourglass 沙漏"},{"e":"☀️","k":"sun 太陽"},{"e":"🌙","k":"moon 月亮"},{"e":"⭐","k":"star 星"},{"e":"🌈","k":"rainbow 彩虹"},{"e":"☁️","k":"cloud 雲"},{"e":"⛅","k":"cloud sun 多雲"},{"e":"🌧️","k":"rain 下雨"},{"e":"⛈️","k":"thunderstorm 雷雨"},{"e":"❄️","k":"snowflake 雪"},{"e":"🔥","k":"fire 火 讚"},{"e":"💧","k":"drop 水滴"},{"e":"🌊","k":"wave 海浪"},{"e":"🚀","k":"rocket 火箭"},{"e":"✈️","k":"airplane 飛機"},{"e":"🚗","k":"car 汽車"},{"e":"🏠","k":"house 房子"},{"e":"⛔","k":"no entry 禁止"},{"e":"✅","k":"check 打勾"},{"e":"❌","k":"cross 叉"},{"e":"❓","k":"question 問號"},{"e":"❗","k":"exclamation 驚嘆"},{"e":"💯","k":"hundred 100 滿分"},{"e":"🎵","k":"music note 音符"}];
const EMOJI_CATS=[{"id":"face","icon":"😀","title":"表情","start":0,"end":98},{"id":"hand","icon":"👋","title":"手勢","start":98,"end":138},{"id":"heart","icon":"❤️","title":"愛","start":138,"end":162},{"id":"celebrate","icon":"🎉","title":"慶祝","start":162,"end":186},{"id":"food","icon":"🍎","title":"食物","start":186,"end":258},{"id":"animal","icon":"🐶","title":"動物","start":258,"end":305},{"id":"object","icon":"⚽","title":"物品","start":305,"end":375}];
let emojiActiveCat = 'face';
let pendingImage = null;
let pendingImageSize = 0;

function renderEmojiGrid(filter){
  const grid = document.getElementById('emoji-grid');
  if(!grid) return;
  while(grid.firstChild) grid.removeChild(grid.firstChild);
  let items;
  if(filter && filter.trim().length > 0){
    const q = filter.toLowerCase();
    items = EMOJI_DATA.filter(x => x.k.toLowerCase().indexOf(q) !== -1 || x.e.indexOf(q) !== -1);
  } else {
    const cat = EMOJI_CATS.find(c => c.id === emojiActiveCat) || EMOJI_CATS[0];
    items = EMOJI_DATA.slice(cat.start, cat.end);
  }
  for(const it of items){
    const cell = document.createElement('div');
    cell.className = 'emoji-cell';
    cell.textContent = it.e;
    cell.title = it.k;
    cell.onclick = () => insertEmojiAtCursor(it.e);
    grid.appendChild(cell);
  }
}
function renderEmojiTabs(){
  const tabs = document.getElementById('emoji-tabs');
  if(!tabs) return;
  while(tabs.firstChild) tabs.removeChild(tabs.firstChild);
  for(const c of EMOJI_CATS){
    const t = document.createElement('span');
    t.className = 'tab' + (c.id === emojiActiveCat ? ' active' : '');
    t.textContent = c.icon;
    t.title = c.title;
    t.onclick = () => {
      emojiActiveCat = c.id;
      const srch = document.getElementById('emoji-search');
      if(srch) srch.value = '';
      renderEmojiTabs();
      renderEmojiGrid('');
    };
    tabs.appendChild(t);
  }
}
function insertEmojiAtCursor(emoji){
  const mi = document.getElementById('msg-input');
  if(!mi) return;
  const start = mi.selectionStart || mi.value.length;
  const end = mi.selectionEnd || mi.value.length;
  mi.value = mi.value.slice(0, start) + emoji + mi.value.slice(end);
  mi.focus();
  try { mi.setSelectionRange(start + emoji.length, start + emoji.length); } catch(e){}
}
function toggleEmojiPicker(){
  const p = document.getElementById('emoji-panel');
  const btn = document.getElementById('emoji-toggle');
  if(!p) return;
  if(p.style.display === 'none' || p.style.display === ''){
    p.style.display = 'block';
    if(btn) btn.classList.add('active');
    renderEmojiTabs();
    renderEmojiGrid('');
    const srch = document.getElementById('emoji-search');
    if(srch){ srch.value = ''; srch.focus(); }
  } else {
    p.style.display = 'none';
    if(btn) btn.classList.remove('active');
  }
}
document.addEventListener('click', (e) => {
  const p = document.getElementById('emoji-panel');
  const btn = document.getElementById('emoji-toggle');
  if(!p || p.style.display === 'none') return;
  if(p.contains(e.target) || (btn && btn.contains(e.target))) return;
  p.style.display = 'none';
  if(btn) btn.classList.remove('active');
});
(function bindEmojiSearch(){
  const wait = setInterval(() => {
    const s = document.getElementById('emoji-search');
    if(!s) return;
    clearInterval(wait);
    s.oninput = () => renderEmojiGrid(s.value);
  }, 100);
})();

// ─── 圖片上傳 ──────────────────────────────────────────────
const IMG_MAX_BYTES = 800 * 1024;
const IMG_MAX_DIM = 1280;

async function handleImageFile(file){
  if(!file) return;
  if(['image/jpeg','image/png','image/webp'].indexOf(file.type) === -1){
    alert('只支援 JPG / PNG / WebP');
    return;
  }
  try {
    const dataUrl = await new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.onerror = () => rej(r.error);
      r.readAsDataURL(file);
    });
    const img = await new Promise((res, rej) => {
      const im = new Image();
      im.onload = () => res(im);
      im.onerror = () => rej(new Error('load failed'));
      im.src = dataUrl;
    });
    let w = img.width, h = img.height;
    if(w > IMG_MAX_DIM || h > IMG_MAX_DIM){
      if(w > h){ h = Math.round(h * IMG_MAX_DIM / w); w = IMG_MAX_DIM; }
      else { w = Math.round(w * IMG_MAX_DIM / h); h = IMG_MAX_DIM; }
    }
    const canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    canvas.getContext('2d').drawImage(img, 0, 0, w, h);
    const compressed = canvas.toDataURL('image/jpeg', 0.7);
    const sizeBytes = Math.ceil(compressed.length * 3 / 4);
    if(sizeBytes > IMG_MAX_BYTES){
      const again = canvas.toDataURL('image/jpeg', 0.5);
      const sz2 = Math.ceil(again.length * 3 / 4);
      if(sz2 > IMG_MAX_BYTES){ alert('圖片太大(壓縮後仍超過 800 KB),請選較小的圖片'); return; }
      pendingImage = again; pendingImageSize = sz2;
    } else {
      pendingImage = compressed; pendingImageSize = sizeBytes;
    }
    const prev = document.getElementById('img-preview');
    const thumb = document.getElementById('img-preview-thumb');
    const szEl = document.getElementById('img-preview-size');
    thumb.src = pendingImage;
    szEl.textContent = Math.round(pendingImageSize / 1024) + ' KB';
    prev.style.display = 'flex';
  } catch(e){
    alert('處理圖片失敗' + ': ' + e.message);
    pendingImage = null;
  }
  const inp = document.getElementById('img-file-input');
  if(inp) inp.value = '';
}
function clearImagePreview(){
  pendingImage = null;
  pendingImageSize = 0;
  const prev = document.getElementById('img-preview');
  if(prev) prev.style.display = 'none';
}
(function bindImgInput(){
  const wait = setInterval(() => {
    const f = document.getElementById('img-file-input');
    if(!f) return;
    clearInterval(wait);
    f.onchange = (e) => handleImageFile(e.target.files && e.target.files[0]);
  }, 100);
})();

// ─── Fullscreen Viewer ─────────────────────────────────────
let viewerZoom = 1;
let viewerPanX = 0, viewerPanY = 0;
let viewerCurrentMsgEl = null;
let viewerDevtoolsCheckTimer = null;
let msgLiveCheckTimer = null;

function openImageViewer(dataUrl, msgEl){
  const v = document.getElementById('img-viewer');
  const content = document.getElementById('img-viewer-content');
  const warn = document.getElementById('img-viewer-warn');
  if(!v || !content) return;
  viewerCurrentMsgEl = msgEl;
  viewerZoom = 1; viewerPanX = 0; viewerPanY = 0;
  content.style.backgroundImage = "url('" + dataUrl + "')";
  applyViewerTransform();
  v.style.display = 'flex';
  if(warn){ warn.textContent = '⚠ 請勿截圖或轉傳 · 訊息焚毀後圖片自動消失'; warn.style.display = 'block'; }
  setTimeout(() => { if(warn) warn.style.display = 'none'; }, 3500);
  startDevtoolsCheck();
  startMsgLiveCheck();
}
function closeImageViewer(){
  const v = document.getElementById('img-viewer');
  const content = document.getElementById('img-viewer-content');
  if(v) v.style.display = 'none';
  if(content) content.style.backgroundImage = '';
  viewerCurrentMsgEl = null;
  stopDevtoolsCheck();
  stopMsgLiveCheck();
}
function applyViewerTransform(){
  const content = document.getElementById('img-viewer-content');
  const zoomText = document.getElementById('img-viewer-zoom');
  if(!content) return;
  content.style.transform = 'translate(' + viewerPanX + 'px,' + viewerPanY + 'px) scale(' + viewerZoom + ')';
  if(zoomText) zoomText.textContent = Math.round(viewerZoom * 100) + '%';
}
function viewerZoomIn(){ viewerZoom = Math.min(5, viewerZoom + 0.25); applyViewerTransform(); }
function viewerZoomOut(){ viewerZoom = Math.max(0.25, viewerZoom - 0.25); if(viewerZoom <= 1){ viewerPanX = 0; viewerPanY = 0; } applyViewerTransform(); }
function viewerReset(){ viewerZoom = 1; viewerPanX = 0; viewerPanY = 0; applyViewerTransform(); }

(function bindViewer(){
  const wait = setInterval(() => {
    const stage = document.getElementById('img-viewer-stage');
    if(!stage) return;
    clearInterval(wait);
    let dragging = false, lastX = 0, lastY = 0;
    stage.addEventListener('mousedown', (e) => {
      if(viewerZoom <= 1) return;
      dragging = true; lastX = e.clientX; lastY = e.clientY;
      stage.classList.add('dragging');
    });
    document.addEventListener('mousemove', (e) => {
      if(!dragging) return;
      viewerPanX += e.clientX - lastX;
      viewerPanY += e.clientY - lastY;
      lastX = e.clientX; lastY = e.clientY;
      applyViewerTransform();
    });
    document.addEventListener('mouseup', () => {
      dragging = false;
      const st = document.getElementById('img-viewer-stage');
      if(st) st.classList.remove('dragging');
    });
    stage.addEventListener('wheel', (e) => {
      e.preventDefault();
      if(e.deltaY < 0) viewerZoomIn(); else viewerZoomOut();
    }, {passive: false});
    stage.addEventListener('click', (e) => {
      if(e.target === stage) closeImageViewer();
    });
    document.addEventListener('keydown', (e) => {
      const v = document.getElementById('img-viewer');
      if(v && v.style.display !== 'none' && e.key === 'Escape') closeImageViewer();
    });
    stage.addEventListener('contextmenu', (e) => e.preventDefault());
  }, 100);
})();

function startDevtoolsCheck(){
  stopDevtoolsCheck();
  viewerDevtoolsCheckTimer = setInterval(() => {
    const threshold = 160;
    if(window.outerWidth - window.innerWidth > threshold || window.outerHeight - window.innerHeight > threshold){
      const warn = document.getElementById('img-viewer-warn');
      if(warn){ warn.textContent = '⚠ 偵測到開發者工具 · 請勿擷取內容'; warn.style.display = 'block'; }
    }
  }, 800);
}
function stopDevtoolsCheck(){ if(viewerDevtoolsCheckTimer){ clearInterval(viewerDevtoolsCheckTimer); viewerDevtoolsCheckTimer = null; } }
function startMsgLiveCheck(){
  stopMsgLiveCheck();
  msgLiveCheckTimer = setInterval(() => {
    if(!viewerCurrentMsgEl || !document.body.contains(viewerCurrentMsgEl)) closeImageViewer();
  }, 500);
}
function stopMsgLiveCheck(){ if(msgLiveCheckTimer){ clearInterval(msgLiveCheckTimer); msgLiveCheckTimer = null; } }

// 動態注入 emoji + 圖片按鈕到 input-area 左邊(在 clean-toggle 右邊、msg-input 前)
(function injectInputButtons(){
  const wait = setInterval(() => {
    const inp = document.getElementById('input-area');
    const mi = document.getElementById('msg-input');
    if(!inp || !mi || document.getElementById('emoji-toggle')){ if(document.getElementById('emoji-toggle')) clearInterval(wait); return; }
    clearInterval(wait);
    const emojiBtn = document.createElement('button');
    emojiBtn.id = 'emoji-toggle';
    emojiBtn.className = 'clean-btn';
    emojiBtn.title = 'Emoji';
    emojiBtn.textContent = '😀';
    emojiBtn.onclick = (e) => { e.stopPropagation(); toggleEmojiPicker(); };
    inp.insertBefore(emojiBtn, mi);
    const imgBtn = document.createElement('button');
    imgBtn.id = 'img-attach';
    imgBtn.className = 'clean-btn';
    imgBtn.title = '附加圖片';
    imgBtn.textContent = '📎';
    imgBtn.onclick = () => document.getElementById('img-file-input').click();
    inp.insertBefore(imgBtn, mi);
  }, 200);
})();


// ─── E2E 加密 (AES-256-GCM, key 派生自房間密碼) ───
// 優先 WebCrypto;不可用時 fallback 到純 JS (insecure context 保護)
const HAS_SUBTLE = typeof crypto !== 'undefined' && crypto.subtle && typeof crypto.subtle.importKey === 'function';

function b64encode(buf){
  let s = ''; const b = new Uint8Array(buf);
  for(let i=0;i<b.length;i++) s += String.fromCharCode(b[i]);
  return btoa(s);
}
function b64decode(str){
  const s = atob(str); const b = new Uint8Array(s.length);
  for(let i=0;i<s.length;i++) b[i] = s.charCodeAt(i);
  return b;
}
const _K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
function _sha256(msg){
  const len=msg.length, bits=len*8, padLen=((len+9+63)>>6)<<6;
  const buf=new Uint8Array(padLen); buf.set(msg); buf[len]=0x80;
  const dv=new DataView(buf.buffer);
  dv.setUint32(padLen-4, bits>>>0, false);
  dv.setUint32(padLen-8, Math.floor(bits/0x100000000), false);
  let h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
  const W=new Uint32Array(64);
  for(let i=0;i<padLen;i+=64){
    for(let t=0;t<16;t++) W[t]=dv.getUint32(i+t*4,false);
    for(let t=16;t<64;t++){
      const x=W[t-15],y=W[t-2];
      const s0=((x>>>7)|(x<<25))^((x>>>18)|(x<<14))^(x>>>3);
      const s1=((y>>>17)|(y<<15))^((y>>>19)|(y<<13))^(y>>>10);
      W[t]=(W[t-16]+s0+W[t-7]+s1)>>>0;
    }
    let a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;
    for(let t=0;t<64;t++){
      const S1=((e>>>6)|(e<<26))^((e>>>11)|(e<<21))^((e>>>25)|(e<<7));
      const ch=(e&f)^(~e&g);
      const T1=(h+S1+ch+_K[t]+W[t])>>>0;
      const S0=((a>>>2)|(a<<30))^((a>>>13)|(a<<19))^((a>>>22)|(a<<10));
      const mj=(a&b)^(a&c)^(b&c);
      const T2=(S0+mj)>>>0;
      h=g;g=f;f=e;e=(d+T1)>>>0;d=c;c=b;b=a;a=(T1+T2)>>>0;
    }
    h0=(h0+a)>>>0;h1=(h1+b)>>>0;h2=(h2+c)>>>0;h3=(h3+d)>>>0;h4=(h4+e)>>>0;h5=(h5+f)>>>0;h6=(h6+g)>>>0;h7=(h7+h)>>>0;
  }
  const out=new Uint8Array(32),odv=new DataView(out.buffer);
  odv.setUint32(0,h0,false);odv.setUint32(4,h1,false);odv.setUint32(8,h2,false);odv.setUint32(12,h3,false);
  odv.setUint32(16,h4,false);odv.setUint32(20,h5,false);odv.setUint32(24,h6,false);odv.setUint32(28,h7,false);
  return out;
}
function _hmac(key,msg){
  let k=key; if(k.length>64) k=_sha256(k);
  const k0=new Uint8Array(64); k0.set(k);
  const ipad=new Uint8Array(64),opad=new Uint8Array(64);
  for(let i=0;i<64;i++){ipad[i]=k0[i]^0x36;opad[i]=k0[i]^0x5c;}
  const inner=new Uint8Array(64+msg.length); inner.set(ipad); inner.set(msg,64);
  const ih=_sha256(inner);
  const outer=new Uint8Array(96); outer.set(opad); outer.set(ih,64);
  return _sha256(outer);
}
function _pbkdf2(pwd,salt,iter,dkLen){
  const blocks=Math.ceil(dkLen/32), out=new Uint8Array(blocks*32);
  for(let i=1;i<=blocks;i++){
    const sI=new Uint8Array(salt.length+4); sI.set(salt);
    new DataView(sI.buffer).setUint32(salt.length,i,false);
    let U=_hmac(pwd,sI); const T=new Uint8Array(U);
    for(let j=1;j<iter;j++){U=_hmac(pwd,U); for(let k=0;k<32;k++) T[k]^=U[k];}
    out.set(T,(i-1)*32);
  }
  return out.slice(0,dkLen);
}
const _SBOX=new Uint8Array([99,124,119,123,242,107,111,197,48,1,103,43,254,215,171,118,202,130,201,125,250,89,71,240,173,212,162,175,156,164,114,192,183,253,147,38,54,63,247,204,52,165,229,241,113,216,49,21,4,199,35,195,24,150,5,154,7,18,128,226,235,39,178,117,9,131,44,26,27,110,90,160,82,59,214,179,41,227,47,132,83,209,0,237,32,252,177,91,106,203,190,57,74,76,88,207,208,239,170,251,67,77,51,133,69,249,2,127,80,60,159,168,81,163,64,143,146,157,56,245,188,182,218,33,16,255,243,210,205,12,19,236,95,151,68,23,196,167,126,61,100,93,25,115,96,129,79,220,34,42,144,136,70,238,184,20,222,94,11,219,224,50,58,10,73,6,36,92,194,211,172,98,145,149,228,121,231,200,55,109,141,213,78,169,108,86,244,234,101,122,174,8,186,120,37,46,28,166,180,198,232,221,116,31,75,189,139,138,112,62,181,102,72,3,246,14,97,53,87,185,134,193,29,158,225,248,152,17,105,217,142,148,155,30,135,233,206,85,40,223,140,161,137,13,191,230,66,104,65,153,45,15,176,84,187,22]);
const _RCON=new Uint8Array([0,1,2,4,8,16,32,64,128,27,54]);
function _xt(b){return((b<<1)^(((b>>7)&1)*0x1b))&0xff;}
function _aesExp(key){
  const Nk=8,Nr=14, w=new Uint8Array(240), temp=new Uint8Array(4);
  w.set(key);
  for(let i=Nk;i<4*(Nr+1);i++){
    temp[0]=w[(i-1)*4];temp[1]=w[(i-1)*4+1];temp[2]=w[(i-1)*4+2];temp[3]=w[(i-1)*4+3];
    if(i%Nk===0){
      const t=temp[0];temp[0]=temp[1];temp[1]=temp[2];temp[2]=temp[3];temp[3]=t;
      temp[0]=_SBOX[temp[0]];temp[1]=_SBOX[temp[1]];temp[2]=_SBOX[temp[2]];temp[3]=_SBOX[temp[3]];
      temp[0]^=_RCON[i/Nk];
    } else if(i%Nk===4){
      temp[0]=_SBOX[temp[0]];temp[1]=_SBOX[temp[1]];temp[2]=_SBOX[temp[2]];temp[3]=_SBOX[temp[3]];
    }
    w[i*4]=w[(i-Nk)*4]^temp[0]; w[i*4+1]=w[(i-Nk)*4+1]^temp[1];
    w[i*4+2]=w[(i-Nk)*4+2]^temp[2]; w[i*4+3]=w[(i-Nk)*4+3]^temp[3];
  }
  return w;
}
function _aesEnc(block,w){
  const Nr=14, s=new Uint8Array(block);
  for(let i=0;i<16;i++) s[i]^=w[i];
  for(let r=1;r<Nr;r++){
    for(let i=0;i<16;i++) s[i]=_SBOX[s[i]];
    let t;
    t=s[1];s[1]=s[5];s[5]=s[9];s[9]=s[13];s[13]=t;
    t=s[2];s[2]=s[10];s[10]=t;t=s[6];s[6]=s[14];s[14]=t;
    t=s[15];s[15]=s[11];s[11]=s[7];s[7]=s[3];s[3]=t;
    for(let c=0;c<4;c++){
      const a0=s[c*4],a1=s[c*4+1],a2=s[c*4+2],a3=s[c*4+3];
      const all=a0^a1^a2^a3;
      s[c*4]^=all^_xt(a0^a1); s[c*4+1]^=all^_xt(a1^a2);
      s[c*4+2]^=all^_xt(a2^a3); s[c*4+3]^=all^_xt(a3^a0);
    }
    for(let i=0;i<16;i++) s[i]^=w[r*16+i];
  }
  for(let i=0;i<16;i++) s[i]=_SBOX[s[i]];
  let t;
  t=s[1];s[1]=s[5];s[5]=s[9];s[9]=s[13];s[13]=t;
  t=s[2];s[2]=s[10];s[10]=t;t=s[6];s[6]=s[14];s[14]=t;
  t=s[15];s[15]=s[11];s[11]=s[7];s[7]=s[3];s[3]=t;
  for(let i=0;i<16;i++) s[i]^=w[Nr*16+i];
  return s;
}
function _gmul(X,Y){
  const Z=new Uint8Array(16),V=new Uint8Array(Y);
  for(let i=0;i<128;i++){
    if((X[i>>3]>>(7-(i&7)))&1){for(let j=0;j<16;j++) Z[j]^=V[j];}
    const lsb=V[15]&1;
    for(let j=15;j>0;j--) V[j]=(V[j]>>>1)|((V[j-1]&1)<<7);
    V[0]>>>=1; if(lsb) V[0]^=0xe1;
  }
  return Z;
}
function _ghash(H,data){
  const Y=new Uint8Array(16);
  for(let i=0;i<data.length;i+=16){
    const blk=new Uint8Array(16); blk.set(data.slice(i,i+16));
    for(let j=0;j<16;j++) Y[j]^=blk[j];
    Y.set(_gmul(Y,H));
  }
  return Y;
}
function _gcmEnc(key,iv,plain){
  const w=_aesExp(key), H=_aesEnc(new Uint8Array(16),w);
  const J0=new Uint8Array(16); J0.set(iv); J0[15]=1;
  const ct=new Uint8Array(plain.length), ctr=new Uint8Array(J0);
  for(let i=0;i<plain.length;i+=16){
    for(let j=15;j>=12;j--){ctr[j]=(ctr[j]+1)&0xff; if(ctr[j]!==0) break;}
    const ks=_aesEnc(ctr,w);
    const bl=Math.min(16,plain.length-i);
    for(let j=0;j<bl;j++) ct[i+j]=plain[i+j]^ks[j];
  }
  const ctPad=ct.length%16===0?0:16-(ct.length%16);
  const gIn=new Uint8Array(ct.length+ctPad+16);
  gIn.set(ct);
  new DataView(gIn.buffer).setUint32(gIn.length-4, ct.length*8, false);
  const S=_ghash(H,gIn);
  const ekJ0=_aesEnc(J0,w), tag=new Uint8Array(16);
  for(let i=0;i<16;i++) tag[i]=S[i]^ekJ0[i];
  const out=new Uint8Array(ct.length+16);
  out.set(ct); out.set(tag,ct.length);
  return out;
}
function _gcmDec(key,iv,combined){
  if(combined.length<16) throw new Error('ciphertext too short');
  const ct=combined.slice(0,combined.length-16), tag=combined.slice(combined.length-16);
  const w=_aesExp(key), H=_aesEnc(new Uint8Array(16),w);
  const J0=new Uint8Array(16); J0.set(iv); J0[15]=1;
  const ctPad=ct.length%16===0?0:16-(ct.length%16);
  const gIn=new Uint8Array(ct.length+ctPad+16);
  gIn.set(ct);
  new DataView(gIn.buffer).setUint32(gIn.length-4, ct.length*8, false);
  const S=_ghash(H,gIn);
  const ekJ0=_aesEnc(J0,w);
  let diff=0;
  for(let i=0;i<16;i++) diff|=(S[i]^ekJ0[i])^tag[i];
  if(diff!==0) throw new Error('Auth tag mismatch');
  const pt=new Uint8Array(ct.length), ctr=new Uint8Array(J0);
  for(let i=0;i<ct.length;i+=16){
    for(let j=15;j>=12;j--){ctr[j]=(ctr[j]+1)&0xff; if(ctr[j]!==0) break;}
    const ks=_aesEnc(ctr,w);
    const bl=Math.min(16,ct.length-i);
    for(let j=0;j<bl;j++) pt[i+j]=ct[i+j]^ks[j];
  }
  return pt;
}
function _randBytes(n){
  if(typeof crypto!=='undefined' && crypto.getRandomValues){
    const b=new Uint8Array(n); crypto.getRandomValues(b); return b;
  }
  const b=new Uint8Array(n);
  for(let i=0;i<n;i++) b[i]=Math.floor(Math.random()*256);
  return b;
}

async function deriveKey(password, salt){
  const enc = new TextEncoder();
  if(HAS_SUBTLE){
    const baseKey = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey(
      { name:'PBKDF2', salt: enc.encode(salt), iterations: 200000, hash: 'SHA-256' },
      baseKey, { name:'AES-GCM', length: 256 }, false, ['encrypt','decrypt']
    );
  }
  return _pbkdf2(enc.encode(password), enc.encode(salt), 50000, 32);
}
async function encryptText(plaintext){
  if(!cryptoKey) throw new Error('no key');
  const iv = _randBytes(12);
  const ptBytes = new TextEncoder().encode(plaintext);
  let ctBuf;
  if(HAS_SUBTLE){
    ctBuf = new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM', iv}, cryptoKey, ptBytes));
  } else {
    ctBuf = _gcmEnc(cryptoKey, iv, ptBytes);
  }
  return { ct: b64encode(ctBuf), iv: b64encode(iv) };
}
async function decryptText(payload){
  if(!cryptoKey || !payload || !payload.ct || !payload.iv) throw new Error('bad payload');
  const ctBytes = b64decode(payload.ct);
  const ivBytes = b64decode(payload.iv);
  let pt;
  if(HAS_SUBTLE){
    pt = await crypto.subtle.decrypt({name:'AES-GCM', iv: ivBytes}, cryptoKey, ctBytes);
  } else {
    pt = _gcmDec(cryptoKey, ivBytes, ctBytes);
  }
  return new TextDecoder().decode(pt);
}

function ensureAudioCtx() {
  if (!audioCtx) { try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e){} }
  if (audioCtx && audioCtx.state === 'suspended') { try { audioCtx.resume(); } catch(e){} }
  return audioCtx;
}
function playNotify() {
  if (!soundEnabled) return;
  const ctx = ensureAudioCtx(); if (!ctx) return;
  const now = ctx.currentTime;
  function tone(f, s, d, v) { try {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type='sine'; o.frequency.value=f;
    g.gain.setValueAtTime(0, now+s);
    g.gain.linearRampToValueAtTime(v, now+s+0.008);
    g.gain.exponentialRampToValueAtTime(0.001, now+s+d);
    o.connect(g); g.connect(ctx.destination);
    o.start(now+s); o.stop(now+s+d+0.02);
  } catch(e){} }
  tone(784,0,0.22,0.14); tone(1568,0,0.22,0.035); tone(2352,0,0.22,0.015);
  tone(1047,0.09,0.40,0.16); tone(2094,0.09,0.40,0.04); tone(3141,0.09,0.40,0.017);
}
function toggleSound() {
  soundEnabled = !soundEnabled;
  const btn = document.getElementById('sound-btn');
  if (btn) btn.textContent = soundEnabled ? '🔔' : '🔕';
  if (soundEnabled) { ensureAudioCtx(); playNotify(); }
}
function updateTitle() {
  document.title = unreadCount > 0 ? '(' + unreadCount + ') ' + BASE_TITLE : BASE_TITLE;
  if (vscodeApi) { try { vscodeApi.postMessage({type:'unread', count: unreadCount}); } catch(e){} }
}

function authenticate() {
  const name = document.getElementById('nick-input').value.trim();
  const pwd = document.getElementById('pwd-input').value;
  const err = document.getElementById('auth-err');
  if (!name) { err.textContent = '❌ 請輸入名字'; return; }
  if (!pwd) { err.textContent = '❌ 請輸入密碼'; return; }
  ensureAudioCtx();

  fetch(SERVER + '/auth', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({roomId: ROOM_ID_FROM_URL, password: pwd, nickname: name})
  })
  .then(r => r.json()).then(async data => {
    if (data.ok) {
      try {
        cryptoKey = await deriveKey(pwd, 'burnerchat-v1:' + (ROOM_ID_FROM_URL || 'default'));
      } catch(e){
        err.textContent = '❌ 加密初始化失敗:' + (e.message || e);
        return;
      }
      authToken = data.token;
      nick = data.nick;
      clientId = data.clientId;
      sinceSeq = data.since || 0;
      if (typeof data.burnDuration === 'number') {
        burnDuration = data.burnDuration;
        const bs = document.getElementById('burn-sec');
        if (bs) bs.value = burnDuration;
      }
      // 初始化 roster
      roster = Array.isArray(data.nicks) ? data.nicks.slice() : [];
      rosterExpanded = false;
      renderRoster();
      // 預設遮罩(還沒 focus 輸入框)
      updateChatVisibility();
      // 啟動 heartbeat
      startHeartbeat();
      document.getElementById('me-label').textContent = '@' + nick;
      document.getElementById('auth-overlay').style.display = 'none';
      ['header','roster','sys-log','burn-bar','messages','input-area'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = (id === 'messages' || id === 'burn-bar' || id === 'roster') ? 'flex' : '';
        // sys-log 預設隱藏直到有第一則系統訊息(由 renderSysLog 控制)
      });
      renderSysLog();
      onConnected();
      startPolling();
    } else {
      err.textContent = '❌ ' + (data.error || '認證失敗');
      setTimeout(()=>err.textContent='', 2500);
    }
  }).catch(() => document.getElementById('auth-err').textContent = '❌ 無法連線');
}

function onConnected() {
  const mi = document.getElementById('msg-input');
  const s = document.getElementById('status');
  s.textContent = '●  已連線 🔒'; s.style.color = '#00ff88';
  s.title = '訊息使用 AES-256-GCM 端對端加密 + HTTP long polling';
  addSysMsg('🔥 已加入焚模式聊天室 (🔒 端對端加密)');
  if (mi) { mi.disabled = false; mi.placeholder = '輸入訊息... (Enter 發送)'; mi.focus(); }
}

function onDisconnected(reason) {
  const mi = document.getElementById('msg-input');
  const s = document.getElementById('status');
  if (s) { s.textContent = '●  已斷線'; s.style.color = '#ff4500'; }
  addSysMsg('🔥 ' + (reason || '連線已關閉'));
  if (mi) { mi.disabled = true; mi.placeholder = '已斷線'; }
}

// ─── Long polling loop ──────────────────────────────────────────
async function startPolling() {
  if (polling) return;
  polling = true;
  let backoff = 0;
  while (polling) {
    pollAbortCtrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    try {
      const url = SERVER + '/poll?token=' + encodeURIComponent(authToken) + '&since=' + sinceSeq;
      const opts = pollAbortCtrl ? { signal: pollAbortCtrl.signal } : {};
      const r = await fetch(url, opts);
      if (r.status === 401 || r.status === 404) {
        polling = false;
        resetToLogin('連線逾時或已被管理員移除,請重新登入');
        return;
      }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json();
      backoff = 0;
      if (d.events && d.events.length > 0) {
        for (const ev of d.events) {
          await handleEvent(ev);
        }
        sinceSeq = d.nextSince;
      } else if (typeof d.nextSince === 'number') {
        sinceSeq = d.nextSince;
      }
    } catch(e) {
      if (e.name === 'AbortError') break;
      backoff = Math.min(10000, (backoff || 500) * 2);
      await new Promise(r => setTimeout(r, backoff));
    }
  }
}

function stopPolling() {
  polling = false;
  if (pollAbortCtrl) { try { pollAbortCtrl.abort(); } catch(e){} }
}

async function handleEvent(d) {
  if (d.type === 'chat') {
    let text = '', image = null;
    try {
      const raw = await decryptText(d.encrypted);
      if (raw && raw.length > 0 && raw.charAt(0) === '{') {
        try { const obj = JSON.parse(raw); text = obj.text || ''; image = obj.image || null; }
        catch(e){ text = raw; }
      } else { text = raw; }
    } catch(err){ text = '⚠ [無法解密 — 密碼不一致或訊息毀損]'; }
    addChatMsg(d.sender, text, d.sender === nick, d.msgId, d.expectedReaders, image);
  }
  else if (d.type === 'system') addSysMsg(d.text);
  else if (d.type === 'burnUpdate') {
    burnDuration = d.duration;
    const bs = document.getElementById('burn-sec');
    if (bs) bs.value = burnDuration;
    if (!d.silent) addSysMsg('⏱ ' + d.by + ' 設定訊息存活為 ' + (burnDuration === 0 ? '永久' : burnDuration + ' 秒'));
  }
  else if (d.type === 'read') {
    markRead(d.msgId, d.reader);
    if (d.reader !== nick) tickMineReaders(d.msgId);
  }
  else if (d.type === 'presenceChange') {
    if (Array.isArray(d.nicks)) {
      roster = d.nicks.slice();
      renderRoster();
    }
    onPresenceChange(d.onlineCount);
  }
  else if (d.type === 'roomDeleted') {
    resetToLogin('此房間已被管理員刪除');
  }
}

async function apiSend(payload) {
  if (!authToken) return false;
  try {
    const r = await fetch(SERVER + '/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({ token: authToken }, payload))
    });
    return r.ok;
  } catch(e) { return false; }
}

// ─── 線上名單 ─────────────────────────────────────────────
function renderRoster() {
  const el = document.getElementById('roster');
  if (!el) return;
  const list = el.querySelector('.roster-list');
  const toggle = el.querySelector('.roster-toggle');
  const n = roster.length;
  const shouldCollapse = n > ROSTER_COLLAPSE_THRESHOLD && !rosterExpanded;
  if (shouldCollapse) {
    el.classList.add('collapsed');
    toggle.textContent = '▼ 展開 ' + n + ' 人';
  } else {
    el.classList.remove('collapsed');
    toggle.textContent = n > ROSTER_COLLAPSE_THRESHOLD ? '▲ 收合' : '👥';
    list.textContent = '線上 (' + n + '):' + roster.join(', ');
  }
}
function toggleRoster() {
  rosterExpanded = !rosterExpanded;
  renderRoster();
}

// ─── 系統訊息獨立區 ──────────────────────────────────────────────
function addSysEntry(text) {
  sysMsgs.push(text);
  if (sysMsgs.length > MAX_SYS_MSGS) sysMsgs.shift();
  renderSysLog();
}
function renderSysLog() {
  const el = document.getElementById('sys-log');
  if (!el) return;
  const last = el.querySelector('.sys-last');
  const full = el.querySelector('.sys-full');
  const toggle = el.querySelector('.sys-toggle');
  const n = sysMsgs.length;
  if (n === 0) { el.style.display = 'none'; return; }
  el.style.display = '';
  last.textContent = '⚙️ ' + sysMsgs[n - 1];
  while (full.firstChild) full.removeChild(full.firstChild);
  for (const m of sysMsgs) {
    const line = document.createElement('div');
    line.className = 'sys-line';
    line.textContent = '⚙️ ' + m;
    full.appendChild(line);
  }
  if (n === 1) {
    toggle.textContent = '';
    toggle.style.display = 'none';
    el.classList.add('collapsed');
  } else {
    toggle.style.display = '';
    toggle.textContent = sysExpanded ? '▲ 收合' : ('▼ 展開 ' + n + ' 則');
    if (sysExpanded) el.classList.remove('collapsed');
    else el.classList.add('collapsed');
  }
}
function toggleSysLog() {
  sysExpanded = !sysExpanded;
  renderSysLog();
}

// 乾淨版(本地狀態):隱藏 header/notice/roster/sys-log/burn-bar,只保留訊息區與輸入列
function toggleCleanMode() {
  cleanMode = !cleanMode;
  const btn = document.getElementById('clean-toggle');
  const input = document.getElementById('msg-input');
  if (cleanMode) {
    document.body.classList.add('clean-mode');
    if (btn) btn.classList.add('active');
    if (input) {
      input.dataset.originalPlaceholder = input.placeholder || '';
      input.placeholder = '';
    }
  } else {
    document.body.classList.remove('clean-mode');
    if (btn) btn.classList.remove('active');
    if (input && input.dataset.originalPlaceholder !== undefined) {
      input.placeholder = input.dataset.originalPlaceholder;
    } else if (input) {
      input.placeholder = '輸入訊息...';
    }
  }
}

// ─── 聊天遮罩 ─────────────────────────────────────────────
function updateChatVisibility() {
  const msgsEl = document.getElementById('messages');
  if (!msgsEl) return;
  const visible = inputFocused && !document.hidden;
  if (visible) msgsEl.classList.remove('redacted');
  else msgsEl.classList.add('redacted');
}

// ─── Heartbeat ───────────────────────────────────────────
function startHeartbeat() {
  stopHeartbeat();
  heartbeatTimer = setInterval(() => { apiSend({ type: 'heartbeat' }); }, HEARTBEAT_INTERVAL);
}
function stopHeartbeat() {
  if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null; }
}

// ─── 重置登入 ─────────────────────────────────────────────
function resetToLogin(reason) {
  stopPolling();
  stopHeartbeat();
  authToken = null; nick = ''; clientId = null; cryptoKey = null;
  sinceSeq = 0;
  roster = []; rosterExpanded = false;
  sysMsgs.length = 0; sysExpanded = false;
  // 解除乾淨版(不然登入畫面被 clean-mode 蓋住)
  cleanMode = false;
  document.body.classList.remove('clean-mode');
  const cleanBtn = document.getElementById('clean-toggle');
  if (cleanBtn) cleanBtn.classList.remove('active');
  pendingBurn.clear();
  for (const k in msgReads) delete msgReads[k];
  for (const k in sentReads) delete sentReads[k];
  unreadCount = 0; updateTitle();
  const msgsEl = document.getElementById('messages');
  if (msgsEl) { msgsEl.innerHTML = ''; msgsEl.classList.remove('redacted'); msgsEl.style.display = 'none'; }
  const rosterEl = document.getElementById('roster');
  if (rosterEl) rosterEl.style.display = 'none';
  const sysLogEl = document.getElementById('sys-log');
  if (sysLogEl) sysLogEl.style.display = 'none';
  const burnBar = document.getElementById('burn-bar');
  if (burnBar) burnBar.style.display = 'none';
  const inputArea = document.getElementById('input-area');
  if (inputArea) inputArea.style.display = 'none';
  const authOverlay = document.getElementById('auth-overlay');
  if (authOverlay) authOverlay.style.display = 'flex';
  const err = document.getElementById('auth-err');
  if (err && reason) { err.textContent = '⚠ ' + reason; setTimeout(() => err.textContent = '', 4000); }
  const st = document.getElementById('status');
  if (st) { st.textContent = '●  連線中...'; st.style.color = ''; }
  const nickInput = document.getElementById('nick-input');
  if (nickInput) nickInput.focus();
}

function updateBurn() {
  const v = parseInt(document.getElementById('burn-sec').value);
  if (isNaN(v) || v < 0) return;
  apiSend({type: 'setBurn', duration: Math.min(3600, v)});
}

function scheduleBurn(el, extraDelay) {
  if (burnDuration <= 0) return;
  const cd = document.createElement('div');
  cd.className = 'countdown'; el.appendChild(cd);
  let r = burnDuration + (extraDelay || 0); cd.textContent = '🔥 ' + r + 's';
  const iv = setInterval(() => {
    r--;
    if (r <= 2) el.classList.add('burning');
    if (r <= 0) {
      clearInterval(iv);
      el.style.opacity = '0'; el.style.transform = 'translateX(25px) scale(.9)';
      setTimeout(() => el.remove(), 700); return;
    }
    cd.textContent = '🔥 ' + r + 's';
  }, 1000);
}

function markRead(msgId, reader) {
  if (!msgId || !reader) return;
  if (!msgReads[msgId]) msgReads[msgId] = [];
  if (msgReads[msgId].indexOf(reader) === -1) msgReads[msgId].push(reader);
  updateReadIndicator(msgId);
}
function updateReadIndicator(msgId) {
  const el = document.querySelector('[data-msg-id="' + msgId + '"]'); if (!el) return;
  const rs = msgReads[msgId] || []; if (rs.length === 0) return;
  let ind = el.querySelector('.readby');
  if (!ind) {
    ind = document.createElement('div'); ind.className = 'readby';
    const cd = el.querySelector('.countdown');
    if (cd) el.insertBefore(ind, cd); else el.appendChild(ind);
  }
  // 拆成兩個 span:.check(永遠可見) + .names(乾淨版隱藏)
  while (ind.firstChild) ind.removeChild(ind.firstChild);
  const checkSpan = document.createElement('span');
  checkSpan.className = 'check';
  checkSpan.textContent = '✓';
  const namesSpan = document.createElement('span');
  namesSpan.className = 'names';
  namesSpan.textContent = ' 已讀: ' + (rs.length <= 3 ? rs.join(', ') : rs.slice(0,3).join(', ') + ' +' + (rs.length-3));
  ind.appendChild(checkSpan);
  ind.appendChild(namesSpan);
}

function addChatMsg(sender, text, isMine, msgId, expectedReaders, image) {
  const msgs = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'msg ' + (isMine ? 'mine' : 'other');
  if (msgId) div.setAttribute('data-msg-id', msgId);
  const s = document.createElement('div'); s.className = 'sender'; s.textContent = sender; div.appendChild(s);
  if (text) {
    const t = document.createElement('div');
    const inner = document.createElement('span');
    inner.className = 'text-content';
    const maskLen = Math.min(30, Math.max(4, Math.ceil((text || '').length / 2) || 4));
    inner.setAttribute('data-mask', '█'.repeat(maskLen));
    inner.textContent = text;
    t.appendChild(inner);
    div.appendChild(t);
  }
  if (image) {
    const imgDiv = document.createElement('div');
    imgDiv.className = 'msg-image';
    imgDiv.style.backgroundImage = "url('" + image + "')";
    imgDiv.addEventListener('click', () => openImageViewer(image, div));
    imgDiv.addEventListener('contextmenu', (e) => e.preventDefault());
    div.appendChild(imgDiv);
  }
  msgs.appendChild(div); msgs.scrollTop = msgs.scrollHeight;

  // 倒數觸發邏輯:
  // - 自己的訊息:若沒人需要讀 (expectedReaders === 0) 立刻燒;否則等 read events 湊齊
  // - 別人的訊息:加 unread 標記,等我 focus 輸入框才燒
  if (isMine) {
    const need = Math.max(0, expectedReaders || 0);
    if (need === 0) {
      scheduleBurn(div);
    } else if (msgId) {
      pendingBurn.set(msgId, { el: div, isMine: true, readersNeeded: need, readersGot: 0 });
    }
  } else {
    div.classList.add('unread');
    if (msgId) pendingBurn.set(msgId, { el: div, isMine: false });
  }

  if (msgId && msgReads[msgId]) updateReadIndicator(msgId);
  if (!isMine) {
    playNotify();
    if (document.hidden) { unreadCount++; updateTitle(); }
  }
}

// focus 輸入框時觸發:所有當下未讀的別人訊息 → 標為已讀 + 開始倒數
function onUserRead() {
  // Batch scheduleBurn: oldest first, +0/+1/+2... seconds per message
  // Prevents mass simultaneous burn when multiple messages pile up
  let delay = 0;
  for (const [msgId, info] of pendingBurn) {
    if (info.isMine) continue;
    info.el.classList.remove('unread');
    scheduleBurn(info.el, delay);
    delay++;
    if (!sentReads[msgId]) {
      sentReads[msgId] = true;
      apiSend({type: 'read', msgId: msgId});
    }
    pendingBurn.delete(msgId);
  }
}

// 收到 read event:若是別人讀了我的訊息,湊齊需要的讀者人數就開始燒
function tickMineReaders(msgId) {
  const info = pendingBurn.get(msgId);
  if (!info || !info.isMine) return;
  info.readersGot++;
  if (info.readersGot >= info.readersNeeded) {
    scheduleBurn(info.el);
    pendingBurn.delete(msgId);
  }
}

// 有人離開 → 降低 readersNeeded,必要時觸發燒
function onPresenceChange(onlineCount) {
  const newNeeded = Math.max(0, onlineCount - 1);
  for (const [msgId, info] of pendingBurn) {
    if (!info.isMine) continue;
    if (newNeeded < info.readersNeeded) {
      info.readersNeeded = newNeeded;
      if (info.readersGot >= info.readersNeeded) {
        scheduleBurn(info.el);
        pendingBurn.delete(msgId);
      }
    }
  }
}
function addSysMsg(text) {
  // 系統訊息改進入獨立區 (#sys-log),不再插入 #messages
  addSysEntry(text);
}
async function sendMsg() {
  const i = document.getElementById('msg-input');
  const text = i.value.trim();
  if (!text && !pendingImage) return;
  if (!authToken) {
    addSysMsg('⚠ 尚未連線,無法發送');
    return;
  }
  const imgToSend = pendingImage;
  i.value = '';
  clearImagePreview();
  try {
    const payload = imgToSend ? JSON.stringify({text: text, image: imgToSend}) : text;
    const enc = await encryptText(payload);
    const ok = await apiSend({type: 'chat', encrypted: enc});
    if (!ok) {
      addSysMsg('⚠ 傳送失敗(網路不穩或圖片太大?)');
      i.value = text;
      if (imgToSend) { pendingImage = imgToSend; document.getElementById('img-preview').style.display = 'flex'; }
    }
  } catch(err){
    addSysMsg('⚠ 加密失敗:' + (err.message || err));
    i.value = text;
    if (imgToSend) { pendingImage = imgToSend; document.getElementById('img-preview').style.display = 'flex'; }
  }
}

document.addEventListener('visibilitychange', () => {
  if (!document.hidden && unreadCount > 0) { unreadCount = 0; updateTitle(); }
});
window.addEventListener('beforeunload', () => {
  if (!authToken) return;
  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([JSON.stringify({token: authToken, type: 'leave'})], {type: 'application/json'});
      navigator.sendBeacon(SERVER + '/send', blob);
    }
  } catch(e){}
  stopPolling();
  stopHeartbeat();
});
document.getElementById('msg-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') sendMsg(); });
document.getElementById('msg-input')?.addEventListener('focus', () => {
  inputFocused = true;
  updateChatVisibility();
  onUserRead();
});
document.getElementById('msg-input')?.addEventListener('blur', () => {
  inputFocused = false;
  updateChatVisibility();
});
document.getElementById('nick-input')?.addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('pwd-input').focus();
});
document.getElementById('pwd-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') authenticate(); });
</script>
</body></html>`;
}

function deactivate() {}
module.exports = { activate, deactivate };
"""

SERVER_JS = r"""
/**
 * 🔥 BurnerChat Server v1.5
 * 多房間焚模式 HTTP long-polling 聊天伺服器 (E2E 加密由 client 負責)
 *
 * v1.5:
 *  - WebSocket → HTTP long polling (GET /poll + POST /send)
 *  - 支援 WebSocket 被封鎖的環境
 * v1.4:
 *  - Admin 後台 (/admin) + admin token 認證
 *  - 多房間架構:每房間獨立密碼與 burn 設定
 *  - POST /admin/auth, GET /admin/rooms, POST /admin/create-room
 */
const http = require('http');
const crypto = require('crypto');

const PORT = parseInt(process.env.PORT || '7788');
const ROOM_ID = process.env.ROOM_ID || crypto.randomBytes(4).toString('hex');
const DEFAULT_ROOM_PASSWORD = process.env.PLAIN_PASSWORD || '';
const DEFAULT_ROOM_PASSWORD_HASH = process.env.PASSWORD_HASH || '';
const ADMIN_PASSWORD_HASH = process.env.ADMIN_PASSWORD_HASH || '';
const LOCAL_IP = process.env.LOCAL_IP || '127.0.0.1';
const DEFAULT_BURN = parseInt(process.env.DEFAULT_BURN || '30');

// rooms 結構:id -> { id, name, password, passwordHash, clients:Set<ws>, burnDuration, createdAt, isDefault }
const rooms = new Map();
const tokens = new Map();        // token -> { nick, roomId, exp }
const adminTokens = new Map();   // token -> { exp }
let messageCount = 0;

// URL 組裝:port 80 時省略(避免 http://ip:80/... 醜樣)
function roomUrl(roomId) {
  const portStr = (PORT === 80) ? '' : (':' + PORT);
  return 'http://' + LOCAL_IP + portStr + '/room/' + roomId;
}

function hashPassword(pwd) {
  const salt = crypto.randomBytes(16).toString('hex');
  const h = crypto.createHash('sha256').update(salt + pwd).digest('hex');
  return salt + ':' + h;
}
function verifyPasswordHash(pwd, hashStr) {
  if (!hashStr || typeof pwd !== 'string') return false;
  const parts = hashStr.split(':');
  if (parts.length !== 2) return false;
  const check = crypto.createHash('sha256').update(parts[0] + pwd).digest('hex');
  return check === parts[1];
}
function generateRoomPassword(len) {
  const chars = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789';
  const bytes = crypto.randomBytes(len || 12);
  let s = '';
  for (let i = 0; i < bytes.length; i++) s += chars[bytes[i] % chars.length];
  return s;
}
function sanitizeNickname(raw) {
  if (typeof raw !== 'string') return '';
  let s = raw.replace(/[\x00-\x1f\x7f]/g, '').trim();
  if (s.length > 20) s = s.slice(0, 20);
  return s;
}
function sanitizeRoomName(raw) {
  if (typeof raw !== 'string') return '';
  let s = raw.replace(/[\x00-\x1f\x7f]/g, '').trim();
  if (s.length > 30) s = s.slice(0, 30);
  return s;
}
function createRoom(name, isDefault) {
  const id = crypto.randomBytes(4).toString('hex');
  const password = generateRoomPassword(12);
  const room = {
    id, name: name || ('room-' + id),
    password, passwordHash: hashPassword(password),
    clients: new Map(),        // clientId -> { nick, lastSeen, lastSeq }
    log: [],                    // 事件 log: [{ seq, type, ...payload, ts }]
    seq: 0,                     // 單調遞增 seq
    waiters: [],                // pending long-poll: [{ res, since, timer, clientId }]
    burnDuration: DEFAULT_BURN,
    createdAt: Date.now(), isDefault: !!isDefault
  };
  rooms.set(id, room);
  return room;
}

// 初始化預設房間(沿用 Python 傳入的 ROOM_ID 與密碼)
(function initDefaultRoom() {
  if (!DEFAULT_ROOM_PASSWORD_HASH) return;
  rooms.set(ROOM_ID, {
    id: ROOM_ID, name: '預設房間',
    password: DEFAULT_ROOM_PASSWORD, passwordHash: DEFAULT_ROOM_PASSWORD_HASH,
    clients: new Map(),
    log: [], seq: 0, waiters: [],
    burnDuration: DEFAULT_BURN,
    createdAt: Date.now(), isDefault: true
  });
})();

// ─── 訊息廣播 (append 到 log + 喚醒所有 waiters) ─────────────────────────────
const MAX_LOG_SIZE = 200;
const MAX_LOG_BYTES = 100 * 1024 * 1024;  // 100 MB/房間(照片加入後可能變大)

// 估算一筆 event 佔用的 bytes(概略:JSON.stringify 長度)
function estimateEventBytes(ev) {
  if (ev._bytes) return ev._bytes;
  try { ev._bytes = JSON.stringify(ev).length; } catch(e) { ev._bytes = 500; }
  return ev._bytes;
}

function enforceLogSize(room) {
  // 先按筆數限制
  if (room.log.length > MAX_LOG_SIZE) {
    room.log.splice(0, room.log.length - MAX_LOG_SIZE);
  }
  // 再按總 bytes 限制:從最舊推掉直到總大小 < MAX_LOG_BYTES
  let total = 0;
  for (const e of room.log) total += estimateEventBytes(e);
  while (total > MAX_LOG_BYTES && room.log.length > 1) {
    const removed = room.log.shift();
    total -= estimateEventBytes(removed);
  }
}

function appendEvent(roomId, event) {
  const room = rooms.get(roomId);
  if (!room) return;
  room.seq++;
  const entry = Object.assign({ seq: room.seq, ts: Date.now() }, event);
  room.log.push(entry);
  enforceLogSize(room);
  // 喚醒所有 long-poll waiters
  const waiters = room.waiters;
  room.waiters = [];
  for (const w of waiters) {
    try { clearTimeout(w.timer); } catch(e) {}
    try {
      const events = room.log.filter(e => e.seq > w.since);
      w.res.writeHead(200, {'Content-Type': 'application/json'});
      w.res.end(JSON.stringify({ ok: true, events, nextSince: room.seq }));
    } catch(e) {}
  }
}

// ─── Client 狀態維護 (heartbeat / 離線偵測) ──────────────────────────────────
const CLIENT_TIMEOUT_MS = 30000;  // 30s 沒 poll 就當離線(被 reap)

function touchClient(roomId, clientId, nick) {
  const room = rooms.get(roomId);
  if (!room) return false;
  const existing = room.clients.get(clientId);
  if (existing) {
    existing.lastSeen = Date.now();
    return false;  // 不是新上線
  }
  room.clients.set(clientId, { nick, lastSeen: Date.now() });
  return true;  // 新上線
}

function reapOfflineClients() {
  const now = Date.now();
  for (const room of rooms.values()) {
    for (const [cid, info] of room.clients) {
      if (now - info.lastSeen > CLIENT_TIMEOUT_MS) {
        room.clients.delete(cid);
        // 同時刪掉該 clientId 對應的 token(強制重新登入)
        for (const [t, td] of tokens) {
          if (td.clientId === cid) tokens.delete(t);
        }
        appendEvent(room.id, {
          type: 'system',
          text: '🔥 ' + info.nick + ' 已離開(線上:' + room.clients.size + ')'
        });
        appendEvent(room.id, {
          type: 'presenceChange',
          onlineCount: room.clients.size,
          nicks: roomNicks(room)
        });
      }
    }
  }
}

// 取得房間當下的 nick 清單
function roomNicks(room) {
  const ns = [];
  for (const info of room.clients.values()) ns.push(info.nick);
  return ns;
}
setInterval(reapOfflineClients, 15000);

// ─── Admin 認證輔助 ──────────────────────────────────────────────────────────
function getAdminToken(req) {
  const h = req.headers['authorization'] || '';
  const m = h.match(/^Bearer\s+(.+)$/i);
  return m ? m[1] : null;
}
function isAdmin(req) {
  const t = getAdminToken(req);
  if (!t) return false;
  const d = adminTokens.get(t);
  if (!d || Date.now() > d.exp) { adminTokens.delete(t); return false; }
  return true;
}
function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', d => { body += d; if (body.length > 1500000) { req.destroy(); reject(new Error('payload too large')); } });
    req.on('end', () => { try { resolve(JSON.parse(body || '{}')); } catch(e) { reject(e); } });
    req.on('error', reject);
  });
}
function sendJson(res, code, obj) {
  res.writeHead(code, {'Content-Type': 'application/json'});
  res.end(JSON.stringify(obj));
}

// ─── HTTP 路由 ───────────────────────────────────────────────────────────────
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost:' + PORT);
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type,Authorization');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  const p = url.pathname;

  // ─── Admin API ───
  if (p === '/admin/auth' && req.method === 'POST') {
    try {
      const { password } = await readJsonBody(req);
      if (!verifyPasswordHash(password, ADMIN_PASSWORD_HASH)) return sendJson(res, 401, { ok:false, error:'管理員密碼錯誤' });
      const token = crypto.randomBytes(24).toString('hex');
      adminTokens.set(token, { exp: Date.now() + 3600000 });
      return sendJson(res, 200, { ok:true, token });
    } catch(e) { return sendJson(res, 400, { ok:false, error:'請求格式錯誤' }); }
  }

  if (p === '/admin/rooms' && req.method === 'GET') {
    if (!isAdmin(req)) return sendJson(res, 401, { ok:false, error:'未授權' });
    const list = Array.from(rooms.values()).map(r => ({
      id: r.id, name: r.name, password: r.password,
      online: r.clients.size, burnDuration: r.burnDuration,
      createdAt: r.createdAt, isDefault: r.isDefault,
      url: roomUrl(r.id),
      clients: Array.from(r.clients.entries()).map(([cid, info]) => ({
        clientId: cid, nick: info.nick
      }))
    }));
    list.sort((a, b) => (b.isDefault ? 1 : 0) - (a.isDefault ? 1 : 0) || a.createdAt - b.createdAt);
    return sendJson(res, 200, { ok:true, rooms: list });
  }

  if (p === '/admin/create-room' && req.method === 'POST') {
    if (!isAdmin(req)) return sendJson(res, 401, { ok:false, error:'未授權' });
    try {
      const { name } = await readJsonBody(req);
      const cleanName = sanitizeRoomName(name);
      if (!cleanName) return sendJson(res, 400, { ok:false, error:'請輸入房間名稱' });
      const room = createRoom(cleanName, false);
      return sendJson(res, 200, { ok:true, room: {
        id: room.id, name: room.name, password: room.password,
        url: roomUrl(room.id)
      }});
    } catch(e) { return sendJson(res, 400, { ok:false, error:'請求格式錯誤' }); }
  }

  // 列出某房間的在線成員(給 admin 後台用)
  if (p === '/admin/room-clients' && req.method === 'GET') {
    if (!isAdmin(req)) return sendJson(res, 401, { ok:false, error:'未授權' });
    const roomId = url.searchParams.get('roomId');
    const room = rooms.get(roomId);
    if (!room) return sendJson(res, 404, { ok:false, error:'房間不存在' });
    const clients = [];
    for (const [cid, info] of room.clients) {
      clients.push({ clientId: cid, nick: info.nick, lastSeen: info.lastSeen });
    }
    return sendJson(res, 200, { ok:true, clients });
  }

  // Admin 踢人下線
  if (p === '/admin/kick' && req.method === 'POST') {
    if (!isAdmin(req)) return sendJson(res, 401, { ok:false, error:'未授權' });
    try {
      const { roomId, clientId } = await readJsonBody(req);
      const room = rooms.get(roomId);
      if (!room) return sendJson(res, 404, { ok:false, error:'房間不存在' });
      const info = room.clients.get(clientId);
      if (!info) return sendJson(res, 404, { ok:false, error:'成員不存在' });
      room.clients.delete(clientId);
      // 刪該 clientId 對應的 token
      for (const [t, td] of tokens) {
        if (td.clientId === clientId) tokens.delete(t);
      }
      appendEvent(room.id, {
        type: 'system',
        text: '🚫 ' + info.nick + ' 已被管理員移除(線上:' + room.clients.size + ')'
      });
      appendEvent(room.id, {
        type: 'presenceChange',
        onlineCount: room.clients.size,
        nicks: roomNicks(room)
      });
      return sendJson(res, 200, { ok:true });
    } catch(e) { return sendJson(res, 400, { ok:false, error:'請求格式錯誤' }); }
  }

  // ─── Admin:改密碼 ─────────────────────────────────────────────────
  // 改密碼後房間內所有人被踢(token 失效)、訊息 log 清空(避免解密失敗)
  if (p === '/admin/change-password' && req.method === 'POST') {
    if (!isAdmin(req)) return sendJson(res, 401, { ok:false, error:'未授權' });
    try {
      const { roomId } = await readJsonBody(req);
      const room = rooms.get(roomId);
      if (!room) return sendJson(res, 404, { ok:false, error:'房間不存在' });
      // 產生新密碼
      const newPwd = generateRoomPassword(12);
      room.password = newPwd;
      room.passwordHash = hashPassword(newPwd);
      // 踢出所有線上使用者:刪除對應 tokens,讓他們下次 poll 收到 401
      for (const [t, td] of tokens) {
        if (td.roomId === roomId) tokens.delete(t);
      }
      // 清空房間狀態:log、seq、clients
      room.clients.clear();
      room.log = [];
      room.seq = 0;
      // 喚醒所有 waiters(回傳空陣列,他們會再 poll 一次就收到 401)
      const waiters = room.waiters;
      room.waiters = [];
      for (const w of waiters) {
        try { clearTimeout(w.timer); } catch(e) {}
        try {
          w.res.writeHead(401, {'Content-Type': 'application/json'});
          w.res.end(JSON.stringify({ ok:false, error:'房間密碼已變更' }));
        } catch(e) {}
      }
      return sendJson(res, 200, { ok:true, password: newPwd });
    } catch(e) { return sendJson(res, 400, { ok:false, error:'請求格式錯誤' }); }
  }

  // ─── Admin:刪除房間 ──────────────────────────────────────────────
  // 廣播 roomDeleted 事件讓 client 自動跳回登入畫面,接著刪掉房間本身
  if (p === '/admin/delete-room' && req.method === 'POST') {
    if (!isAdmin(req)) return sendJson(res, 401, { ok:false, error:'未授權' });
    try {
      const { roomId } = await readJsonBody(req);
      const room = rooms.get(roomId);
      if (!room) return sendJson(res, 404, { ok:false, error:'房間不存在' });
      // 先廣播 roomDeleted 事件(這會喚醒 waiters 回傳此事件)
      appendEvent(room.id, { type: 'roomDeleted' });
      // 刪除對應 tokens
      for (const [t, td] of tokens) {
        if (td.roomId === roomId) tokens.delete(t);
      }
      // 給 waiters 一點時間送出(雖然 appendEvent 裡已經 flush 了),然後刪房間
      setImmediate(() => {
        rooms.delete(roomId);
      });
      return sendJson(res, 200, { ok:true });
    } catch(e) { return sendJson(res, 400, { ok:false, error:'請求格式錯誤' }); }
  }

  if (p === '/admin') {
    res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'});
    res.end(generateAdminPage());
    return;
  }

  // ─── 房間認證 ───
  if (p === '/auth' && req.method === 'POST') {
    try {
      const body = await readJsonBody(req);
      const { password, nickname } = body;
      let { roomId } = body;
      if (!roomId) roomId = ROOM_ID; // 後相容:沒傳 roomId 就用預設房間
      const room = rooms.get(roomId);
      if (!room) return sendJson(res, 404, { ok:false, error:'房間不存在' });
      if (!verifyPasswordHash(password, room.passwordHash)) return sendJson(res, 401, { ok:false, error:'密碼錯誤' });
      const cleaned = sanitizeNickname(nickname);
      const nick = cleaned || ('user_' + crypto.randomBytes(3).toString('hex'));
      const token = crypto.randomBytes(16).toString('hex');
      const clientId = crypto.randomBytes(8).toString('hex');
      tokens.set(token, { nick, roomId: room.id, clientId });  // 無 exp:只有離開/reap/admin踢/重啟才失效
      return sendJson(res, 200, {
        ok:true, token, nick, clientId,
        since: room.seq, burnDuration: room.burnDuration,
        nicks: roomNicks(room)  // 初始化 roster
      });
    } catch(e) { return sendJson(res, 400, { ok:false, error:'請求格式錯誤' }); }
  }

  // ─── Long polling ──────────────────────────────────────────────
  // GET /poll?token=xxx&since=N
  // 如果有 seq > since 的事件,立刻回;否則 hold 25 秒直到有新事件
  if (p === '/poll' && req.method === 'GET') {
    const token = url.searchParams.get('token');
    const since = parseInt(url.searchParams.get('since') || '0');
    const tokenData = tokens.get(token);
    if (!tokenData) return sendJson(res, 401, { ok:false, error:'token 失效' });
    const room = rooms.get(tokenData.roomId);
    if (!room) return sendJson(res, 404, { ok:false, error:'房間不存在' });
    // 標記這個 client 還活著(用於線上偵測)
    const wasNew = touchClient(room.id, tokenData.clientId, tokenData.nick);
    if (wasNew) {
      appendEvent(room.id, {
        type: 'system',
        text: '🔥 ' + tokenData.nick + ' 已加入房間(線上:' + room.clients.size + ')'
      });
      appendEvent(room.id, {
        type: 'presenceChange',
        onlineCount: room.clients.size,
        nicks: roomNicks(room)
      });
    }
    // 有已累積的新事件就立刻回
    const pending = room.log.filter(e => e.seq > since);
    if (pending.length > 0) {
      return sendJson(res, 200, { ok:true, events: pending, nextSince: room.seq });
    }
    // 否則 hold 住,加入 waiters 等待
    const waiter = { res, since, clientId: tokenData.clientId };
    waiter.timer = setTimeout(() => {
      // timeout:回空陣列讓 client 立刻重新 poll
      const idx = room.waiters.indexOf(waiter);
      if (idx >= 0) room.waiters.splice(idx, 1);
      try {
        res.writeHead(200, {'Content-Type': 'application/json'});
        res.end(JSON.stringify({ ok:true, events: [], nextSince: since }));
      } catch(e) {}
    }, 25000);
    // client 斷線也清掉 waiter
    req.on('close', () => {
      clearTimeout(waiter.timer);
      const idx = room.waiters.indexOf(waiter);
      if (idx >= 0) room.waiters.splice(idx, 1);
    });
    room.waiters.push(waiter);
    return;
  }

  // ─── 發送事件 ─────────────────────────────────────────────────
  // POST /send  { token, type:'chat'|'setBurn'|'read', ... }
  if (p === '/send' && req.method === 'POST') {
    try {
      const body = await readJsonBody(req);
      const { token } = body;
      const tokenData = tokens.get(token);
      if (!tokenData) return sendJson(res, 401, { ok:false, error:'token 失效' });
      const room = rooms.get(tokenData.roomId);
      if (!room) return sendJson(res, 404, { ok:false, error:'房間不存在' });
      const { nick } = tokenData;
      touchClient(room.id, tokenData.clientId, nick);

      if (body.type === 'chat' && body.encrypted && typeof body.encrypted.ct === 'string' && typeof body.encrypted.iv === 'string') {
        if (body.encrypted.ct.length > 1200000 || body.encrypted.iv.length > 32) {
          return sendJson(res, 400, { ok:false, error:'payload 過大' });
        }
        messageCount++;
        const msgId = crypto.randomBytes(6).toString('hex');
        // 接收者 = 當下線上人數 - 發送者自己;為 0 代表「沒人需要讀」
        const expectedReaders = Math.max(0, room.clients.size - 1);
        appendEvent(room.id, { type: 'chat', sender: nick, encrypted: body.encrypted, msgId, expectedReaders });
        return sendJson(res, 200, { ok:true, msgId });
      } else if (body.type === 'setBurn') {
        const duration = Math.max(0, Math.min(3600, parseInt(body.duration) || 0));
        room.burnDuration = duration;
        appendEvent(room.id, { type: 'burnUpdate', duration, by: nick, silent: false });
        return sendJson(res, 200, { ok:true });
      } else if (body.type === 'read' && typeof body.msgId === 'string') {
        appendEvent(room.id, { type: 'read', msgId: body.msgId, reader: nick });
        return sendJson(res, 200, { ok:true });
      } else if (body.type === 'leave') {
        // 明確離開 (beforeunload)
        if (room.clients.delete(tokenData.clientId)) {
          tokens.delete(token);  // 離開時一併失效 token
          appendEvent(room.id, {
            type: 'system',
            text: '🔥 ' + nick + ' 已離開(線上:' + room.clients.size + ')'
          });
          appendEvent(room.id, {
            type: 'presenceChange',
            onlineCount: room.clients.size,
            nicks: roomNicks(room)
          });
        }
        return sendJson(res, 200, { ok:true });
      } else if (body.type === 'heartbeat') {
        // touchClient 已在上面執行了,這裡只需要回 ok
        return sendJson(res, 200, { ok:true });
      }
      return sendJson(res, 400, { ok:false, error:'未知的 type' });
    } catch(e) { return sendJson(res, 400, { ok:false, error:'請求格式錯誤' }); }
  }

  if (p === '/status') {
    return sendJson(res, 200, {
      rooms: rooms.size, messages: messageCount,
      online: Array.from(rooms.values()).reduce((a, r) => a + r.clients.size, 0)
    });
  }

  // ─── 房間頁面 ───
  if (p === '/' || p === '/room/' + ROOM_ID) {
    res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'});
    res.end(generateChatPage(ROOM_ID));
    return;
  }
  const roomMatch = p.match(/^\/room\/([a-f0-9]{4,16})$/i);
  if (roomMatch) {
    const rid = roomMatch[1];
    if (!rooms.has(rid)) { res.writeHead(404); res.end('Room not found'); return; }
    res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'});
    res.end(generateChatPage(rid));
    return;
  }

  res.writeHead(404); res.end('Not Found');
});

// ═════════════════════════════════════════════════════════════════════════════
// 管理員後台頁面
// ═════════════════════════════════════════════════════════════════════════════
function generateAdminPage() {
  return `<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🛡️ BurnerChat Admin</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0a0a0a;--bg2:#111;--border:#1e1e1e;--accent:#ff4500;--accent2:#ff8c35;--purple:#a855f7;--green:#00ff88;--text:#d4d4d4;--dim:#555}
body{background:var(--bg);color:var(--text);font-family:'JetBrains Mono',monospace;min-height:100vh;display:flex;flex-direction:column}

#admin-auth{position:fixed;inset:0;background:#0a0a0a;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:20px;z-index:100}
.auth-box{background:var(--bg2);border:1px solid var(--purple);padding:32px 40px;border-radius:6px;display:flex;flex-direction:column;gap:14px;align-items:center;min-width:340px}
.auth-box h2{color:var(--purple);font-size:16px;letter-spacing:3px}
.auth-box p{color:var(--dim);font-size:11px;text-align:center}
.auth-box input{background:#0d0d0d;border:1px solid var(--border);color:var(--text);padding:10px 16px;width:100%;border-radius:4px;font-family:inherit;font-size:14px;outline:none;text-align:center;letter-spacing:2px}
.auth-box input:focus{border-color:var(--purple)}
.auth-box button{background:var(--purple);color:white;border:none;padding:10px;width:100%;border-radius:4px;cursor:pointer;font-family:inherit;font-size:13px;letter-spacing:1px;transition:.2s}
.auth-box button:hover{background:#9333ea}
.err{color:#ff4444;font-size:12px;text-align:center;min-height:16px}

#panel{display:none;padding:0;flex:1}
header.topbar{background:#0f0015;border-bottom:2px solid var(--purple);padding:14px 24px;display:flex;align-items:center;gap:16px}
header.topbar h1{font-size:15px;color:#c084fc;letter-spacing:2px}
header.topbar .stats{margin-left:auto;display:flex;gap:20px;font-size:11px;color:var(--dim)}
header.topbar .stats b{color:var(--accent2);font-weight:700}
header.topbar .logout{background:transparent;color:var(--dim);border:1px solid var(--border);padding:5px 12px;border-radius:3px;cursor:pointer;font-family:inherit;font-size:11px}
header.topbar .logout:hover{border-color:#ff4444;color:#ff4444}

.create-section{padding:20px 24px;border-bottom:1px solid var(--border);background:#0c0818;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.create-section label{color:#c084fc;font-size:11px;font-weight:bold}
.create-section input{flex:1;min-width:200px;background:#0a0a0a;border:1px solid var(--border);color:var(--text);padding:8px 12px;border-radius:3px;font-family:inherit;font-size:13px;outline:none}
.create-section input:focus{border-color:var(--purple)}
.create-section button{background:var(--purple);color:white;border:none;padding:8px 16px;border-radius:3px;cursor:pointer;font-family:inherit;font-size:12px;letter-spacing:1px}
.create-section button:hover{background:#9333ea}

.rooms{padding:20px 24px;display:flex;flex-direction:column;gap:14px}
.room-card{background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:16px 20px;transition:border-color .2s}
.room-card:hover{border-color:#333}
.room-card.default{border-left:3px solid var(--accent)}
.room-head{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.room-head h3{font-size:14px;color:var(--accent2);font-weight:700}
.badge{background:var(--accent);color:white;font-size:9px;padding:2px 6px;border-radius:3px;letter-spacing:1px}
.room-head .online{margin-left:auto;font-size:11px;color:var(--green)}
.room-head .online.zero{color:var(--dim)}
.room-body{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;font-size:12px;margin-bottom:12px;align-items:center}
.room-body label{color:var(--dim);font-size:10px;letter-spacing:1px}
.room-body code{background:#050505;border:1px solid #1a1a1a;padding:4px 8px;border-radius:3px;font-family:inherit;font-size:11px;color:#ffd700;word-break:break-all;display:inline-block}
.room-body code.url{color:var(--accent2);font-size:10px}
.members{margin-bottom:12px;display:flex;flex-direction:column;gap:6px}
.members label{color:var(--dim);font-size:10px;letter-spacing:1px}
.member-list{display:flex;flex-wrap:wrap;gap:6px}
.member-chip{display:inline-flex;align-items:center;gap:4px;background:#0a1a0a;border:1px solid #1a3a1a;color:#88ffbb;padding:3px 4px 3px 10px;border-radius:12px;font-size:11px}
.btn-kick{background:transparent;border:none;color:#ff4444;cursor:pointer;padding:2px 6px;border-radius:50%;font-size:11px;line-height:1;transition:.15s}
.btn-kick:hover{background:#ff4444;color:white}
.room-actions{display:flex;gap:8px;flex-wrap:wrap}
.room-actions button,.room-actions a{background:transparent;color:var(--accent);border:1px solid var(--accent);padding:6px 14px;border-radius:3px;cursor:pointer;font-family:inherit;font-size:11px;text-decoration:none;display:inline-block;letter-spacing:1px;transition:.15s}
.room-actions button:hover,.room-actions a:hover{background:var(--accent);color:white}
.room-actions .btn-primary{background:var(--purple);border-color:var(--purple);color:white}
.room-actions .btn-primary:hover{background:#9333ea;border-color:#9333ea}
.room-actions .btn-warn{color:#ffb347;border-color:#ffb347}
.room-actions .btn-warn:hover{background:#ffb347;color:#1a0a00}
.room-actions .btn-danger{color:#ff4444;border-color:#ff4444}
.room-actions .btn-danger:hover{background:#ff4444;color:white}

#empty{text-align:center;color:var(--dim);padding:60px 20px;font-size:13px}

#toast{position:fixed;bottom:30px;left:50%;transform:translateX(-50%) translateY(100px);background:var(--bg2);color:var(--green);border:1px solid var(--green);padding:10px 20px;border-radius:4px;font-size:12px;opacity:0;transition:all .3s;pointer-events:none;z-index:1000}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
#toast.err{color:#ff4444;border-color:#ff4444}
</style>
</head>
<body>

<div id="admin-auth">
  <div class="auth-box">
    <h2>🛡️ ADMIN PANEL</h2>
    <p>BurnerChat 管理員後台<br/>密碼請見伺服器 console</p>
    <input type="password" id="adminPwd" placeholder="管理員密碼" autofocus />
    <div id="authErr" class="err"></div>
    <button onclick="adminLogin()">登入</button>
  </div>
</div>

<div id="panel">
  <header class="topbar">
    <span style="font-size:20px">🛡️</span>
    <h1>BURNER CHAT ADMIN</h1>
    <div class="stats">
      <span>房間: <b id="stat-rooms">0</b></span>
      <span>線上: <b id="stat-online">0</b></span>
      <span>訊息: <b id="stat-msgs">0</b></span>
    </div>
    <button class="logout" onclick="logout()">登出</button>
  </header>

  <div class="create-section">
    <label>➕ 新增房間:</label>
    <input type="text" id="roomName" placeholder="房間名稱(例:產品會議、Code Review)" maxlength="30" />
    <button onclick="createRoom()">建立</button>
  </div>

  <div class="rooms" id="rooms-list">
    <div id="empty">載入中...</div>
  </div>
</div>

<div id="toast"></div>

<script>
let adminToken = sessionStorage.getItem('bc_admin_token') || null;
let refreshTimer = null;
let lastRooms = [];

function showToast(msg, isErr){
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = isErr ? 'err show' : 'show';
  setTimeout(()=>t.className = isErr ? 'err' : '', 2200);
}

function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

async function adminLogin(){
  const pwd = document.getElementById('adminPwd').value;
  const err = document.getElementById('authErr');
  if(!pwd){ err.textContent = '❌ 請輸入密碼'; return; }
  try {
    const r = await fetch('/admin/auth', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({password: pwd})
    });
    const d = await r.json();
    if(d.ok){
      adminToken = d.token;
      sessionStorage.setItem('bc_admin_token', adminToken);
      showPanel();
    } else {
      err.textContent = '❌ ' + (d.error || '認證失敗');
      setTimeout(()=>err.textContent='', 2500);
    }
  } catch(e){
    err.textContent = '❌ 無法連線';
  }
}

function logout(){
  adminToken = null;
  sessionStorage.removeItem('bc_admin_token');
  if(refreshTimer) clearInterval(refreshTimer);
  document.getElementById('panel').style.display = 'none';
  document.getElementById('admin-auth').style.display = 'flex';
  document.getElementById('adminPwd').value = '';
  document.getElementById('adminPwd').focus();
}

function showPanel(){
  document.getElementById('admin-auth').style.display = 'none';
  document.getElementById('panel').style.display = 'block';
  refreshRooms();
  if(refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(refreshRooms, 4000);
}

async function apiCall(path, opts){
  opts = opts || {};
  opts.headers = Object.assign({}, opts.headers || {}, {'Authorization': 'Bearer ' + adminToken});
  const r = await fetch(path, opts);
  if(r.status === 401){ logout(); throw new Error('unauthorized'); }
  return r.json();
}

async function refreshRooms(){
  try {
    const d = await apiCall('/admin/rooms');
    if(!d.ok) return;
    lastRooms = d.rooms;
    renderRooms(d.rooms);
  } catch(e){}
}

function renderRooms(rooms){
  const list = document.getElementById('rooms-list');
  let totalOnline = 0;
  rooms.forEach(r => totalOnline += r.online);
  document.getElementById('stat-rooms').textContent = rooms.length;
  document.getElementById('stat-online').textContent = totalOnline;

  // 清空列表 (不用 innerHTML,避免 outer template literal 的轉義陷阱)
  while(list.firstChild) list.removeChild(list.firstChild);

  if(rooms.length === 0){
    const empty = document.createElement('div');
    empty.id = 'empty';
    empty.textContent = '尚無房間,點上方「建立」新增';
    list.appendChild(empty);
    return;
  }

  rooms.forEach(r => {
    const card = document.createElement('div');
    card.className = 'room-card' + (r.isDefault ? ' default' : '');

    // 頭部:房間名 + 預設標籤 + 線上人數
    const head = document.createElement('div');
    head.className = 'room-head';
    const h3 = document.createElement('h3');
    h3.textContent = r.name;
    head.appendChild(h3);
    if(r.isDefault){
      const badge = document.createElement('span');
      badge.className = 'badge';
      badge.textContent = '預設';
      head.appendChild(badge);
    }
    const online = document.createElement('span');
    online.className = 'online' + (r.online === 0 ? ' zero' : '');
    online.textContent = (r.online > 0 ? '🟢' : '⚫') + ' ' + r.online + ' 人在線';
    head.appendChild(online);
    card.appendChild(head);

    // 房間資訊
    const body = document.createElement('div');
    body.className = 'room-body';
    const rows = [
      ['ROOM ID', r.id, ''],
      ['密碼', r.password, ''],
      ['URL', r.url, 'url']
    ];
    rows.forEach(([label, value, cls]) => {
      const lb = document.createElement('label');
      lb.textContent = label;
      const code = document.createElement('code');
      if(cls) code.className = cls;
      code.textContent = value;
      body.appendChild(lb);
      body.appendChild(code);
    });
    card.appendChild(body);

    // 在線成員列表 + 踢人按鈕
    if (r.clients && r.clients.length > 0) {
      const membersWrap = document.createElement('div');
      membersWrap.className = 'members';
      const label = document.createElement('label');
      label.textContent = '在線成員';
      membersWrap.appendChild(label);
      const memList = document.createElement('div');
      memList.className = 'member-list';
      r.clients.forEach(c => {
        const chip = document.createElement('span');
        chip.className = 'member-chip';
        const nickSpan = document.createElement('span');
        nickSpan.textContent = c.nick;
        chip.appendChild(nickSpan);
        const kickBtn = document.createElement('button');
        kickBtn.className = 'btn-kick';
        kickBtn.title = '踢出 ' + c.nick;
        kickBtn.textContent = '✕';
        kickBtn.addEventListener('click', () => kickClient(r.id, c.clientId, c.nick));
        chip.appendChild(kickBtn);
        memList.appendChild(chip);
      });
      membersWrap.appendChild(memList);
      card.appendChild(membersWrap);
    }

    // 操作按鈕
    const actions = document.createElement('div');
    actions.className = 'room-actions';

    const btnCopy = document.createElement('button');
    btnCopy.className = 'btn-primary';
    btnCopy.textContent = '📋 複製連結+密碼';
    btnCopy.addEventListener('click', () => copyInvite(r.id));
    actions.appendChild(btnCopy);

    const btnUrl = document.createElement('button');
    btnUrl.textContent = '🔗 僅複製連結';
    btnUrl.addEventListener('click', () => copyUrl(r.id));
    actions.appendChild(btnUrl);

    const link = document.createElement('a');
    link.href = r.url;
    link.target = '_blank';
    link.textContent = '↗ 開啟房間';
    actions.appendChild(link);

    // 改密碼
    const btnChangePwd = document.createElement('button');
    btnChangePwd.className = 'btn-warn';
    btnChangePwd.textContent = '🔑 改密碼';
    btnChangePwd.addEventListener('click', () => changePassword(r.id, r.name));
    actions.appendChild(btnChangePwd);

    // 刪除房間
    const btnDelete = document.createElement('button');
    btnDelete.className = 'btn-danger';
    btnDelete.textContent = '🗑️ 刪除';
    btnDelete.addEventListener('click', () => deleteRoom(r.id, r.name));
    actions.appendChild(btnDelete);

    card.appendChild(actions);
    list.appendChild(card);
  });
}

async function createRoom(){
  const input = document.getElementById('roomName');
  const name = input.value.trim();
  if(!name){ showToast('❌ 請輸入房間名稱', true); input.focus(); return; }
  try {
    const d = await apiCall('/admin/create-room', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name})
    });
    if(d.ok){
      input.value = '';
      showToast('✓ 已建立房間:' + d.room.name);
      refreshRooms();
    } else {
      showToast('❌ ' + (d.error || '建立失敗'), true);
    }
  } catch(e){}
}

async function kickClient(roomId, clientId, nick){
  if (!confirm('確定要踢出 ' + nick + ' 嗎?\\n(他可以立即以相同密碼重新進入)')) return;
  try {
    const d = await apiCall('/admin/kick', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({roomId, clientId})
    });
    if (d.ok) {
      showToast('✓ 已踢出 ' + nick);
      refreshRooms();
    } else {
      showToast('❌ ' + (d.error || '踢出失敗'), true);
    }
  } catch(e){}
}

async function changePassword(roomId, name){
  if (!confirm('確定要更換 "' + name + '" 的密碼嗎?\\n\\n' +
               '這會:\\n' +
               '• 踢出房間內所有人\\n' +
               '• 清空所有訊息記錄\\n' +
               '• 自動產生新的隨機密碼')) return;
  try {
    const d = await apiCall('/admin/change-password', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({roomId})
    });
    if (d.ok) {
      showToast('✓ 已更新密碼:' + d.password);
      refreshRooms();
    } else {
      showToast('❌ ' + (d.error || '改密碼失敗'), true);
    }
  } catch(e){}
}

async function deleteRoom(roomId, name){
  if (!confirm('確定要刪除 "' + name + '" 嗎?\\n\\n' +
               '• 所有線上使用者會立即斷線\\n' +
               '• 所有訊息紀錄消失\\n' +
               '• 此動作不可復原')) return;
  try {
    const d = await apiCall('/admin/delete-room', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({roomId})
    });
    if (d.ok) {
      showToast('✓ 已刪除房間 "' + name + '"');
      refreshRooms();
    } else {
      showToast('❌ ' + (d.error || '刪除失敗'), true);
    }
  } catch(e){}
}

async function copyText(text){
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch(e){
    // fallback for non-HTTPS LAN environments
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;';
    document.body.appendChild(ta);
    ta.focus(); ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch(e){}
    document.body.removeChild(ta);
    return ok;
  }
}

async function copyInvite(roomId){
  const r = lastRooms.find(x => x.id === roomId);
  if(!r) return;
  const text = '🔥 BurnerChat 房間邀請\\n' +
    '房間:' + r.name + '\\n' +
    '連結:' + r.url + '\\n' +
    '密碼:' + r.password;
  const ok = await copyText(text);
  showToast(ok ? '✓ 已複製「連結 + 密碼」到剪貼簿' : '❌ 複製失敗(請手動選取)', !ok);
}

async function copyUrl(roomId){
  const r = lastRooms.find(x => x.id === roomId);
  if(!r) return;
  const ok = await copyText(r.url);
  showToast(ok ? '✓ 已複製連結' : '❌ 複製失敗', !ok);
}

document.getElementById('adminPwd').addEventListener('keydown', e => { if(e.key === 'Enter') adminLogin(); });
document.getElementById('roomName').addEventListener('keydown', e => { if(e.key === 'Enter') createRoom(); });

// Session 恢復:若 sessionStorage 有 token,嘗試直接進入
if(adminToken){
  fetch('/admin/rooms', {headers:{'Authorization':'Bearer ' + adminToken}})
    .then(r => {
      if(r.ok) showPanel();
      else { sessionStorage.removeItem('bc_admin_token'); adminToken = null; }
    })
    .catch(()=>{});
}
</script>
</body>
</html>`;
}

// ═════════════════════════════════════════════════════════════════════════════
// 聊天室頁面
// ═════════════════════════════════════════════════════════════════════════════
function generateChatPage(roomId) {
  return `<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🔥 BurnerChat</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0a0a0a;--bg2:#111;--border:#1e1e1e;--accent:#ff4500;--accent2:#ff8c35;--green:#00ff88;--text:#d4d4d4;--dim:#555}
body{background:var(--bg);color:var(--text);font-family:'JetBrains Mono',monospace;height:100vh;display:flex;flex-direction:column;overflow:hidden}
#header{background:#100500;border-bottom:2px solid var(--accent);padding:12px 20px;display:flex;align-items:center;gap:12px}
.logo{font-size:20px}
h1{font-size:15px;color:var(--accent2);letter-spacing:2px}
#me-label{font-size:12px;color:var(--accent2);opacity:.8}
.sound-btn{font-size:16px;cursor:pointer;opacity:.75;user-select:none;transition:opacity .2s,transform .1s;padding:2px 6px;border-radius:3px}
.sound-btn:hover{opacity:1;transform:scale(1.15);background:rgba(255,69,0,.1)}
#online{margin-left:auto;font-size:11px;color:var(--dim)}
#notice{background:#0d0200;border-bottom:1px solid #1e0a00;padding:6px 20px;font-size:11px;color:#ff4500;opacity:.7;text-align:center}

#roster{background:#0a0503;border-bottom:1px solid #2a1a00;padding:6px 20px;font-size:11px;color:var(--dim);display:flex;align-items:center;gap:8px;flex-wrap:wrap}
#roster .roster-toggle{cursor:pointer;color:var(--accent);user-select:none;padding:2px 6px;border:1px solid #2a1a00;border-radius:3px}
#roster .roster-toggle:hover{background:#1a0a00}
#roster .roster-list{flex:1;line-height:1.6}
#roster.collapsed .roster-list{display:none}

#sys-log{background:#080503;border-bottom:1px solid #2a1a00;padding:4px 20px;font-size:11px;color:var(--dim);font-style:italic}
#sys-log .sys-header{display:flex;align-items:center;gap:10px}
#sys-log .sys-last{flex:1;opacity:.85;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#sys-log .sys-toggle{cursor:pointer;color:var(--accent);user-select:none;padding:1px 6px;border:1px solid #2a1a00;border-radius:3px;font-style:normal;font-size:10px;flex-shrink:0}
#sys-log .sys-toggle:hover{background:#1a0a00}
#sys-log .sys-full{max-height:10vh;overflow-y:auto;margin-top:4px}
#sys-log .sys-line{padding:2px 0;opacity:.7}
#sys-log.collapsed .sys-full{display:none}
#sys-log:not(.collapsed) .sys-last{display:none}

#burn-bar{background:#0f0a05;border-bottom:1px solid #2a1a00;padding:8px 20px;display:flex;align-items:center;gap:10px;font-size:11px;color:var(--dim);flex-wrap:wrap}
#burn-bar label{color:var(--accent2);font-weight:bold}
#burn-bar input[type=number]{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:4px 8px;width:70px;border-radius:3px;font-family:inherit;font-size:12px;outline:none;text-align:center}
#burn-bar input[type=number]:focus{border-color:var(--accent)}
#burn-bar button{background:transparent;color:var(--accent);border:1px solid var(--accent);padding:4px 12px;width:auto;border-radius:3px;cursor:pointer;font-family:inherit;font-size:11px;letter-spacing:1px}
#burn-bar button:hover{background:var(--accent);color:white}
#burn-bar .hint{margin-left:auto;font-size:10px;opacity:.6}
#burn-bar .preset{background:#1a0a00;border:1px solid #2a1000;color:var(--accent2);padding:3px 8px;border-radius:3px;cursor:pointer;font-size:10px}
#burn-bar .preset:hover{background:var(--accent);color:white;border-color:var(--accent)}

#auth{position:fixed;inset:0;background:rgba(10,10,10,.97);display:flex;align-items:center;justify-content:center;flex-direction:column;gap:20px;z-index:100}
.auth-box{background:var(--bg2);border:1px solid var(--accent);padding:32px 40px;border-radius:6px;display:flex;flex-direction:column;gap:14px;align-items:center;min-width:320px}
.auth-box h2{color:var(--accent);font-size:16px;letter-spacing:3px}
.auth-box p{color:var(--dim);font-size:11px;text-align:center}
.auth-box input{background:#0d0d0d;border:1px solid var(--border);color:var(--text);padding:10px 16px;width:100%;border-radius:4px;font-family:inherit;font-size:14px;outline:none;text-align:center}
.auth-box input[type=password]{letter-spacing:3px}
.auth-box input:focus{border-color:var(--accent)}
button{background:var(--accent);color:white;border:none;padding:10px;width:100%;border-radius:4px;cursor:pointer;font-family:inherit;font-size:13px;letter-spacing:1px}
button:hover{background:var(--accent2)}
#msgs{flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:10px}
#msgs::-webkit-scrollbar{width:4px}
#msgs::-webkit-scrollbar-track{background:var(--bg)}
#msgs::-webkit-scrollbar-thumb{background:var(--accent);border-radius:2px}
.msg{display:flex;flex-direction:column;max-width:70%;transition:opacity .6s,transform .6s}
.msg.sys{align-self:center;color:var(--dim);font-size:11px;font-style:italic}
.msg.me{align-self:flex-end}
.msg.other{align-self:flex-start}
.bubble{padding:8px 14px;border-radius:4px;font-size:13px;line-height:1.5}
.msg.me .bubble{background:#1a0800;border:1px solid #2a1000;color:#ffaa88}
.msg.other .bubble{background:#001a0a;border:1px solid #003018;color:#88ffbb}
.sender{font-size:10px;color:var(--dim);margin-bottom:3px;padding:0 2px}
.msg.me .sender{text-align:right}
.readby{font-size:9px;color:var(--green);opacity:.65;margin-top:3px;padding:0 4px;letter-spacing:.5px}
.msg.me .readby{text-align:right}
.countdown{font-size:9px;color:var(--dim);margin-top:2px;padding:0 4px;opacity:.55;letter-spacing:.5px}
.msg.me .countdown{text-align:right}
.msg.sys .countdown{text-align:center;opacity:.35}
.msg.burning{animation:flicker .5s infinite}
.msg.burning .bubble{box-shadow:0 0 8px rgba(255,69,0,.4)}
.msg.unread .bubble{border-left:3px solid var(--accent)}
/* 反黑遮罩:未 focus 或分頁背景時,訊息文字顯示為 █████ */
#msgs.redacted .msg:not(.sys) .bubble .text-content{font-size:0}
#msgs.redacted .msg:not(.sys) .bubble .text-content::before{content:attr(data-mask);font-size:14px;color:var(--dim);opacity:.6;letter-spacing:-2px}
@keyframes flicker{0%,100%{opacity:1}50%{opacity:.65}}
#input{display:flex;gap:8px;padding:12px 20px;background:var(--bg2);border-top:1px solid var(--border)}
#input input{flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:8px 14px;border-radius:4px;font-family:inherit;font-size:13px;outline:none}
#input input:focus{border-color:var(--accent)}
#input button{padding:8px 20px;width:auto;letter-spacing:0}
#clean-toggle{background:transparent;border:1px solid var(--border);cursor:pointer;padding:4px 6px;border-radius:4px;flex-shrink:0;transition:.15s;display:flex;align-items:center;justify-content:center}
#clean-toggle img{width:24px;height:24px;display:block;opacity:.7;transition:opacity .15s}
#clean-toggle:hover img{opacity:1}
#clean-toggle:hover{background:var(--bg);border-color:var(--accent)}
#clean-toggle.active{color:var(--accent);border-color:var(--accent);background:rgba(255,69,0,.1)}
/* 乾淨版:隱藏 header/notice/roster/sys-log/burn-bar,保留 #msgs 與輸入列 */
body.clean-mode #header,
body.clean-mode #notice,
body.clean-mode #roster,
body.clean-mode #sys-log,
body.clean-mode #burn-bar{display:none !important}
body.clean-mode #mi::placeholder{color:transparent}
body.clean-mode #send-btn{font-size:0;padding:8px 14px}
body.clean-mode #send-btn::after{content:'→';font-size:16px}
body.clean-mode .readby .names{display:none}

/* Emoji / 圖片按鈕(共用 clean-btn 樣式已定義在 #clean-toggle) */
#emoji-toggle,#img-attach{background:transparent;border:1px solid var(--border);cursor:pointer;padding:4px 8px;border-radius:4px;font-size:16px;flex-shrink:0;transition:.15s;color:var(--text)}
#emoji-toggle:hover,#img-attach:hover{background:var(--bg);border-color:var(--accent)}
#emoji-toggle.active{color:var(--accent);border-color:var(--accent);background:rgba(255,69,0,.1)}

/* Emoji 彈出面板 */
#emoji-panel{position:fixed;bottom:68px;left:20px;width:320px;max-width:92vw;background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:8px;z-index:999;box-shadow:0 4px 20px rgba(0,0,0,.5)}
#emoji-search{width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:4px;font-family:inherit;font-size:12px;outline:none;box-sizing:border-box;margin-bottom:6px}
#emoji-search:focus{border-color:var(--accent)}
#emoji-tabs{display:flex;gap:4px;border-bottom:1px solid var(--border);padding-bottom:6px;margin-bottom:6px}
#emoji-tabs .tab{cursor:pointer;padding:3px 7px;border-radius:3px;font-size:15px;transition:.15s;opacity:.5}
#emoji-tabs .tab:hover{opacity:.9;background:var(--bg)}
#emoji-tabs .tab.active{opacity:1;background:var(--bg);box-shadow:inset 0 -2px 0 var(--accent)}
#emoji-grid{display:grid;grid-template-columns:repeat(8,1fr);gap:2px;max-height:220px;overflow-y:auto}
#emoji-grid .emoji-cell{cursor:pointer;padding:4px;text-align:center;font-size:20px;border-radius:3px;transition:.1s;user-select:none}
#emoji-grid .emoji-cell:hover{background:var(--accent);transform:scale(1.15)}

/* 圖片預覽(發送前) */
#img-preview{position:fixed;bottom:68px;right:20px;background:var(--bg2);border:1px solid var(--accent);border-radius:6px;padding:8px;display:flex;align-items:center;gap:8px;z-index:999;box-shadow:0 4px 20px rgba(0,0,0,.5)}
#img-preview #img-preview-thumb{max-width:80px;max-height:80px;border-radius:3px;object-fit:cover}
#img-preview #img-preview-size{font-size:10px;color:var(--dim)}
#img-preview button{background:transparent;border:1px solid var(--border);color:#ff4444;cursor:pointer;width:24px;height:24px;padding:0;border-radius:50%;font-size:12px}
#img-preview button:hover{background:#ff4444;color:white}

/* 訊息內的圖片(background-image 形式,防右鍵另存) */
.msg-image{width:100%;max-width:300px;aspect-ratio:4/3;background-size:contain;background-position:left center;background-repeat:no-repeat;margin-top:6px;border-radius:4px;cursor:zoom-in;border:1px solid var(--border)}
.msg.me .msg-image{background-position:right center}
#msgs.redacted .msg:not(.sys) .msg-image{filter:blur(18px)}

/* 全螢幕圖片檢視器 */
#img-viewer{position:fixed;inset:0;background:rgba(0,0,0,.96);z-index:9999;display:flex;flex-direction:column}
#img-viewer-stage{flex:1;overflow:hidden;position:relative;cursor:grab;display:flex;align-items:center;justify-content:center}
#img-viewer-stage.dragging{cursor:grabbing}
#img-viewer-content{width:100%;height:100%;background-size:contain;background-position:center;background-repeat:no-repeat;transition:transform .1s ease-out;transform-origin:center}
#img-viewer-toolbar{padding:10px 20px;display:flex;gap:8px;align-items:center;justify-content:center;background:rgba(0,0,0,.5);border-top:1px solid #222}
#img-viewer-toolbar button{background:transparent;border:1px solid #555;color:#ccc;cursor:pointer;padding:6px 14px;border-radius:4px;font-size:14px;min-width:44px}
#img-viewer-toolbar button:hover{background:#333;color:white;border-color:#888}
#img-viewer-zoom{color:#ccc;font-size:12px;min-width:50px;text-align:center}
#img-viewer-warn{position:absolute;top:20px;left:50%;transform:translateX(-50%);background:rgba(255,69,0,.15);border:1px solid var(--accent);color:var(--accent);padding:6px 14px;border-radius:20px;font-size:11px;letter-spacing:.5px}

/* 乾淨版:emoji 按鈕保持可用,但 emoji 面板關閉時 */
body.clean-mode #img-preview{box-shadow:none}
.err{color:#ff4444;font-size:12px;text-align:center;min-height:16px}
</style>
</head>
<body>
<div id="auth">
  <div class="auth-box">
    <h2>🔥 BURNER CHAT</h2>
    <p>端對端加密 · 焚後即毀 · 零留存</p>
    <input type="text" id="nickInput" placeholder="你的名字" maxlength="20" autofocus />
    <input type="password" id="pwd" placeholder="房間密碼" />
    <div id="err" class="err"></div>
    <button onclick="auth()">進入房間</button>
  </div>
</div>
<div id="header">
  <span class="logo">🔥</span>
  <h1>BURNER CHAT</h1>
  <span id="me-label"></span>
  <span id="sound-btn" class="sound-btn" onclick="toggleSound()">🔔</span>
  <span id="online">● 連線中...</span>
</div>
<div id="notice">焚後即毀模式 — 訊息不會落地儲存</div>
<div id="roster" class="collapsed">
  <span class="roster-toggle" onclick="toggleRoster()"></span>
  <span class="roster-list"></span>
</div>
<div id="sys-log" class="collapsed" style="display:none">
  <div class="sys-header">
    <span class="sys-last"></span>
    <span class="sys-toggle" onclick="toggleSysLog()"></span>
  </div>
  <div class="sys-full"></div>
</div>
<div id="burn-bar">
  <label>🔥 訊息存活時間:</label>
  <input type="number" id="burnSec" min="0" max="3600" value="30" />
  <span>秒</span>
  <button onclick="applyBurn()">套用</button>
  <span class="preset" onclick="setPreset(5)">5s</span>
  <span class="preset" onclick="setPreset(10)">10s</span>
  <span class="preset" onclick="setPreset(30)">30s</span>
  <span class="preset" onclick="setPreset(60)">60s</span>
  <span class="preset" onclick="setPreset(0)">永久</span>
  <span class="hint">0 = 永不消失 · 所有人同步</span>
</div>
<div id="msgs"></div>
<div id="input">
  <button id="clean-toggle" class="clean-btn" onclick="toggleCleanMode()" title="切換乾淨版"><img src="data:image/png;base64,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" alt="toggle"/></button>
  <input type="text" id="mi" placeholder="輸入訊息(Enter 發送)..." />
  <button id="send-btn" onclick="send()">發送</button>
</div>
<!-- Emoji Picker 彈出面板 -->
<div id="emoji-panel" style="display:none">
  <input type="text" id="emoji-search" placeholder="搜尋 emoji..." />
  <div id="emoji-tabs"></div>
  <div id="emoji-grid"></div>
</div>
<!-- 圖片預覽區(使用者選好還沒發送時) -->
<div id="img-preview" style="display:none">
  <img id="img-preview-thumb" />
  <span id="img-preview-size"></span>
  <button onclick="clearImagePreview()" title="取消">✕</button>
</div>
<!-- 圖片全螢幕檢視器 -->
<div id="img-viewer" style="display:none">
  <div id="img-viewer-stage">
    <div id="img-viewer-content"></div>
  </div>
  <div id="img-viewer-toolbar">
    <button onclick="viewerZoomOut()" title="縮小">−</button>
    <span id="img-viewer-zoom">100%</span>
    <button onclick="viewerZoomIn()" title="放大">+</button>
    <button onclick="viewerReset()" title="重設">重設</button>
    <button onclick="closeImageViewer()" title="關閉 (Esc)">✕</button>
  </div>
  <div id="img-viewer-warn" style="display:none">⚠ 請勿截圖或轉傳 · 訊息焚毀後圖片自動消失</div>
</div>
<!-- 隱藏的檔案 input -->
<input type="file" id="img-file-input" accept="image/jpeg,image/png,image/webp" style="display:none" />
<script>
// Input 左邊再加兩個按鈕(emoji + 圖片)
(function injectInputButtons(){
  const inp = document.getElementById('input');
  const cleanBtn = document.getElementById('clean-toggle');
  const mi = document.getElementById('mi');
  const emojiBtn = document.createElement('button');
  emojiBtn.id = 'emoji-toggle';
  emojiBtn.className = 'clean-btn';
  emojiBtn.title = 'Emoji';
  emojiBtn.textContent = '😀';
  emojiBtn.onclick = (e) => { e.stopPropagation(); toggleEmojiPicker(); };
  inp.insertBefore(emojiBtn, mi);
  const imgBtn = document.createElement('button');
  imgBtn.id = 'img-attach';
  imgBtn.className = 'clean-btn';
  imgBtn.title = '附加圖片';
  imgBtn.textContent = '📎';
  imgBtn.onclick = () => document.getElementById('img-file-input').click();
  inp.insertBefore(imgBtn, mi);
})();
</script>
<script>
const ROOM_ID = '${roomId}';
const BASE_TITLE = '🔥 BurnerChat';
let authToken = null, nick = '', clientId = null;
let sinceSeq = 0;         // 最後收到的 seq
let polling = false;      // polling loop 是否還活著
let pollAbortCtrl = null; // 當前 fetch 的 AbortController
let burnDuration = 30, unreadCount = 0, soundEnabled = true, audioCtx = null;
let cryptoKey = null; // AES-256-GCM key,從房間密碼派生
const msgReads = {}, sentReads = {};
// 訊息「尚未開始倒數」的暫存區
// 別人的訊息 → 等我 focus 輸入框才燒
// 自己的訊息 → 等所有人都讀過才燒 (readersNeeded 人次)
const pendingBurn = new Map();  // msgId -> { el, isMine, readersNeeded, readersGot }
// 線上名單 + UI 狀態
let roster = [];                // 當下線上使用者 nick 陣列
let rosterExpanded = false;     // 使用者手動切換
const ROSTER_COLLAPSE_THRESHOLD = 6;  // 超過這個人數預設折疊
// 系統訊息獨立區:最新 10 則,預設折疊只顯示最後一則
const sysMsgs = [];
const MAX_SYS_MSGS = 10;
let sysExpanded = false;
let cleanMode = false;  // 乾淨版(本地狀態,不發給 server)
// 聊天可見性:需要 (input focused) AND (document 在前景)
let inputFocused = false;
let heartbeatTimer = null;
const HEARTBEAT_INTERVAL = 15000;  // 15 秒 heartbeat
const HOST = location.host;

// ─── Emoji Picker 資料 + 功能 ──────────────────────────────────
const EMOJI_DATA=[{"e":"😀","k":"grin smile happy 笑 開心"},{"e":"😃","k":"smile happy 開心 笑"},{"e":"😄","k":"laugh happy 大笑 開心"},{"e":"😁","k":"grin teeth 露齒 笑"},{"e":"😆","k":"laugh happy 哈哈"},{"e":"😅","k":"sweat laugh 尷尬 笑"},{"e":"🤣","k":"rofl laugh 笑翻 笑哭"},{"e":"😂","k":"joy laugh tears 笑哭"},{"e":"🙂","k":"slight smile 微笑"},{"e":"🙃","k":"upside flip 倒立 倒過來"},{"e":"😉","k":"wink 眨眼"},{"e":"😊","k":"blush smile 害羞 微笑"},{"e":"😇","k":"angel halo 天使"},{"e":"🥰","k":"love heart 愛心"},{"e":"😍","k":"heart eyes 愛心眼"},{"e":"🤩","k":"star eyes 星星眼 驚嘆"},{"e":"😘","k":"kiss 親親 飛吻"},{"e":"😗","k":"kiss 吻"},{"e":"☺️","k":"smile blush 微笑"},{"e":"😚","k":"kiss closed 閉眼親"},{"e":"😙","k":"kiss smile 親"},{"e":"🥲","k":"tear smile 含淚笑"},{"e":"😋","k":"yum tongue 好吃"},{"e":"😛","k":"tongue 吐舌"},{"e":"😜","k":"wink tongue 調皮"},{"e":"🤪","k":"zany crazy 瘋狂"},{"e":"😝","k":"tongue closed 扮鬼臉"},{"e":"🤑","k":"money mouth 錢 貪財"},{"e":"🤗","k":"hug 擁抱"},{"e":"🤭","k":"hand mouth 偷笑 驚"},{"e":"🤫","k":"shush quiet 噓 安靜"},{"e":"🤔","k":"thinking 思考"},{"e":"🤐","k":"zipper mouth 閉嘴"},{"e":"🤨","k":"raised eyebrow 懷疑"},{"e":"😐","k":"neutral 面無表情"},{"e":"😑","k":"expressionless 無奈"},{"e":"😶","k":"no mouth 無言"},{"e":"😏","k":"smirk 奸笑"},{"e":"😒","k":"unamused 無聊 不爽"},{"e":"🙄","k":"roll eyes 翻白眼"},{"e":"😬","k":"grimace 尷尬"},{"e":"🤥","k":"lying nose 說謊"},{"e":"😌","k":"relieved 放鬆"},{"e":"😔","k":"pensive 難過 沉思"},{"e":"😪","k":"sleepy 想睡"},{"e":"🤤","k":"drooling 流口水"},{"e":"😴","k":"sleeping 睡覺"},{"e":"😷","k":"mask 口罩 生病"},{"e":"🤒","k":"thermometer sick 發燒"},{"e":"🤕","k":"head bandage 受傷"},{"e":"🤢","k":"nauseated 想吐"},{"e":"🤮","k":"vomit 吐"},{"e":"🤧","k":"sneeze 打噴嚏"},{"e":"🥵","k":"hot 熱"},{"e":"🥶","k":"cold 冷"},{"e":"🥴","k":"woozy 醉"},{"e":"😵","k":"dizzy 暈"},{"e":"🤯","k":"exploding 爆炸 震驚"},{"e":"🤠","k":"cowboy 牛仔"},{"e":"🥳","k":"party 派對 慶生"},{"e":"😎","k":"sunglasses cool 酷 墨鏡"},{"e":"🤓","k":"nerd 書呆子"},{"e":"🧐","k":"monocle 單片眼鏡"},{"e":"😕","k":"confused 困惑"},{"e":"😟","k":"worried 擔心"},{"e":"🙁","k":"frown 皺眉"},{"e":"☹️","k":"frowning 難過"},{"e":"😮","k":"surprised 驚訝"},{"e":"😯","k":"hushed 驚"},{"e":"😲","k":"astonished 驚訝"},{"e":"😳","k":"flushed 臉紅"},{"e":"🥺","k":"pleading 拜託"},{"e":"😦","k":"frown open 驚慌"},{"e":"😧","k":"anguished 痛苦"},{"e":"😨","k":"fearful 害怕"},{"e":"😰","k":"cold sweat 冷汗"},{"e":"😥","k":"sad relieved 難過"},{"e":"😢","k":"cry 哭"},{"e":"😭","k":"loud cry 大哭"},{"e":"😱","k":"scream 尖叫"},{"e":"😖","k":"confounded 糾結"},{"e":"😣","k":"persevering 努力"},{"e":"😞","k":"disappointed 失望"},{"e":"😓","k":"downcast sweat 汗顏"},{"e":"😩","k":"weary 累"},{"e":"😫","k":"tired 疲累"},{"e":"🥱","k":"yawn 哈欠"},{"e":"😤","k":"triumph angry 生氣 哼"},{"e":"😡","k":"pout rage 憤怒"},{"e":"😠","k":"angry 生氣"},{"e":"🤬","k":"cursing 罵人 髒話"},{"e":"😈","k":"devil smile 壞笑"},{"e":"👿","k":"devil angry 惡魔"},{"e":"💀","k":"skull 骷髏 死"},{"e":"👻","k":"ghost 鬼 幽靈"},{"e":"👽","k":"alien 外星人"},{"e":"🤖","k":"robot 機器人"},{"e":"💩","k":"poop 便便"},{"e":"👋","k":"wave hi 揮手 你好"},{"e":"🤚","k":"raised back 舉手"},{"e":"🖐️","k":"hand spread 五指張開"},{"e":"✋","k":"raised 舉手 停"},{"e":"🖖","k":"vulcan 瓦肯"},{"e":"👌","k":"ok perfect 好 完美"},{"e":"🤌","k":"pinched 捏"},{"e":"🤏","k":"pinch small 一點點"},{"e":"✌️","k":"peace victory 勝利 二"},{"e":"🤞","k":"crossed fingers 祈禱 希望"},{"e":"🤟","k":"love you 我愛你"},{"e":"🤘","k":"rock horns 搖滾"},{"e":"🤙","k":"call me 打電話"},{"e":"👈","k":"point left 指左"},{"e":"👉","k":"point right 指右"},{"e":"👆","k":"point up 指上"},{"e":"🖕","k":"middle finger 中指"},{"e":"👇","k":"point down 指下"},{"e":"☝️","k":"point up 食指"},{"e":"👍","k":"thumbs up 讚 好"},{"e":"👎","k":"thumbs down 噓 差"},{"e":"✊","k":"fist 拳頭"},{"e":"👊","k":"punch 揍"},{"e":"🤛","k":"left fist 拳"},{"e":"🤜","k":"right fist 拳"},{"e":"👏","k":"clap 拍手 鼓掌"},{"e":"🙌","k":"praise 舉手 萬歲"},{"e":"👐","k":"open hands 雙手"},{"e":"🤲","k":"palms up 攤手"},{"e":"🤝","k":"handshake 握手"},{"e":"🙏","k":"pray please 拜託 祈禱"},{"e":"✍️","k":"writing 寫字"},{"e":"💅","k":"nail polish 指甲油"},{"e":"🤳","k":"selfie 自拍"},{"e":"💪","k":"muscle 肌肉 加油"},{"e":"🦾","k":"mechanical arm 機械手"},{"e":"🦿","k":"mechanical leg 機械腿"},{"e":"🦵","k":"leg 腿"},{"e":"🦶","k":"foot 腳"},{"e":"👂","k":"ear 耳朵"},{"e":"❤️","k":"red heart 愛心 紅色"},{"e":"🧡","k":"orange heart 橘色愛心"},{"e":"💛","k":"yellow heart 黃色愛心"},{"e":"💚","k":"green heart 綠色愛心"},{"e":"💙","k":"blue heart 藍色愛心"},{"e":"💜","k":"purple heart 紫色愛心"},{"e":"🖤","k":"black heart 黑色愛心"},{"e":"🤍","k":"white heart 白色愛心"},{"e":"🤎","k":"brown heart 棕色愛心"},{"e":"💔","k":"broken heart 心碎"},{"e":"❣️","k":"heart exclamation 愛心驚嘆"},{"e":"💕","k":"two hearts 雙愛心"},{"e":"💞","k":"revolving hearts 旋轉愛心"},{"e":"💓","k":"beating heart 愛心跳動"},{"e":"💗","k":"growing heart 愛心放大"},{"e":"💖","k":"sparkling heart 閃亮愛心"},{"e":"💘","k":"cupid arrow 丘比特之箭"},{"e":"💝","k":"heart gift 禮物愛心"},{"e":"💟","k":"heart decoration 愛心"},{"e":"♥️","k":"suit heart 愛心"},{"e":"💌","k":"love letter 情書"},{"e":"😻","k":"heart eyes cat 愛心貓"},{"e":"💑","k":"couple heart 情侶"},{"e":"💏","k":"kiss couple 接吻"},{"e":"🎉","k":"party popper 慶祝 派對"},{"e":"🎊","k":"confetti 彩紙"},{"e":"🎂","k":"cake 蛋糕 生日"},{"e":"🎁","k":"gift present 禮物"},{"e":"🎈","k":"balloon 氣球"},{"e":"🎆","k":"fireworks 煙火"},{"e":"🎇","k":"sparkler 仙女棒"},{"e":"✨","k":"sparkles 閃亮"},{"e":"⭐","k":"star 星星"},{"e":"🌟","k":"glowing star 閃亮星星"},{"e":"💫","k":"dizzy stars 星星"},{"e":"🎀","k":"ribbon 蝴蝶結"},{"e":"🎗️","k":"reminder ribbon 紀念緞帶"},{"e":"🏆","k":"trophy 獎盃"},{"e":"🥇","k":"gold medal 金牌"},{"e":"🥈","k":"silver medal 銀牌"},{"e":"🥉","k":"bronze medal 銅牌"},{"e":"🎖️","k":"military medal 勳章"},{"e":"👑","k":"crown 皇冠"},{"e":"💎","k":"diamond 鑽石"},{"e":"🥂","k":"clinking glasses 乾杯"},{"e":"🍾","k":"champagne 香檳"},{"e":"🎵","k":"music note 音符"},{"e":"🎶","k":"music notes 音符"},{"e":"🍎","k":"red apple 蘋果"},{"e":"🍊","k":"orange 柳橙"},{"e":"🍋","k":"lemon 檸檬"},{"e":"🍌","k":"banana 香蕉"},{"e":"🍉","k":"watermelon 西瓜"},{"e":"🍇","k":"grapes 葡萄"},{"e":"🍓","k":"strawberry 草莓"},{"e":"🫐","k":"blueberries 藍莓"},{"e":"🍈","k":"melon 哈密瓜"},{"e":"🍒","k":"cherries 櫻桃"},{"e":"🍑","k":"peach 桃子"},{"e":"🥭","k":"mango 芒果"},{"e":"🍍","k":"pineapple 鳳梨"},{"e":"🥝","k":"kiwi 奇異果"},{"e":"🥥","k":"coconut 椰子"},{"e":"🍅","k":"tomato 番茄"},{"e":"🥑","k":"avocado 酪梨"},{"e":"🍆","k":"eggplant 茄子"},{"e":"🌽","k":"corn 玉米"},{"e":"🥕","k":"carrot 紅蘿蔔"},{"e":"🍞","k":"bread 麵包"},{"e":"🥐","k":"croissant 可頌"},{"e":"🥖","k":"baguette 法國麵包"},{"e":"🥨","k":"pretzel 椒鹽脆餅"},{"e":"🧀","k":"cheese 起司"},{"e":"🍳","k":"egg fried 煎蛋"},{"e":"🥞","k":"pancakes 鬆餅"},{"e":"🥓","k":"bacon 培根"},{"e":"🥩","k":"steak 牛排"},{"e":"🍗","k":"chicken drumstick 雞腿"},{"e":"🍖","k":"meat bone 肉"},{"e":"🌭","k":"hotdog 熱狗"},{"e":"🍔","k":"hamburger 漢堡"},{"e":"🍟","k":"fries 薯條"},{"e":"🍕","k":"pizza 披薩"},{"e":"🌮","k":"taco 墨西哥捲餅"},{"e":"🌯","k":"burrito 墨西哥捲"},{"e":"🥗","k":"salad 沙拉"},{"e":"🍝","k":"spaghetti 義大利麵"},{"e":"🍜","k":"ramen 拉麵"},{"e":"🍱","k":"bento 便當"},{"e":"🍣","k":"sushi 壽司"},{"e":"🍤","k":"shrimp 炸蝦"},{"e":"🍙","k":"rice ball 飯糰"},{"e":"🍚","k":"rice 白飯"},{"e":"🍘","k":"rice cracker 仙貝"},{"e":"🍢","k":"oden 關東煮"},{"e":"🍡","k":"dango 糯米糰"},{"e":"🥟","k":"dumpling 餃子"},{"e":"🍦","k":"ice cream soft 霜淇淋"},{"e":"🍧","k":"shaved ice 剉冰"},{"e":"🍨","k":"ice cream 冰淇淋"},{"e":"🍩","k":"donut 甜甜圈"},{"e":"🍪","k":"cookie 餅乾"},{"e":"🎂","k":"birthday cake 生日蛋糕"},{"e":"🍰","k":"cake 蛋糕"},{"e":"🧁","k":"cupcake 杯子蛋糕"},{"e":"🥧","k":"pie 派"},{"e":"🍫","k":"chocolate 巧克力"},{"e":"🍬","k":"candy 糖果"},{"e":"🍭","k":"lollipop 棒棒糖"},{"e":"🍮","k":"pudding 布丁"},{"e":"🍯","k":"honey 蜂蜜"},{"e":"☕","k":"coffee 咖啡"},{"e":"🍵","k":"tea 茶"},{"e":"🧋","k":"bubble tea 珍珠奶茶"},{"e":"🍺","k":"beer 啤酒"},{"e":"🍻","k":"cheers beer 乾杯"},{"e":"🍷","k":"wine 紅酒"},{"e":"🍸","k":"cocktail 雞尾酒"},{"e":"🍹","k":"tropical 熱帶飲料"},{"e":"🥤","k":"cup drink 飲料"},{"e":"🐶","k":"dog face 小狗"},{"e":"🐱","k":"cat face 小貓"},{"e":"🐭","k":"mouse 老鼠"},{"e":"🐹","k":"hamster 倉鼠"},{"e":"🐰","k":"rabbit face 兔子"},{"e":"🦊","k":"fox 狐狸"},{"e":"🐻","k":"bear 熊"},{"e":"🐼","k":"panda 熊貓"},{"e":"🐨","k":"koala 無尾熊"},{"e":"🐯","k":"tiger 老虎"},{"e":"🦁","k":"lion 獅子"},{"e":"🐮","k":"cow 牛"},{"e":"🐷","k":"pig 豬"},{"e":"🐸","k":"frog 青蛙"},{"e":"🐵","k":"monkey face 猴子"},{"e":"🙈","k":"see no evil 猴子摀眼"},{"e":"🙉","k":"hear no evil 猴子摀耳"},{"e":"🙊","k":"speak no evil 猴子摀嘴"},{"e":"🐒","k":"monkey 猴子"},{"e":"🐔","k":"chicken 雞"},{"e":"🐧","k":"penguin 企鵝"},{"e":"🐦","k":"bird 鳥"},{"e":"🐤","k":"baby chick 小雞"},{"e":"🦆","k":"duck 鴨子"},{"e":"🦅","k":"eagle 老鷹"},{"e":"🦉","k":"owl 貓頭鷹"},{"e":"🦇","k":"bat 蝙蝠"},{"e":"🐺","k":"wolf 狼"},{"e":"🐗","k":"boar 野豬"},{"e":"🐴","k":"horse face 馬"},{"e":"🦄","k":"unicorn 獨角獸"},{"e":"🐝","k":"bee 蜜蜂"},{"e":"🐛","k":"bug 毛毛蟲"},{"e":"🦋","k":"butterfly 蝴蝶"},{"e":"🐌","k":"snail 蝸牛"},{"e":"🐞","k":"ladybug 瓢蟲"},{"e":"🐜","k":"ant 螞蟻"},{"e":"🕷️","k":"spider 蜘蛛"},{"e":"🐢","k":"turtle 烏龜"},{"e":"🐍","k":"snake 蛇"},{"e":"🐙","k":"octopus 章魚"},{"e":"🦑","k":"squid 魷魚"},{"e":"🦐","k":"shrimp 蝦"},{"e":"🐟","k":"fish 魚"},{"e":"🐬","k":"dolphin 海豚"},{"e":"🐳","k":"whale 鯨魚"},{"e":"🦈","k":"shark 鯊魚"},{"e":"⚽","k":"soccer 足球"},{"e":"🏀","k":"basketball 籃球"},{"e":"🏈","k":"football 美式足球"},{"e":"⚾","k":"baseball 棒球"},{"e":"🎾","k":"tennis 網球"},{"e":"🏐","k":"volleyball 排球"},{"e":"🎱","k":"billiards 撞球"},{"e":"🏓","k":"ping pong 桌球"},{"e":"🏸","k":"badminton 羽球"},{"e":"🎯","k":"dart 飛鏢 目標"},{"e":"🎲","k":"dice 骰子"},{"e":"🎮","k":"game 電動"},{"e":"🕹️","k":"joystick 搖桿"},{"e":"🎨","k":"palette 調色盤"},{"e":"🎬","k":"clapperboard 場記板"},{"e":"📷","k":"camera 相機"},{"e":"📹","k":"video camera 攝影機"},{"e":"🎥","k":"movie camera 電影"},{"e":"📺","k":"tv 電視"},{"e":"📱","k":"phone 手機"},{"e":"💻","k":"laptop 筆電"},{"e":"🖥️","k":"desktop 桌電"},{"e":"⌨️","k":"keyboard 鍵盤"},{"e":"🖱️","k":"mouse 滑鼠"},{"e":"💾","k":"floppy 磁碟片"},{"e":"💿","k":"cd CD"},{"e":"📀","k":"dvd DVD"},{"e":"🔋","k":"battery 電池"},{"e":"🔌","k":"plug 插頭"},{"e":"💡","k":"bulb 燈泡 想法"},{"e":"🔦","k":"flashlight 手電筒"},{"e":"🕯️","k":"candle 蠟燭"},{"e":"📚","k":"books 書本"},{"e":"📖","k":"open book 開書"},{"e":"📝","k":"memo 筆記"},{"e":"✏️","k":"pencil 鉛筆"},{"e":"✒️","k":"pen 鋼筆"},{"e":"📎","k":"paperclip 迴紋針"},{"e":"📌","k":"pushpin 圖釘"},{"e":"📍","k":"round pin 地點"},{"e":"🔑","k":"key 鑰匙"},{"e":"🔒","k":"lock 鎖"},{"e":"🔓","k":"unlock 開鎖"},{"e":"🔔","k":"bell 鈴鐺"},{"e":"🔕","k":"bell mute 靜音"},{"e":"⏰","k":"alarm 鬧鐘"},{"e":"⏳","k":"hourglass 沙漏"},{"e":"☀️","k":"sun 太陽"},{"e":"🌙","k":"moon 月亮"},{"e":"⭐","k":"star 星"},{"e":"🌈","k":"rainbow 彩虹"},{"e":"☁️","k":"cloud 雲"},{"e":"⛅","k":"cloud sun 多雲"},{"e":"🌧️","k":"rain 下雨"},{"e":"⛈️","k":"thunderstorm 雷雨"},{"e":"❄️","k":"snowflake 雪"},{"e":"🔥","k":"fire 火 讚"},{"e":"💧","k":"drop 水滴"},{"e":"🌊","k":"wave 海浪"},{"e":"🚀","k":"rocket 火箭"},{"e":"✈️","k":"airplane 飛機"},{"e":"🚗","k":"car 汽車"},{"e":"🏠","k":"house 房子"},{"e":"⛔","k":"no entry 禁止"},{"e":"✅","k":"check 打勾"},{"e":"❌","k":"cross 叉"},{"e":"❓","k":"question 問號"},{"e":"❗","k":"exclamation 驚嘆"},{"e":"💯","k":"hundred 100 滿分"},{"e":"🎵","k":"music note 音符"}];
const EMOJI_CATS=[{"id":"face","icon":"😀","title":"表情","start":0,"end":98},{"id":"hand","icon":"👋","title":"手勢","start":98,"end":138},{"id":"heart","icon":"❤️","title":"愛","start":138,"end":162},{"id":"celebrate","icon":"🎉","title":"慶祝","start":162,"end":186},{"id":"food","icon":"🍎","title":"食物","start":186,"end":258},{"id":"animal","icon":"🐶","title":"動物","start":258,"end":305},{"id":"object","icon":"⚽","title":"物品","start":305,"end":375}];
let emojiActiveCat = 'face';
let pendingImage = null;  // 待發送的圖片 base64
// 待發送圖片的 data URL (含 data:image/jpeg;base64, 前綴)
let pendingImageSize = 0;

function renderEmojiGrid(filter){
  const grid = document.getElementById('emoji-grid');
  if(!grid) return;
  while(grid.firstChild) grid.removeChild(grid.firstChild);
  let items;
  if(filter && filter.trim().length > 0){
    const q = filter.toLowerCase();
    items = EMOJI_DATA.filter(x => x.k.toLowerCase().indexOf(q) !== -1 || x.e.indexOf(q) !== -1);
  } else {
    const cat = EMOJI_CATS.find(c => c.id === emojiActiveCat) || EMOJI_CATS[0];
    items = EMOJI_DATA.slice(cat.start, cat.end);
  }
  for(const it of items){
    const cell = document.createElement('div');
    cell.className = 'emoji-cell';
    cell.textContent = it.e;
    cell.title = it.k;
    cell.onclick = () => insertEmojiAtCursor(it.e);
    grid.appendChild(cell);
  }
}
function renderEmojiTabs(){
  const tabs = document.getElementById('emoji-tabs');
  if(!tabs) return;
  while(tabs.firstChild) tabs.removeChild(tabs.firstChild);
  for(const c of EMOJI_CATS){
    const t = document.createElement('span');
    t.className = 'tab' + (c.id === emojiActiveCat ? ' active' : '');
    t.textContent = c.icon;
    t.title = c.title;
    t.onclick = () => {
      emojiActiveCat = c.id;
      document.getElementById('emoji-search').value = '';
      renderEmojiTabs();
      renderEmojiGrid('');
    };
    tabs.appendChild(t);
  }
}
function insertEmojiAtCursor(emoji){
  const mi = document.getElementById('mi') || document.getElementById('msg-input');
  if(!mi) return;
  const start = mi.selectionStart || mi.value.length;
  const end = mi.selectionEnd || mi.value.length;
  mi.value = mi.value.slice(0, start) + emoji + mi.value.slice(end);
  const newPos = start + emoji.length;
  mi.focus();
  try { mi.setSelectionRange(newPos, newPos); } catch(e){}
}
function toggleEmojiPicker(){
  const p = document.getElementById('emoji-panel');
  const btn = document.getElementById('emoji-toggle');
  if(!p) return;
  if(p.style.display === 'none' || p.style.display === ''){
    p.style.display = 'block';
    if(btn) btn.classList.add('active');
    renderEmojiTabs();
    renderEmojiGrid('');
    const srch = document.getElementById('emoji-search');
    if(srch){ srch.value = ''; srch.focus(); }
  } else {
    p.style.display = 'none';
    if(btn) btn.classList.remove('active');
  }
}
// 點外面關閉
document.addEventListener('click', (e) => {
  const p = document.getElementById('emoji-panel');
  const btn = document.getElementById('emoji-toggle');
  if(!p || p.style.display === 'none') return;
  if(p.contains(e.target) || (btn && btn.contains(e.target))) return;
  p.style.display = 'none';
  if(btn) btn.classList.remove('active');
});
// 搜尋框過濾
(function bindEmojiSearch(){
  const wait = setInterval(() => {
    const s = document.getElementById('emoji-search');
    if(!s) return;
    clearInterval(wait);
    s.oninput = () => renderEmojiGrid(s.value);
  }, 100);
})();

// ─── 圖片上傳:壓縮後存到 pendingImage ──────────────────────────
const IMG_MAX_BYTES = 800 * 1024;   // 800 KB 上限
const IMG_MAX_DIM = 1280;

async function handleImageFile(file){
  if(!file) return;
  if(['image/jpeg','image/png','image/webp'].indexOf(file.type) === -1){
    alert('只支援 JPG / PNG / WebP');
    return;
  }
  try {
    const dataUrl = await new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.onerror = () => rej(r.error);
      r.readAsDataURL(file);
    });
    const img = await new Promise((res, rej) => {
      const im = new Image();
      im.onload = () => res(im);
      im.onerror = () => rej(new Error('圖片載入失敗'));
      im.src = dataUrl;
    });
    // 計算縮放後尺寸(最長邊 1280)
    let w = img.width, h = img.height;
    if(w > IMG_MAX_DIM || h > IMG_MAX_DIM){
      if(w > h){ h = Math.round(h * IMG_MAX_DIM / w); w = IMG_MAX_DIM; }
      else { w = Math.round(w * IMG_MAX_DIM / h); h = IMG_MAX_DIM; }
    }
    const canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, w, h);
    // 一律轉 JPEG 0.7 壓縮
    const compressed = canvas.toDataURL('image/jpeg', 0.7);
    const sizeBytes = Math.ceil(compressed.length * 3 / 4);
    if(sizeBytes > IMG_MAX_BYTES){
      // 再壓一次 0.5
      const again = canvas.toDataURL('image/jpeg', 0.5);
      const sz2 = Math.ceil(again.length * 3 / 4);
      if(sz2 > IMG_MAX_BYTES){
        alert('圖片太大(壓縮後仍超過 800 KB),請選較小的圖片');
        return;
      }
      pendingImage = again; pendingImageSize = sz2;
    } else {
      pendingImage = compressed; pendingImageSize = sizeBytes;
    }
    // 顯示預覽
    const prev = document.getElementById('img-preview');
    const thumb = document.getElementById('img-preview-thumb');
    const szEl = document.getElementById('img-preview-size');
    thumb.src = pendingImage;
    szEl.textContent = Math.round(pendingImageSize / 1024) + ' KB';
    prev.style.display = 'flex';
  } catch(e){
    alert('處理圖片失敗:' + e.message);
    pendingImage = null;
  }
  // 清除 input,同一檔案可再選一次
  const inp = document.getElementById('img-file-input');
  if(inp) inp.value = '';
}
function clearImagePreview(){
  pendingImage = null;
  pendingImageSize = 0;
  const prev = document.getElementById('img-preview');
  if(prev) prev.style.display = 'none';
}
(function bindImgInput(){
  const wait = setInterval(() => {
    const f = document.getElementById('img-file-input');
    if(!f) return;
    clearInterval(wait);
    f.onchange = (e) => handleImageFile(e.target.files && e.target.files[0]);
  }, 100);
})();

// ─── 圖片全螢幕檢視器 ──────────────────────────────────────────
let viewerZoom = 1;
let viewerPanX = 0, viewerPanY = 0;
let viewerCurrentMsgEl = null;  // 對應哪則訊息的圖(用來偵測是否被焚毀)
let viewerDevtoolsCheckTimer = null;

function openImageViewer(dataUrl, msgEl){
  const v = document.getElementById('img-viewer');
  const content = document.getElementById('img-viewer-content');
  const warn = document.getElementById('img-viewer-warn');
  if(!v || !content) return;
  viewerCurrentMsgEl = msgEl;
  viewerZoom = 1; viewerPanX = 0; viewerPanY = 0;
  content.style.backgroundImage = "url('" + dataUrl + "')";
  applyViewerTransform();
  v.style.display = 'flex';
  warn.style.display = 'block';
  setTimeout(() => { warn.style.display = 'none'; }, 3500);
  // F12 / devtools 偵測(用視窗內外高度差)
  startDevtoolsCheck();
  // 偵測原訊息被焚毀 → 自動關閉
  startMsgLiveCheck();
}
function closeImageViewer(){
  const v = document.getElementById('img-viewer');
  const content = document.getElementById('img-viewer-content');
  if(v) v.style.display = 'none';
  if(content) content.style.backgroundImage = '';
  viewerCurrentMsgEl = null;
  stopDevtoolsCheck();
  stopMsgLiveCheck();
}
function applyViewerTransform(){
  const content = document.getElementById('img-viewer-content');
  const zoomText = document.getElementById('img-viewer-zoom');
  if(!content) return;
  content.style.transform = 'translate(' + viewerPanX + 'px,' + viewerPanY + 'px) scale(' + viewerZoom + ')';
  if(zoomText) zoomText.textContent = Math.round(viewerZoom * 100) + '%';
}
function viewerZoomIn(){ viewerZoom = Math.min(5, viewerZoom + 0.25); applyViewerTransform(); }
function viewerZoomOut(){ viewerZoom = Math.max(0.25, viewerZoom - 0.25); if(viewerZoom <= 1){ viewerPanX = 0; viewerPanY = 0; } applyViewerTransform(); }
function viewerReset(){ viewerZoom = 1; viewerPanX = 0; viewerPanY = 0; applyViewerTransform(); }

// 滑鼠拖曳 + 滾輪縮放
(function bindViewer(){
  const wait = setInterval(() => {
    const stage = document.getElementById('img-viewer-stage');
    if(!stage) return;
    clearInterval(wait);
    let dragging = false, lastX = 0, lastY = 0;
    stage.addEventListener('mousedown', (e) => {
      if(viewerZoom <= 1) return;
      dragging = true; lastX = e.clientX; lastY = e.clientY;
      stage.classList.add('dragging');
    });
    document.addEventListener('mousemove', (e) => {
      if(!dragging) return;
      viewerPanX += e.clientX - lastX;
      viewerPanY += e.clientY - lastY;
      lastX = e.clientX; lastY = e.clientY;
      applyViewerTransform();
    });
    document.addEventListener('mouseup', () => {
      dragging = false;
      const st = document.getElementById('img-viewer-stage');
      if(st) st.classList.remove('dragging');
    });
    stage.addEventListener('wheel', (e) => {
      e.preventDefault();
      if(e.deltaY < 0) viewerZoomIn(); else viewerZoomOut();
    }, {passive: false});
    stage.addEventListener('click', (e) => {
      // 點黑色區域(非圖片中心)→ 關閉
      if(e.target === stage) closeImageViewer();
    });
    // ESC 關閉
    document.addEventListener('keydown', (e) => {
      const v = document.getElementById('img-viewer');
      if(v && v.style.display !== 'none' && e.key === 'Escape') closeImageViewer();
    });
    // 禁用右鍵(基本防另存)
    stage.addEventListener('contextmenu', (e) => e.preventDefault());
  }, 100);
})();

// F12 偵測(用視窗外框大小差:開啟 devtools 會讓外框 > 內部)
function startDevtoolsCheck(){
  stopDevtoolsCheck();
  viewerDevtoolsCheckTimer = setInterval(() => {
    const threshold = 160;
    const widthGap = window.outerWidth - window.innerWidth;
    const heightGap = window.outerHeight - window.innerHeight;
    if(widthGap > threshold || heightGap > threshold){
      const warn = document.getElementById('img-viewer-warn');
      if(warn){
        warn.textContent = '⚠ 偵測到開發者工具 · 請勿擷取內容';
        warn.style.display = 'block';
      }
    }
  }, 800);
}
function stopDevtoolsCheck(){
  if(viewerDevtoolsCheckTimer){ clearInterval(viewerDevtoolsCheckTimer); viewerDevtoolsCheckTimer = null; }
}
// 偵測原訊息 DOM 是否還在(被焚毀 → 自動關閉)
let msgLiveCheckTimer = null;
function startMsgLiveCheck(){
  stopMsgLiveCheck();
  msgLiveCheckTimer = setInterval(() => {
    if(!viewerCurrentMsgEl || !document.body.contains(viewerCurrentMsgEl)){
      closeImageViewer();
    }
  }, 500);
}
function stopMsgLiveCheck(){
  if(msgLiveCheckTimer){ clearInterval(msgLiveCheckTimer); msgLiveCheckTimer = null; }
}


// ─── E2E 加密 (AES-256-GCM, key 派生自房間密碼) ───
// 優先使用 Web Crypto API (HTTPS / localhost);否則 fallback 到純 JS 實作
// (因為 http://192.168.x.x 不是 secure context,瀏覽器會把 crypto.subtle 設為 undefined)
const HAS_SUBTLE = typeof crypto !== 'undefined' && crypto.subtle && typeof crypto.subtle.importKey === 'function';

function b64encode(buf){
  let s = ''; const b = new Uint8Array(buf);
  for(let i=0;i<b.length;i++) s += String.fromCharCode(b[i]);
  return btoa(s);
}
function b64decode(str){
  const s = atob(str); const b = new Uint8Array(s.length);
  for(let i=0;i<s.length;i++) b[i] = s.charCodeAt(i);
  return b;
}

// ── 純 JS fallback (SHA-256 / HMAC / PBKDF2 / AES-256-GCM) ──
const _K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
function _sha256(msg){
  const len=msg.length, bits=len*8, padLen=((len+9+63)>>6)<<6;
  const buf=new Uint8Array(padLen); buf.set(msg); buf[len]=0x80;
  const dv=new DataView(buf.buffer);
  dv.setUint32(padLen-4, bits>>>0, false);
  dv.setUint32(padLen-8, Math.floor(bits/0x100000000), false);
  let h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
  const W=new Uint32Array(64);
  for(let i=0;i<padLen;i+=64){
    for(let t=0;t<16;t++) W[t]=dv.getUint32(i+t*4,false);
    for(let t=16;t<64;t++){
      const x=W[t-15],y=W[t-2];
      const s0=((x>>>7)|(x<<25))^((x>>>18)|(x<<14))^(x>>>3);
      const s1=((y>>>17)|(y<<15))^((y>>>19)|(y<<13))^(y>>>10);
      W[t]=(W[t-16]+s0+W[t-7]+s1)>>>0;
    }
    let a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;
    for(let t=0;t<64;t++){
      const S1=((e>>>6)|(e<<26))^((e>>>11)|(e<<21))^((e>>>25)|(e<<7));
      const ch=(e&f)^(~e&g);
      const T1=(h+S1+ch+_K[t]+W[t])>>>0;
      const S0=((a>>>2)|(a<<30))^((a>>>13)|(a<<19))^((a>>>22)|(a<<10));
      const mj=(a&b)^(a&c)^(b&c);
      const T2=(S0+mj)>>>0;
      h=g;g=f;f=e;e=(d+T1)>>>0;d=c;c=b;b=a;a=(T1+T2)>>>0;
    }
    h0=(h0+a)>>>0;h1=(h1+b)>>>0;h2=(h2+c)>>>0;h3=(h3+d)>>>0;h4=(h4+e)>>>0;h5=(h5+f)>>>0;h6=(h6+g)>>>0;h7=(h7+h)>>>0;
  }
  const out=new Uint8Array(32),odv=new DataView(out.buffer);
  odv.setUint32(0,h0,false);odv.setUint32(4,h1,false);odv.setUint32(8,h2,false);odv.setUint32(12,h3,false);
  odv.setUint32(16,h4,false);odv.setUint32(20,h5,false);odv.setUint32(24,h6,false);odv.setUint32(28,h7,false);
  return out;
}
function _hmac(key,msg){
  let k=key; if(k.length>64) k=_sha256(k);
  const k0=new Uint8Array(64); k0.set(k);
  const ipad=new Uint8Array(64),opad=new Uint8Array(64);
  for(let i=0;i<64;i++){ipad[i]=k0[i]^0x36;opad[i]=k0[i]^0x5c;}
  const inner=new Uint8Array(64+msg.length); inner.set(ipad); inner.set(msg,64);
  const ih=_sha256(inner);
  const outer=new Uint8Array(96); outer.set(opad); outer.set(ih,64);
  return _sha256(outer);
}
function _pbkdf2(pwd,salt,iter,dkLen){
  const blocks=Math.ceil(dkLen/32), out=new Uint8Array(blocks*32);
  for(let i=1;i<=blocks;i++){
    const sI=new Uint8Array(salt.length+4); sI.set(salt);
    new DataView(sI.buffer).setUint32(salt.length,i,false);
    let U=_hmac(pwd,sI); const T=new Uint8Array(U);
    for(let j=1;j<iter;j++){U=_hmac(pwd,U); for(let k=0;k<32;k++) T[k]^=U[k];}
    out.set(T,(i-1)*32);
  }
  return out.slice(0,dkLen);
}
const _SBOX=new Uint8Array([99,124,119,123,242,107,111,197,48,1,103,43,254,215,171,118,202,130,201,125,250,89,71,240,173,212,162,175,156,164,114,192,183,253,147,38,54,63,247,204,52,165,229,241,113,216,49,21,4,199,35,195,24,150,5,154,7,18,128,226,235,39,178,117,9,131,44,26,27,110,90,160,82,59,214,179,41,227,47,132,83,209,0,237,32,252,177,91,106,203,190,57,74,76,88,207,208,239,170,251,67,77,51,133,69,249,2,127,80,60,159,168,81,163,64,143,146,157,56,245,188,182,218,33,16,255,243,210,205,12,19,236,95,151,68,23,196,167,126,61,100,93,25,115,96,129,79,220,34,42,144,136,70,238,184,20,222,94,11,219,224,50,58,10,73,6,36,92,194,211,172,98,145,149,228,121,231,200,55,109,141,213,78,169,108,86,244,234,101,122,174,8,186,120,37,46,28,166,180,198,232,221,116,31,75,189,139,138,112,62,181,102,72,3,246,14,97,53,87,185,134,193,29,158,225,248,152,17,105,217,142,148,155,30,135,233,206,85,40,223,140,161,137,13,191,230,66,104,65,153,45,15,176,84,187,22]);
const _RCON=new Uint8Array([0,1,2,4,8,16,32,64,128,27,54]);
function _xt(b){return((b<<1)^(((b>>7)&1)*0x1b))&0xff;}
function _aesExp(key){
  const Nk=8,Nr=14, w=new Uint8Array(240), temp=new Uint8Array(4);
  w.set(key);
  for(let i=Nk;i<4*(Nr+1);i++){
    temp[0]=w[(i-1)*4];temp[1]=w[(i-1)*4+1];temp[2]=w[(i-1)*4+2];temp[3]=w[(i-1)*4+3];
    if(i%Nk===0){
      const t=temp[0];temp[0]=temp[1];temp[1]=temp[2];temp[2]=temp[3];temp[3]=t;
      temp[0]=_SBOX[temp[0]];temp[1]=_SBOX[temp[1]];temp[2]=_SBOX[temp[2]];temp[3]=_SBOX[temp[3]];
      temp[0]^=_RCON[i/Nk];
    } else if(i%Nk===4){
      temp[0]=_SBOX[temp[0]];temp[1]=_SBOX[temp[1]];temp[2]=_SBOX[temp[2]];temp[3]=_SBOX[temp[3]];
    }
    w[i*4]=w[(i-Nk)*4]^temp[0]; w[i*4+1]=w[(i-Nk)*4+1]^temp[1];
    w[i*4+2]=w[(i-Nk)*4+2]^temp[2]; w[i*4+3]=w[(i-Nk)*4+3]^temp[3];
  }
  return w;
}
function _aesEnc(block,w){
  const Nr=14, s=new Uint8Array(block);
  for(let i=0;i<16;i++) s[i]^=w[i];
  for(let r=1;r<Nr;r++){
    for(let i=0;i<16;i++) s[i]=_SBOX[s[i]];
    let t;
    t=s[1];s[1]=s[5];s[5]=s[9];s[9]=s[13];s[13]=t;
    t=s[2];s[2]=s[10];s[10]=t;t=s[6];s[6]=s[14];s[14]=t;
    t=s[15];s[15]=s[11];s[11]=s[7];s[7]=s[3];s[3]=t;
    for(let c=0;c<4;c++){
      const a0=s[c*4],a1=s[c*4+1],a2=s[c*4+2],a3=s[c*4+3];
      const all=a0^a1^a2^a3;
      s[c*4]^=all^_xt(a0^a1); s[c*4+1]^=all^_xt(a1^a2);
      s[c*4+2]^=all^_xt(a2^a3); s[c*4+3]^=all^_xt(a3^a0);
    }
    for(let i=0;i<16;i++) s[i]^=w[r*16+i];
  }
  for(let i=0;i<16;i++) s[i]=_SBOX[s[i]];
  let t;
  t=s[1];s[1]=s[5];s[5]=s[9];s[9]=s[13];s[13]=t;
  t=s[2];s[2]=s[10];s[10]=t;t=s[6];s[6]=s[14];s[14]=t;
  t=s[15];s[15]=s[11];s[11]=s[7];s[7]=s[3];s[3]=t;
  for(let i=0;i<16;i++) s[i]^=w[Nr*16+i];
  return s;
}
function _gmul(X,Y){
  const Z=new Uint8Array(16),V=new Uint8Array(Y);
  for(let i=0;i<128;i++){
    if((X[i>>3]>>(7-(i&7)))&1){for(let j=0;j<16;j++) Z[j]^=V[j];}
    const lsb=V[15]&1;
    for(let j=15;j>0;j--) V[j]=(V[j]>>>1)|((V[j-1]&1)<<7);
    V[0]>>>=1; if(lsb) V[0]^=0xe1;
  }
  return Z;
}
function _ghash(H,data){
  const Y=new Uint8Array(16);
  for(let i=0;i<data.length;i+=16){
    const blk=new Uint8Array(16); blk.set(data.slice(i,i+16));
    for(let j=0;j<16;j++) Y[j]^=blk[j];
    Y.set(_gmul(Y,H));
  }
  return Y;
}
function _gcmEnc(key,iv,plain){
  const w=_aesExp(key), H=_aesEnc(new Uint8Array(16),w);
  const J0=new Uint8Array(16); J0.set(iv); J0[15]=1;
  const ct=new Uint8Array(plain.length), ctr=new Uint8Array(J0);
  for(let i=0;i<plain.length;i+=16){
    for(let j=15;j>=12;j--){ctr[j]=(ctr[j]+1)&0xff; if(ctr[j]!==0) break;}
    const ks=_aesEnc(ctr,w);
    const bl=Math.min(16,plain.length-i);
    for(let j=0;j<bl;j++) ct[i+j]=plain[i+j]^ks[j];
  }
  const ctPad=ct.length%16===0?0:16-(ct.length%16);
  const gIn=new Uint8Array(ct.length+ctPad+16);
  gIn.set(ct);
  new DataView(gIn.buffer).setUint32(gIn.length-4, ct.length*8, false);
  const S=_ghash(H,gIn);
  const ekJ0=_aesEnc(J0,w), tag=new Uint8Array(16);
  for(let i=0;i<16;i++) tag[i]=S[i]^ekJ0[i];
  const out=new Uint8Array(ct.length+16);
  out.set(ct); out.set(tag,ct.length);
  return out;
}
function _gcmDec(key,iv,combined){
  if(combined.length<16) throw new Error('ciphertext too short');
  const ct=combined.slice(0,combined.length-16), tag=combined.slice(combined.length-16);
  const w=_aesExp(key), H=_aesEnc(new Uint8Array(16),w);
  const J0=new Uint8Array(16); J0.set(iv); J0[15]=1;
  const ctPad=ct.length%16===0?0:16-(ct.length%16);
  const gIn=new Uint8Array(ct.length+ctPad+16);
  gIn.set(ct);
  new DataView(gIn.buffer).setUint32(gIn.length-4, ct.length*8, false);
  const S=_ghash(H,gIn);
  const ekJ0=_aesEnc(J0,w);
  let diff=0;
  for(let i=0;i<16;i++) diff|=(S[i]^ekJ0[i])^tag[i];
  if(diff!==0) throw new Error('Auth tag mismatch');
  const pt=new Uint8Array(ct.length), ctr=new Uint8Array(J0);
  for(let i=0;i<ct.length;i+=16){
    for(let j=15;j>=12;j--){ctr[j]=(ctr[j]+1)&0xff; if(ctr[j]!==0) break;}
    const ks=_aesEnc(ctr,w);
    const bl=Math.min(16,ct.length-i);
    for(let j=0;j<bl;j++) pt[i+j]=ct[i+j]^ks[j];
  }
  return pt;
}
function _randBytes(n){
  if(typeof crypto!=='undefined' && crypto.getRandomValues){
    const b=new Uint8Array(n); crypto.getRandomValues(b); return b;
  }
  const b=new Uint8Array(n);
  for(let i=0;i<n;i++) b[i]=Math.floor(Math.random()*256);
  return b;
}

// ── 統一介面 ──
async function deriveKey(password, salt){
  const enc = new TextEncoder();
  if(HAS_SUBTLE){
    const baseKey = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey(
      { name:'PBKDF2', salt: enc.encode(salt), iterations: 200000, hash: 'SHA-256' },
      baseKey, { name:'AES-GCM', length: 256 }, false, ['encrypt','decrypt']
    );
  }
  return _pbkdf2(enc.encode(password), enc.encode(salt), 50000, 32);
}
async function encryptText(plaintext){
  if(!cryptoKey) throw new Error('no key');
  const iv = _randBytes(12);
  const ptBytes = new TextEncoder().encode(plaintext);
  let ctBuf;
  if(HAS_SUBTLE){
    ctBuf = new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM', iv}, cryptoKey, ptBytes));
  } else {
    ctBuf = _gcmEnc(cryptoKey, iv, ptBytes);
  }
  return { ct: b64encode(ctBuf), iv: b64encode(iv) };
}
async function decryptText(payload){
  if(!cryptoKey || !payload || !payload.ct || !payload.iv) throw new Error('bad payload');
  const ctBytes = b64decode(payload.ct);
  const ivBytes = b64decode(payload.iv);
  let pt;
  if(HAS_SUBTLE){
    pt = await crypto.subtle.decrypt({name:'AES-GCM', iv: ivBytes}, cryptoKey, ctBytes);
  } else {
    pt = _gcmDec(cryptoKey, ivBytes, ctBytes);
  }
  return new TextDecoder().decode(pt);
}

function ensureAudioCtx(){
  if(!audioCtx){ try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e){} }
  if(audioCtx && audioCtx.state === 'suspended'){ try { audioCtx.resume(); } catch(e){} }
  return audioCtx;
}
function playNotify(){
  if(!soundEnabled) return;
  const ctx = ensureAudioCtx(); if(!ctx) return;
  const now = ctx.currentTime;
  function tone(f,s,d,v){ try {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type='sine'; o.frequency.value=f;
    g.gain.setValueAtTime(0, now+s);
    g.gain.linearRampToValueAtTime(v, now+s+0.008);
    g.gain.exponentialRampToValueAtTime(0.001, now+s+d);
    o.connect(g); g.connect(ctx.destination);
    o.start(now+s); o.stop(now+s+d+0.02);
  } catch(e){} }
  tone(784,0,0.22,0.14); tone(1568,0,0.22,0.035); tone(2352,0,0.22,0.015);
  tone(1047,0.09,0.40,0.16); tone(2094,0.09,0.40,0.04); tone(3141,0.09,0.40,0.017);
}
function toggleSound(){
  soundEnabled = !soundEnabled;
  const btn = document.getElementById('sound-btn');
  btn.textContent = soundEnabled ? '🔔' : '🔕';
  if(soundEnabled){ ensureAudioCtx(); playNotify(); }
}
function updateTitle(){
  document.title = unreadCount > 0 ? '(' + unreadCount + ') ' + BASE_TITLE : BASE_TITLE;
}
document.addEventListener('visibilitychange', () => {
  if(!document.hidden && unreadCount > 0){ unreadCount = 0; updateTitle(); }
  updateChatVisibility();
});

function auth() {
  const name = document.getElementById('nickInput').value.trim();
  const pwd = document.getElementById('pwd').value;
  const errEl = document.getElementById('err');
  if(!name){ errEl.textContent = '❌ 請輸入名字'; return; }
  if(!pwd){ errEl.textContent = '❌ 請輸入密碼'; return; }
  ensureAudioCtx();

  fetch('/auth', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({roomId: ROOM_ID, password: pwd, nickname: name})
  })
  .then(r => r.json()).then(async d => {
    if(d.ok){
      try {
        cryptoKey = await deriveKey(pwd, 'burnerchat-v1:' + ROOM_ID);
      } catch(e){
        errEl.textContent = '❌ 加密初始化失敗:' + (e.message || e);
        return;
      }
      authToken = d.token;
      nick = d.nick;
      clientId = d.clientId;
      sinceSeq = d.since || 0;
      if (typeof d.burnDuration === 'number') {
        burnDuration = d.burnDuration;
        const bs = document.getElementById('burnSec');
        if (bs) bs.value = burnDuration;
      }
      // 初始化 roster(從 /auth 回應拿到當下的 nick 清單)
      roster = Array.isArray(d.nicks) ? d.nicks.slice() : [];
      rosterExpanded = false;
      renderRoster();
      // 預設遮罩(還沒 focus 輸入框)
      updateChatVisibility();
      // 啟動 heartbeat
      startHeartbeat();
      document.getElementById('me-label').textContent = '@' + nick;
      document.getElementById('auth').style.display = 'none';
      startPolling();
      onConnected();
    } else {
      errEl.textContent = '❌ ' + (d.error || '認證失敗');
      setTimeout(()=>errEl.textContent='', 2500);
    }
  }).catch(()=>errEl.textContent = '❌ 無法連線');
}

function onConnected() {
  const mi = document.getElementById('mi');
  const el = document.getElementById('online');
  el.textContent = '● 已連線 🔒'; el.style.color = '#00ff88';
  el.title = '訊息使用 AES-256-GCM 端對端加密 + HTTP long polling';
  addSys('🔥 已加入焚模式聊天室 (🔒 端對端加密)');
  mi.disabled = false;
  mi.placeholder = '輸入訊息(Enter 發送)...';
  mi.focus();
}

function onDisconnected(reason) {
  const mi = document.getElementById('mi');
  const el = document.getElementById('online');
  el.textContent = '● 已斷線';
  el.style.color = '#ff4500';
  addSys('🔥 ' + (reason || '連線已關閉'));
  mi.disabled = true;
  mi.placeholder = '已斷線';
}

// ─── Long polling loop ──────────────────────────────────────────
async function startPolling() {
  if (polling) return;
  polling = true;
  let backoff = 0;
  while (polling) {
    pollAbortCtrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    try {
      const url = '/poll?token=' + encodeURIComponent(authToken) + '&since=' + sinceSeq;
      const opts = pollAbortCtrl ? { signal: pollAbortCtrl.signal } : {};
      const r = await fetch(url, opts);
      if (r.status === 401 || r.status === 404) {
        polling = false;
        resetToLogin('連線逾時或已被管理員移除,請重新登入');
        return;
      }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json();
      backoff = 0;  // 重置 backoff
      if (d.events && d.events.length > 0) {
        for (const ev of d.events) {
          await handleEvent(ev);
        }
        sinceSeq = d.nextSince;
      } else if (typeof d.nextSince === 'number') {
        sinceSeq = d.nextSince;
      }
    } catch(e) {
      if (e.name === 'AbortError') break;
      // 網路斷線:指數 backoff 重試,最多 10 秒
      backoff = Math.min(10000, (backoff || 500) * 2);
      await new Promise(r => setTimeout(r, backoff));
    }
  }
}

function stopPolling() {
  polling = false;
  if (pollAbortCtrl) { try { pollAbortCtrl.abort(); } catch(e){} }
}

async function handleEvent(d) {
  if (d.type === 'chat') {
    let text = '', image = null;
    try {
      const raw = await decryptText(d.encrypted);
      // 新格式:JSON({text, image});舊格式:純 string
      if (raw && raw.length > 0 && raw.charAt(0) === '{') {
        try {
          const obj = JSON.parse(raw);
          text = obj.text || '';
          image = obj.image || null;
        } catch(e) { text = raw; }
      } else {
        text = raw;
      }
    }
    catch(err){ text = '⚠ [無法解密 — 密碼不一致或訊息毀損]'; }
    addMsg(d.sender, text, d.sender === nick, d.msgId, d.expectedReaders, image);
  }
  else if (d.type === 'system') addSys(d.text);
  else if (d.type === 'burnUpdate') {
    burnDuration = d.duration;
    document.getElementById('burnSec').value = burnDuration;
    if (!d.silent) addSys('⏱ ' + d.by + ' 設定訊息存活為 ' + (burnDuration === 0 ? '永久' : burnDuration + ' 秒'));
  }
  else if (d.type === 'read') {
    markRead(d.msgId, d.reader);
    // 若是別人讀了我的訊息,檢查是否湊齊所有讀者
    if (d.reader !== nick) tickMineReaders(d.msgId);
  }
  else if (d.type === 'presenceChange') {
    if (Array.isArray(d.nicks)) {
      roster = d.nicks.slice();
      renderRoster();
    }
    onPresenceChange(d.onlineCount);
  }
  else if (d.type === 'roomDeleted') {
    resetToLogin('此房間已被管理員刪除');
  }
}

// 統一發送 helper (取代原本的 wsSend)
async function apiSend(payload) {
  if (!authToken) return false;
  try {
    const r = await fetch('/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({ token: authToken }, payload))
    });
    return r.ok;
  } catch(e) { return false; }
}

// ─── 線上名單(roster) ──────────────────────────────────────────────
function renderRoster() {
  const el = document.getElementById('roster');
  if (!el) return;
  const list = el.querySelector('.roster-list');
  const toggle = el.querySelector('.roster-toggle');
  const n = roster.length;
  // 超過門檻 + 使用者沒展開 → 折疊
  const shouldCollapse = n > ROSTER_COLLAPSE_THRESHOLD && !rosterExpanded;
  if (shouldCollapse) {
    el.classList.add('collapsed');
    toggle.textContent = '▼ 展開 ' + n + ' 人';
  } else {
    el.classList.remove('collapsed');
    toggle.textContent = n > ROSTER_COLLAPSE_THRESHOLD ? '▲ 收合' : '👥';
    list.textContent = '線上 (' + n + '):' + roster.join(', ');
  }
}
function toggleRoster() {
  rosterExpanded = !rosterExpanded;
  renderRoster();
}

// ─── 系統訊息獨立區 ──────────────────────────────────────────────
function addSysEntry(text) {
  sysMsgs.push(text);
  if (sysMsgs.length > MAX_SYS_MSGS) sysMsgs.shift();
  renderSysLog();
}
function renderSysLog() {
  const el = document.getElementById('sys-log');
  if (!el) return;
  const last = el.querySelector('.sys-last');
  const full = el.querySelector('.sys-full');
  const toggle = el.querySelector('.sys-toggle');
  const n = sysMsgs.length;
  if (n === 0) { el.style.display = 'none'; return; }
  el.style.display = '';
  last.textContent = '⚙️ ' + sysMsgs[n - 1];
  while (full.firstChild) full.removeChild(full.firstChild);
  for (const m of sysMsgs) {
    const line = document.createElement('div');
    line.className = 'sys-line';
    line.textContent = '⚙️ ' + m;
    full.appendChild(line);
  }
  if (n === 1) {
    toggle.textContent = '';
    toggle.style.display = 'none';
    el.classList.add('collapsed');
  } else {
    toggle.style.display = '';
    toggle.textContent = sysExpanded ? '▲ 收合' : ('▼ 展開 ' + n + ' 則');
    if (sysExpanded) el.classList.remove('collapsed');
    else el.classList.add('collapsed');
  }
}
function toggleSysLog() {
  sysExpanded = !sysExpanded;
  renderSysLog();
}

// 乾淨版(本地狀態):隱藏 header/notice/roster/sys-log/burn-bar,只保留訊息區與輸入列
function toggleCleanMode() {
  cleanMode = !cleanMode;
  const btn = document.getElementById('clean-toggle');
  const input = document.getElementById('mi');
  if (cleanMode) {
    document.body.classList.add('clean-mode');
    if (btn) btn.classList.add('active');
    if (input) {
      input.dataset.originalPlaceholder = input.placeholder || '';
      input.placeholder = '';
    }
  } else {
    document.body.classList.remove('clean-mode');
    if (btn) btn.classList.remove('active');
    if (input && input.dataset.originalPlaceholder !== undefined) {
      input.placeholder = input.dataset.originalPlaceholder;
    } else if (input) {
      input.placeholder = '輸入訊息(Enter 發送)...';
    }
  }
}

// ─── 聊天顯示 / 遮罩邏輯 ──────────────────────────────────────────────
function updateChatVisibility() {
  const msgsEl = document.getElementById('msgs');
  if (!msgsEl) return;
  const visible = inputFocused && !document.hidden;
  if (visible) {
    msgsEl.classList.remove('redacted');
  } else {
    msgsEl.classList.add('redacted');
  }
}

// ─── Heartbeat ─────────────────────────────────────────────────────
function startHeartbeat() {
  stopHeartbeat();
  heartbeatTimer = setInterval(() => {
    apiSend({ type: 'heartbeat' });
  }, HEARTBEAT_INTERVAL);
}
function stopHeartbeat() {
  if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null; }
}

// ─── 重置到登入畫面(被 reap / admin 踢 / 401) ───────────────────────
function resetToLogin(reason) {
  // 停止各種迴圈
  stopPolling();
  stopHeartbeat();
  // 清本地狀態
  authToken = null; nick = ''; clientId = null; cryptoKey = null;
  sinceSeq = 0;
  roster = []; rosterExpanded = false;
  sysMsgs.length = 0; sysExpanded = false;
  // 解除乾淨版(不然登入畫面被 clean-mode 蓋住)
  cleanMode = false;
  document.body.classList.remove('clean-mode');
  const cleanBtn = document.getElementById('clean-toggle');
  if (cleanBtn) cleanBtn.classList.remove('active');
  pendingBurn.clear();
  for (const k in msgReads) delete msgReads[k];
  for (const k in sentReads) delete sentReads[k];
  unreadCount = 0; updateTitle();
  // 清 DOM
  const msgsEl = document.getElementById('msgs');
  if (msgsEl) { msgsEl.innerHTML = ''; msgsEl.classList.remove('redacted'); }
  renderRoster();
  renderSysLog();
  // 顯示登入 overlay
  const authEl = document.getElementById('auth');
  if (authEl) authEl.style.display = 'flex';
  const err = document.getElementById('err');
  if (err && reason) { err.textContent = '⚠ ' + reason; setTimeout(() => err.textContent = '', 4000); }
  // disable 訊息輸入
  const mi = document.getElementById('mi');
  if (mi) { mi.disabled = true; mi.placeholder = '請先登入'; mi.value = ''; }
  // 連線狀態
  const online = document.getElementById('online');
  if (online) { online.textContent = '● 連線中...'; online.style.color = ''; }
  // focus 登入名稱欄位
  const nickInput = document.getElementById('nickInput');
  if (nickInput) nickInput.focus();
}

function applyBurn(){
  const v = parseInt(document.getElementById('burnSec').value);
  if(isNaN(v) || v < 0) return;
  apiSend({type:'setBurn', duration: Math.min(3600, v)});
}
function setPreset(n){ document.getElementById('burnSec').value = n; applyBurn(); }

function scheduleBurn(el, extraDelay){
  if(burnDuration <= 0) return;
  const cd = document.createElement('div'); cd.className = 'countdown'; el.appendChild(cd);
  let r = burnDuration + (extraDelay || 0); cd.textContent = '🔥 ' + r + 's';
  const iv = setInterval(()=>{
    r--;
    if(r <= 2) el.classList.add('burning');
    if(r <= 0){
      clearInterval(iv);
      el.style.opacity = '0'; el.style.transform = 'translateX(30px) scale(.9)';
      setTimeout(()=>{ el.style.maxHeight = '0'; el.style.margin = '0'; el.style.padding = '0'; el.style.overflow = 'hidden'; }, 100);
      setTimeout(()=>el.remove(), 800); return;
    }
    cd.textContent = '🔥 ' + r + 's';
  }, 1000);
}

function markRead(msgId, reader){
  if(!msgId || !reader) return;
  if(!msgReads[msgId]) msgReads[msgId] = [];
  if(msgReads[msgId].indexOf(reader) === -1) msgReads[msgId].push(reader);
  updateReadIndicator(msgId);
}
function updateReadIndicator(msgId){
  const el = document.querySelector('[data-msg-id="' + msgId + '"]'); if(!el) return;
  const rs = msgReads[msgId] || []; if(rs.length === 0) return;
  let ind = el.querySelector('.readby');
  if(!ind){
    ind = document.createElement('div'); ind.className = 'readby';
    const cd = el.querySelector('.countdown');
    if(cd) el.insertBefore(ind, cd); else el.appendChild(ind);
  }
  // 拆成兩個 span:.check(永遠可見) + .names(乾淨版隱藏)
  while (ind.firstChild) ind.removeChild(ind.firstChild);
  const checkSpan = document.createElement('span');
  checkSpan.className = 'check';
  checkSpan.textContent = '✓';
  const namesSpan = document.createElement('span');
  namesSpan.className = 'names';
  namesSpan.textContent = ' 已讀: ' + (rs.length <= 3 ? rs.join(', ') : rs.slice(0,3).join(', ') + ' +' + (rs.length-3));
  ind.appendChild(checkSpan);
  ind.appendChild(namesSpan);
}

function addMsg(sender, text, isMe, msgId, expectedReaders, image){
  const m = document.getElementById('msgs');
  const d = document.createElement('div');
  d.className = 'msg ' + (isMe ? 'me' : 'other');
  if(msgId) d.setAttribute('data-msg-id', msgId);
  const maskLen = Math.min(30, Math.max(4, Math.ceil((text || '').length / 2) || 4));
  const mask = '█'.repeat(maskLen);
  const bubbleInner = '<div class="sender">' + escHtml(sender) +
    '</div><div class="bubble">' +
    (text ? '<span class="text-content" data-mask="' + mask + '">' + escHtml(text) + '</span>' : '') +
    '</div>';
  d.innerHTML = bubbleInner;
  // 若有圖片:以 background-image 形式附加(防右鍵另存)
  if(image){
    const imgDiv = document.createElement('div');
    imgDiv.className = 'msg-image';
    imgDiv.style.backgroundImage = "url('" + image + "')";
    imgDiv.addEventListener('click', () => openImageViewer(image, d));
    imgDiv.addEventListener('contextmenu', (e) => e.preventDefault());
    d.querySelector('.bubble').appendChild(imgDiv);
  }
  m.appendChild(d); m.scrollTop = m.scrollHeight;

  // 倒數觸發邏輯
  // - 自己的訊息:若當下沒人需要讀 (expectedReaders === 0),立刻燒;否則等 read event 湊齊
  // - 別人的訊息:加 unread 標記,等我 focus 輸入框才燒
  if (isMe) {
    const need = Math.max(0, expectedReaders || 0);
    if (need === 0) {
      scheduleBurn(d);
    } else if (msgId) {
      pendingBurn.set(msgId, { el: d, isMine: true, readersNeeded: need, readersGot: 0 });
    }
  } else {
    d.classList.add('unread');
    if (msgId) pendingBurn.set(msgId, { el: d, isMine: false });
  }

  if(msgId && msgReads[msgId]) updateReadIndicator(msgId);
  if(!isMe){
    playNotify();
    if(document.hidden){ unreadCount++; updateTitle(); }
  }
}

// focus 輸入框 → 所有當下未讀的別人訊息,標為已讀 + 開始倒數
function onUserRead() {
  // 批次 scheduleBurn:按年齡順序(最舊在前)遞增 delay
  // 第 1 則 +0 秒,第 2 則 +1 秒,第 3 則 +2 秒...
  // 避免一次堆疊大量訊息時同時消失
  let delay = 0;
  for (const [msgId, info] of pendingBurn) {
    if (info.isMine) continue;
    info.el.classList.remove('unread');
    scheduleBurn(info.el, delay);
    delay++;
    if (!sentReads[msgId]) {
      sentReads[msgId] = true;
      apiSend({type:'read', msgId: msgId});
    }
    pendingBurn.delete(msgId);
  }
}

// 收到 read event 時:若此訊息是我發的,湊齊讀者人數就開始燒
function tickMineReaders(msgId) {
  const info = pendingBurn.get(msgId);
  if (!info || !info.isMine) return;
  info.readersGot++;
  if (info.readersGot >= info.readersNeeded) {
    scheduleBurn(info.el);
    pendingBurn.delete(msgId);
  }
}

// 有人離開 → 重算我自己 pending 訊息的 readersNeeded
function onPresenceChange(onlineCount) {
  // onlineCount 是當下線上人數,接收者 = onlineCount - 1 (自己)
  // 但若我發完訊息後對方離開,readersNeeded 要降低
  const newNeeded = Math.max(0, onlineCount - 1);
  for (const [msgId, info] of pendingBurn) {
    if (!info.isMine) continue;
    if (newNeeded < info.readersNeeded) {
      info.readersNeeded = newNeeded;
      if (info.readersGot >= info.readersNeeded) {
        scheduleBurn(info.el);
        pendingBurn.delete(msgId);
      }
    }
  }
}
function addSys(t){
  // 系統訊息改進入獨立區 (#sys-log),不再插入 #msgs
  addSysEntry(t);
}
function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
async function send(){
  const i = document.getElementById('mi');
  const text = i.value.trim();
  // 文字或圖片任一存在即可發送
  if(!text && !pendingImage) return;
  if(!authToken){
    addSys('⚠ 尚未連線,無法發送');
    return;
  }
  const imgToSend = pendingImage;
  i.value = '';
  clearImagePreview();
  try {
    // 有圖片時打包成 JSON;純文字依舊送 string(向後相容)
    const payload = imgToSend ? JSON.stringify({text: text, image: imgToSend}) : text;
    const enc = await encryptText(payload);
    const ok = await apiSend({type:'chat', encrypted: enc});
    if(!ok){
      addSys('⚠ 傳送失敗(網路不穩或圖片太大?)');
      i.value = text;
      if(imgToSend){ pendingImage = imgToSend; document.getElementById('img-preview').style.display = 'flex'; }
    }
  } catch(err){
    addSys('⚠ 加密失敗:' + (err.message || err));
    i.value = text;
    if(imgToSend){ pendingImage = imgToSend; document.getElementById('img-preview').style.display = 'flex'; }
  }
}

// 關閉分頁時通知 server (best-effort;server 也會靠 60s timeout 自動清)
window.addEventListener('beforeunload', () => {
  if (!authToken) return;
  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([JSON.stringify({token: authToken, type: 'leave'})], {type: 'application/json'});
      navigator.sendBeacon('/send', blob);
    }
  } catch(e) {}
  stopPolling();
  stopHeartbeat();
});

// 初始狀態:輸入框 disable 直到連線成功
(function initInputState(){
  const mi = document.getElementById('mi');
  if (mi) { mi.disabled = true; mi.placeholder = '請先登入'; }
})();

document.getElementById('mi').addEventListener('keydown', e => { if(e.key === 'Enter') send(); });
document.getElementById('mi').addEventListener('focus', () => {
  inputFocused = true;
  updateChatVisibility();
  onUserRead();
});
document.getElementById('mi').addEventListener('blur', () => {
  inputFocused = false;
  updateChatVisibility();
});
document.getElementById('nickInput').addEventListener('keydown', e => { if(e.key === 'Enter') document.getElementById('pwd').focus(); });
document.getElementById('pwd').addEventListener('keydown', e => { if(e.key === 'Enter') auth(); });
document.getElementById('burnSec').addEventListener('keydown', e => { if(e.key === 'Enter') applyBurn(); });
</script>
</body>
</html>`;
}

// ─── 啟動 ────────────────────────────────────────────────────────────────────
server.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error('\x1b[91m[BurnerChat] ❌ Port ' + PORT + ' 已被其他程式占用\x1b[0m');
    if (PORT === 80) {
      console.error('  Windows 常見占用者:IIS / Skype / World Wide Web Publishing Service');
      console.error('  在 PowerShell (管理員) 跑:netstat -ano | findstr :80');
      console.error('  若是 IIS:iisreset /stop');
    }
  } else if (err.code === 'EACCES') {
    console.error('\x1b[91m[BurnerChat] ❌ 沒有權限監聽 port ' + PORT + '\x1b[0m');
    if (process.platform === 'win32') {
      console.error('  Windows:以「系統管理員身分」重新執行');
    } else {
      console.error('  Linux/Mac:用 sudo 執行,或 sudo setcap cap_net_bind_service=+ep $(which node)');
    }
  } else {
    console.error('\x1b[91m[BurnerChat] ❌ Server 錯誤: ' + err.code + ' - ' + err.message + '\x1b[0m');
  }
  process.exit(1);
});

server.listen(PORT, '0.0.0.0', () => {
  const portStr = (PORT === 80) ? '' : (':' + PORT);
  const link = 'http://' + LOCAL_IP + portStr + '/room/' + ROOM_ID;
  const adminLink = 'http://' + LOCAL_IP + portStr + '/admin';
  console.log('');
  console.log('\x1b[91m╔══════════════════════════════════════════════╗');
  console.log('║  🔥  BurnerChat Server v1.5  已啟動            ║');
  console.log('╚══════════════════════════════════════════════╝\x1b[0m');
  console.log('');
  console.log('  \x1b[1m📡 預設房間 (Room ID: ' + ROOM_ID + '):\x1b[0m');
  console.log('  \x1b[96m' + link + '\x1b[0m');
  if (DEFAULT_ROOM_PASSWORD) {
    console.log('  \x1b[1m🔑 預設房間密碼:\x1b[0m \x1b[93m' + DEFAULT_ROOM_PASSWORD + '\x1b[0m');
  }
  console.log('');
  console.log('  \x1b[95m╭──────────── 🛡️  ADMIN 後台 ────────────╮\x1b[0m');
  console.log('  \x1b[95m│\x1b[0m \x1b[1m後台網址:\x1b[0m \x1b[96m' + adminLink + '\x1b[0m');
  if (process.env.ADMIN_PASSWORD) {
    console.log('  \x1b[95m│\x1b[0m \x1b[1m管理員密碼:\x1b[0m \x1b[93m\x1b[1m' + process.env.ADMIN_PASSWORD + '\x1b[0m');
  }
  console.log('  \x1b[95m│\x1b[0m \x1b[2m(僅 console 可見,請勿外流)\x1b[0m');
  console.log('  \x1b[95m╰─────────────────────────────────────────╯\x1b[0m');
  console.log('');
  console.log('  \x1b[2m按 Ctrl+C 關閉伺服器並銷毀所有訊息\x1b[0m');
  console.log('');
});
"""

# ═════════════════════════════════════════════════════════════════════════════
# Marketplace 版本(client-only,可上架 VSCode Marketplace)
# ═════════════════════════════════════════════════════════════════════════════

MARKETPLACE_PACKAGE_JSON_TEMPLATE = {
    "name": "burner-chat",
    "displayName": "BurnerChat - Ephemeral E2EE Chat",
    "description": "Burn-after-reading end-to-end encrypted chat room (AES-256-GCM)",
    "version": "1.5.0",
    "publisher": "PLACEHOLDER_PUBLISHER",
    "icon": "icon.png",
    "license": "MIT",
    "repository": {"type": "git", "url": "PLACEHOLDER_REPO"},
    "bugs": {"url": "PLACEHOLDER_REPO/issues"},
    "homepage": "PLACEHOLDER_REPO#readme",
    "engines": {"vscode": "^1.80.0"},
    "categories": ["Other", "Chat"],
    "keywords": ["chat", "ephemeral", "encryption", "e2ee", "burn-after-reading", "team"],
    "activationEvents": ["onCommand:burnerChat.connect", "onCommand:burnerChat.connectRecent"],
    "main": "./extension.js",
    "contributes": {
        "commands": [
            {"command": "burnerChat.connect", "title": "BurnerChat: Connect to Server", "category": "BurnerChat"},
            {"command": "burnerChat.connectRecent", "title": "BurnerChat: Connect to Recent Server", "category": "BurnerChat"},
            {"command": "burnerChat.clearRecent", "title": "BurnerChat: Clear Recent Servers", "category": "BurnerChat"}
        ],
        "keybindings": [
            {"command": "burnerChat.connect", "key": "ctrl+shift+b", "mac": "cmd+shift+b"}
        ],
        "configuration": {
            "title": "BurnerChat",
            "properties": {
                "burnerChat.maxRecentServers": {
                    "type": "number", "default": 10, "minimum": 1, "maximum": 50,
                    "description": "Maximum number of recent server URLs to remember"
                }
            }
        }
    }
}

# Marketplace 版的 extension.js — 沒有預設 localhost,強制使用者輸入 server URL,
# 並用 globalState 記住歷史 URL
MARKETPLACE_EXTENSION_JS = r"""
const vscode = require('vscode');

const RECENT_KEY = 'burnerChat.recentServers';

function activate(context) {
    const connectCmd = vscode.commands.registerCommand('burnerChat.connect', async () => {
        const recent = context.globalState.get(RECENT_KEY, []);

        const url = await vscode.window.showInputBox({
            prompt: 'Enter BurnerChat server URL or room invite link',
            placeHolder: 'http://192.168.1.100:7788/room/abcd1234',
            value: recent[0] || '',
            validateInput: (v) => {
                if (!v || !v.trim()) return 'URL is required';
                try { new URL(v.trim()); return null; }
                catch (e) { return 'Invalid URL format'; }
            }
        });
        if (!url) return;
        const trimmed = url.trim();
        await rememberServer(context, trimmed);
        openPanel(context, trimmed);
    });

    const recentCmd = vscode.commands.registerCommand('burnerChat.connectRecent', async () => {
        const recent = context.globalState.get(RECENT_KEY, []);
        if (recent.length === 0) {
            vscode.window.showInformationMessage('No recent servers. Use "BurnerChat: Connect" to add one.');
            return;
        }
        const picked = await vscode.window.showQuickPick(recent, {
            placeHolder: 'Select a recent server'
        });
        if (!picked) return;
        await rememberServer(context, picked); // bump to top
        openPanel(context, picked);
    });

    const clearCmd = vscode.commands.registerCommand('burnerChat.clearRecent', async () => {
        await context.globalState.update(RECENT_KEY, []);
        vscode.window.showInformationMessage('BurnerChat: Recent servers cleared.');
    });

    context.subscriptions.push(connectCmd, recentCmd, clearCmd);
}

async function rememberServer(context, url) {
    const max = vscode.workspace.getConfiguration('burnerChat').get('maxRecentServers', 10);
    let recent = context.globalState.get(RECENT_KEY, []);
    recent = recent.filter(u => u !== url);
    recent.unshift(url);
    if (recent.length > max) recent = recent.slice(0, max);
    await context.globalState.update(RECENT_KEY, recent);
}

function openPanel(context, serverUrl) {
    const panel = vscode.window.createWebviewPanel(
        'burnerChat', 'BurnerChat',
        vscode.ViewColumn.Two,
        { enableScripts: true, retainContextWhenHidden: true }
    );
    panel.webview.onDidReceiveMessage(msg => {
        if (msg && msg.type === 'unread') {
            const n = parseInt(msg.count) || 0;
            panel.title = n > 0 ? '(' + n + ') BurnerChat' : 'BurnerChat';
        }
    });
    panel.webview.html = getWebviewContent(serverUrl);
}

function getWebviewContent(serverUrl) {
    return `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0d0d0d; color: #e0e0e0; font-family: 'Courier New', monospace;
         display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
  #header { background: #1a0a00; border-bottom: 1px solid #ff4500;
            padding: 12px 16px; display: flex; align-items: center; gap: 10px; }
  #header h1 { font-size: 14px; color: #ff6b35; font-weight: bold; }
  #header .me { font-size: 11px; color: #ff8c35; margin-left: 8px; }
  .sound-btn { font-size: 14px; cursor: pointer; opacity: .75; user-select: none;
               transition: opacity .2s, transform .1s; padding: 2px 6px; border-radius: 3px; }
  .sound-btn:hover { opacity: 1; transform: scale(1.15); background: rgba(255,69,0,.1); }
  #status { font-size: 11px; color: #666; margin-left: auto; }
  #roster { background: #0a0503; border-bottom: 1px solid #2a1a00;
            padding: 5px 16px; font-size: 11px; color: #888;
            display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  #roster .roster-toggle { cursor: pointer; color: #ff4500; user-select: none;
                           padding: 1px 6px; border: 1px solid #2a1a00; border-radius: 2px; }
  #roster .roster-toggle:hover { background: #1a0a00; }
  #roster .roster-list { flex: 1; line-height: 1.5; }
  #roster.collapsed .roster-list { display: none; }
  #sys-log { background: #080503; border-bottom: 1px solid #2a1a00;
             padding: 4px 16px; font-size: 11px; color: #888; font-style: italic; }
  #sys-log .sys-header { display: flex; align-items: center; gap: 8px; }
  #sys-log .sys-last { flex: 1; opacity: .85;
                       white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #sys-log .sys-toggle { cursor: pointer; color: #ff4500; user-select: none;
                         padding: 1px 6px; border: 1px solid #2a1a00; border-radius: 2px;
                         font-style: normal; font-size: 10px; flex-shrink: 0; }
  #sys-log .sys-toggle:hover { background: #1a0a00; }
  #sys-log .sys-full { max-height: 10vh; overflow-y: auto; margin-top: 4px; }
  #sys-log .sys-line { padding: 2px 0; opacity: .7; }
  #sys-log.collapsed .sys-full { display: none; }
  #sys-log:not(.collapsed) .sys-last { display: none; }
  #burn-bar { background: #0f0a05; border-bottom: 1px solid #2a1a00;
              padding: 6px 16px; display: flex; align-items: center; gap: 8px;
              font-size: 11px; color: #888; flex-wrap: wrap; }
  #burn-bar label { color: #ff8c35; }
  #burn-bar input[type=number] { background: #0a0a0a; border: 1px solid #333;
              color: #e0e0e0; padding: 3px 6px; width: 55px; border-radius: 2px;
              font-size: 11px; outline: none; }
  #burn-bar button { background: transparent; color: #ff4500; border: 1px solid #ff4500;
              padding: 3px 10px; border-radius: 2px; cursor: pointer; font-size: 10px; }
  #burn-bar button:hover { background: #ff4500; color: white; }
  #messages { flex: 1; overflow-y: auto; padding: 16px; display: flex;
              flex-direction: column; gap: 8px; }
  .msg { padding: 8px 12px; border-radius: 4px; max-width: 80%; font-size: 12px;
         transition: opacity .6s, transform .6s; }
  .msg.system { color: #666; font-style: italic; align-self: center; background: #111; }
  .msg.mine { align-self: flex-end; background: #1a0a00; color: #ff8c66; }
  .msg.other { align-self: flex-start; background: #0a1a0a; color: #88ffbb; }
  .msg .sender { font-size: 10px; opacity: 0.6; margin-bottom: 3px; }
  .msg .readby { font-size: 9px; color: #00ff88; opacity: .55; margin-top: 3px; }
  .msg.mine .readby { text-align: right; }
  .msg .countdown { font-size: 9px; opacity: .5; margin-top: 2px; }
  .msg.mine .countdown { text-align: right; }
  .msg.burning { animation: flicker .6s infinite; }
  .msg.unread { border-left: 3px solid #ff4500; padding-left: 9px; }
  /* 反黑遮罩:未 focus 或分頁背景時,訊息文字顯示為 █████ */
  #messages.redacted .msg:not(.system) .text-content { font-size: 0; }
  #messages.redacted .msg:not(.system) .text-content::before {
    content: attr(data-mask); font-size: 12px; color: #888; opacity: .6; letter-spacing: -2px;
  }
  @keyframes flicker { 0%,100%{opacity:1} 50%{opacity:.6} }
  #input-area { display: flex; gap: 8px; padding: 12px 16px; background: #111; }
  #input-area input { flex: 1; background: #1a1a1a; border: 1px solid #333; color: #e0e0e0;
                      padding: 8px 12px; border-radius: 3px; font-size: 12px; outline: none; }
  #input-area button { background: #ff4500; color: white; border: none;
                       padding: 8px 16px; border-radius: 3px; cursor: pointer; }
  #clean-toggle { background: transparent !important; border: 1px solid #333 !important;
                  cursor: pointer; padding: 4px 6px !important;
                  border-radius: 3px; flex-shrink: 0; transition: .15s;
                  display: flex; align-items: center; justify-content: center; }
  #clean-toggle img { width: 22px; height: 22px; display: block; opacity: .7; transition: opacity .15s; }
  #clean-toggle:hover img { opacity: 1; }
  #clean-toggle:hover { background: #1a0a00 !important; border-color: #ff4500 !important; }
  #clean-toggle.active { color: #ff4500 !important; border-color: #ff4500 !important;
                         background: rgba(255,69,0,.1) !important; }
  /* 乾淨版:隱藏 header/roster/sys-log/burn-bar,保留訊息區與輸入列 */
  body.clean-mode #header,
  body.clean-mode #roster,
  body.clean-mode #sys-log,
  body.clean-mode #burn-bar { display: none !important; }
  body.clean-mode #msg-input::placeholder { color: transparent; }
  body.clean-mode #send-btn { font-size: 0; padding: 8px 14px; }
  body.clean-mode #send-btn::after { content: '→'; font-size: 16px; }
  body.clean-mode .readby .names { display: none; }

  /* Emoji + 圖片按鈕 */
  #emoji-toggle,#img-attach { background: transparent !important; border: 1px solid #333 !important;
                              cursor: pointer; padding: 4px 8px !important; border-radius: 3px;
                              font-size: 16px; flex-shrink: 0; transition: .15s; color: #e0e0e0 !important; }
  #emoji-toggle:hover,#img-attach:hover { background: #1a0a00 !important; border-color: #ff4500 !important; }
  #emoji-toggle.active { color: #ff4500 !important; border-color: #ff4500 !important; background: rgba(255,69,0,.1) !important; }

  /* Emoji 面板 */
  #emoji-panel { position: fixed; bottom: 68px; left: 16px; width: 300px; max-width: 92vw;
                 background: #1a1a1a; border: 1px solid #333; border-radius: 6px; padding: 8px;
                 z-index: 999; box-shadow: 0 4px 20px rgba(0,0,0,.5); }
  #emoji-search { width: 100%; background: #0d0d0d; border: 1px solid #333; color: #e0e0e0;
                  padding: 6px 10px; border-radius: 4px; font-size: 12px; outline: none;
                  box-sizing: border-box; margin-bottom: 6px; }
  #emoji-search:focus { border-color: #ff4500; }
  #emoji-tabs { display: flex; gap: 4px; border-bottom: 1px solid #333; padding-bottom: 6px; margin-bottom: 6px; }
  #emoji-tabs .tab { cursor: pointer; padding: 3px 7px; border-radius: 3px; font-size: 15px; opacity: .5; }
  #emoji-tabs .tab:hover { opacity: .9; background: #0d0d0d; }
  #emoji-tabs .tab.active { opacity: 1; background: #0d0d0d; box-shadow: inset 0 -2px 0 #ff4500; }
  #emoji-grid { display: grid; grid-template-columns: repeat(8,1fr); gap: 2px; max-height: 220px; overflow-y: auto; }
  #emoji-grid .emoji-cell { cursor: pointer; padding: 4px; text-align: center; font-size: 20px; border-radius: 3px; user-select: none; }
  #emoji-grid .emoji-cell:hover { background: #ff4500; transform: scale(1.15); }

  /* 圖片預覽 */
  #img-preview { position: fixed; bottom: 68px; right: 16px; background: #1a1a1a; border: 1px solid #ff4500;
                 border-radius: 6px; padding: 8px; display: flex; align-items: center; gap: 8px; z-index: 999;
                 box-shadow: 0 4px 20px rgba(0,0,0,.5); }
  #img-preview #img-preview-thumb { max-width: 80px; max-height: 80px; border-radius: 3px; object-fit: cover; }
  #img-preview #img-preview-size { font-size: 10px; color: #888; }
  #img-preview button { background: transparent; border: 1px solid #333; color: #ff4444; cursor: pointer;
                        width: 24px; height: 24px; padding: 0; border-radius: 50%; font-size: 12px; }
  #img-preview button:hover { background: #ff4444; color: white; }

  /* 訊息內圖片 */
  .msg-image { width: 100%; max-width: 280px; aspect-ratio: 4/3; background-size: contain;
               background-position: left center; background-repeat: no-repeat; margin-top: 6px;
               border-radius: 4px; cursor: zoom-in; border: 1px solid #333; }
  .msg.mine .msg-image { background-position: right center; }
  #messages.redacted .msg:not(.system) .msg-image { filter: blur(18px); }

  /* 全螢幕 viewer */
  #img-viewer { position: fixed; inset: 0; background: rgba(0,0,0,.96); z-index: 9999; display: flex; flex-direction: column; }
  #img-viewer-stage { flex: 1; overflow: hidden; position: relative; cursor: grab;
                      display: flex; align-items: center; justify-content: center; }
  #img-viewer-stage.dragging { cursor: grabbing; }
  #img-viewer-content { width: 100%; height: 100%; background-size: contain; background-position: center;
                        background-repeat: no-repeat; transition: transform .1s ease-out; transform-origin: center; }
  #img-viewer-toolbar { padding: 10px 20px; display: flex; gap: 8px; align-items: center;
                        justify-content: center; background: rgba(0,0,0,.5); border-top: 1px solid #222; }
  #img-viewer-toolbar button { background: transparent; border: 1px solid #555; color: #ccc; cursor: pointer;
                               padding: 6px 14px; border-radius: 4px; font-size: 14px; min-width: 44px; }
  #img-viewer-toolbar button:hover { background: #333; color: white; border-color: #888; }
  #img-viewer-zoom { color: #ccc; font-size: 12px; min-width: 50px; text-align: center; }
  #img-viewer-warn { position: absolute; top: 20px; left: 50%; transform: translateX(-50%);
                     background: rgba(255,69,0,.15); border: 1px solid #ff4500; color: #ff4500;
                     padding: 6px 14px; border-radius: 20px; font-size: 11px; letter-spacing: .5px; }
  #auth-overlay { position: fixed; inset: 0; background: #0d0d0d;
                  display: flex; align-items: center; justify-content: center;
                  flex-direction: column; gap: 12px; z-index: 100; }
  #auth-overlay input { background: #1a1a1a; border: 1px solid #333; color: #e0e0e0;
                         padding: 10px 16px; width: 280px; border-radius: 4px;
                         font-size: 14px; outline: none; text-align: center; }
  #auth-overlay input[type=password] { letter-spacing: 2px; }
  #auth-overlay button { background: #ff4500; color: white; border: none; width: 280px;
                          padding: 10px; border-radius: 4px; cursor: pointer; font-size: 14px; }
  #auth-overlay .title { color: #ff6b35; font-size: 18px; font-weight: bold; }
  #auth-overlay .subtitle { color: #666; font-size: 12px; }
  #auth-err { color: #ff4444; font-size: 12px; min-height: 16px; }
</style></head>
<body>
<div id="auth-overlay">
  <div class="title">BurnerChat</div>
  <div class="subtitle">Enter your nickname and room password</div>
  <input type="text" id="nick-input" placeholder="Your nickname..." maxlength="20" autofocus />
  <input type="password" id="pwd-input" placeholder="Room password..." />
  <div id="auth-err"></div>
  <button onclick="authenticate()">Join Room</button>
</div>

<div id="header" style="display:none">
  <span>BurnerChat</span><h1></h1>
  <span class="me" id="me-label"></span>
  <span id="sound-btn" class="sound-btn" onclick="toggleSound()">🔔</span>
  <span id="status">Connecting...</span>
</div>
<div id="roster" class="collapsed" style="display:none">
  <span class="roster-toggle" onclick="toggleRoster()"></span>
  <span class="roster-list"></span>
</div>
<div id="sys-log" class="collapsed" style="display:none">
  <div class="sys-header">
    <span class="sys-last"></span>
    <span class="sys-toggle" onclick="toggleSysLog()"></span>
  </div>
  <div class="sys-full"></div>
</div>
<div id="burn-bar" style="display:none">
  <label>Burn after:</label>
  <input type="number" id="burn-sec" min="0" max="3600" value="30" />
  <span>sec</span>
  <button onclick="updateBurn()">Apply</button>
</div>
<div id="messages" style="display:none"></div>
<div id="input-area" style="display:none">
  <button id="clean-toggle" class="clean-btn" onclick="toggleCleanMode()" title="Toggle clean mode"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAABCGlDQ1BJQ0MgUHJvZmlsZQAAeJxjYGA8wQAELAYMDLl5JUVB7k4KEZFRCuwPGBiBEAwSk4sLGHADoKpv1yBqL+viUYcLcKakFicD6Q9ArFIEtBxopAiQLZIOYWuA2EkQtg2IXV5SUAJkB4DYRSFBzkB2CpCtkY7ETkJiJxcUgdT3ANk2uTmlyQh3M/Ck5oUGA2kOIJZhKGYIYnBncAL5H6IkfxEDg8VXBgbmCQixpJkMDNtbGRgkbiHEVBYwMPC3MDBsO48QQ4RJQWJRIliIBYiZ0tIYGD4tZ2DgjWRgEL7AwMAVDQsIHG5TALvNnSEfCNMZchhSgSKeDHkMyQx6QJYRgwGDIYMZAKbWPz9HbOBQAAAOxUlEQVR42q2ae4xc9XXHP7/fvXfuzOzM7K5f7NPeXdu7i2MDNsURNTgkARywIY1JSaMEhwBVqlRtlTaK0v9IKjUiqqqKKolQ2ySQRk3URgmpnGKC0oBKAoYEAuYRg4mN3zbex7zu+3f6x5293vE+/AhXulrNzvx+93zP6/c951wFCJdwaa0REUTS5ePj49x0401s2bKFyy9fx7IlS3FshyiKqNVqnD51iv1v7ueZvc/y8yef5I039gOglEIphTHmUsRAXQoAy7JIkgSAHTt2cN+993HdlutYsmQpIkIURcRJghiTbm4E0/psjDA1PcWze5/hke88wmOP75mz58VecqG3Ukq01gLINX9wjTzx0ydEjIgYkXq1IZNnpmRqYlqmJ6tSnaxKdarWdk+emZITR07I0d8dkclTEzL9zpQ8+oMfycaNGwUQrbUopeRiZLKA+y/IVEqlaEX4/N98nocffoTRtaNMT03j+wEohdY6cwlavz/X7XKui2Vb1Gt1Go0GY2NjfOyPP0YYBDy799mz6y/UGy4EwMymCsVDDz3EF//2i/hegOd5WJaVCn6RLpjP5xER6vU6ALftuI3Llq9gz08ff3cBqJZmjTF889++xb333cPEO5NordFac8mXgpzrIsYQxzH1ep2tW7fS29vH7p/sxrKsdwfATHB96f4v81ef+0sm3pnEcZyL0tJil+PmMFGMANVala1brkOM8NT/PYVlWVmWu6QsNCP8zTdt47HH/ofqVA1lpa70bl1KKUySUJ2upllLhM5KhZ133sHPfv6/581OCwKY8ftCocjeZ/ayZs0aPM/7/dxmERCB79OsNxARioUCb771Fh/cdiOe18ySx7zn0WLaN8Zw3733sW795dTr9XdNeBHBGINpaVxEyLl5bMdGK0290WDD+vXc9cm7EJFFnzuvBWb8u5Av8Kvnf83w8DC+7//eAM4Km8OxHQQhDELiOMayLMIgoFFLs5Lruhw8dJAbbnw/vu8vaAW9GE344AdvZGx8dEHXma3J81EBEcG2bYrFIiePn+S5Z5/jxV+9SKPRoFQqYcRgOw6WnWYfz/MYGx1j6/XvW9QK9mIPvf3221BazYtcjCHnujiOk9mx0WjMm51EBMdxqFdr/Nf3/pOXf/MyjUYDL/ApdHRw2+072PHhHcRxjOPkSGIvU+StH/oQex5/bEEZ7fncJ0kSHMdh8zXvJQriOehFBLdQ4O3fHeKXT/+Cqakp3rNhPVuu30IURef8FixL43keX/unr3HgjTcplUuUSyVK5TKTU5M89I2HqNVq3PXpXQRBgGoJ7/s+mzZtwrZt4ji+cAAiQn9fP4ODg+mGs7RqjCFfKPDqS/v4xj9/ncALQMGenzzOgQMH+PS9n6bZbGagRQz5fIndP9rNm2+8QXd3N3EckxiDAjrLFYwIj/7wUTZvvobVY2totuIgDEP6+wbo7e3j8OG3swN10RiYEXZgYIByuUySJG0AtNYkccx//+jHxGFEpbNCpVKhr7eH3T/ezZv738howszvm02PfS/to5AvtOV0aT0vl8sRBiHPPfc8uZwLWmXKKpdK9Pf2tcl2QWl0yZIl2Hb7SSgiaMuiVqsxOTlFznWJk4QkSbBtG2MMR44exXGcLONorfE9j2azgdJqYa6lFRMTE20Ba4zBth26u7sWrkvaPiiNbdlY2sJ184iSeU/NUkeJzkqFKAyxLCs7LZVW9Pb2EsdxW6GSz+cpFAqIkUXTa1dXJ1q3s1GlFK6bR2uNZVlzrKBnu4YRQxAGJCYhiqJ5TWaMwXEdbr19OyhFvVqjXqtz5Ngxbtp2E6Njo/i+n601xlAsFVm3fh2+788haTMFkG3bXH311Rn4TC5L4wc+xhjCMJyTUi3g/pngGBgYYNfH7+LmD9zMVRuupPeyXoodxXRDSY89pRRxFNO/cpCxy8cBodJVYfvtO9j50Z3zZguTGFYOreS1V17j1MlTuK6b0nBLU63WOH36NB/e+Udsu2UbnueRRHEWe2EQYGub9ePrWTO0mhOnT1Kr19BKIwhKay3GGG65eRtf/co/sGzpMrx6k6OHjzA9Nc3ynhWMXTGOZdtz4sFtFSdICqzZbC7oIrlcjskzE3z/u9/j1VdeS7mP5+HkXW7dfgt33HlHpv1GvU7oBfh+SBSGFAoFqlNVmtU607UqX/nHB3jqF09mdYiMrh1l9w93Z0I4jkPg+Zw+cYowCFgx0MO6K9fPMa8YQWYxkcWohojBcXJorTl08BBHjx7Ftm1GVo/Q09NDs9nM3KPZaDB9Zpo4TlCqRSEUHDt8FJWA0nDPX/wpBw8dTGNg1yd2US6VMuERKHQUyRfy2I7DxMkzVKeqWOdkJaVVVticjycppYmiiCAIWDm0iq3vu55rt1xLd3d3VpVlgZ8Y4ijOqlKFwtIWy5Ytwws8Oood7Nyx8+xBNj42jh8EswJMsmKDRpPEJDTqdTq7O0lIsuBciB2qRTkReM0mnpD6cKviOzdmBDlbd7SsYDt26h1ByOrhkRSAk8tRLpUxxsxyj/Svpa0MTxxGbZIVO4pobbWRWQV4RkhE2kEohdIaS4S8Ortips5OTILX9LIvZB6uLEhmaWMMHcUOHMfBLhU7KJdK7RpVZ1PYzBWFUZs7PP3k05w8cQLbtkHAALEIV3TkGXZdLNWiEklC5DcJQ58jaF4VC0uBxDFBHBHHMf19fWy5/joSSTKiOF/zRyuNpTWJSegoFikUCtilUolCsUCSmHmLmpkCMooixKRmPHXiFP/+zYcJwwitFQLERti1YhlrujpxZiygFYgiZxKaE6foq57hAA4/SGxsBZPVKmEY4uZd1oyupbe/N+NJ7aaY3WCwiMKIfL5AR7EDu1KpkMvlEDFth0/mmyo1SRzFaZZQGpSiUCzi5g2WUtSThBsqZbb19mCSuPVshUlSq1l2kWK5RHxMc1vocVpc9opFlwI/DFMrqlb0CMg8yjTGoFpnhxFDznEol8roy1asoFwqE4ZRRrRKpRIKhW3bqRspCP0AjJAkCZVymWJHkSiMMMaQGMN43kWSGGMSMAaF0Dx9nObp46lyRNCOSxAb1khCHCfEcUQURXSUOujs7CRpgU+SeA6dKJVKLYWqdE1HB0uXLEUfPHSIN986wIoVy1nSvQSU4pfPPkOcxDQaDUI/RIyh0t0FOq0VypUyA4ODKd3QqYtZWeio2WpL77OxnHJ90n2MCFEYMTQ8RGdnhSROMu4zw4+UUoRhyC/3PkMUx3QUiyxbupSDhw9x5NgR7Ld+9xYfufMjfPYzf87QypX8y7f+ldd/+zq/fW0/OccmSRJ6BnpZ3rMis5BSsOmaTfzquefPkzTnb8UqBUEUYrWyy7V/eG1GV0SEypJO4iQiCiLcvIsow72fuYe1I2vZeftOjp04xne//11q9Rq2Uorp6Wm+8tW/zx6xYcMGurq66Orupm94MDVrHANpXHiez5VXb2R49QhHDh5C53IX1UKJk4Qojgg9n9GxUTa/d3NaBM3Keq6bw7ZT9lnp7GTVqlW8+PKLvPjyi+1BPWMmy7LI5dKjvq+vj0IhTxgExFFMHMVtmjYmDaI7/uSjKK0xiUGpC+1YpHk/jmIsS/Ope3bhuE5bGletgBaBODEU8nl6L+tBa43jOFjayipHPUO2kiTJugvDQyMoS2U+OIeD67TGHV83zifu/iS+76cs9JzfiRhEzNyaO07wPJ/PfPbPWH/FBpqNZttprFoH38zR7TgOK1euyvpIiUkySjNvV2LtmjUXNKFp1Btcf8NWYsvCfeJnbQELkCt2nj1NVcppjDG4eZe//sLnuOkDN1Ct1eZt5M52J4CRkZHzF/UzZlw7OgqG8zZwtdbUazWu+8D1MD2N2fs8ulgAYxBjyHctaSkxAZUK2Ww22bTtFjpufj/VM1Noe/7OzgyNUUAcx6xevXpeDqbbykVjyOVyjIyMEIbRBXWglVL4Xojp7ZmXQqcupBBjSMIAtEINjeD58eItw5YFlNZpql01RM5xzuFs5wAA6O8foL+vnzAML6yFrjU6iohH15KsWA5BALPNL4LSNlHgE09NoAZXoTdehQqDeac4bTSm9X0YhfT29NI7T3diDoCxsTE6OytzipdFL2Mgnye49UMkORfV9FPhtEY7OZLIp/H2AaRQwL7rblSxCEmyIICUspyl2UmS0NXZyZo1a88PYONVV2UZ6CKSOwQBsnKA4BMfIx4eQpIEaTTwTh6jeuQtGB3D+cIXsUZHEc+H8xVArS7E7L7qFRvWzwFgzy4PATZu3JjVuBc5OE5B9PQQfPxOOHECOX6cJPSxevuwhoZTruZ55xX+bCY6m52SJOGKDVfOCWQ7y80mIZfLsW7dewiD6NJGSEpDFKUsuK8PBgextUbiGAmCs0AvdIDX6lRrrQmDkPGx8bSL14rP7CCbEXZ4aJiVgysJguDSZwEzI9YwhGYTqdfTwF5g9LrY8HomkFNCF9A/0M/g4Mo2N2oDsH7Dekrl0kVNzGe/bjAHiNbpvUDLfdE4a7UxtZXOKuIkoVwqs+7yyxcGsHnze1teEC26uYgQxzHGGCxtYWkr+9+FrBORbJ1pjVnnW6eUQlt2ts6xba7edHUbAHv26OaFX7+AGGH5ZcsIvDCbzMye0htjcF2XSleZJDRUa1UAyqUytmvhN4NsHHXuunw+T77oEgXpXFgB5XIFK6fxGn7murPXKcDN5VjSasu/9NLLbeOmrO5XKAThyiuuZPv27dz9qbtZO7oW3w+yctK2bQqFPMeOH+c733mE3bt3c/jIYUSEvt5+tm27mU/dfTdDq1bhe0E27HAch3ze5eDbh3j4299mz549HDt+DKUUgwOD3Lp9O7s+eRd9fX14np+1J3NuDktZ/OaFF/iP73+PPY/vYd+r+xZ+2WP2ixbLl6+QL3/p72TfS/tk4p1JmZqYlv2v75cHH3xQRkZGFnz5on+gXx544Kvy6iuvyeSZKZk8MyWvvvKaPPDAA9I/0L/gupGREXnwwQdl/+v7ZWpiWibemZR9L70iX7r/y7Js2fJ5ZQTk/wGie9Ascw1rOAAAAABJRU5ErkJggg==" alt="toggle"/></button>
  <input type="text" id="msg-input" placeholder="Type a message... (Enter to send)" />
  <button id="send-btn" onclick="sendMsg()">Send</button>
</div>
<div id="emoji-panel" style="display:none">
  <input type="text" id="emoji-search" placeholder="Search emoji..." />
  <div id="emoji-tabs"></div>
  <div id="emoji-grid"></div>
</div>
<div id="img-preview" style="display:none">
  <img id="img-preview-thumb" />
  <span id="img-preview-size"></span>
  <button onclick="clearImagePreview()" title="Cancel">✕</button>
</div>
<div id="img-viewer" style="display:none">
  <div id="img-viewer-stage"><div id="img-viewer-content"></div></div>
  <div id="img-viewer-toolbar">
    <button onclick="viewerZoomOut()" title="Zoom out">−</button>
    <span id="img-viewer-zoom">100%</span>
    <button onclick="viewerZoomIn()" title="Zoom in">+</button>
    <button onclick="viewerReset()" title="Reset">Reset</button>
    <button onclick="closeImageViewer()" title="Close (Esc)">✕</button>
  </div>
  <div id="img-viewer-warn" style="display:none">⚠ Do not screenshot or share · image auto-destroyed</div>
</div>
<input type="file" id="img-file-input" accept="image/jpeg,image/png,image/webp" style="display:none" />

<script>
const RAW_URL = '${serverUrl}';
const _u = new URL(RAW_URL);
const SERVER = _u.protocol + '//' + _u.host;
const _parts = _u.pathname.split('/').filter(Boolean);
const ROOM_ID_FROM_URL = (_parts[0] === 'room' && _parts[1]) ? _parts[1] : '';
const BASE_TITLE = 'BurnerChat';
let authToken = null, nick = '', clientId = null;
let sinceSeq = 0;
let polling = false;
let pollAbortCtrl = null;
let burnDuration = 30, unreadCount = 0, soundEnabled = true, audioCtx = null;
let cryptoKey = null;
const msgReads = {}, sentReads = {};
// 訊息暫存:等 focus 輸入框(別人訊息)或湊齊所有讀者(自己訊息)才開始倒數
const pendingBurn = new Map();  // msgId -> { el, isMine, readersNeeded, readersGot }
// 線上名單 + UI 狀態
let roster = [];
let rosterExpanded = false;
const ROSTER_COLLAPSE_THRESHOLD = 6;
// 系統訊息獨立區:最新 10 則,預設折疊只顯示最後一則
const sysMsgs = [];
const MAX_SYS_MSGS = 10;
let sysExpanded = false;
let cleanMode = false;  // 乾淨版(本地狀態,不發給 server)
let inputFocused = false;
let heartbeatTimer = null;
const HEARTBEAT_INTERVAL = 15000;
const vscodeApi = (typeof acquireVsCodeApi === 'function') ? acquireVsCodeApi() : null;

// ─── Emoji Picker 資料 + 功能 ──────────────────────────────────
const EMOJI_DATA=[{"e":"😀","k":"grin smile happy 笑 開心"},{"e":"😃","k":"smile happy 開心 笑"},{"e":"😄","k":"laugh happy 大笑 開心"},{"e":"😁","k":"grin teeth 露齒 笑"},{"e":"😆","k":"laugh happy 哈哈"},{"e":"😅","k":"sweat laugh 尷尬 笑"},{"e":"🤣","k":"rofl laugh 笑翻 笑哭"},{"e":"😂","k":"joy laugh tears 笑哭"},{"e":"🙂","k":"slight smile 微笑"},{"e":"🙃","k":"upside flip 倒立 倒過來"},{"e":"😉","k":"wink 眨眼"},{"e":"😊","k":"blush smile 害羞 微笑"},{"e":"😇","k":"angel halo 天使"},{"e":"🥰","k":"love heart 愛心"},{"e":"😍","k":"heart eyes 愛心眼"},{"e":"🤩","k":"star eyes 星星眼 驚嘆"},{"e":"😘","k":"kiss 親親 飛吻"},{"e":"😗","k":"kiss 吻"},{"e":"☺️","k":"smile blush 微笑"},{"e":"😚","k":"kiss closed 閉眼親"},{"e":"😙","k":"kiss smile 親"},{"e":"🥲","k":"tear smile 含淚笑"},{"e":"😋","k":"yum tongue 好吃"},{"e":"😛","k":"tongue 吐舌"},{"e":"😜","k":"wink tongue 調皮"},{"e":"🤪","k":"zany crazy 瘋狂"},{"e":"😝","k":"tongue closed 扮鬼臉"},{"e":"🤑","k":"money mouth 錢 貪財"},{"e":"🤗","k":"hug 擁抱"},{"e":"🤭","k":"hand mouth 偷笑 驚"},{"e":"🤫","k":"shush quiet 噓 安靜"},{"e":"🤔","k":"thinking 思考"},{"e":"🤐","k":"zipper mouth 閉嘴"},{"e":"🤨","k":"raised eyebrow 懷疑"},{"e":"😐","k":"neutral 面無表情"},{"e":"😑","k":"expressionless 無奈"},{"e":"😶","k":"no mouth 無言"},{"e":"😏","k":"smirk 奸笑"},{"e":"😒","k":"unamused 無聊 不爽"},{"e":"🙄","k":"roll eyes 翻白眼"},{"e":"😬","k":"grimace 尷尬"},{"e":"🤥","k":"lying nose 說謊"},{"e":"😌","k":"relieved 放鬆"},{"e":"😔","k":"pensive 難過 沉思"},{"e":"😪","k":"sleepy 想睡"},{"e":"🤤","k":"drooling 流口水"},{"e":"😴","k":"sleeping 睡覺"},{"e":"😷","k":"mask 口罩 生病"},{"e":"🤒","k":"thermometer sick 發燒"},{"e":"🤕","k":"head bandage 受傷"},{"e":"🤢","k":"nauseated 想吐"},{"e":"🤮","k":"vomit 吐"},{"e":"🤧","k":"sneeze 打噴嚏"},{"e":"🥵","k":"hot 熱"},{"e":"🥶","k":"cold 冷"},{"e":"🥴","k":"woozy 醉"},{"e":"😵","k":"dizzy 暈"},{"e":"🤯","k":"exploding 爆炸 震驚"},{"e":"🤠","k":"cowboy 牛仔"},{"e":"🥳","k":"party 派對 慶生"},{"e":"😎","k":"sunglasses cool 酷 墨鏡"},{"e":"🤓","k":"nerd 書呆子"},{"e":"🧐","k":"monocle 單片眼鏡"},{"e":"😕","k":"confused 困惑"},{"e":"😟","k":"worried 擔心"},{"e":"🙁","k":"frown 皺眉"},{"e":"☹️","k":"frowning 難過"},{"e":"😮","k":"surprised 驚訝"},{"e":"😯","k":"hushed 驚"},{"e":"😲","k":"astonished 驚訝"},{"e":"😳","k":"flushed 臉紅"},{"e":"🥺","k":"pleading 拜託"},{"e":"😦","k":"frown open 驚慌"},{"e":"😧","k":"anguished 痛苦"},{"e":"😨","k":"fearful 害怕"},{"e":"😰","k":"cold sweat 冷汗"},{"e":"😥","k":"sad relieved 難過"},{"e":"😢","k":"cry 哭"},{"e":"😭","k":"loud cry 大哭"},{"e":"😱","k":"scream 尖叫"},{"e":"😖","k":"confounded 糾結"},{"e":"😣","k":"persevering 努力"},{"e":"😞","k":"disappointed 失望"},{"e":"😓","k":"downcast sweat 汗顏"},{"e":"😩","k":"weary 累"},{"e":"😫","k":"tired 疲累"},{"e":"🥱","k":"yawn 哈欠"},{"e":"😤","k":"triumph angry 生氣 哼"},{"e":"😡","k":"pout rage 憤怒"},{"e":"😠","k":"angry 生氣"},{"e":"🤬","k":"cursing 罵人 髒話"},{"e":"😈","k":"devil smile 壞笑"},{"e":"👿","k":"devil angry 惡魔"},{"e":"💀","k":"skull 骷髏 死"},{"e":"👻","k":"ghost 鬼 幽靈"},{"e":"👽","k":"alien 外星人"},{"e":"🤖","k":"robot 機器人"},{"e":"💩","k":"poop 便便"},{"e":"👋","k":"wave hi 揮手 你好"},{"e":"🤚","k":"raised back 舉手"},{"e":"🖐️","k":"hand spread 五指張開"},{"e":"✋","k":"raised 舉手 停"},{"e":"🖖","k":"vulcan 瓦肯"},{"e":"👌","k":"ok perfect 好 完美"},{"e":"🤌","k":"pinched 捏"},{"e":"🤏","k":"pinch small 一點點"},{"e":"✌️","k":"peace victory 勝利 二"},{"e":"🤞","k":"crossed fingers 祈禱 希望"},{"e":"🤟","k":"love you 我愛你"},{"e":"🤘","k":"rock horns 搖滾"},{"e":"🤙","k":"call me 打電話"},{"e":"👈","k":"point left 指左"},{"e":"👉","k":"point right 指右"},{"e":"👆","k":"point up 指上"},{"e":"🖕","k":"middle finger 中指"},{"e":"👇","k":"point down 指下"},{"e":"☝️","k":"point up 食指"},{"e":"👍","k":"thumbs up 讚 好"},{"e":"👎","k":"thumbs down 噓 差"},{"e":"✊","k":"fist 拳頭"},{"e":"👊","k":"punch 揍"},{"e":"🤛","k":"left fist 拳"},{"e":"🤜","k":"right fist 拳"},{"e":"👏","k":"clap 拍手 鼓掌"},{"e":"🙌","k":"praise 舉手 萬歲"},{"e":"👐","k":"open hands 雙手"},{"e":"🤲","k":"palms up 攤手"},{"e":"🤝","k":"handshake 握手"},{"e":"🙏","k":"pray please 拜託 祈禱"},{"e":"✍️","k":"writing 寫字"},{"e":"💅","k":"nail polish 指甲油"},{"e":"🤳","k":"selfie 自拍"},{"e":"💪","k":"muscle 肌肉 加油"},{"e":"🦾","k":"mechanical arm 機械手"},{"e":"🦿","k":"mechanical leg 機械腿"},{"e":"🦵","k":"leg 腿"},{"e":"🦶","k":"foot 腳"},{"e":"👂","k":"ear 耳朵"},{"e":"❤️","k":"red heart 愛心 紅色"},{"e":"🧡","k":"orange heart 橘色愛心"},{"e":"💛","k":"yellow heart 黃色愛心"},{"e":"💚","k":"green heart 綠色愛心"},{"e":"💙","k":"blue heart 藍色愛心"},{"e":"💜","k":"purple heart 紫色愛心"},{"e":"🖤","k":"black heart 黑色愛心"},{"e":"🤍","k":"white heart 白色愛心"},{"e":"🤎","k":"brown heart 棕色愛心"},{"e":"💔","k":"broken heart 心碎"},{"e":"❣️","k":"heart exclamation 愛心驚嘆"},{"e":"💕","k":"two hearts 雙愛心"},{"e":"💞","k":"revolving hearts 旋轉愛心"},{"e":"💓","k":"beating heart 愛心跳動"},{"e":"💗","k":"growing heart 愛心放大"},{"e":"💖","k":"sparkling heart 閃亮愛心"},{"e":"💘","k":"cupid arrow 丘比特之箭"},{"e":"💝","k":"heart gift 禮物愛心"},{"e":"💟","k":"heart decoration 愛心"},{"e":"♥️","k":"suit heart 愛心"},{"e":"💌","k":"love letter 情書"},{"e":"😻","k":"heart eyes cat 愛心貓"},{"e":"💑","k":"couple heart 情侶"},{"e":"💏","k":"kiss couple 接吻"},{"e":"🎉","k":"party popper 慶祝 派對"},{"e":"🎊","k":"confetti 彩紙"},{"e":"🎂","k":"cake 蛋糕 生日"},{"e":"🎁","k":"gift present 禮物"},{"e":"🎈","k":"balloon 氣球"},{"e":"🎆","k":"fireworks 煙火"},{"e":"🎇","k":"sparkler 仙女棒"},{"e":"✨","k":"sparkles 閃亮"},{"e":"⭐","k":"star 星星"},{"e":"🌟","k":"glowing star 閃亮星星"},{"e":"💫","k":"dizzy stars 星星"},{"e":"🎀","k":"ribbon 蝴蝶結"},{"e":"🎗️","k":"reminder ribbon 紀念緞帶"},{"e":"🏆","k":"trophy 獎盃"},{"e":"🥇","k":"gold medal 金牌"},{"e":"🥈","k":"silver medal 銀牌"},{"e":"🥉","k":"bronze medal 銅牌"},{"e":"🎖️","k":"military medal 勳章"},{"e":"👑","k":"crown 皇冠"},{"e":"💎","k":"diamond 鑽石"},{"e":"🥂","k":"clinking glasses 乾杯"},{"e":"🍾","k":"champagne 香檳"},{"e":"🎵","k":"music note 音符"},{"e":"🎶","k":"music notes 音符"},{"e":"🍎","k":"red apple 蘋果"},{"e":"🍊","k":"orange 柳橙"},{"e":"🍋","k":"lemon 檸檬"},{"e":"🍌","k":"banana 香蕉"},{"e":"🍉","k":"watermelon 西瓜"},{"e":"🍇","k":"grapes 葡萄"},{"e":"🍓","k":"strawberry 草莓"},{"e":"🫐","k":"blueberries 藍莓"},{"e":"🍈","k":"melon 哈密瓜"},{"e":"🍒","k":"cherries 櫻桃"},{"e":"🍑","k":"peach 桃子"},{"e":"🥭","k":"mango 芒果"},{"e":"🍍","k":"pineapple 鳳梨"},{"e":"🥝","k":"kiwi 奇異果"},{"e":"🥥","k":"coconut 椰子"},{"e":"🍅","k":"tomato 番茄"},{"e":"🥑","k":"avocado 酪梨"},{"e":"🍆","k":"eggplant 茄子"},{"e":"🌽","k":"corn 玉米"},{"e":"🥕","k":"carrot 紅蘿蔔"},{"e":"🍞","k":"bread 麵包"},{"e":"🥐","k":"croissant 可頌"},{"e":"🥖","k":"baguette 法國麵包"},{"e":"🥨","k":"pretzel 椒鹽脆餅"},{"e":"🧀","k":"cheese 起司"},{"e":"🍳","k":"egg fried 煎蛋"},{"e":"🥞","k":"pancakes 鬆餅"},{"e":"🥓","k":"bacon 培根"},{"e":"🥩","k":"steak 牛排"},{"e":"🍗","k":"chicken drumstick 雞腿"},{"e":"🍖","k":"meat bone 肉"},{"e":"🌭","k":"hotdog 熱狗"},{"e":"🍔","k":"hamburger 漢堡"},{"e":"🍟","k":"fries 薯條"},{"e":"🍕","k":"pizza 披薩"},{"e":"🌮","k":"taco 墨西哥捲餅"},{"e":"🌯","k":"burrito 墨西哥捲"},{"e":"🥗","k":"salad 沙拉"},{"e":"🍝","k":"spaghetti 義大利麵"},{"e":"🍜","k":"ramen 拉麵"},{"e":"🍱","k":"bento 便當"},{"e":"🍣","k":"sushi 壽司"},{"e":"🍤","k":"shrimp 炸蝦"},{"e":"🍙","k":"rice ball 飯糰"},{"e":"🍚","k":"rice 白飯"},{"e":"🍘","k":"rice cracker 仙貝"},{"e":"🍢","k":"oden 關東煮"},{"e":"🍡","k":"dango 糯米糰"},{"e":"🥟","k":"dumpling 餃子"},{"e":"🍦","k":"ice cream soft 霜淇淋"},{"e":"🍧","k":"shaved ice 剉冰"},{"e":"🍨","k":"ice cream 冰淇淋"},{"e":"🍩","k":"donut 甜甜圈"},{"e":"🍪","k":"cookie 餅乾"},{"e":"🎂","k":"birthday cake 生日蛋糕"},{"e":"🍰","k":"cake 蛋糕"},{"e":"🧁","k":"cupcake 杯子蛋糕"},{"e":"🥧","k":"pie 派"},{"e":"🍫","k":"chocolate 巧克力"},{"e":"🍬","k":"candy 糖果"},{"e":"🍭","k":"lollipop 棒棒糖"},{"e":"🍮","k":"pudding 布丁"},{"e":"🍯","k":"honey 蜂蜜"},{"e":"☕","k":"coffee 咖啡"},{"e":"🍵","k":"tea 茶"},{"e":"🧋","k":"bubble tea 珍珠奶茶"},{"e":"🍺","k":"beer 啤酒"},{"e":"🍻","k":"cheers beer 乾杯"},{"e":"🍷","k":"wine 紅酒"},{"e":"🍸","k":"cocktail 雞尾酒"},{"e":"🍹","k":"tropical 熱帶飲料"},{"e":"🥤","k":"cup drink 飲料"},{"e":"🐶","k":"dog face 小狗"},{"e":"🐱","k":"cat face 小貓"},{"e":"🐭","k":"mouse 老鼠"},{"e":"🐹","k":"hamster 倉鼠"},{"e":"🐰","k":"rabbit face 兔子"},{"e":"🦊","k":"fox 狐狸"},{"e":"🐻","k":"bear 熊"},{"e":"🐼","k":"panda 熊貓"},{"e":"🐨","k":"koala 無尾熊"},{"e":"🐯","k":"tiger 老虎"},{"e":"🦁","k":"lion 獅子"},{"e":"🐮","k":"cow 牛"},{"e":"🐷","k":"pig 豬"},{"e":"🐸","k":"frog 青蛙"},{"e":"🐵","k":"monkey face 猴子"},{"e":"🙈","k":"see no evil 猴子摀眼"},{"e":"🙉","k":"hear no evil 猴子摀耳"},{"e":"🙊","k":"speak no evil 猴子摀嘴"},{"e":"🐒","k":"monkey 猴子"},{"e":"🐔","k":"chicken 雞"},{"e":"🐧","k":"penguin 企鵝"},{"e":"🐦","k":"bird 鳥"},{"e":"🐤","k":"baby chick 小雞"},{"e":"🦆","k":"duck 鴨子"},{"e":"🦅","k":"eagle 老鷹"},{"e":"🦉","k":"owl 貓頭鷹"},{"e":"🦇","k":"bat 蝙蝠"},{"e":"🐺","k":"wolf 狼"},{"e":"🐗","k":"boar 野豬"},{"e":"🐴","k":"horse face 馬"},{"e":"🦄","k":"unicorn 獨角獸"},{"e":"🐝","k":"bee 蜜蜂"},{"e":"🐛","k":"bug 毛毛蟲"},{"e":"🦋","k":"butterfly 蝴蝶"},{"e":"🐌","k":"snail 蝸牛"},{"e":"🐞","k":"ladybug 瓢蟲"},{"e":"🐜","k":"ant 螞蟻"},{"e":"🕷️","k":"spider 蜘蛛"},{"e":"🐢","k":"turtle 烏龜"},{"e":"🐍","k":"snake 蛇"},{"e":"🐙","k":"octopus 章魚"},{"e":"🦑","k":"squid 魷魚"},{"e":"🦐","k":"shrimp 蝦"},{"e":"🐟","k":"fish 魚"},{"e":"🐬","k":"dolphin 海豚"},{"e":"🐳","k":"whale 鯨魚"},{"e":"🦈","k":"shark 鯊魚"},{"e":"⚽","k":"soccer 足球"},{"e":"🏀","k":"basketball 籃球"},{"e":"🏈","k":"football 美式足球"},{"e":"⚾","k":"baseball 棒球"},{"e":"🎾","k":"tennis 網球"},{"e":"🏐","k":"volleyball 排球"},{"e":"🎱","k":"billiards 撞球"},{"e":"🏓","k":"ping pong 桌球"},{"e":"🏸","k":"badminton 羽球"},{"e":"🎯","k":"dart 飛鏢 目標"},{"e":"🎲","k":"dice 骰子"},{"e":"🎮","k":"game 電動"},{"e":"🕹️","k":"joystick 搖桿"},{"e":"🎨","k":"palette 調色盤"},{"e":"🎬","k":"clapperboard 場記板"},{"e":"📷","k":"camera 相機"},{"e":"📹","k":"video camera 攝影機"},{"e":"🎥","k":"movie camera 電影"},{"e":"📺","k":"tv 電視"},{"e":"📱","k":"phone 手機"},{"e":"💻","k":"laptop 筆電"},{"e":"🖥️","k":"desktop 桌電"},{"e":"⌨️","k":"keyboard 鍵盤"},{"e":"🖱️","k":"mouse 滑鼠"},{"e":"💾","k":"floppy 磁碟片"},{"e":"💿","k":"cd CD"},{"e":"📀","k":"dvd DVD"},{"e":"🔋","k":"battery 電池"},{"e":"🔌","k":"plug 插頭"},{"e":"💡","k":"bulb 燈泡 想法"},{"e":"🔦","k":"flashlight 手電筒"},{"e":"🕯️","k":"candle 蠟燭"},{"e":"📚","k":"books 書本"},{"e":"📖","k":"open book 開書"},{"e":"📝","k":"memo 筆記"},{"e":"✏️","k":"pencil 鉛筆"},{"e":"✒️","k":"pen 鋼筆"},{"e":"📎","k":"paperclip 迴紋針"},{"e":"📌","k":"pushpin 圖釘"},{"e":"📍","k":"round pin 地點"},{"e":"🔑","k":"key 鑰匙"},{"e":"🔒","k":"lock 鎖"},{"e":"🔓","k":"unlock 開鎖"},{"e":"🔔","k":"bell 鈴鐺"},{"e":"🔕","k":"bell mute 靜音"},{"e":"⏰","k":"alarm 鬧鐘"},{"e":"⏳","k":"hourglass 沙漏"},{"e":"☀️","k":"sun 太陽"},{"e":"🌙","k":"moon 月亮"},{"e":"⭐","k":"star 星"},{"e":"🌈","k":"rainbow 彩虹"},{"e":"☁️","k":"cloud 雲"},{"e":"⛅","k":"cloud sun 多雲"},{"e":"🌧️","k":"rain 下雨"},{"e":"⛈️","k":"thunderstorm 雷雨"},{"e":"❄️","k":"snowflake 雪"},{"e":"🔥","k":"fire 火 讚"},{"e":"💧","k":"drop 水滴"},{"e":"🌊","k":"wave 海浪"},{"e":"🚀","k":"rocket 火箭"},{"e":"✈️","k":"airplane 飛機"},{"e":"🚗","k":"car 汽車"},{"e":"🏠","k":"house 房子"},{"e":"⛔","k":"no entry 禁止"},{"e":"✅","k":"check 打勾"},{"e":"❌","k":"cross 叉"},{"e":"❓","k":"question 問號"},{"e":"❗","k":"exclamation 驚嘆"},{"e":"💯","k":"hundred 100 滿分"},{"e":"🎵","k":"music note 音符"}];
const EMOJI_CATS=[{"id":"face","icon":"😀","title":"Faces","start":0,"end":98},{"id":"hand","icon":"👋","title":"Hands","start":98,"end":138},{"id":"heart","icon":"❤️","title":"Hearts","start":138,"end":162},{"id":"celebrate","icon":"🎉","title":"Party","start":162,"end":186},{"id":"food","icon":"🍎","title":"Food","start":186,"end":258},{"id":"animal","icon":"🐶","title":"Animals","start":258,"end":305},{"id":"object","icon":"⚽","title":"Objects","start":305,"end":375}];
let emojiActiveCat = 'face';
let pendingImage = null;
let pendingImageSize = 0;

function renderEmojiGrid(filter){
  const grid = document.getElementById('emoji-grid');
  if(!grid) return;
  while(grid.firstChild) grid.removeChild(grid.firstChild);
  let items;
  if(filter && filter.trim().length > 0){
    const q = filter.toLowerCase();
    items = EMOJI_DATA.filter(x => x.k.toLowerCase().indexOf(q) !== -1 || x.e.indexOf(q) !== -1);
  } else {
    const cat = EMOJI_CATS.find(c => c.id === emojiActiveCat) || EMOJI_CATS[0];
    items = EMOJI_DATA.slice(cat.start, cat.end);
  }
  for(const it of items){
    const cell = document.createElement('div');
    cell.className = 'emoji-cell';
    cell.textContent = it.e;
    cell.title = it.k;
    cell.onclick = () => insertEmojiAtCursor(it.e);
    grid.appendChild(cell);
  }
}
function renderEmojiTabs(){
  const tabs = document.getElementById('emoji-tabs');
  if(!tabs) return;
  while(tabs.firstChild) tabs.removeChild(tabs.firstChild);
  for(const c of EMOJI_CATS){
    const t = document.createElement('span');
    t.className = 'tab' + (c.id === emojiActiveCat ? ' active' : '');
    t.textContent = c.icon;
    t.title = c.title;
    t.onclick = () => {
      emojiActiveCat = c.id;
      const srch = document.getElementById('emoji-search');
      if(srch) srch.value = '';
      renderEmojiTabs();
      renderEmojiGrid('');
    };
    tabs.appendChild(t);
  }
}
function insertEmojiAtCursor(emoji){
  const mi = document.getElementById('msg-input');
  if(!mi) return;
  const start = mi.selectionStart || mi.value.length;
  const end = mi.selectionEnd || mi.value.length;
  mi.value = mi.value.slice(0, start) + emoji + mi.value.slice(end);
  mi.focus();
  try { mi.setSelectionRange(start + emoji.length, start + emoji.length); } catch(e){}
}
function toggleEmojiPicker(){
  const p = document.getElementById('emoji-panel');
  const btn = document.getElementById('emoji-toggle');
  if(!p) return;
  if(p.style.display === 'none' || p.style.display === ''){
    p.style.display = 'block';
    if(btn) btn.classList.add('active');
    renderEmojiTabs();
    renderEmojiGrid('');
    const srch = document.getElementById('emoji-search');
    if(srch){ srch.value = ''; srch.focus(); }
  } else {
    p.style.display = 'none';
    if(btn) btn.classList.remove('active');
  }
}
document.addEventListener('click', (e) => {
  const p = document.getElementById('emoji-panel');
  const btn = document.getElementById('emoji-toggle');
  if(!p || p.style.display === 'none') return;
  if(p.contains(e.target) || (btn && btn.contains(e.target))) return;
  p.style.display = 'none';
  if(btn) btn.classList.remove('active');
});
(function bindEmojiSearch(){
  const wait = setInterval(() => {
    const s = document.getElementById('emoji-search');
    if(!s) return;
    clearInterval(wait);
    s.oninput = () => renderEmojiGrid(s.value);
  }, 100);
})();

// ─── 圖片上傳 ──────────────────────────────────────────────
const IMG_MAX_BYTES = 800 * 1024;
const IMG_MAX_DIM = 1280;

async function handleImageFile(file){
  if(!file) return;
  if(['image/jpeg','image/png','image/webp'].indexOf(file.type) === -1){
    alert('Only JPG / PNG / WebP supported');
    return;
  }
  try {
    const dataUrl = await new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.onerror = () => rej(r.error);
      r.readAsDataURL(file);
    });
    const img = await new Promise((res, rej) => {
      const im = new Image();
      im.onload = () => res(im);
      im.onerror = () => rej(new Error('load failed'));
      im.src = dataUrl;
    });
    let w = img.width, h = img.height;
    if(w > IMG_MAX_DIM || h > IMG_MAX_DIM){
      if(w > h){ h = Math.round(h * IMG_MAX_DIM / w); w = IMG_MAX_DIM; }
      else { w = Math.round(w * IMG_MAX_DIM / h); h = IMG_MAX_DIM; }
    }
    const canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    canvas.getContext('2d').drawImage(img, 0, 0, w, h);
    const compressed = canvas.toDataURL('image/jpeg', 0.7);
    const sizeBytes = Math.ceil(compressed.length * 3 / 4);
    if(sizeBytes > IMG_MAX_BYTES){
      const again = canvas.toDataURL('image/jpeg', 0.5);
      const sz2 = Math.ceil(again.length * 3 / 4);
      if(sz2 > IMG_MAX_BYTES){ alert('Image too large (still over 800 KB after compression), please pick a smaller one'); return; }
      pendingImage = again; pendingImageSize = sz2;
    } else {
      pendingImage = compressed; pendingImageSize = sizeBytes;
    }
    const prev = document.getElementById('img-preview');
    const thumb = document.getElementById('img-preview-thumb');
    const szEl = document.getElementById('img-preview-size');
    thumb.src = pendingImage;
    szEl.textContent = Math.round(pendingImageSize / 1024) + ' KB';
    prev.style.display = 'flex';
  } catch(e){
    alert('Image processing failed' + ': ' + e.message);
    pendingImage = null;
  }
  const inp = document.getElementById('img-file-input');
  if(inp) inp.value = '';
}
function clearImagePreview(){
  pendingImage = null;
  pendingImageSize = 0;
  const prev = document.getElementById('img-preview');
  if(prev) prev.style.display = 'none';
}
(function bindImgInput(){
  const wait = setInterval(() => {
    const f = document.getElementById('img-file-input');
    if(!f) return;
    clearInterval(wait);
    f.onchange = (e) => handleImageFile(e.target.files && e.target.files[0]);
  }, 100);
})();

// ─── Fullscreen Viewer ─────────────────────────────────────
let viewerZoom = 1;
let viewerPanX = 0, viewerPanY = 0;
let viewerCurrentMsgEl = null;
let viewerDevtoolsCheckTimer = null;
let msgLiveCheckTimer = null;

function openImageViewer(dataUrl, msgEl){
  const v = document.getElementById('img-viewer');
  const content = document.getElementById('img-viewer-content');
  const warn = document.getElementById('img-viewer-warn');
  if(!v || !content) return;
  viewerCurrentMsgEl = msgEl;
  viewerZoom = 1; viewerPanX = 0; viewerPanY = 0;
  content.style.backgroundImage = "url('" + dataUrl + "')";
  applyViewerTransform();
  v.style.display = 'flex';
  if(warn){ warn.textContent = '⚠ Do not screenshot or share · image auto-destroyed'; warn.style.display = 'block'; }
  setTimeout(() => { if(warn) warn.style.display = 'none'; }, 3500);
  startDevtoolsCheck();
  startMsgLiveCheck();
}
function closeImageViewer(){
  const v = document.getElementById('img-viewer');
  const content = document.getElementById('img-viewer-content');
  if(v) v.style.display = 'none';
  if(content) content.style.backgroundImage = '';
  viewerCurrentMsgEl = null;
  stopDevtoolsCheck();
  stopMsgLiveCheck();
}
function applyViewerTransform(){
  const content = document.getElementById('img-viewer-content');
  const zoomText = document.getElementById('img-viewer-zoom');
  if(!content) return;
  content.style.transform = 'translate(' + viewerPanX + 'px,' + viewerPanY + 'px) scale(' + viewerZoom + ')';
  if(zoomText) zoomText.textContent = Math.round(viewerZoom * 100) + '%';
}
function viewerZoomIn(){ viewerZoom = Math.min(5, viewerZoom + 0.25); applyViewerTransform(); }
function viewerZoomOut(){ viewerZoom = Math.max(0.25, viewerZoom - 0.25); if(viewerZoom <= 1){ viewerPanX = 0; viewerPanY = 0; } applyViewerTransform(); }
function viewerReset(){ viewerZoom = 1; viewerPanX = 0; viewerPanY = 0; applyViewerTransform(); }

(function bindViewer(){
  const wait = setInterval(() => {
    const stage = document.getElementById('img-viewer-stage');
    if(!stage) return;
    clearInterval(wait);
    let dragging = false, lastX = 0, lastY = 0;
    stage.addEventListener('mousedown', (e) => {
      if(viewerZoom <= 1) return;
      dragging = true; lastX = e.clientX; lastY = e.clientY;
      stage.classList.add('dragging');
    });
    document.addEventListener('mousemove', (e) => {
      if(!dragging) return;
      viewerPanX += e.clientX - lastX;
      viewerPanY += e.clientY - lastY;
      lastX = e.clientX; lastY = e.clientY;
      applyViewerTransform();
    });
    document.addEventListener('mouseup', () => {
      dragging = false;
      const st = document.getElementById('img-viewer-stage');
      if(st) st.classList.remove('dragging');
    });
    stage.addEventListener('wheel', (e) => {
      e.preventDefault();
      if(e.deltaY < 0) viewerZoomIn(); else viewerZoomOut();
    }, {passive: false});
    stage.addEventListener('click', (e) => {
      if(e.target === stage) closeImageViewer();
    });
    document.addEventListener('keydown', (e) => {
      const v = document.getElementById('img-viewer');
      if(v && v.style.display !== 'none' && e.key === 'Escape') closeImageViewer();
    });
    stage.addEventListener('contextmenu', (e) => e.preventDefault());
  }, 100);
})();

function startDevtoolsCheck(){
  stopDevtoolsCheck();
  viewerDevtoolsCheckTimer = setInterval(() => {
    const threshold = 160;
    if(window.outerWidth - window.innerWidth > threshold || window.outerHeight - window.innerHeight > threshold){
      const warn = document.getElementById('img-viewer-warn');
      if(warn){ warn.textContent = '⚠ DevTools detected · do not capture content'; warn.style.display = 'block'; }
    }
  }, 800);
}
function stopDevtoolsCheck(){ if(viewerDevtoolsCheckTimer){ clearInterval(viewerDevtoolsCheckTimer); viewerDevtoolsCheckTimer = null; } }
function startMsgLiveCheck(){
  stopMsgLiveCheck();
  msgLiveCheckTimer = setInterval(() => {
    if(!viewerCurrentMsgEl || !document.body.contains(viewerCurrentMsgEl)) closeImageViewer();
  }, 500);
}
function stopMsgLiveCheck(){ if(msgLiveCheckTimer){ clearInterval(msgLiveCheckTimer); msgLiveCheckTimer = null; } }

// 動態注入 emoji + 圖片按鈕到 input-area 左邊(在 clean-toggle 右邊、msg-input 前)
(function injectInputButtons(){
  const wait = setInterval(() => {
    const inp = document.getElementById('input-area');
    const mi = document.getElementById('msg-input');
    if(!inp || !mi || document.getElementById('emoji-toggle')){ if(document.getElementById('emoji-toggle')) clearInterval(wait); return; }
    clearInterval(wait);
    const emojiBtn = document.createElement('button');
    emojiBtn.id = 'emoji-toggle';
    emojiBtn.className = 'clean-btn';
    emojiBtn.title = 'Emoji';
    emojiBtn.textContent = '😀';
    emojiBtn.onclick = (e) => { e.stopPropagation(); toggleEmojiPicker(); };
    inp.insertBefore(emojiBtn, mi);
    const imgBtn = document.createElement('button');
    imgBtn.id = 'img-attach';
    imgBtn.className = 'clean-btn';
    imgBtn.title = 'Attach image';
    imgBtn.textContent = '📎';
    imgBtn.onclick = () => document.getElementById('img-file-input').click();
    inp.insertBefore(imgBtn, mi);
  }, 200);
})();


// ─── E2E 加密 (AES-256-GCM) — WebCrypto + 純 JS fallback ───
const HAS_SUBTLE = typeof crypto !== 'undefined' && crypto.subtle && typeof crypto.subtle.importKey === 'function';

function b64encode(buf){ let s=''; const b=new Uint8Array(buf); for(let i=0;i<b.length;i++) s+=String.fromCharCode(b[i]); return btoa(s); }
function b64decode(str){ const s=atob(str); const b=new Uint8Array(s.length); for(let i=0;i<s.length;i++) b[i]=s.charCodeAt(i); return b; }

const _K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
function _sha256(msg){
  const len=msg.length, bits=len*8, padLen=((len+9+63)>>6)<<6;
  const buf=new Uint8Array(padLen); buf.set(msg); buf[len]=0x80;
  const dv=new DataView(buf.buffer);
  dv.setUint32(padLen-4, bits>>>0, false);
  dv.setUint32(padLen-8, Math.floor(bits/0x100000000), false);
  let h0=0x6a09e667,h1=0xbb67ae85,h2=0x3c6ef372,h3=0xa54ff53a,h4=0x510e527f,h5=0x9b05688c,h6=0x1f83d9ab,h7=0x5be0cd19;
  const W=new Uint32Array(64);
  for(let i=0;i<padLen;i+=64){
    for(let t=0;t<16;t++) W[t]=dv.getUint32(i+t*4,false);
    for(let t=16;t<64;t++){
      const x=W[t-15],y=W[t-2];
      const s0=((x>>>7)|(x<<25))^((x>>>18)|(x<<14))^(x>>>3);
      const s1=((y>>>17)|(y<<15))^((y>>>19)|(y<<13))^(y>>>10);
      W[t]=(W[t-16]+s0+W[t-7]+s1)>>>0;
    }
    let a=h0,b=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;
    for(let t=0;t<64;t++){
      const S1=((e>>>6)|(e<<26))^((e>>>11)|(e<<21))^((e>>>25)|(e<<7));
      const ch=(e&f)^(~e&g);
      const T1=(h+S1+ch+_K[t]+W[t])>>>0;
      const S0=((a>>>2)|(a<<30))^((a>>>13)|(a<<19))^((a>>>22)|(a<<10));
      const mj=(a&b)^(a&c)^(b&c);
      const T2=(S0+mj)>>>0;
      h=g;g=f;f=e;e=(d+T1)>>>0;d=c;c=b;b=a;a=(T1+T2)>>>0;
    }
    h0=(h0+a)>>>0;h1=(h1+b)>>>0;h2=(h2+c)>>>0;h3=(h3+d)>>>0;h4=(h4+e)>>>0;h5=(h5+f)>>>0;h6=(h6+g)>>>0;h7=(h7+h)>>>0;
  }
  const out=new Uint8Array(32),odv=new DataView(out.buffer);
  odv.setUint32(0,h0,false);odv.setUint32(4,h1,false);odv.setUint32(8,h2,false);odv.setUint32(12,h3,false);
  odv.setUint32(16,h4,false);odv.setUint32(20,h5,false);odv.setUint32(24,h6,false);odv.setUint32(28,h7,false);
  return out;
}
function _hmac(key,msg){
  let k=key; if(k.length>64) k=_sha256(k);
  const k0=new Uint8Array(64); k0.set(k);
  const ipad=new Uint8Array(64),opad=new Uint8Array(64);
  for(let i=0;i<64;i++){ipad[i]=k0[i]^0x36;opad[i]=k0[i]^0x5c;}
  const inner=new Uint8Array(64+msg.length); inner.set(ipad); inner.set(msg,64);
  const ih=_sha256(inner);
  const outer=new Uint8Array(96); outer.set(opad); outer.set(ih,64);
  return _sha256(outer);
}
function _pbkdf2(pwd,salt,iter,dkLen){
  const blocks=Math.ceil(dkLen/32), out=new Uint8Array(blocks*32);
  for(let i=1;i<=blocks;i++){
    const sI=new Uint8Array(salt.length+4); sI.set(salt);
    new DataView(sI.buffer).setUint32(salt.length,i,false);
    let U=_hmac(pwd,sI); const T=new Uint8Array(U);
    for(let j=1;j<iter;j++){U=_hmac(pwd,U); for(let k=0;k<32;k++) T[k]^=U[k];}
    out.set(T,(i-1)*32);
  }
  return out.slice(0,dkLen);
}
const _SBOX=new Uint8Array([99,124,119,123,242,107,111,197,48,1,103,43,254,215,171,118,202,130,201,125,250,89,71,240,173,212,162,175,156,164,114,192,183,253,147,38,54,63,247,204,52,165,229,241,113,216,49,21,4,199,35,195,24,150,5,154,7,18,128,226,235,39,178,117,9,131,44,26,27,110,90,160,82,59,214,179,41,227,47,132,83,209,0,237,32,252,177,91,106,203,190,57,74,76,88,207,208,239,170,251,67,77,51,133,69,249,2,127,80,60,159,168,81,163,64,143,146,157,56,245,188,182,218,33,16,255,243,210,205,12,19,236,95,151,68,23,196,167,126,61,100,93,25,115,96,129,79,220,34,42,144,136,70,238,184,20,222,94,11,219,224,50,58,10,73,6,36,92,194,211,172,98,145,149,228,121,231,200,55,109,141,213,78,169,108,86,244,234,101,122,174,8,186,120,37,46,28,166,180,198,232,221,116,31,75,189,139,138,112,62,181,102,72,3,246,14,97,53,87,185,134,193,29,158,225,248,152,17,105,217,142,148,155,30,135,233,206,85,40,223,140,161,137,13,191,230,66,104,65,153,45,15,176,84,187,22]);
const _RCON=new Uint8Array([0,1,2,4,8,16,32,64,128,27,54]);
function _xt(b){return((b<<1)^(((b>>7)&1)*0x1b))&0xff;}
function _aesExp(key){
  const Nk=8,Nr=14, w=new Uint8Array(240), temp=new Uint8Array(4);
  w.set(key);
  for(let i=Nk;i<4*(Nr+1);i++){
    temp[0]=w[(i-1)*4];temp[1]=w[(i-1)*4+1];temp[2]=w[(i-1)*4+2];temp[3]=w[(i-1)*4+3];
    if(i%Nk===0){
      const t=temp[0];temp[0]=temp[1];temp[1]=temp[2];temp[2]=temp[3];temp[3]=t;
      temp[0]=_SBOX[temp[0]];temp[1]=_SBOX[temp[1]];temp[2]=_SBOX[temp[2]];temp[3]=_SBOX[temp[3]];
      temp[0]^=_RCON[i/Nk];
    } else if(i%Nk===4){
      temp[0]=_SBOX[temp[0]];temp[1]=_SBOX[temp[1]];temp[2]=_SBOX[temp[2]];temp[3]=_SBOX[temp[3]];
    }
    w[i*4]=w[(i-Nk)*4]^temp[0]; w[i*4+1]=w[(i-Nk)*4+1]^temp[1];
    w[i*4+2]=w[(i-Nk)*4+2]^temp[2]; w[i*4+3]=w[(i-Nk)*4+3]^temp[3];
  }
  return w;
}
function _aesEnc(block,w){
  const Nr=14, s=new Uint8Array(block);
  for(let i=0;i<16;i++) s[i]^=w[i];
  for(let r=1;r<Nr;r++){
    for(let i=0;i<16;i++) s[i]=_SBOX[s[i]];
    let t;
    t=s[1];s[1]=s[5];s[5]=s[9];s[9]=s[13];s[13]=t;
    t=s[2];s[2]=s[10];s[10]=t;t=s[6];s[6]=s[14];s[14]=t;
    t=s[15];s[15]=s[11];s[11]=s[7];s[7]=s[3];s[3]=t;
    for(let c=0;c<4;c++){
      const a0=s[c*4],a1=s[c*4+1],a2=s[c*4+2],a3=s[c*4+3];
      const all=a0^a1^a2^a3;
      s[c*4]^=all^_xt(a0^a1); s[c*4+1]^=all^_xt(a1^a2);
      s[c*4+2]^=all^_xt(a2^a3); s[c*4+3]^=all^_xt(a3^a0);
    }
    for(let i=0;i<16;i++) s[i]^=w[r*16+i];
  }
  for(let i=0;i<16;i++) s[i]=_SBOX[s[i]];
  let t;
  t=s[1];s[1]=s[5];s[5]=s[9];s[9]=s[13];s[13]=t;
  t=s[2];s[2]=s[10];s[10]=t;t=s[6];s[6]=s[14];s[14]=t;
  t=s[15];s[15]=s[11];s[11]=s[7];s[7]=s[3];s[3]=t;
  for(let i=0;i<16;i++) s[i]^=w[Nr*16+i];
  return s;
}
function _gmul(X,Y){
  const Z=new Uint8Array(16),V=new Uint8Array(Y);
  for(let i=0;i<128;i++){
    if((X[i>>3]>>(7-(i&7)))&1){for(let j=0;j<16;j++) Z[j]^=V[j];}
    const lsb=V[15]&1;
    for(let j=15;j>0;j--) V[j]=(V[j]>>>1)|((V[j-1]&1)<<7);
    V[0]>>>=1; if(lsb) V[0]^=0xe1;
  }
  return Z;
}
function _ghash(H,data){
  const Y=new Uint8Array(16);
  for(let i=0;i<data.length;i+=16){
    const blk=new Uint8Array(16); blk.set(data.slice(i,i+16));
    for(let j=0;j<16;j++) Y[j]^=blk[j];
    Y.set(_gmul(Y,H));
  }
  return Y;
}
function _gcmEnc(key,iv,plain){
  const w=_aesExp(key), H=_aesEnc(new Uint8Array(16),w);
  const J0=new Uint8Array(16); J0.set(iv); J0[15]=1;
  const ct=new Uint8Array(plain.length), ctr=new Uint8Array(J0);
  for(let i=0;i<plain.length;i+=16){
    for(let j=15;j>=12;j--){ctr[j]=(ctr[j]+1)&0xff; if(ctr[j]!==0) break;}
    const ks=_aesEnc(ctr,w);
    const bl=Math.min(16,plain.length-i);
    for(let j=0;j<bl;j++) ct[i+j]=plain[i+j]^ks[j];
  }
  const ctPad=ct.length%16===0?0:16-(ct.length%16);
  const gIn=new Uint8Array(ct.length+ctPad+16);
  gIn.set(ct);
  new DataView(gIn.buffer).setUint32(gIn.length-4, ct.length*8, false);
  const S=_ghash(H,gIn);
  const ekJ0=_aesEnc(J0,w), tag=new Uint8Array(16);
  for(let i=0;i<16;i++) tag[i]=S[i]^ekJ0[i];
  const out=new Uint8Array(ct.length+16);
  out.set(ct); out.set(tag,ct.length);
  return out;
}
function _gcmDec(key,iv,combined){
  if(combined.length<16) throw new Error('ciphertext too short');
  const ct=combined.slice(0,combined.length-16), tag=combined.slice(combined.length-16);
  const w=_aesExp(key), H=_aesEnc(new Uint8Array(16),w);
  const J0=new Uint8Array(16); J0.set(iv); J0[15]=1;
  const ctPad=ct.length%16===0?0:16-(ct.length%16);
  const gIn=new Uint8Array(ct.length+ctPad+16);
  gIn.set(ct);
  new DataView(gIn.buffer).setUint32(gIn.length-4, ct.length*8, false);
  const S=_ghash(H,gIn);
  const ekJ0=_aesEnc(J0,w);
  let diff=0;
  for(let i=0;i<16;i++) diff|=(S[i]^ekJ0[i])^tag[i];
  if(diff!==0) throw new Error('Auth tag mismatch');
  const pt=new Uint8Array(ct.length), ctr=new Uint8Array(J0);
  for(let i=0;i<ct.length;i+=16){
    for(let j=15;j>=12;j--){ctr[j]=(ctr[j]+1)&0xff; if(ctr[j]!==0) break;}
    const ks=_aesEnc(ctr,w);
    const bl=Math.min(16,ct.length-i);
    for(let j=0;j<bl;j++) pt[i+j]=ct[i+j]^ks[j];
  }
  return pt;
}
function _randBytes(n){
  if(typeof crypto!=='undefined' && crypto.getRandomValues){
    const b=new Uint8Array(n); crypto.getRandomValues(b); return b;
  }
  const b=new Uint8Array(n);
  for(let i=0;i<n;i++) b[i]=Math.floor(Math.random()*256);
  return b;
}

async function deriveKey(password, salt){
  const enc = new TextEncoder();
  if(HAS_SUBTLE){
    const baseKey = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey(
      { name:'PBKDF2', salt: enc.encode(salt), iterations: 200000, hash: 'SHA-256' },
      baseKey, { name:'AES-GCM', length: 256 }, false, ['encrypt','decrypt']
    );
  }
  return _pbkdf2(enc.encode(password), enc.encode(salt), 50000, 32);
}
async function encryptText(plaintext){
  if(!cryptoKey) throw new Error('no key');
  const iv = _randBytes(12);
  const ptBytes = new TextEncoder().encode(plaintext);
  let ctBuf;
  if(HAS_SUBTLE){
    ctBuf = new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM', iv}, cryptoKey, ptBytes));
  } else {
    ctBuf = _gcmEnc(cryptoKey, iv, ptBytes);
  }
  return { ct: b64encode(ctBuf), iv: b64encode(iv) };
}
async function decryptText(payload){
  if(!cryptoKey || !payload || !payload.ct || !payload.iv) throw new Error('bad payload');
  const ctBytes = b64decode(payload.ct);
  const ivBytes = b64decode(payload.iv);
  let pt;
  if(HAS_SUBTLE){
    pt = await crypto.subtle.decrypt({name:'AES-GCM', iv: ivBytes}, cryptoKey, ctBytes);
  } else {
    pt = _gcmDec(cryptoKey, ivBytes, ctBytes);
  }
  return new TextDecoder().decode(pt);
}

function ensureAudioCtx(){
  if(!audioCtx){ try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch(e){} }
  if(audioCtx && audioCtx.state === 'suspended'){ try { audioCtx.resume(); } catch(e){} }
  return audioCtx;
}
function playNotify(){
  if(!soundEnabled) return;
  const ctx = ensureAudioCtx(); if(!ctx) return;
  const now = ctx.currentTime;
  function tone(f,s,d,v){ try {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type='sine'; o.frequency.value=f;
    g.gain.setValueAtTime(0, now+s);
    g.gain.linearRampToValueAtTime(v, now+s+0.008);
    g.gain.exponentialRampToValueAtTime(0.001, now+s+d);
    o.connect(g); g.connect(ctx.destination);
    o.start(now+s); o.stop(now+s+d+0.02);
  } catch(e){} }
  tone(784,0,0.22,0.14); tone(1568,0,0.22,0.035); tone(2352,0,0.22,0.015);
  tone(1047,0.09,0.40,0.16); tone(2094,0.09,0.40,0.04); tone(3141,0.09,0.40,0.017);
}
function toggleSound(){
  soundEnabled = !soundEnabled;
  const btn = document.getElementById('sound-btn');
  if(btn) btn.textContent = soundEnabled ? '🔔' : '🔕';
  if(soundEnabled){ ensureAudioCtx(); playNotify(); }
}
function updateTitle(){
  document.title = unreadCount > 0 ? '(' + unreadCount + ') ' + BASE_TITLE : BASE_TITLE;
  if(vscodeApi){ try { vscodeApi.postMessage({type:'unread', count: unreadCount}); } catch(e){} }
}

function authenticate() {
  const name = document.getElementById('nick-input').value.trim();
  const pwd = document.getElementById('pwd-input').value;
  const err = document.getElementById('auth-err');
  if(!name){ err.textContent = 'Nickname required'; return; }
  if(!pwd){ err.textContent = 'Password required'; return; }
  ensureAudioCtx();

  fetch(SERVER + '/auth', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({roomId: ROOM_ID_FROM_URL, password: pwd, nickname: name})
  })
  .then(r => r.json()).then(async data => {
    if(data.ok){
      try {
        cryptoKey = await deriveKey(pwd, 'burnerchat-v1:' + (ROOM_ID_FROM_URL || 'default'));
      } catch(e){
        err.textContent = 'Crypto init failed: ' + (e.message || e); return;
      }
      authToken = data.token;
      nick = data.nick;
      clientId = data.clientId;
      sinceSeq = data.since || 0;
      if(typeof data.burnDuration === 'number'){
        burnDuration = data.burnDuration;
        const bs = document.getElementById('burn-sec');
        if(bs) bs.value = burnDuration;
      }
      // Initialize roster
      roster = Array.isArray(data.nicks) ? data.nicks.slice() : [];
      rosterExpanded = false;
      renderRoster();
      // Start redacted by default (not focused yet)
      updateChatVisibility();
      startHeartbeat();
      document.getElementById('me-label').textContent = '@' + nick;
      document.getElementById('auth-overlay').style.display = 'none';
      ['header','roster','sys-log','burn-bar','messages','input-area'].forEach(id => {
        const el = document.getElementById(id);
        if(el) el.style.display = (id === 'messages' || id === 'burn-bar' || id === 'roster') ? 'flex' : '';
      });
      renderSysLog();
      onConnected();
      startPolling();
    } else {
      err.textContent = data.error || 'Authentication failed';
      setTimeout(()=>err.textContent='', 2500);
    }
  }).catch(()=>document.getElementById('auth-err').textContent = 'Cannot connect to server');
}

function onConnected(){
  const mi = document.getElementById('msg-input');
  const s = document.getElementById('status');
  s.textContent = 'Connected (E2E encrypted) via HTTP long polling'; s.style.color = '#00ff88';
  addSysMsg('Joined chat room (end-to-end encrypted)');
  if(mi){ mi.disabled = false; mi.placeholder = 'Type a message... (Enter to send)'; mi.focus(); }
}

function onDisconnected(reason){
  const mi = document.getElementById('msg-input');
  const s = document.getElementById('status');
  if(s){ s.textContent = 'Disconnected'; s.style.color = '#ff4500'; }
  addSysMsg(reason || 'Connection closed');
  if(mi){ mi.disabled = true; mi.placeholder = 'Disconnected'; }
}

async function startPolling(){
  if(polling) return;
  polling = true;
  let backoff = 0;
  while(polling){
    pollAbortCtrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    try {
      const url = SERVER + '/poll?token=' + encodeURIComponent(authToken) + '&since=' + sinceSeq;
      const opts = pollAbortCtrl ? { signal: pollAbortCtrl.signal } : {};
      const r = await fetch(url, opts);
      if(r.status === 401 || r.status === 404){
        polling = false;
        resetToLogin('Disconnected or kicked by admin, please re-login');
        return;
      }
      if(!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json();
      backoff = 0;
      if(d.events && d.events.length > 0){
        for(const ev of d.events) await handleEvent(ev);
        sinceSeq = d.nextSince;
      } else if(typeof d.nextSince === 'number'){
        sinceSeq = d.nextSince;
      }
    } catch(e){
      if(e.name === 'AbortError') break;
      backoff = Math.min(10000, (backoff || 500) * 2);
      await new Promise(r => setTimeout(r, backoff));
    }
  }
}

function stopPolling(){
  polling = false;
  if(pollAbortCtrl){ try { pollAbortCtrl.abort(); } catch(e){} }
}

async function handleEvent(d){
  if(d.type === 'chat'){
    let text = '', image = null;
    try {
      const raw = await decryptText(d.encrypted);
      if(raw && raw.length > 0 && raw.charAt(0) === '{'){
        try { const obj = JSON.parse(raw); text = obj.text || ''; image = obj.image || null; }
        catch(e){ text = raw; }
      } else { text = raw; }
    } catch(err){ text = '[Cannot decrypt - wrong password or corrupted message]'; }
    addChatMsg(d.sender, text, d.sender === nick, d.msgId, d.expectedReaders, image);
  }
  else if(d.type === 'system') addSysMsg(d.text);
  else if(d.type === 'burnUpdate'){
    burnDuration = d.duration;
    const bs = document.getElementById('burn-sec');
    if(bs) bs.value = burnDuration;
    if(!d.silent) addSysMsg(d.by + ' set message lifetime to ' + (burnDuration === 0 ? 'never' : burnDuration + 's'));
  }
  else if(d.type === 'read'){
    markRead(d.msgId, d.reader);
    if(d.reader !== nick) tickMineReaders(d.msgId);
  }
  else if(d.type === 'presenceChange'){
    if(Array.isArray(d.nicks)){
      roster = d.nicks.slice();
      renderRoster();
    }
    onPresenceChange(d.onlineCount);
  }
  else if(d.type === 'roomDeleted'){
    resetToLogin('This room has been deleted by admin');
  }
}

async function apiSend(payload){
  if(!authToken) return false;
  try {
    const r = await fetch(SERVER + '/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(Object.assign({ token: authToken }, payload))
    });
    return r.ok;
  } catch(e){ return false; }
}

// ─── Roster ──────────────────────────────────────────────
function renderRoster() {
  const el = document.getElementById('roster');
  if(!el) return;
  const list = el.querySelector('.roster-list');
  const toggle = el.querySelector('.roster-toggle');
  const n = roster.length;
  const shouldCollapse = n > ROSTER_COLLAPSE_THRESHOLD && !rosterExpanded;
  if(shouldCollapse){
    el.classList.add('collapsed');
    toggle.textContent = '▼ Show ' + n + ' online';
  } else {
    el.classList.remove('collapsed');
    toggle.textContent = n > ROSTER_COLLAPSE_THRESHOLD ? '▲ Hide' : '👥';
    list.textContent = 'Online (' + n + '): ' + roster.join(', ');
  }
}
function toggleRoster() {
  rosterExpanded = !rosterExpanded;
  renderRoster();
}

// ─── 系統訊息獨立區 ──────────────────────────────────────────────
function addSysEntry(text) {
  sysMsgs.push(text);
  if (sysMsgs.length > MAX_SYS_MSGS) sysMsgs.shift();
  renderSysLog();
}
function renderSysLog() {
  const el = document.getElementById('sys-log');
  if (!el) return;
  const last = el.querySelector('.sys-last');
  const full = el.querySelector('.sys-full');
  const toggle = el.querySelector('.sys-toggle');
  const n = sysMsgs.length;
  if (n === 0) { el.style.display = 'none'; return; }
  el.style.display = '';
  last.textContent = '⚙️ ' + sysMsgs[n - 1];
  while (full.firstChild) full.removeChild(full.firstChild);
  for (const m of sysMsgs) {
    const line = document.createElement('div');
    line.className = 'sys-line';
    line.textContent = '⚙️ ' + m;
    full.appendChild(line);
  }
  if (n === 1) {
    toggle.textContent = '';
    toggle.style.display = 'none';
    el.classList.add('collapsed');
  } else {
    toggle.style.display = '';
    toggle.textContent = sysExpanded ? '▲ Hide' : ('▼ Show ' + n + ' system msgs');
    if (sysExpanded) el.classList.remove('collapsed');
    else el.classList.add('collapsed');
  }
}
function toggleSysLog() {
  sysExpanded = !sysExpanded;
  renderSysLog();
}

// 乾淨版(本地狀態):隱藏 header/notice/roster/sys-log/burn-bar,只保留訊息區與輸入列
function toggleCleanMode() {
  cleanMode = !cleanMode;
  const btn = document.getElementById('clean-toggle');
  const input = document.getElementById('msg-input');
  if (cleanMode) {
    document.body.classList.add('clean-mode');
    if (btn) btn.classList.add('active');
    if (input) {
      input.dataset.originalPlaceholder = input.placeholder || '';
      input.placeholder = '';
    }
  } else {
    document.body.classList.remove('clean-mode');
    if (btn) btn.classList.remove('active');
    if (input && input.dataset.originalPlaceholder !== undefined) {
      input.placeholder = input.dataset.originalPlaceholder;
    } else if (input) {
      input.placeholder = 'Type a message...';
    }
  }
}

// ─── Chat redaction ──────────────────────────────────────
function updateChatVisibility() {
  const msgsEl = document.getElementById('messages');
  if(!msgsEl) return;
  const visible = inputFocused && !document.hidden;
  if(visible) msgsEl.classList.remove('redacted');
  else msgsEl.classList.add('redacted');
}

// ─── Heartbeat ───────────────────────────────────────────
function startHeartbeat() {
  stopHeartbeat();
  heartbeatTimer = setInterval(() => { apiSend({ type: 'heartbeat' }); }, HEARTBEAT_INTERVAL);
}
function stopHeartbeat() {
  if(heartbeatTimer){ clearInterval(heartbeatTimer); heartbeatTimer = null; }
}

// ─── Reset to login ──────────────────────────────────────
function resetToLogin(reason) {
  stopPolling();
  stopHeartbeat();
  authToken = null; nick = ''; clientId = null; cryptoKey = null;
  sinceSeq = 0;
  roster = []; rosterExpanded = false;
  sysMsgs.length = 0; sysExpanded = false;
  // 解除乾淨版(不然登入畫面被 clean-mode 蓋住)
  cleanMode = false;
  document.body.classList.remove('clean-mode');
  const cleanBtn = document.getElementById('clean-toggle');
  if (cleanBtn) cleanBtn.classList.remove('active');
  pendingBurn.clear();
  for(const k in msgReads) delete msgReads[k];
  for(const k in sentReads) delete sentReads[k];
  unreadCount = 0; updateTitle();
  const msgsEl = document.getElementById('messages');
  if(msgsEl){ msgsEl.innerHTML = ''; msgsEl.classList.remove('redacted'); msgsEl.style.display = 'none'; }
  const rosterEl = document.getElementById('roster');
  if(rosterEl) rosterEl.style.display = 'none';
  const sysLogEl = document.getElementById('sys-log');
  if(sysLogEl) sysLogEl.style.display = 'none';
  const burnBar = document.getElementById('burn-bar');
  if(burnBar) burnBar.style.display = 'none';
  const inputArea = document.getElementById('input-area');
  if(inputArea) inputArea.style.display = 'none';
  const authOverlay = document.getElementById('auth-overlay');
  if(authOverlay) authOverlay.style.display = 'flex';
  const err = document.getElementById('auth-err');
  if(err && reason){ err.textContent = '⚠ ' + reason; setTimeout(() => err.textContent = '', 4000); }
  const st = document.getElementById('status');
  if(st){ st.textContent = 'Connecting...'; st.style.color = ''; }
  const nickInput = document.getElementById('nick-input');
  if(nickInput) nickInput.focus();
}

function updateBurn() {
  const v = parseInt(document.getElementById('burn-sec').value);
  if(isNaN(v) || v < 0) return;
  apiSend({type: 'setBurn', duration: Math.min(3600, v)});
}

function scheduleBurn(el, extraDelay) {
  if(burnDuration <= 0) return;
  const cd = document.createElement('div');
  cd.className = 'countdown'; el.appendChild(cd);
  let r = burnDuration + (extraDelay || 0); cd.textContent = r + 's';
  const iv = setInterval(() => {
    r--;
    if(r <= 2) el.classList.add('burning');
    if(r <= 0){
      clearInterval(iv);
      el.style.opacity = '0'; el.style.transform = 'translateX(25px) scale(.9)';
      setTimeout(() => el.remove(), 700); return;
    }
    cd.textContent = r + 's';
  }, 1000);
}

function markRead(msgId, reader) {
  if(!msgId || !reader) return;
  if(!msgReads[msgId]) msgReads[msgId] = [];
  if(msgReads[msgId].indexOf(reader) === -1) msgReads[msgId].push(reader);
  updateReadIndicator(msgId);
}
function updateReadIndicator(msgId) {
  const el = document.querySelector('[data-msg-id="' + msgId + '"]'); if(!el) return;
  const rs = msgReads[msgId] || []; if(rs.length === 0) return;
  let ind = el.querySelector('.readby');
  if(!ind){
    ind = document.createElement('div'); ind.className = 'readby';
    const cd = el.querySelector('.countdown');
    if(cd) el.insertBefore(ind, cd); else el.appendChild(ind);
  }
  // Split into two spans: .check (always visible) + .names (hidden in clean mode)
  while(ind.firstChild) ind.removeChild(ind.firstChild);
  const checkSpan = document.createElement('span');
  checkSpan.className = 'check';
  checkSpan.textContent = '✓';
  const namesSpan = document.createElement('span');
  namesSpan.className = 'names';
  namesSpan.textContent = ' Read by: ' + (rs.length <= 3 ? rs.join(', ') : rs.slice(0,3).join(', ') + ' +' + (rs.length-3));
  ind.appendChild(checkSpan);
  ind.appendChild(namesSpan);
}

async function sendMsg() {
  const i = document.getElementById('msg-input');
  const text = i.value.trim();
  if(!text && !pendingImage) return;
  if(!authToken){
    addSysMsg('Not connected, cannot send');
    return;
  }
  const imgToSend = pendingImage;
  i.value = '';
  clearImagePreview();
  try {
    const payload = imgToSend ? JSON.stringify({text: text, image: imgToSend}) : text;
    const enc = await encryptText(payload);
    const ok = await apiSend({type: 'chat', encrypted: enc});
    if(!ok){
      addSysMsg('Transmission failed (network unstable or image too large?)');
      i.value = text;
      if(imgToSend){ pendingImage = imgToSend; document.getElementById('img-preview').style.display = 'flex'; }
    }
  } catch(err){
    addSysMsg('Encryption failed: ' + (err.message || err));
    i.value = text;
    if(imgToSend){ pendingImage = imgToSend; document.getElementById('img-preview').style.display = 'flex'; }
  }
}

function addChatMsg(sender, text, isMine, msgId, expectedReaders, image) {
  const msgs = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'msg ' + (isMine ? 'mine' : 'other');
  if(msgId) div.setAttribute('data-msg-id', msgId);
  const s = document.createElement('div'); s.className = 'sender'; s.textContent = sender; div.appendChild(s);
  if(text){
    const t = document.createElement('div');
    const inner = document.createElement('span');
    inner.className = 'text-content';
    const maskLen = Math.min(30, Math.max(4, Math.ceil((text || '').length / 2) || 4));
    inner.setAttribute('data-mask', '█'.repeat(maskLen));
    inner.textContent = text;
    t.appendChild(inner);
    div.appendChild(t);
  }
  if(image){
    const imgDiv = document.createElement('div');
    imgDiv.className = 'msg-image';
    imgDiv.style.backgroundImage = "url('" + image + "')";
    imgDiv.addEventListener('click', () => openImageViewer(image, div));
    imgDiv.addEventListener('contextmenu', (e) => e.preventDefault());
    div.appendChild(imgDiv);
  }
  msgs.appendChild(div); msgs.scrollTop = msgs.scrollHeight;

  // Burn timing:
  // - My own msg: if nobody needs to read (expectedReaders === 0), start burning immediately;
  //               otherwise wait for enough read events.
  // - Others' msg: add unread marker, start burning when I focus input.
  if(isMine){
    const need = Math.max(0, expectedReaders || 0);
    if(need === 0){
      scheduleBurn(div);
    } else if(msgId){
      pendingBurn.set(msgId, { el: div, isMine: true, readersNeeded: need, readersGot: 0 });
    }
  } else {
    div.classList.add('unread');
    if(msgId) pendingBurn.set(msgId, { el: div, isMine: false });
  }

  if(msgId && msgReads[msgId]) updateReadIndicator(msgId);
  if(!isMine){
    playNotify();
    if(document.hidden){ unreadCount++; updateTitle(); }
  }
}

// When input gets focused → mark all others' unread msgs as read + start burning
function onUserRead() {
  // Batch scheduleBurn: oldest first, +0/+1/+2... seconds per message
  // Prevents mass simultaneous burn when multiple messages pile up
  let delay = 0;
  for (const [msgId, info] of pendingBurn) {
    if (info.isMine) continue;
    info.el.classList.remove('unread');
    scheduleBurn(info.el, delay);
    delay++;
    if (!sentReads[msgId]) {
      sentReads[msgId] = true;
      apiSend({type: 'read', msgId: msgId});
    }
    pendingBurn.delete(msgId);
  }
}

// Tick when someone else read one of my msgs; burn when all needed readers are in
function tickMineReaders(msgId) {
  const info = pendingBurn.get(msgId);
  if (!info || !info.isMine) return;
  info.readersGot++;
  if (info.readersGot >= info.readersNeeded) {
    scheduleBurn(info.el);
    pendingBurn.delete(msgId);
  }
}

// Someone left → lower readersNeeded for my pending msgs; trigger burn if satisfied
function onPresenceChange(onlineCount) {
  const newNeeded = Math.max(0, onlineCount - 1);
  for (const [msgId, info] of pendingBurn) {
    if (!info.isMine) continue;
    if (newNeeded < info.readersNeeded) {
      info.readersNeeded = newNeeded;
      if (info.readersGot >= info.readersNeeded) {
        scheduleBurn(info.el);
        pendingBurn.delete(msgId);
      }
    }
  }
}
function addSysMsg(text) {
  // 系統訊息改進入獨立區 (#sys-log),不再插入 #messages
  addSysEntry(text);
}

window.addEventListener('beforeunload', () => {
  if(!authToken) return;
  try {
    if(navigator.sendBeacon){
      const blob = new Blob([JSON.stringify({token: authToken, type: 'leave'})], {type: 'application/json'});
      navigator.sendBeacon(SERVER + '/send', blob);
    }
  } catch(e){}
  stopPolling();
  stopHeartbeat();
});

document.addEventListener('visibilitychange', () => {
  if(!document.hidden && unreadCount > 0){ unreadCount = 0; updateTitle(); }
  updateChatVisibility();
});
document.getElementById('msg-input')?.addEventListener('keydown', e => { if(e.key === 'Enter') sendMsg(); });
document.getElementById('msg-input')?.addEventListener('focus', () => {
  inputFocused = true;
  updateChatVisibility();
  onUserRead();
});
document.getElementById('msg-input')?.addEventListener('blur', () => {
  inputFocused = false;
  updateChatVisibility();
});
document.getElementById('nick-input')?.addEventListener('keydown', e => {
  if(e.key === 'Enter') document.getElementById('pwd-input').focus();
});
document.getElementById('pwd-input')?.addEventListener('keydown', e => { if(e.key === 'Enter') authenticate(); });
</script>
</body></html>`;
}

function deactivate() {}
module.exports = { activate, deactivate };
"""

MIT_LICENSE_TEMPLATE = """MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

MARKETPLACE_README_TEMPLATE = """# BurnerChat

> Burn-after-reading end-to-end encrypted chat for teams. Messages auto-destroy after a configurable countdown. AES-256-GCM encryption — the server never sees your plaintext.

## Features

- **End-to-end encrypted** — AES-256-GCM, key derived from room password using PBKDF2 (200k iterations). The server only relays ciphertext.
- **Burn after reading** — messages auto-destroy after N seconds (configurable, 0 = never)
- **Read receipts** — see exactly who read each message
- **Custom nicknames** — pick any name when joining
- **Multiple rooms** — admin can create named rooms with independent passwords
- **Notification sounds** — Teams-style two-note chime, mutable per-user
- **Tab title unread count** — `(3) BurnerChat` when window is in background

## Requirements

You need a **BurnerChat server** running somewhere reachable (your LAN, a VPS, etc.). This extension is the **client only** — see [Server Setup](#server-setup) below.

## Quick Start

1. Press `Ctrl+Shift+B` (or `Cmd+Shift+B` on Mac), or run `BurnerChat: Connect to Server` from the command palette
2. Paste your server URL (e.g. `http://192.168.1.100:7788/room/abcd1234`)
3. Enter your nickname and the room password
4. Chat

Recent server URLs are remembered. Use `BurnerChat: Connect to Recent Server` to pick from history.

## Commands

| Command | Default Shortcut | Description |
|---------|-----------------|-------------|
| `BurnerChat: Connect to Server` | `Ctrl+Shift+B` | Enter a server URL and connect |
| `BurnerChat: Connect to Recent Server` | — | Pick from previously-used URLs |
| `BurnerChat: Clear Recent Servers` | — | Wipe URL history |

## Server Setup

The server is a small Node.js script. Get it from the [project repository]({repo}) and run:

```bash
node server.js
```

The server prints the connection URL, default room password, and admin password to the console. Share the URL+password pair with your team via your normal channel (Slack/LINE/email).

## Security Model

**What this protects against:**
- LAN packet sniffing / Wi-Fi eavesdropping
- Compromised proxies / man-in-the-middle
- Server memory dumps (plaintext never exists on server)
- Recorded WebSocket traffic replay

**What it does NOT protect against:**
- Anyone who knows the room password (the password IS the encryption seed)
- A malicious endpoint (compromised laptop, screen recording, etc.)
- Server admins seeing room metadata (sender names, message timing, read receipts)

For maximum security, use long random passwords and treat the room password like a shared secret.

## Privacy

This extension does not collect telemetry. It only connects to the server URL you explicitly provide. URLs you've connected to are stored in VSCode's local global state and never transmitted anywhere except to that server.

## License

MIT — see [LICENSE](LICENSE)
"""

MARKETPLACE_CHANGELOG = """# Change Log

## [1.5.0] - Initial Marketplace Release

- End-to-end encryption (AES-256-GCM, PBKDF2 key derivation)
- Burn-after-reading with configurable lifetime
- Read receipts with sender names
- Multiple rooms with admin panel (server-side)
- Teams-style notification sounds
- Tab title unread count
- Recent servers history

## Earlier versions (pre-marketplace)

- 1.4.0 — Admin panel + multi-room support
- 1.3.0 — Notification sounds + unread title count
- 1.2.0 — Custom nicknames + read receipts
- 1.1.0 — Auto-burn message lifetime
- 1.0.0 — Initial release
"""

VSCODEIGNORE_CONTENT = """.vscode/**
.vscode-test/**
src/**
.gitignore
.yarnrc
vsc-extension-quickstart.md
**/jsconfig.json
**/*.map
**/.eslintrc.json
node_modules/**
*.vsix.bak
"""

def make_burner_icon(path: Path):
    """生成 128x128 BurnerChat icon (深色背景 + 火焰圖示)。
    用 PIL 純程式繪製,不依賴外部圖檔。"""
    from PIL import Image, ImageDraw
    size = 128
    img = Image.new("RGB", (size, size), (10, 10, 10))
    draw = ImageDraw.Draw(img)

    # 圓形背景 (深紅黑漸層感)
    draw.ellipse([8, 8, size-8, size-8], fill=(26, 10, 0))

    # 火焰主體 — 用兩個橢圓堆疊出火焰輪廓
    # 外層深橘
    flame_outer = [
        (32, 96), (38, 78), (28, 60), (44, 44),
        (40, 28), (60, 36), (64, 16), (78, 38),
        (96, 28), (88, 50), (102, 60), (90, 80),
        (100, 96), (32, 96)
    ]
    draw.polygon(flame_outer, fill=(255, 69, 0))

    # 內層亮橘 (火焰核心)
    flame_inner = [
        (48, 92), (52, 78), (44, 64), (58, 52),
        (56, 40), (66, 50), (70, 36), (78, 52),
        (88, 50), (82, 64), (90, 76), (82, 88),
        (88, 92), (48, 92)
    ]
    draw.polygon(flame_inner, fill=(255, 140, 53))

    # 最內層黃白 (火焰最熱點)
    flame_core = [
        (60, 86), (62, 76), (58, 68), (66, 60),
        (68, 52), (74, 62), (78, 56), (80, 70),
        (76, 80), (78, 86), (60, 86)
    ]
    draw.polygon(flame_core, fill=(255, 215, 100))

    img.save(path, "PNG", optimize=True)


def build_marketplace_package(output_dir: Path,
                              publisher: str,
                              repo_url: str,
                              author: str) -> Path:
    """產生可上架 VSCode Marketplace 的擴充套件目錄。
    
    產出包含:package.json (含 publisher/repo)、client-only extension.js、
    README、CHANGELOG、LICENSE、icon.png、.vscodeignore
    """
    mkt_dir = output_dir / "marketplace"
    if mkt_dir.exists():
        shutil.rmtree(mkt_dir)
    mkt_dir.mkdir(parents=True)

    # 1) package.json (替換 placeholder)
    pkg = json.loads(json.dumps(MARKETPLACE_PACKAGE_JSON_TEMPLATE))  # deep copy
    # 正規化 repo URL (移除尾端 / 與 .git,但只能用 endswith,不能用 rstrip)
    repo_clean = repo_url.strip()
    if repo_clean.endswith("/"): repo_clean = repo_clean[:-1]
    if repo_clean.endswith(".git"): repo_clean = repo_clean[:-4]
    pkg["publisher"] = publisher
    pkg["repository"]["url"] = repo_url
    pkg["bugs"]["url"] = repo_clean + "/issues"
    pkg["homepage"] = repo_clean + "#readme"
    (mkt_dir / "package.json").write_text(
        json.dumps(pkg, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 2) client-only extension.js
    (mkt_dir / "extension.js").write_text(MARKETPLACE_EXTENSION_JS, encoding="utf-8")

    # 3) README
    (mkt_dir / "README.md").write_text(
        MARKETPLACE_README_TEMPLATE.format(repo=repo_clean),
        encoding="utf-8"
    )

    # 4) CHANGELOG
    (mkt_dir / "CHANGELOG.md").write_text(MARKETPLACE_CHANGELOG, encoding="utf-8")

    # 5) LICENSE
    (mkt_dir / "LICENSE").write_text(
        MIT_LICENSE_TEMPLATE.format(year=datetime.now().year, author=author),
        encoding="utf-8"
    )

    # 6) icon.png (PIL 生成)
    try:
        make_burner_icon(mkt_dir / "icon.png")
    except Exception as e:
        log(f"  ⚠ Icon 生成失敗 ({e}),請手動放 128x128 PNG 至 icon.png", C.YELLOW)

    # 7) .vscodeignore
    (mkt_dir / ".vscodeignore").write_text(VSCODEIGNORE_CONTENT, encoding="utf-8")

    return mkt_dir


def print_marketplace_instructions(mkt_dir: Path, publisher: str):
    """印出上架步驟指引"""
    print()
    print(f"{C.MAGENTA}{'═'*60}{C.RESET}")
    print(f"{C.BOLD}{C.MAGENTA}  📦  Marketplace 套件已建立!{C.RESET}")
    print(f"{C.MAGENTA}{'═'*60}{C.RESET}")
    print()
    print(f"  {C.BOLD}套件目錄:{C.RESET}")
    print(f"  {C.CYAN}{mkt_dir}{C.RESET}")
    print()
    print(f"  {C.BOLD}下一步上架流程:{C.RESET}")
    print()
    print(f"  {C.YELLOW}1.{C.RESET} 安裝 vsce:")
    print(f"     {C.DIM}npm install -g @vscode/vsce{C.RESET}")
    print()
    print(f"  {C.YELLOW}2.{C.RESET} 在 https://dev.azure.com 建立 Personal Access Token (PAT)")
    print(f"     {C.DIM}- Organization: All accessible organizations{C.RESET}")
    print(f"     {C.DIM}- Scopes: Marketplace → Manage{C.RESET}")
    print()
    print(f"  {C.YELLOW}3.{C.RESET} 在 https://marketplace.visualstudio.com/manage 建立 publisher")
    print(f"     {C.DIM}publisher ID 必須是: {publisher}{C.RESET}")
    print()
    print(f"  {C.YELLOW}4.{C.RESET} 進入套件目錄並登入:")
    print(f"     {C.CYAN}cd {mkt_dir}{C.RESET}")
    print(f"     {C.CYAN}vsce login {publisher}{C.RESET}")
    print()
    print(f"  {C.YELLOW}5.{C.RESET} 先打包測試 (產生 .vsix,可本地安裝測試):")
    print(f"     {C.CYAN}vsce package{C.RESET}")
    print()
    print(f"  {C.YELLOW}6.{C.RESET} 確認沒問題後發布:")
    print(f"     {C.CYAN}vsce publish{C.RESET}")
    print()
    print(f"  {C.DIM}發布後 5–10 分鐘可在以下網址看到:{C.RESET}")
    print(f"  {C.DIM}https://marketplace.visualstudio.com/items?itemName={publisher}.burner-chat{C.RESET}")
    print()
    print(f"{C.MAGENTA}{'═'*60}{C.RESET}")
    print()


def main_marketplace():
    """獨立的 marketplace 流程,不啟動伺服器"""
    print()
    print(f"{C.MAGENTA}╔══════════════════════════════════════════════╗")
    print(f"║  📦  BurnerChat Marketplace Builder           ║")
    print(f"║      產生可上架 VSCode Marketplace 的套件      ║")
    print(f"╚══════════════════════════════════════════════╝{C.RESET}")
    print()

    print(f"{C.DIM}  請輸入以下資訊(會寫入 package.json):{C.RESET}")
    print()

    # 互動式詢問
    publisher = input(f"  {C.BOLD}Publisher ID{C.RESET} (在 marketplace.visualstudio.com/manage 建立的): ").strip()
    if not publisher:
        log("❌ Publisher ID 不可為空", C.RED)
        sys.exit(1)
    if not publisher.replace("-", "").replace("_", "").isalnum():
        log("❌ Publisher ID 只能含英數字、底線、hyphen", C.RED)
        sys.exit(1)

    repo_url = input(f"  {C.BOLD}GitHub Repo URL{C.RESET} (例: https://github.com/you/burner-chat): ").strip()
    if not repo_url:
        log("❌ Repo URL 不可為空 (marketplace 規範要求)", C.RED)
        sys.exit(1)
    if not (repo_url.startswith("http://") or repo_url.startswith("https://")):
        log("❌ Repo URL 必須以 http(s):// 開頭", C.RED)
        sys.exit(1)

    author = input(f"  {C.BOLD}作者名稱{C.RESET} (寫入 LICENSE 的 copyright): ").strip()
    if not author:
        author = publisher

    print()
    log("正在建立 marketplace 套件...", C.CYAN)
    output_dir = Path.home() / ".burner-chat"
    output_dir.mkdir(exist_ok=True)
    mkt_dir = build_marketplace_package(output_dir, publisher, repo_url, author)

    # 列出產出檔案
    log("產出檔案:", C.GREEN)
    for f in sorted(mkt_dir.iterdir()):
        size = f.stat().st_size
        if size > 1024:
            sz = f"{size//1024}KB"
        else:
            sz = f"{size}B"
        log(f"  ✓ {f.name:20s} ({sz})", C.GREEN)

    print_marketplace_instructions(mkt_dir, publisher)


def create_extension(ext_dir: Path):
    ext_dir.mkdir(parents=True, exist_ok=True)
    (ext_dir / "package.json").write_text(
        json.dumps(EXTENSION_PACKAGE_JSON, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (ext_dir / "extension.js").write_text(EXTENSION_JS, encoding="utf-8")
    (ext_dir / "server.js").write_text(SERVER_JS, encoding="utf-8")
    (ext_dir / "README.md").write_text(
        "# BurnerChat\n\n焚後即毀的端對端加密即時聊天室。\n\n"
        "## 新功能 v1.4\n"
        "- 🛡️ Admin 後台 — 獨立 `/admin` 頁面,密碼僅印於 console\n"
        "- 🏠 多房間 — admin 可建立多個具名房間\n"
        "- 📋 一鍵複製邀請 — 連結 + 密碼格式化複製\n\n"
        "## v1.3\n"
        "- 🔔 Teams 風格提示音 + 📊 標題未讀計數\n\n"
        "## v1.2\n"
        "- 👤 自訂暱稱 + 👁 已讀回執\n\n"
        "## v1.1\n"
        "- ⏱ 訊息自動燃燒\n",
        encoding="utf-8"
    )


def build_vsix(ext_dir: Path, output_dir: Path) -> Path:
    vsix_path = output_dir / "burner-chat-1.4.0.vsix"
    log("打包 VSIX 擴充套件...", C.CYAN)
    with zipfile.ZipFile(vsix_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension=".json" ContentType="application/json"/>
  <Default Extension=".js" ContentType="application/javascript"/>
  <Default Extension=".md" ContentType="text/plain"/>
  <Default Extension=".vsixmanifest" ContentType="text/xml"/>
</Types>""")
        zf.writestr("extension.vsixmanifest", """<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="burner-chat" Version="1.4.0" Publisher="burner-chat"/>
    <DisplayName>🔥 BurnerChat</DisplayName>
    <Description>焚後即毀的端對端加密聊天室 — Admin 後台 + 多房間</Description>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json"/>
    <Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md"/>
  </Assets>
</PackageManifest>""")
        for file in ext_dir.rglob("*"):
            if file.is_file():
                arcname = "extension/" + file.relative_to(ext_dir).as_posix()
                zf.write(file, arcname)
    log(f"  ✓ VSIX 已建立: {vsix_path}", C.GREEN)
    return vsix_path


def install_vscode_extension(vsix_path: Path):
    log("安裝 VSCode 擴充套件...", C.CYAN)
    try:
        result = subprocess.run(
            ["code", "--install-extension", str(vsix_path), "--force"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            log("  ✓ VSCode 擴充套件安裝成功", C.GREEN)
        else:
            log(f"  ⚠ 安裝輸出: {result.stdout.strip()}", C.YELLOW)
            if result.stderr:
                log(f"  ⚠ 錯誤: {result.stderr.strip()}", C.YELLOW)
    except subprocess.TimeoutExpired:
        log("  ⚠ 安裝超時,請手動執行:", C.YELLOW)
        log(f"    code --install-extension {vsix_path}", C.WHITE)
    except Exception as e:
        log(f"  ⚠ {e}", C.YELLOW)


def start_chat_server(server_js: Path, port: int, password: str,
                      password_hash: str, room_id: str, local_ip: str,
                      admin_password: str, admin_password_hash: str,
                      default_burn: int = 30):
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["PASSWORD_HASH"] = password_hash
    env["PLAIN_PASSWORD"] = password
    env["ADMIN_PASSWORD_HASH"] = admin_password_hash
    env["ADMIN_PASSWORD"] = admin_password
    env["LOCAL_IP"] = local_ip
    env["ROOM_ID"] = room_id
    env["DEFAULT_BURN"] = str(default_burn)
    env["NODE_OPTIONS"] = "--no-warnings"

    proc = subprocess.Popen(
        ["node", str(server_js)], env=env, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace"
    )

    output_lines = []
    def watch_stderr():
        for line in proc.stderr:
            output_lines.append(("ERR", line.rstrip()))
    threading.Thread(target=watch_stderr, daemon=True).start()

    deadline = time.time() + 6
    while time.time() < deadline:
        if proc.poll() is not None: break
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex(("localhost", port)) == 0: break
        except OSError: pass
        time.sleep(0.2)
    time.sleep(0.3)

    if proc.poll() is not None:
        print()
        log("--- Node.js 錯誤輸出 ---", C.YELLOW)
        for kind, line in output_lines:
            log(f"  [{kind}] {line}", C.RED)
        if not output_lines:
            log("  (無任何輸出)", C.DIM)
        log("--- 結束 ---", C.YELLOW)

    return proc, output_lines


def main():
    banner()
    has_vscode = check_prerequisites()

    # 允許 --port N 指定固定 port(特別是 80 port 以繞過防火牆)
    forced_port = None
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            try:
                forced_port = int(sys.argv[i + 1])
            except ValueError:
                log(f"❌ --port 參數必須是數字,收到: {sys.argv[i + 1]}", C.RED)
                sys.exit(1)
        elif arg.startswith("--port="):
            try:
                forced_port = int(arg.split("=", 1)[1])
            except ValueError:
                log(f"❌ --port 參數必須是數字", C.RED)
                sys.exit(1)

    password = generate_room_password()
    password_hash = hash_password(password)
    admin_password = generate_admin_password()
    admin_password_hash = hash_password(admin_password)
    room_id = secrets.token_hex(4)
    if forced_port is not None:
        # 檢查 port 是否可用
        port_in_use = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("localhost", forced_port)) == 0:
                    port_in_use = True
        except Exception:
            pass

        if port_in_use:
            log(f"❌ Port {forced_port} 已被占用", C.RED)
            if os.name == "nt":
                log(f"   Windows 檢查占用 port 的程序:", C.DIM)
                log(f"   在 PowerShell (管理員)執行:", C.DIM)
                log(f"     netstat -ano | findstr :{forced_port}", C.CYAN)
                log(f"   Port 80 常見佔用者:IIS / Skype / World Wide Web Publishing Service", C.DIM)
                if forced_port == 80:
                    log(f"   如果是 IIS,停止它:", C.DIM)
                    log(f"     iisreset /stop", C.CYAN)
                    log(f"   如果是 Skype:設定 → 進階 → 取消「使用 port 80/443」", C.DIM)
            else:
                log(f"   查詢占用程序:sudo lsof -i :{forced_port}", C.DIM)
            sys.exit(1)

        port = forced_port
        if port < 1024:
            if os.name == "nt":
                log(f"ℹ Port {port} 在 Windows 不需要特殊權限,但要確認:", C.CYAN)
                log(f"   1. 以系統管理員身分執行此腳本(右鍵 → 以系統管理員身分執行)", C.DIM)
                log(f"   2. Windows 防火牆第一次會跳出視窗,請按「允許存取」", C.DIM)
                log(f"   3. 若要讓其他電腦連線,防火牆要放行 node.exe 的 inbound 規則", C.DIM)
            elif os.geteuid() != 0:
                log(f"⚠ Port {port} 是 privileged port,Linux/Mac 需要 root 權限", C.YELLOW)
                log(f"   執行方式:sudo python3 {sys.argv[0]} --port {port}", C.DIM)
                log(f"   或用 setcap:sudo setcap 'cap_net_bind_service=+ep' $(which node)", C.DIM)
    else:
        port = find_free_port(7788)
    local_ip = get_local_ip()
    default_burn = 30

    log("正在建立擴充套件...", C.CYAN)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ext_dir = tmp_path / "burner-chat"
        output_dir = Path.home() / ".burner-chat"
        output_dir.mkdir(exist_ok=True)

        total = 5 if has_vscode else 3
        step(1, total, "建立擴充套件檔案")
        create_extension(ext_dir)
        if has_vscode:
            step(2, total, "打包 VSIX")
            vsix_path = build_vsix(ext_dir, output_dir)
            step(3, total, "安裝 VSCode 擴充套件")
            install_vscode_extension(vsix_path)
            step(4, total, "複製伺服器到本機")
            shutil.copy(ext_dir / "server.js", output_dir / "server.js")
            step(5, total, "啟動聊天伺服器")
        else:
            step(2, total, "複製伺服器到本機")
            shutil.copy(ext_dir / "server.js", output_dir / "server.js")
            step(3, total, "啟動聊天伺服器")

    print()
    log("啟動 BurnerChat 伺服器...", C.CYAN)
    proc, _ = start_chat_server(
        Path.home() / ".burner-chat" / "server.js",
        port, password, password_hash, room_id, local_ip,
        admin_password, admin_password_hash, default_burn
    )
    time.sleep(1)

    if proc.poll() is not None:
        log("❌ 伺服器啟動失敗,請查看上方 [ERR] 錯誤訊息", C.RED)
        sys.exit(1)

    port_suffix = "" if port == 80 else f":{port}"
    web_url = f"http://{local_ip}{port_suffix}/room/{room_id}"
    admin_url = f"http://{local_ip}{port_suffix}/admin"

    print()
    print(f"{C.RED}{'═'*52}{C.RESET}")
    print(f"{C.BOLD}{C.RED}  🔥  BurnerChat 已就緒!{C.RESET}")
    print(f"{C.RED}{'═'*52}{C.RESET}")
    print()
    print(f"  {C.BOLD}📡 預設房間網址:{C.RESET}")
    print(f"  {C.CYAN}{web_url}{C.RESET}")
    print(f"  {C.BOLD}🔑 預設房間密碼:{C.RESET} {C.YELLOW}{password}{C.RESET}")
    print()
    print(f"  {C.MAGENTA}╭───────────── 🛡️  ADMIN 後台 ─────────────╮{C.RESET}")
    print(f"  {C.MAGENTA}│{C.RESET} {C.BOLD}後台網址:{C.RESET} {C.CYAN}{admin_url}{C.RESET}")
    print(f"  {C.MAGENTA}│{C.RESET} {C.BOLD}管理員密碼:{C.RESET} {C.YELLOW}{C.BOLD}{admin_password}{C.RESET}")
    print(f"  {C.MAGENTA}│{C.RESET} {C.DIM}(此密碼僅此處可見,不會顯示在網頁上){C.RESET}")
    print(f"  {C.MAGENTA}╰────────────────────────────────────────────╯{C.RESET}")
    print()
    print(f"  {C.DIM}Room ID: {room_id}  |  Port: {port}{C.RESET}")
    print(f"{C.RED}{'═'*52}{C.RESET}")
    print()
    print(f"{C.DIM}  Admin 可以做什麼:{C.RESET}")
    print(f"{C.DIM}  • 建立新房間並命名(例:「產品會議」、「Code Review」){C.RESET}")
    print(f"{C.DIM}  • 每個房間自動產生獨立密碼{C.RESET}")
    print(f"{C.DIM}  • 一鍵複製「房間連結 + 密碼」格式化文字,直接貼 LINE/Slack{C.RESET}")
    print(f"{C.DIM}  • 即時監看各房間線上人數{C.RESET}")
    print()
    print(f"  {C.BOLD}按 Ctrl+C 關閉伺服器並銷毀所有訊息{C.RESET}")
    print()

    try: webbrowser.open(web_url)
    except Exception: pass

    try:
        proc.wait()
    except KeyboardInterrupt:
        print()
        log("🔥 正在銷毀所有訊息並關閉伺服器...", C.RED)
        proc.terminate()
        try: proc.wait(timeout=3)
        except subprocess.TimeoutExpired: proc.kill()
        log("✓ 所有訊息已銷毀。BurnerChat 已關閉。", C.GREEN)
        print()


if __name__ == "__main__":
    if "--marketplace" in sys.argv or "-m" in sys.argv:
        main_marketplace()
    elif "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        print("用法:")
        print(f"  {sys.argv[0]}                  啟動本地伺服器(預設 7788 port)")
        print(f"  {sys.argv[0]} --port 80        指定 port(需 root / sudo 權限跑 80)")
        print(f"  {sys.argv[0]} --marketplace    僅產生可上架 Marketplace 的套件目錄")
        print(f"  {sys.argv[0]} --help           顯示此說明")
        print()
        print("跑 80 port 的方式:")
        print("  Linux/Mac:  sudo python3 burner_chat_installer.py --port 80")
        print("  或授權 node:sudo setcap 'cap_net_bind_service=+ep' $(which node)")
        print("              然後一般使用者就能跑:python3 burner_chat_installer.py --port 80")
        print("  Windows:    以系統管理員身分開 PowerShell 跑")
    else:
        main()