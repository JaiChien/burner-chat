# BurnerChat — 維護交接文件

> **給未來接手這個專案的 LLM 讀。** 這份文件的目的不是賣產品、也不是教人怎麼用,而是讓你(未來的 LLM)**快速理解整個專案的實際狀態、設計決策、和踩過的雷**,避免你重複犯錯或問一堆已經回答過的問題。

**對應程式碼版本:BurnerChat v1.5**,entry point 是 `burner_chat_installer.py`(單檔 ~158 KB,~3690 行)。

---

## 第 1 節:10 秒快速理解

- **這是什麼**:一支**單檔 Python installer**,跑下去會產出一個 Node.js 聊天伺服器 + (可選)一個 VSCode extension + (可選)一個可上架 Marketplace 的套件目錄。
- **聊天伺服器特性**:HTTP long polling(不用 WebSocket)、記憶體儲存、E2E 加密(AES-256-GCM)、多房間、admin 後台、訊息焚毀倒數、已讀回執。
- **典型使用情境**:Windows 環境、port 80、企業內網、只開放 HTTP 的防火牆政策。
- **語言**:Python 腳本 + 內嵌的 JS(server)+ 內嵌的 HTML/CSS/JS(chat page)+ 內嵌的 VSCode extension JS。主要使用者介面是**繁體中文(zh-TW)**,marketplace 版是**英文**。

---

## 第 2 節:檔案結構與關鍵符號

整個專案**只有一個 Python 檔**:`burner_chat_installer.py`。裡面有幾個大字串常數和對應函式:

| 符號 | 作用 | 大概行數 |
|------|------|---------|
| `EXTENSION_PACKAGE_JSON` | VSCode extension 的 manifest(dict) | 151-172 |
| `EXTENSION_JS` | **本地版** VSCode webview 的完整 JS(zh-TW UI) | 172-871 |
| `SERVER_JS` | **Node.js 伺服器**的完整程式碼,包含 `generateChatPage()` 和 `generateAdminPage()` 兩個 HTML 模板函式 | 871-2327 |
| `MARKETPLACE_PACKAGE_JSON_TEMPLATE` | 上架 marketplace 用的 manifest 模板 | 2327-2366 |
| `MARKETPLACE_EXTENSION_JS` | **Marketplace 版** VSCode webview 的完整 JS(英文 UI,需使用者自填 server URL) | 2366-3085 |
| `MIT_LICENSE_TEMPLATE`、`MARKETPLACE_README_TEMPLATE`、`MARKETPLACE_CHANGELOG`、`VSCODEIGNORE_CONTENT` | Marketplace 套件所需的附屬檔案內容 | 3085-3211 |
| `make_burner_icon()` | 用 PIL 純程式繪製 128x128 火焰 icon(避免外部圖檔依賴) | 3211-3252 |
| `build_marketplace_package()` | 產生可上架目錄 | 3252-3310 |
| `main_marketplace()` | `--marketplace` CLI 入口 | 3349-3401 |
| `main()` | 預設 CLI 入口(跑 server) | 3525-3673 |

### ⚠️ 關鍵:三個 JS 模組必須維持同步

`EXTENSION_JS`、`SERVER_JS` 中的 `generateChatPage()` 內的 `<script>`、`MARKETPLACE_EXTENSION_JS` — 這**三個**都是 client 端程式,都需要解密訊息、顯示聊天 UI、處理已讀等邏輯。**任何 client 行為變動,三個都要改**。

差異:
- `EXTENSION_JS` 跟 `generateChatPage` 的 UI 是**繁中**
- `MARKETPLACE_EXTENSION_JS` 是**英文**
- `EXTENSION_JS` 的 server URL 從 vscode webview panel 狀態推導;`MARKETPLACE_EXTENSION_JS` 讓使用者從指令面板輸入 URL(並用 `globalState` 記住歷史);`generateChatPage` 的 JS 跑在瀏覽器裡,`SERVER` 就是 `location.host`

前兩者在 VSCode webview 裡跑,最後一個在瀏覽器裡跑。三個都包含:

- 完整的純 JS AES-256-GCM + PBKDF2 + SHA-256 實作(約 10 KB)— 這段**三份完全一樣**,拷貝了三次,不是引用
- `deriveKey` / `encryptText` / `decryptText` 的統一介面(自動偵測 `crypto.subtle`)
- Polling loop (`startPolling` / `apiSend` / `handleEvent`)
- 訊息顯示、焚毀倒數、已讀回執、音效、標題未讀數

