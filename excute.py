#!/usr/bin/env python3
"""
🔥 BurnerChat VSCode Extension Installer
自動安裝焚模式聊天室 VSCode 擴充套件並啟動伺服器

v1.5.0 新增:
  • 端對端加密 (E2EE) — AES-256-GCM,key 派生自房間密碼,伺服器永遠看不到明文

v1.4.0:
  • Admin 後台 + 多房間 + 一鍵複製邀請

v1.3.0:
  • 標題未讀計數 + Teams 風格提示音

v1.2.0:
  • 自訂暱稱 + 已讀回執

v1.1.0:
  • 訊息自動燃燒
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
  @keyframes flicker { 0%,100%{opacity:1} 50%{opacity:.6} }
  #input-area { display: flex; gap: 8px; padding: 12px 16px; background: #111; }
  #input-area input { flex: 1; background: #1a1a1a; border: 1px solid #333; color: #e0e0e0;
                      padding: 8px 12px; border-radius: 3px; font-size: 12px; outline: none; }
  #input-area button { background: #ff4500; color: white; border: none;
                       padding: 8px 16px; border-radius: 3px; cursor: pointer; }
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
<div id="burn-bar" style="display:none">
  <label>🔥 訊息存活:</label>
  <input type="number" id="burn-sec" min="0" max="3600" value="30" />
  <span>秒</span>
  <button onclick="updateBurn()">套用</button>
</div>
<div id="messages" style="display:none"></div>
<div id="input-area" style="display:none">
  <input type="text" id="msg-input" placeholder="輸入訊息..." />
  <button onclick="sendMsg()">發送</button>
</div>

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
const vscodeApi = (typeof acquireVsCodeApi === 'function') ? acquireVsCodeApi() : null;

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
      document.getElementById('me-label').textContent = '@' + nick;
      document.getElementById('auth-overlay').style.display = 'none';
      ['header','burn-bar','messages','input-area'].forEach(id => {
        document.getElementById(id).style.display = (id === 'messages' || id === 'burn-bar') ? 'flex' : '';
      });
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
        onDisconnected('驗證失效,請重新登入');
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
    let text;
    try { text = await decryptText(d.encrypted); }
    catch(err){ text = '⚠ [無法解密 — 密碼不一致或訊息毀損]'; }
    addChatMsg(d.sender, text, d.sender === nick, d.msgId);
  }
  else if (d.type === 'system') addSysMsg(d.text);
  else if (d.type === 'burnUpdate') {
    burnDuration = d.duration;
    const bs = document.getElementById('burn-sec');
    if (bs) bs.value = burnDuration;
    if (!d.silent) addSysMsg('⏱ ' + d.by + ' 設定訊息存活為 ' + (burnDuration === 0 ? '永久' : burnDuration + ' 秒'));
  }
  else if (d.type === 'read') markRead(d.msgId, d.reader);
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

function updateBurn() {
  const v = parseInt(document.getElementById('burn-sec').value);
  if (isNaN(v) || v < 0) return;
  apiSend({type: 'setBurn', duration: Math.min(3600, v)});
}

function scheduleBurn(el) {
  if (burnDuration <= 0) return;
  const cd = document.createElement('div');
  cd.className = 'countdown'; el.appendChild(cd);
  let r = burnDuration; cd.textContent = '🔥 ' + r + 's';
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
  ind.textContent = '✓ 已讀: ' + (rs.length <= 3 ? rs.join(', ') : rs.slice(0,3).join(', ') + ' +' + (rs.length-3));
}

function addChatMsg(sender, text, isMine, msgId) {
  const msgs = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'msg ' + (isMine ? 'mine' : 'other');
  if (msgId) div.setAttribute('data-msg-id', msgId);
  const s = document.createElement('div'); s.className = 'sender'; s.textContent = sender; div.appendChild(s);
  const t = document.createElement('div'); t.textContent = text; div.appendChild(t);
  msgs.appendChild(div); msgs.scrollTop = msgs.scrollHeight;
  scheduleBurn(div);
  if (!isMine && msgId && !sentReads[msgId]) {
    sentReads[msgId] = true;
    setTimeout(() => apiSend({type: 'read', msgId: msgId}), 100);
  }
  if (msgId && msgReads[msgId]) updateReadIndicator(msgId);
  if (!isMine) {
    playNotify();
    if (document.hidden) { unreadCount++; updateTitle(); }
  }
}
function addSysMsg(text) {
  const msgs = document.getElementById('messages');
  const d = document.createElement('div'); d.className = 'msg system'; d.textContent = text;
  msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight;
  scheduleBurn(d);
}
async function sendMsg() {
  const i = document.getElementById('msg-input');
  const text = i.value.trim();
  if (!text) return;
  if (!authToken) {
    addSysMsg('⚠ 尚未連線,無法發送');
    return;
  }
  i.value = '';
  try {
    const enc = await encryptText(text);
    const ok = await apiSend({type: 'chat', encrypted: enc});
    if (!ok) {
      addSysMsg('⚠ 傳送失敗(網路不穩?)');
      i.value = text;
    }
  } catch(err){
    addSysMsg('⚠ 加密失敗:' + (err.message || err));
    i.value = text;
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
});
document.getElementById('msg-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') sendMsg(); });
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

function appendEvent(roomId, event) {
  const room = rooms.get(roomId);
  if (!room) return;
  room.seq++;
  const entry = Object.assign({ seq: room.seq, ts: Date.now() }, event);
  room.log.push(entry);
  // 限制 log 大小,丟掉最舊的
  if (room.log.length > MAX_LOG_SIZE) {
    room.log.splice(0, room.log.length - MAX_LOG_SIZE);
  }
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
const CLIENT_TIMEOUT_MS = 60000;  // 60s 沒 poll 就當離線

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
        appendEvent(room.id, {
          type: 'system',
          text: '🔥 ' + info.nick + ' 已離開(線上:' + room.clients.size + ')'
        });
      }
    }
  }
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
    req.on('data', d => { body += d; if (body.length > 100000) { req.destroy(); reject(new Error('payload too large')); } });
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
      url: roomUrl(r.id)
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
      tokens.set(token, { nick, roomId: room.id, clientId, exp: Date.now() + 3600000 });
      return sendJson(res, 200, {
        ok:true, token, nick, clientId,
        since: room.seq, burnDuration: room.burnDuration
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
    if (!tokenData || Date.now() > tokenData.exp) return sendJson(res, 401, { ok:false, error:'token 失效' });
    const room = rooms.get(tokenData.roomId);
    if (!room) return sendJson(res, 404, { ok:false, error:'房間不存在' });
    // 標記這個 client 還活著(用於線上偵測)
    const wasNew = touchClient(room.id, tokenData.clientId, tokenData.nick);
    if (wasNew) {
      appendEvent(room.id, {
        type: 'system',
        text: '🔥 ' + tokenData.nick + ' 已加入房間(線上:' + room.clients.size + ')'
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
      if (!tokenData || Date.now() > tokenData.exp) return sendJson(res, 401, { ok:false, error:'token 失效' });
      const room = rooms.get(tokenData.roomId);
      if (!room) return sendJson(res, 404, { ok:false, error:'房間不存在' });
      const { nick } = tokenData;
      touchClient(room.id, tokenData.clientId, nick);

      if (body.type === 'chat' && body.encrypted && typeof body.encrypted.ct === 'string' && typeof body.encrypted.iv === 'string') {
        if (body.encrypted.ct.length > 14000 || body.encrypted.iv.length > 32) {
          return sendJson(res, 400, { ok:false, error:'payload 過大' });
        }
        messageCount++;
        const msgId = crypto.randomBytes(6).toString('hex');
        appendEvent(room.id, { type: 'chat', sender: nick, encrypted: body.encrypted, msgId });
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
          appendEvent(room.id, {
            type: 'system',
            text: '🔥 ' + nick + ' 已離開(線上:' + room.clients.size + ')'
          });
        }
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
.room-actions{display:flex;gap:8px;flex-wrap:wrap}
.room-actions button,.room-actions a{background:transparent;color:var(--accent);border:1px solid var(--accent);padding:6px 14px;border-radius:3px;cursor:pointer;font-family:inherit;font-size:11px;text-decoration:none;display:inline-block;letter-spacing:1px;transition:.15s}
.room-actions button:hover,.room-actions a:hover{background:var(--accent);color:white}
.room-actions .btn-primary{background:var(--purple);border-color:var(--purple);color:white}
.room-actions .btn-primary:hover{background:#9333ea;border-color:#9333ea}

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
@keyframes flicker{0%,100%{opacity:1}50%{opacity:.65}}
#input{display:flex;gap:8px;padding:12px 20px;background:var(--bg2);border-top:1px solid var(--border)}
#input input{flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:8px 14px;border-radius:4px;font-family:inherit;font-size:13px;outline:none}
#input input:focus{border-color:var(--accent)}
#input button{padding:8px 20px;width:auto;letter-spacing:0}
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
  <input type="text" id="mi" placeholder="輸入訊息(Enter 發送)..." />
  <button onclick="send()">發送</button>
</div>
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
const HOST = location.host;

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
        onDisconnected('驗證失效,請重新登入');
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
    let text;
    try { text = await decryptText(d.encrypted); }
    catch(err){ text = '⚠ [無法解密 — 密碼不一致或訊息毀損]'; }
    addMsg(d.sender, text, d.sender === nick, d.msgId);
  }
  else if (d.type === 'system') addSys(d.text);
  else if (d.type === 'burnUpdate') {
    burnDuration = d.duration;
    document.getElementById('burnSec').value = burnDuration;
    if (!d.silent) addSys('⏱ ' + d.by + ' 設定訊息存活為 ' + (burnDuration === 0 ? '永久' : burnDuration + ' 秒'));
  }
  else if (d.type === 'read') markRead(d.msgId, d.reader);
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

function applyBurn(){
  const v = parseInt(document.getElementById('burnSec').value);
  if(isNaN(v) || v < 0) return;
  apiSend({type:'setBurn', duration: Math.min(3600, v)});
}
function setPreset(n){ document.getElementById('burnSec').value = n; applyBurn(); }

function scheduleBurn(el){
  if(burnDuration <= 0) return;
  const cd = document.createElement('div'); cd.className = 'countdown'; el.appendChild(cd);
  let r = burnDuration; cd.textContent = '🔥 ' + r + 's';
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
  ind.textContent = '✓ 已讀: ' + (rs.length <= 3 ? rs.join(', ') : rs.slice(0,3).join(', ') + ' +' + (rs.length-3));
}

function addMsg(sender, text, isMe, msgId){
  const m = document.getElementById('msgs');
  const d = document.createElement('div');
  d.className = 'msg ' + (isMe ? 'me' : 'other');
  if(msgId) d.setAttribute('data-msg-id', msgId);
  d.innerHTML = '<div class="sender">' + escHtml(sender) + '</div><div class="bubble">' + escHtml(text) + '</div>';
  m.appendChild(d); m.scrollTop = m.scrollHeight;
  scheduleBurn(d);
  if(!isMe && msgId && !sentReads[msgId]){
    sentReads[msgId] = true;
    setTimeout(() => apiSend({type:'read', msgId: msgId}), 120);
  }
  if(msgId && msgReads[msgId]) updateReadIndicator(msgId);
  if(!isMe){
    playNotify();
    if(document.hidden){ unreadCount++; updateTitle(); }
  }
}
function addSys(t){
  const m = document.getElementById('msgs');
  const d = document.createElement('div'); d.className = 'msg sys'; d.textContent = t;
  m.appendChild(d); m.scrollTop = m.scrollHeight;
  scheduleBurn(d);
}
function escHtml(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
async function send(){
  const i = document.getElementById('mi');
  const text = i.value.trim();
  if(!text) return;
  if(!authToken){
    addSys('⚠ 尚未連線,無法發送');
    return;
  }
  i.value = ''; // 立即清空,避免重複送
  try {
    const enc = await encryptText(text);
    const ok = await apiSend({type:'chat', encrypted: enc});
    if(!ok){
      addSys('⚠ 傳送失敗(網路不穩?)');
      i.value = text; // 還原
    }
  } catch(err){
    addSys('⚠ 加密失敗:' + (err.message || err));
    i.value = text;
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
});

// 初始狀態:輸入框 disable 直到連線成功
(function initInputState(){
  const mi = document.getElementById('mi');
  if (mi) { mi.disabled = true; mi.placeholder = '請先登入'; }
})();

document.getElementById('mi').addEventListener('keydown', e => { if(e.key === 'Enter') send(); });
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
  @keyframes flicker { 0%,100%{opacity:1} 50%{opacity:.6} }
  #input-area { display: flex; gap: 8px; padding: 12px 16px; background: #111; }
  #input-area input { flex: 1; background: #1a1a1a; border: 1px solid #333; color: #e0e0e0;
                      padding: 8px 12px; border-radius: 3px; font-size: 12px; outline: none; }
  #input-area button { background: #ff4500; color: white; border: none;
                       padding: 8px 16px; border-radius: 3px; cursor: pointer; }
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
<div id="burn-bar" style="display:none">
  <label>Burn after:</label>
  <input type="number" id="burn-sec" min="0" max="3600" value="30" />
  <span>sec</span>
  <button onclick="updateBurn()">Apply</button>
</div>
<div id="messages" style="display:none"></div>
<div id="input-area" style="display:none">
  <input type="text" id="msg-input" placeholder="Type a message... (Enter to send)" />
  <button onclick="sendMsg()">Send</button>
</div>

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
const vscodeApi = (typeof acquireVsCodeApi === 'function') ? acquireVsCodeApi() : null;

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
      document.getElementById('me-label').textContent = '@' + nick;
      document.getElementById('auth-overlay').style.display = 'none';
      ['header','burn-bar','messages','input-area'].forEach(id => {
        document.getElementById(id).style.display = (id === 'messages' || id === 'burn-bar') ? 'flex' : '';
      });
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
        onDisconnected('Session expired, please re-login');
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
    let text;
    try { text = await decryptText(d.encrypted); }
    catch(err){ text = '[Cannot decrypt - wrong password or corrupted message]'; }
    addChatMsg(d.sender, text, d.sender === nick, d.msgId);
  }
  else if(d.type === 'system') addSysMsg(d.text);
  else if(d.type === 'burnUpdate'){
    burnDuration = d.duration;
    const bs = document.getElementById('burn-sec');
    if(bs) bs.value = burnDuration;
    if(!d.silent) addSysMsg(d.by + ' set message lifetime to ' + (burnDuration === 0 ? 'never' : burnDuration + 's'));
  }
  else if(d.type === 'read') markRead(d.msgId, d.reader);
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

function updateBurn() {
  const v = parseInt(document.getElementById('burn-sec').value);
  if(isNaN(v) || v < 0) return;
  apiSend({type: 'setBurn', duration: Math.min(3600, v)});
}

function scheduleBurn(el) {
  if(burnDuration <= 0) return;
  const cd = document.createElement('div');
  cd.className = 'countdown'; el.appendChild(cd);
  let r = burnDuration; cd.textContent = r + 's';
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
  ind.textContent = 'Read by: ' + (rs.length <= 3 ? rs.join(', ') : rs.slice(0,3).join(', ') + ' +' + (rs.length-3));
}

async function sendMsg() {
  const i = document.getElementById('msg-input');
  const text = i.value.trim();
  if(!text) return;
  if(!authToken){
    addSysMsg('Not connected, cannot send');
    return;
  }
  i.value = '';
  try {
    const enc = await encryptText(text);
    const ok = await apiSend({type: 'chat', encrypted: enc});
    if(!ok){
      addSysMsg('Transmission failed (network unstable?)');
      i.value = text;
    }
  } catch(err){
    addSysMsg('Encryption failed: ' + (err.message || err));
    i.value = text;
  }
}

function addChatMsg(sender, text, isMine, msgId) {
  const msgs = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'msg ' + (isMine ? 'mine' : 'other');
  if(msgId) div.setAttribute('data-msg-id', msgId);
  const s = document.createElement('div'); s.className = 'sender'; s.textContent = sender; div.appendChild(s);
  const t = document.createElement('div'); t.textContent = text; div.appendChild(t);
  msgs.appendChild(div); msgs.scrollTop = msgs.scrollHeight;
  scheduleBurn(div);
  if(!isMine && msgId && !sentReads[msgId]){
    sentReads[msgId] = true;
    setTimeout(() => apiSend({type: 'read', msgId: msgId}), 100);
  }
  if(msgId && msgReads[msgId]) updateReadIndicator(msgId);
  if(!isMine){
    playNotify();
    if(document.hidden){ unreadCount++; updateTitle(); }
  }
}
function addSysMsg(text) {
  const msgs = document.getElementById('messages');
  const d = document.createElement('div'); d.className = 'msg system'; d.textContent = text;
  msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight;
  scheduleBurn(d);
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
});

document.addEventListener('visibilitychange', () => {
  if(!document.hidden && unreadCount > 0){ unreadCount = 0; updateTitle(); }
});
document.getElementById('msg-input')?.addEventListener('keydown', e => { if(e.key === 'Enter') sendMsg(); });
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