當你要改 client 行為,用這個順序會比較安全:
1. 先在 `SERVER_JS` 的 `generateChatPage` 內的 JS 改一次(最容易測,改完 curl 就能抓出來看)
2. 用 **Python 的 `str.replace` 批次複製**改動到 `EXTENSION_JS` 和 `MARKETPLACE_EXTENSION_JS`(注意空白格式差異:`if(` vs `if (`)
3. 每次改完跑 `node --check` 三個 JS 的完整程式碼

---

## 第 3 節:執行期架構

### 3.1 啟動流程

```
python3 burner_chat_installer.py [--port N] [--marketplace]
    │
    ├─ check_prerequisites()   → Python 3.8+, Node.js 必要;VSCode CLI 可選
    ├─ 產生房間密碼 / admin 密碼 / room_id
    ├─ find_free_port(7788) 或 forced_port
    ├─ 建立臨時 ext_dir,呼叫 create_extension()
    ├─ (若有 VSCode CLI) build_vsix + install_vscode_extension
    ├─ 複製 server.js 到 ~/.burner-chat/
    └─ start_chat_server() — spawn `node server.js`,傳入 env vars
```

### 3.2 Server 端資料結構(SERVER_JS 內)

```js
rooms: Map<roomId, {
  id, name,
  password,            // 明文,用於 admin UI 顯示
  passwordHash,        // 用於驗證
  clients: Map<clientId, { nick, lastSeen }>,  // 注意:不是 Set(Set 在 WebSocket 版)
  log: [{ seq, type, ts, ...payload }],         // 最多 200 筆
  seq: number,                                   // 單調遞增
  waiters: [{ res, since, timer, clientId }],   // long poll pending 請求
  burnDuration, createdAt, isDefault
}>

tokens: Map<token, { nick, roomId, clientId, exp }>  // 1 小時過期
adminTokens: Map<token, { exp }>
```

### 3.3 HTTP routes

```
POST /auth              → 房間認證,回 { token, nick, clientId, since, burnDuration }
GET  /poll              → Long polling,hold 25s 或直到新事件
POST /send              → 發送事件:type 可為 chat / setBurn / read / leave
GET  /status            → 公開狀態:{ rooms, messages, online }
GET  /admin             → Admin 網頁(HTML)
POST /admin/auth        → Admin 登入
GET  /admin/rooms       → 列出所有房間
POST /admin/create-room → 建立新房間
GET  /room/:roomId      → Chat 網頁(HTML)
GET  /                  → 重定向到預設房間
```

### 3.4 Event 類型(server 透過 appendEvent 產生,client 透過 poll 收到)

```js
{ type: 'chat', sender, encrypted: {ct, iv}, msgId, expectedReaders, seq, ts }
{ type: 'system', text, seq, ts }
{ type: 'burnUpdate', duration, by, silent, seq, ts }
{ type: 'read', msgId, reader, seq, ts }
{ type: 'presenceChange', onlineCount, seq, ts }
```

### 3.5 關鍵生命週期

- **Client 斷線偵測**:沒 `ws`,所以用 `CLIENT_TIMEOUT_MS = 60000` 的 `lastSeen` 判斷。每 15s 跑一次 `reapOfflineClients()`。
- **新事件喚醒 waiters**:`appendEvent()` 會把所有 `room.waiters` 拉出來,各自 `res.end()` 回傳新事件後清空 `waiters` 陣列。
- **beforeunload**:瀏覽器關分頁時 `navigator.sendBeacon` 送 `{type: 'leave'}`,server 立刻清掉 client 並廣播離開 + `presenceChange`。

---

## 第 4 節:加密設計(關鍵!不要動錯)

### 4.1 架構

- **Server 完全不看明文**。Server 只看到 `{encrypted: {ct, iv}}` base64 字串。
- **Key 從房間密碼派生**:`deriveKey(password, 'burnerchat-v1:' + roomId)`
- **Salt 前綴 `burnerchat-v1:`**:未來要升級 KDF 參數時把 v1 改 v2,讓舊 client 自動失效

### 4.2 雙路徑實作(WebCrypto + 純 JS fallback)

瀏覽器的 `crypto.subtle` **只在 secure context 下可用**(HTTPS 或 localhost)。但部署情境是 `http://192.168.x.x:80`,這**不是** secure context,`crypto.subtle === undefined`,會炸。

三個 client 都有這段偵測邏輯:

```js
const HAS_SUBTLE = typeof crypto !== 'undefined' && crypto.subtle && typeof crypto.subtle.importKey === 'function';
```

然後 `deriveKey` / `encryptText` / `decryptText` 都有 `if (HAS_SUBTLE) { ... } else { ... 純 JS ... }` 分支。

### 4.3 純 JS 實作

三份 JS 各自內嵌了一份約 10 KB 的純 JS 實作,函式命名都是底線開頭:

- `_sha256(msg)` — FIPS 180-4
- `_hmac(key, msg)` — HMAC-SHA256
- `_pbkdf2(pwd, salt, iter, dkLen)` — PBKDF2-HMAC-SHA256
- `_aesExp(key)` — AES-256 key expansion(15 round keys, 240 bytes)
- `_aesEnc(block, w)` — 單 block AES-256 encrypt
- `_gmul(X, Y)` — GF(2^128) 乘法(位元逐位,慢但正確)
- `_ghash(H, data)` — GHASH
- `_gcmEnc(key, iv, plain)` / `_gcmDec(key, iv, combined)` — AES-GCM
- `_randBytes(n)` — 用 `crypto.getRandomValues`(**這個** API 即使 `crypto.subtle` 沒了還是可用)
- `_xt(b)` — AES 的 xtime helper

### 4.4 兼容性(已驗證)

- 純 JS 加密 ↔ WebCrypto 解密:互通
- WebCrypto 加密 ↔ 純 JS 解密:互通
- 純 JS 50k 迭代派生的 key **等於** WebCrypto 50k 派生的 key(經實測 byte-for-byte)

### 4.5 迭代次數的妥協

- **WebCrypto 路徑**:200,000 次(近乎瞬間完成)
- **純 JS 路徑**:**50,000 次**(瀏覽器跑 V8 約 2-3 秒)

這是效能妥協。如果你要調整,**兩個分支的 salt 都必須一致**,否則同房間 WebCrypto 和純 JS client 無法互通。

### 4.6 密文格式

```
ciphertext (N bytes) || auth_tag (16 bytes)
```

這跟 WebCrypto `encrypt` 的輸出格式相同(WebCrypto 把 tag 附在後面)。純 JS 的 `_gcmEnc` 也這樣輸出,`_gcmDec` 從 combined 切割。序列化時 base64 編碼。

---

## 第 5 節:已讀 + 焚毀倒數邏輯(最新版,v1.5 末期定調)

### 5.1 規則

- **別人的訊息**:進來時加 `.unread` CSS class(橘色左邊豎線),**不** scheduleBurn,放入 `pendingBurn: Map<msgId, {el, isMine: false}>`。使用者 **focus 輸入框** → 掃 `pendingBurn` 裡所有 `!isMine` 的 → 移除 `.unread` + `scheduleBurn` + `apiSend({type:'read', msgId})`。
- **自己的訊息**:Server 在 `/send` type=chat 時附 `expectedReaders = room.clients.size - 1`。Client 端:若 `expectedReaders === 0` → 立刻 scheduleBurn;否則放入 `pendingBurn: Map<msgId, {el, isMine: true, readersNeeded: N, readersGot: 0}>`。每收到 `type: 'read'` 且 `reader !== nick` → `readersGot++`,達到 `readersNeeded` → scheduleBurn + 清出 pendingBurn。
- **有人離開**(leave 或 reap):Server 額外發 `type: 'presenceChange', onlineCount: N`。Client 收到後掃 `pendingBurn`,降低每個自己訊息的 `readersNeeded`,必要時觸發燒。這叫 **C2 規則**(見下節歷程)。
- **系統訊息**(加入/離開/burnUpdate):維持舊行為,進來立刻 scheduleBurn。

### 5.2 `pendingBurn` 狀態表

```js
pendingBurn: Map<msgId, {
  el: HTMLElement,           // 訊息的 DOM node
  isMine: boolean,
  readersNeeded?: number,    // 只 isMine 才有
  readersGot?: number,       // 只 isMine 才有
}>
```

### 5.3 關鍵函式(三個 client 都有)

- `onUserRead()` — focus 觸發時掃 pendingBurn
- `tickMineReaders(msgId)` — 收到 read event 時遞增計數
- `onPresenceChange(onlineCount)` — 收到 presenceChange 時重算

### 5.4 為什麼是 focus 而不是 scroll 或 visibility?

使用者的明確要求:**「focus 輸入框的當下」**算已讀,blur 後不算。這最好理解、最可預測,而且模擬真人「我準備要回覆了」的意圖。不用 scroll 或 visibility 因為那些會有大量誤觸。

---

## 第 6 節:開發歷程(按時間順序)

### v1.0 — 初始版本
雛形:WebSocket 聊天、單房間、固定密碼、無 admin。

### v1.1 — 訊息焚毀
- 加入 `setBurn` / `burnUpdate` event
- Client 端 `scheduleBurn(el)` 函式:倒數到 0 就動畫淡出
- 倒數 seconds 0 = 永不燃燒
- **倒數 UI**:訊息下方 `🔥 Ns`,< 2s 時加 `.burning` class 閃爍

### v1.2 — 暱稱 + 已讀回執
- Auth 時多傳 `nickname`,server 用 `sanitizeNickname` 清理(最大 20 字)
- Server 為每則訊息產 6-byte hex `msgId`
- Client 收到訊息 **立刻** setTimeout 送 `{type:'read', msgId}`(**舊邏輯,v1.5 末才改**)
- 顯示 `✓ 已讀: 小明, 小華`,超過 3 人顯示 `+N`

### v1.3 — 音效 + 標題未讀數
- Web Audio API:G5 → C6 兩音符鐘聲,各帶 2x/3x 泛音,總長 ~0.5s
- AudioContext 要在使用者手勢(auth 按鈕)下 prewarm
- 標題變成 `(3) 🔥 BurnerChat`,只在 `document.hidden` 才增加
- `visibilitychange` 切回來時歸零

### v1.4 — Admin 後台 + 多房間
- 新增 `/admin`(紫色主題)和對應的 POST `/admin/auth`、GET `/admin/rooms`、POST `/admin/create-room`
- **Admin 密碼 20 字,只在 console 印一次**,沒有任何地方(包括前端)能看到
- `rooms: Map` 結構化,每房間獨立密碼、burnDuration
- Admin UI 可建具名房間,一鍵複製「連結+密碼」到剪貼簿
- sessionStorage 存 admin token、4s refresh
- **🔥 踩過的雷**:第一版用 template literal `innerHTML + onclick`,結果 `\'` 轉義被吃掉讓 JS 炸掉。重寫成 `document.createElement + addEventListener`。之後再改 admin UI 記得**永遠不要**用字串串 onclick。

### v1.5 早期 — E2E 加密
- AES-256-GCM,PBKDF2 200k,salt = `burnerchat-v1:<roomId>`
- Server 只儲存 `{ct, iv}` base64,沒看過明文
- 加密初始化失敗會卡住 auth 流程並顯示錯誤

### v1.5 中期 — 修 bug、加 CLI、Windows/port 80 支援
- **Bug 1**:`InvalidStateError: Still in CONNECTING state`。使用者太快輸入 → `ws.send()` 在 readyState=0 時被呼叫。修法:
  - `authenticate` 成功後輸入框 `disabled` 到 `ws.onopen`
  - 所有發送走 `wsSend(payload)` helper,檢查 `ws.readyState === WebSocket.OPEN` 並 try/catch
- **Bug 2**:`Cannot read properties of undefined (reading 'importKey')`。LAN IP 非 secure context → `crypto.subtle === undefined`。
  - 曾嘗試用自簽 HTTPS 解決(`ensure_ssl_cert` + `https.createServer`),使用者要求**不要 HTTPS**
  - **最終解法**:三個 client 各自內嵌純 JS AES-GCM + PBKDF2 fallback(見第 4 節)
- **`--port N` CLI 參數**:用在 Windows 綁 port 80(網路政策要求)
- **Port 80 URL 省略** `:80`:`'http://' + LOCAL_IP + (PORT===80?'':':'+PORT) + ...`
- **EADDRINUSE / EACCES 錯誤處理**:Windows 給 IIS/Skype 提示,Linux 給 setcap 提示
- **VSCode CLI 可選**:`check_prerequisites` 回傳 `has_vscode: bool`,`main()` 根據這個條件化 install 流程

### v1.5 末期 — WebSocket → HTTP long polling
- 使用者回報「有些地方無法用 WebSocket」
- **移除** `SimpleWS` class 和 `server.on('upgrade', ...)` handler
- **新增** `/poll`(long polling,hold 25s)和 `/send`(POST JSON)
- Room 結構:`clients: Set<ws>` 改為 `clients: Map<clientId, {nick, lastSeen}>`
- 新增 `log[]` + `seq` + `waiters[]` + `appendEvent()` + `touchClient()` + `reapOfflineClients()`
- 三個 client 改為 `startPolling()` async loop + AbortController + 指數 backoff
- `beforeunload` 用 `navigator.sendBeacon('/send', {type:'leave'})`
- **🔥 踩過的雷**:測試腳本 state 污染(同 nickname 多次 auth 產生鬼魂 clientId)讓「線上人數」顯示錯誤。debug 許久後發現是**測試問題、不是產品 bug**,server 邏輯完全正確

### v1.5 最終 — focus-based 已讀 + 條件倒數
使用者的最終需求:

1. 「focus 輸入框當下所有未讀變已讀,blur 後不算」
2. 「自己讀到才開始倒數」
3. 「**自己的訊息等所有人都讀過**才倒數(避免剛發就燒)」
4. 「C2:有人離開以剩下的人為準重新判斷」

實作:
- Server `/send` type=chat 加 `expectedReaders` 欄位
- Server leave/reap 額外廣播 `type: 'presenceChange'`
- 三個 client 新增 `pendingBurn: Map` + `onUserRead()` + `tickMineReaders()` + `onPresenceChange()`
- `addChatMsg(sender, text, isMine, msgId, expectedReaders)` 新簽章
- `handleEvent` 接收 `d.expectedReaders` 和 `type:'presenceChange'`
- CSS 新增 `.msg.unread`(橘色左邊豎線)
- 輸入框加 `focus` listener

---

## 第 7 節:已知限制 / 不要做的事

### 7.1 不要加的功能(使用者刻意拒絕過)

- **檔案傳輸** — 跟焚後即毀的概念衝突
- **語音/視訊** — 超出範疇
- **永久儲存** — 沒有「歷史紀錄」是賣點
- **身份驗證系統** — 刻意沒有帳號
- **HTTPS 內建** — 使用者明確表示「不要用 HTTPS」(純 JS crypto fallback 是替代方案)
- **WebSocket** — 使用者明確表示「有些地方無法使用 WebSocket」

### 7.2 設計上的硬限制

- 單則密文 **14 KB 上限**(7-10 KB 明文),server 硬擋
- 訊息 log 每房間最多 **200 筆**(超過丟最舊的)
- Token 有效期 **1 小時**
- Client 離線判定 **60 秒**
- Long poll hold 上限 **25 秒**
- Reap 掃描頻率 **15 秒**

### 7.3 已知的 sharp edges

- **訊息進來時使用者已經 focus 輸入框**:第一次 focus event 不會觸發(瀏覽器不重複觸發 focus)。目前行為:該訊息會留在 `pendingBurn`,直到使用者 blur 再 focus 才開始燒。**這是 sharp edge,目前沒修**。如果要修,可考慮 `document.activeElement === inputEl` 時直接觸發 onUserRead。
- **訊息在焚毀中但使用者重新整理**:DOM 重建,`pendingBurn` 清空,server 若 log 還有這筆就重送(狀態歸零,使用者要重新 focus 才燒)。符合預期。
- **Admin 可以看到明文密碼**:房間密碼明文存在 `rooms.get(roomId).password`,admin 後台會顯示。這是有意的設計(admin 要複製貼給使用者)。**不是 bug**。
- **純 JS crypto 跑 PBKDF2 會卡 UI 2-3 秒**:不用 Web Worker 是因為要保持單檔性質,且只發生一次(登入時)。

---

## 第 8 節:測試方法

### 8.1 基礎語法檢查

```bash
# Python
python3 -c "import py_compile; py_compile.compile('/path/to/burner_chat_installer.py', doraise=True)"

# 三個 JS 模組
python3 -c "
src = open('/path/to/burner_chat_installer.py').read()
ns = {}
exec(compile(src.split('def main_marketplace()')[0] + '\npass\n', '<str>', 'exec'), ns)
for name in ['EXTENSION_JS', 'SERVER_JS', 'MARKETPLACE_EXTENSION_JS']:
    open(f'/tmp/{name}.js','w').write(ns[name])
"
for f in EXTENSION_JS SERVER_JS MARKETPLACE_EXTENSION_JS; do node --check /tmp/$f.js; done
```

### 8.2 跑真實 server 做端對端

```bash
export PORT=17920 ROOM_ID=test1234 PLAIN_PASSWORD=pw
export PASSWORD_HASH=$(python3 -c "import hashlib,secrets;s=secrets.token_hex(16);h=hashlib.sha256((s+'pw').encode()).hexdigest();print(f'{s}:{h}')")
export ADMIN_PASSWORD=A
export ADMIN_PASSWORD_HASH=$(python3 -c "import hashlib,secrets;s=secrets.token_hex(16);h=hashlib.sha256((s+'A').encode()).hexdigest();print(f'{s}:{h}')")
export LOCAL_IP=127.0.0.1 DEFAULT_BURN=30

node /tmp/SERVER_JS.js &
```

然後可以 `curl` 測 `/auth` `/poll` `/send`(參考 `第 3 節` 的 routes),或用 Node.js 客戶端模擬。

### 8.3 **重要**:測試容易踩的雷

- **State 污染**:如果你在同一個 server instance 裡用同 nickname 多次 `/auth`,會產生多個 clientId,看起來像「線上人數暴增」。測試時**每個情境用不同 nickname**,且結束時送 `{type:'leave'}` 清理
- **Long poll hold 住整個腳本**:`/poll` 可能 hold 25 秒,要麼 client-side timeout,要麼 `Promise.all` 讓多個 poll 並行
- **Race condition**:兩個 `/poll` 並行時,誰先 touchClient 會觸發誰先被廣播為「加入」。用 `await new Promise(r => setTimeout(r, 100))` 間隔呼叫會比較穩定
- **並行測試**:`fetch` 的 `AbortController` 在 Node 18+ 可用,若環境較舊要 polyfill

### 8.4 打包 Marketplace vsix

```bash
rm -rf ~/.burner-chat/marketplace
echo "my-publisher
https://github.com/me/burner-chat
My Name" | python3 burner_chat_installer.py --marketplace

cd ~/.burner-chat/marketplace
vsce package --allow-missing-repository
```

產出約 17 KB 的 `.vsix`。

---

## 第 9 節:如果使用者要你做新功能,先問自己

1. **影響 client 行為嗎?** 如果是,記得**三個 JS 模組同步改**。
2. **影響加密格式嗎?** 如果是,三個 client 的加密分支(WebCrypto + 純 JS)**都要改**,且 salt 建議 bump 版本號(`v1` → `v2`)讓舊訊息自動失效
3. **影響 event 格式嗎?** Client 的 `handleEvent` 是 switch dispatch,新 event type **向後相容就好**(舊 client 收到會 silently ignore)
4. **影響 server 狀態嗎?** `rooms` Map 結構有 `log`、`seq`、`waiters`、`clients: Map<clientId, ...>`,這幾個不要動。新欄位儘量加在 event 的 payload 裡
5. **使用者要的功能跟第 7.1 節的「不要做的事」衝突嗎?** 如果是,先跟使用者討論,不要自作主張加

---

## 第 10 節:常見維護情境

### 「收到 `InvalidStateError` / `undefined is not a function`」

→ 通常是 client 在 CONNECTING 時就發送,或是非 secure context 的 crypto.subtle。檢查:
- 所有 `ws.send` 是否都走 `wsSend()` helper(其實 v1.5 之後沒有 WebSocket 了,只剩 apiSend,應不會再遇到)
- `HAS_SUBTLE` 判斷是否正確
- 輸入框是否在連線完成前被 disable

### 「訊息不燒了」

→ 八成是 `pendingBurn` 有東西沒清。檢查:
- 自己的訊息:`expectedReaders` 是否正確?`readersGot` 有沒有遞增?`presenceChange` 是否正確廣播?
- 別人的訊息:focus listener 是否正確綁在輸入框?onUserRead 是否掃到?

### 「已讀回執顯示不正確」

→ `markRead(msgId, reader)` 是更新 `msgReads: {msgId: [reader1, reader2, ...]}`,`updateReadIndicator(msgId)` 從這個讀出並渲染。自己的訊息也會收到自己的 read(但 `reader !== nick` 條件擋掉 tickMineReaders)

### 「訊息太長被拒絕」

→ `msg.encrypted.ct.length > 14000 || msg.encrypted.iv.length > 32` 是 server 擋的。14000 是密文長度,對應明文約 10 KB。要調就兩邊同步調(別忘記 HTTP body 總長也被 `readJsonBody` 限制在 100000)

### 「想改 UI 樣式」

→ 三個地方都有 CSS,都在 HTML 模板裡。`EXTENSION_JS` 和 `MARKETPLACE_EXTENSION_JS` 的 CSS 格式幾乎一樣(主要是文字差);`SERVER_JS` 的 `generateChatPage` 內 CSS 獨立(用 CSS variables `--accent` 等)。改完要確保三處一致。

---

## 第 11 節:對話脈絡與風格注記

- 使用者**說繁體中文**(zh-TW),在台北
- 使用者**直接、技術性強**,不需要冗長解釋,要 bullet points
- 使用者**嚴格**:要求「不要 HTTPS」「不要 WebSocket」這類硬性約束會重複強調,請遵守
- 使用者**會要求看計畫再動手**,特別是大改動 — 先列計畫確認,收到「OK 開始」或「Continue」才執行
- 使用者**會貼錯誤訊息**,不會細說上下文 — 你要主動推斷部署環境(通常是 Windows + port 80 + LAN IP + HTTP)

### 檔案位置慣例

- 輸入:`/mnt/user-data/uploads/`
- 輸出:`/mnt/user-data/outputs/`(最終檔案放這裡,present_files 工具需要)
- 暫存:`/home/claude/` 或 `/tmp/`(使用者看不到)

### 通常的最終交付物

- `burner_chat_installer.py` — 單檔 installer
- `burner-chat-1.5.0.vsix` — marketplace 版 VSCode extension
- `README.md` — 給人看的文件(分架設者/使用者兩節)

---

## 附錄 A:快速對照表

| 你想改什麼 | 去哪改 |
|---------|-------|
| Server HTTP route | `SERVER_JS` 的 `server.on('request'...)` 裡的 `if (p === ...)` chain |
| Event 結構 | `appendEvent()` 呼叫點(server 端) + `handleEvent()`(三個 client) |
| 加密邏輯 | `deriveKey/encryptText/decryptText`(三個 client) + 底層 `_sha256 ~ _gcmDec`(三個 client) |
| Chat UI 樣式 | `generateChatPage()` 內 CSS(server) + EXTENSION_JS 的 `<style>` + MARKETPLACE 的 `<style>` |
| Admin UI | `generateAdminPage()`(只在 server) |
| CLI 參數 | `main()` 開頭的 `sys.argv` 解析 |
| Marketplace 內容 | `MARKETPLACE_*_TEMPLATE` 常數 |
| 已讀/倒數邏輯 | `addMsg/addChatMsg` + `onUserRead` + `tickMineReaders` + `onPresenceChange`(三個 client) |
| 離線偵測 | `CLIENT_TIMEOUT_MS` + `reapOfflineClients`(server) |

---

## 附錄 B:Magic Numbers 清單

```
CLIENT_TIMEOUT_MS        = 60000    # 60s 視為離線
reap interval            = 15000    # 每 15s 掃一次離線
long poll hold           = 25000    # 25s timeout
MAX_LOG_SIZE             = 200      # 每房間訊息 log 上限
token TTL                = 3600000  # 1 hour
admin token TTL          = 3600000  # 1 hour
ct length limit          = 14000    # byte,對應約 10 KB 明文
iv length limit          = 32       # base64 後的 byte 上限
PBKDF2 iter (WebCrypto)  = 200000
PBKDF2 iter (pure JS)    = 50000
room password length     = 12
admin password length    = 20
room id length           = 8 (hex, 4 bytes)
msgId length             = 12 (hex, 6 bytes)
client id length         = 16 (hex, 8 bytes)
nickname max length      = 20
room name max length     = 30
default burn duration    = 30 seconds
```

---

*文件版本:v1.5 末,對應 `burner_chat_installer.py` ~3690 行版本。*