# 🔥 BurnerChat Changelog

所有值得記錄的版本變更都寫在這裡。

格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/),版號遵循 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

未來新增功能或修 bug 時,請把變動記在最上方的 **[Unreleased]** 區塊。發版時把 `[Unreleased]` 改成新版號並寫上日期。

---

## [Unreleased]

### 新增 (Added)

#### 本次新增(剪貼圖片 + Reactions)
- **剪貼簿貼上圖片**:在聊天室登入狀態按 `Ctrl+V` / `Cmd+V` 可直接貼上剪貼簿的圖片
  - 三個 client 全部支援(Chat page / Extension / Marketplace)
  - 偵測 `clipboardData.items` 第一個 `image/` type file,呼叫既有 `handleImageFile(blob)`
  - 沿用現有壓縮流程(1280 px / JPEG 0.7 / 800 KB 上限)
  - 未登入時(登入框)不會觸發,避免誤觸
- **訊息 Reactions(讚 👍 / 哭 😢)**
  - **觸發**:hover 訊息氣泡時右上角出現 `[+]` 按鈕,點開彈出小 picker(👍 😢)
  - **顯示**:訊息下方顯示 `👍 2`、`😢 1` chip,hover chip 看見人名 tooltip(超過 5 人顯示 `Alice, Bob, Carol, ... +N`)
  - **已按顏色反白**:自己按過的 chip 有橘色邊框與背景,表示 "我按過"
  - **不互斥**:同一人可同時按 👍 和 😢;同 emoji 第二次按 = 取消
  - **可對自己訊息按**:沒有限制
  - **已燒毀訊息不能按**:Server 驗證 msgId 仍在 log 裡才接受,返回 404 錯誤
  - **即時同步**:按下立刻廣播給所有 client 更新 UI
  - **新進房間自動看到既有 reactions**:server 把 reactions 掛在 chat event 上,poll 歷史訊息時一起帶出
  - **加密方式**:走明文 event(server 看得到誰對哪訊息按了什麼 — 這是與文字訊息的 E2E 加密不同的妥協,換取輕量)
  - **Emoji 白名單**:server 只接受 `['👍','😢']`,非白名單 emoji 回 400

### 變更 (Changed)

#### 本次變更(與 reactions/paste 相關)
- **移除輸入框的 📎 附加圖片按鈕**:改為只透過 Ctrl+V 貼上
  - HTML 的 `<input type="file" id="img-file-input">` 已移除
  - JS 動態注入的 `#img-attach` 按鈕已移除
  - `bindImgInput()` 綁定已移除
  - **保留** `handleImageFile()` 函式(paste 事件仍然會用)
  - CSS 仍保留 `#img-attach` 規則(無害,DOM 不再產生此 id)

#### Server 端(for reactions)
- 新增 `/send` type `'reaction'` 處理,payload: `{token, type:'reaction', msgId, emoji, action:'add'|'remove'}`
- 每則 chat event 上掛 `reactions: { '👍': [users], '😢': [users] }` map
- 廣播 `reactionUpdate { msgId, emoji, user, action }` event 通知所有 client
- 清理 `event._bytes` 快取讓 `enforceLogSize` 重新估算(reactions 改動後)
- Emoji 白名單驗證、msgId 存在性驗證(已燒毀訊息拒絕)

#### Client(三個 client 共通)
- 三個 client 新增狀態:`msgReactions: {}`, `REACTION_EMOJIS: ['👍','😢']`
- 三個 client 新增函式:`openReactionPicker / closeReactionPicker / toggleReaction / renderReactions`
- 三個 client `addMsg` / `addChatMsg` 在訊息 DOM 上掛 `[+]` 按鈕 + 空的 `.reactions` 容器
- 三個 client `handleEvent`:
  - chat event 帶 reactions 時套用(新進房間看到既有)
  - 新增 `reactionUpdate` 分支(即時同步)
- 三個 client 新增 `document.addEventListener('paste', ...)` 處理剪貼圖片

#### 先前累積(前幾輪 session 的新功能)
- **Emoji 快選面板**:輸入框左邊新增 😀 按鈕,點開彈出面板
  - 內建 **375 個 emoji**,分 7 類(表情/手勢/愛/慶祝/食物/動物/物品),總資料 ~10 KB
  - 頂端**搜尋框**即時過濾(支援中英文關鍵字)
  - 分類 tab 切換,點擊 emoji 插入到輸入框 cursor 位置
  - 點面板外自動關閉
- **附加圖片功能**:輸入框左邊新增 📎 按鈕,可選 JPG/PNG/WebP
  - Client 端 Canvas 壓縮:最長邊 1280 px / JPEG 0.7(超過 800 KB 拒絕)
  - 圖片與文字走**相同 E2E 加密路徑**(payload 格式 `{text, image}` JSON 後加密)
  - 文字與圖片**任一存在即可發送**(空文字有圖直接發、有文字有圖一起發)
  - 訊息氣泡內用 `background-image` 形式顯示(**禁用右鍵另存**)
  - 已讀/倒數/焚毀機制完全照常運作
- **滿版圖片檢視器(Fullscreen Viewer)**:點擊訊息圖片開啟
  - **倍率 25% ~ 500%**,按 `+` / `−` 以 25% 為單位
  - **滑鼠滾輪**縮放、**拖曳**平移(>100% 時)
  - **ESC 鍵** / 點黑色背景 / 工具列 ✕ 可關閉
  - 右鍵禁用(基本防落地)
  - **F12 偵測**:打開開發者工具時顯示警告訊息(用 `outerWidth - innerWidth > 160` 判斷)
  - **焚毀同步**:原訊息 DOM 被焚毀移除時,viewer 自動關閉
  - 開啟時短暫顯示「請勿截圖或轉傳」提醒
- **反黑遮罩擴展至圖片**:未 focus 輸入框時訊息圖片 `filter: blur(18px)` 遮罩

#### 先前累積(前幾輪 session 的新功能)
- **乾淨版(Clean Mode)**:輸入框左邊加一個幽靈圖示切換按鈕,點下去進入「乾淨版」
  - **隱藏**:header(標題/@me/🔔/連線狀態)、焚模式提示條、線上名單 roster、系統訊息區 sys-log、焚毀設定 burn-bar
  - **保留**:主訊息區(訊息、反黑遮罩、已讀、倒數全部照常運作)、輸入框、發送按鈕
  - 輸入框 placeholder 變空白(用 `dataset.originalPlaceholder` 備份原值)
  - 發送按鈕文字隱藏,用 `::after { content: '→' }` 顯示箭頭圖示
  - 切換按鈕 active 狀態時邊框/文字變橘色
  - 再點一次切回正常模式,所有元件回復
  - **本地狀態**:`cleanMode` 變數只存在 client 記憶體,不發給 server,其他 client 看不到
  - `resetToLogin()`(被 reap/踢出/房間刪除)會自動解除乾淨版,避免登入畫面被 clean-mode 蓋住
- **乾淨版切換按鈕使用自訂圖示**:48x48 幽靈 PNG 內嵌 base64(~4 KB × 3 個 client)
- **乾淨版隱藏已讀人名**:乾淨版時只保留 `✓` 打勾符號,「已讀: Alice, Bob」字樣隱藏
  - 實作:`updateReadIndicator` 把 `.readby` 內容拆成兩個 span(`.check` 和 `.names`)
  - 正常模式仍顯示「✓ 已讀: Alice, Bob」完整資訊
- **系統訊息獨立折疊區 (`#sys-log`)**:所有系統訊息(XXX 加入/離開/踢出/改密碼通知等)不再穿插於主訊息區,改到聊天室頂端的獨立區域(位於 roster 下方、burn-bar 上方)
  - 預設折疊,只顯示最後一則
  - 按 `▼ 展開 N 則` 可看完整列表(最大高度 10vh,超過 scroll)
  - 保留最新 10 則,超過自動丟最舊的
  - 單則時不顯示展開按鈕
  - 不受反黑遮罩影響(維持原規格)
- **訊息倒數依年齡遞增**:當使用者 focus 輸入框觸發 `onUserRead()` 批次 scheduleBurn 時,按訊息年齡遞增 delay
  - 最舊的訊息 = `burnDuration` 秒,次舊 = `burnDuration + 1` 秒,以此類推
  - 避免堆疊大量訊息時同時消失
  - `scheduleBurn(el, extraDelay)` 簽章加入可選的第二參數
  - 單獨觸發(如自己訊息 `expectedReaders=0` 立刻燒、`tickMineReaders` 湊齊)**不遞增**,維持原樣

### 變更 (Changed)

#### 本次變更(Server 端為支援照片的調整)
- **Server:訊息 size 上限大幅提升**
  - 單則密文 ct 上限:14 KB → **1.2 MB**
  - HTTP body 總上限:100 KB → **1.5 MB**
- **Server:log 記憶體控制升級**
  - 新增 `MAX_LOG_BYTES = 100 MB/房間` 總大小上限
  - 新增 `enforceLogSize(room)` + `estimateEventBytes` 每次 appendEvent 後檢查
  - 兼顧筆數(200)+ 總大小,滿了從最舊推掉
- **訊息 payload 格式向後相容**
  - 純文字訊息維持舊 string 格式
  - 含圖片時打包 JSON `{text, image}` 後加密
  - 接收端偵測首字元 `{` 判斷格式

#### 先前累積(Client 架構調整)
- `addSys` / `addSysMsg` 改為呼叫 `addSysEntry(text)`,不再建 DOM 進入主訊息區
- 三個 client 新增狀態變數:`sysMsgs: []`, `MAX_SYS_MSGS = 10`, `sysExpanded: false`, `cleanMode = false`, `pendingImage = null`, `emojiActiveCat`, `viewerZoom` 等
- 三個 client 新增函式:`addSysEntry / renderSysLog / toggleSysLog / toggleCleanMode / toggleEmojiPicker / handleImageFile / openImageViewer / viewerZoomIn/Out`
- 發送按鈕加上 `id="send-btn"`(原本沒有 id),供 CSS 在乾淨版隱藏文字
- `addMsg` / `addChatMsg` 簽章新增第 6 個參數 `image`

### 修復 (Fixed)
- **Chat page 登入頁面 JS 語法錯誤**:`handleImageFile` 的正規式 `/^image\/(jpeg|png|webp)$/` 在 server-side template literal 中被 JS 的 template literal 規則誤解析(`$` 被當成 `${...}` 開頭),導致瀏覽器出現 `Uncaught SyntaxError: Unexpected identifier '$'` 錯誤,整個頁面 JS 停擺(連帶 `auth is not a function` 也出現)
  - 改用 `['image/jpeg','image/png','image/webp'].indexOf(file.type) === -1` 避免 regex 中的 `\/` 和 `$` 跟 template literal 跳脫規則衝突
  - 三個 client 全部修復(EXTENSION_JS 不是 template literal 本來沒問題,但仍統一改)

### 安全性 (Security)
- 照片以 `background-image` CSS 形式顯示,避免 `<img>` 右鍵另存
- Fullscreen viewer 禁用右鍵選單
- F12 偵測顯示警告(並非強制阻擋,提醒使用者不要擷取)
- 焚毀機制擴及照片:訊息燒掉時 DOM 整塊移除,圖片也消失
- 照片**不走 server 落地儲存**,僅存在記憶體加密 log 中

---

## [1.5.3] — 2026-04-22

### 新增 (Added)
- **Admin 改房間密碼**:後台每個房間新增「🔑 改密碼」按鈕,按下去會自動產生 12 字隨機密碼、踢出房間內所有人、清空訊息 log
- **Admin 刪除房間**:後台每個房間新增「🗑️ 刪除」按鈕,按下去會廣播 `roomDeleted` event 通知所有在線使用者跳回登入畫面,接著刪除房間本身
- Server 新增 `POST /admin/change-password` endpoint
- Server 新增 `POST /admin/delete-room` endpoint
- Client `handleEvent` 新增 `roomDeleted` 分支,收到會呼叫 `resetToLogin('此房間已被管理員刪除')`

### 變更 (Changed)
- **系統訊息永不焚毀**:`addSys` / `addSysMsg` 移除 `scheduleBurn` 呼叫。XXX 加入/離開/踢出/改密碼 等系統訊息會永久保留在聊天室,不再被倒數消失
- Admin UI 的 `.room-actions` 新增 `btn-warn`(橘色)和 `btn-danger`(紅色)兩種按鈕樣式

### 安全性 (Security)
- 改密碼時一併清空訊息 log(`room.log = []`, `room.seq = 0`),避免新人用新密碼進房時解密失敗(因為舊訊息是用舊密碼派生的 key 加密的)

---

## [1.5.2] — 2026-04-22

### 新增 (Added)
- **頂端線上名單 (Roster)**:聊天室頂端顯示所有在線使用者,由 server push
  - 超過 6 人自動折疊為 `▼ 展開 N 人` 按鈕,使用者手動點開才展開
  - 折疊狀態「黏住」— 後續人員加入/離開不會自動展開
- **未 focus 時反黑遮罩**:輸入框未 focus 或分頁在背景時,訊息文字以 `█████` 遮罩顯示
  - 線上名單**不**遮罩
  - 系統訊息**不**遮罩(無私人內容)
  - focus + 前景時立刻顯示(無動畫過渡)
- **Admin 踢人功能**:後台每個房間卡片顯示在線成員 chip + ✕ 踢出按鈕
  - 踢人時刪除對應 token → 被踢者下次 poll 收到 401 → 自動 `resetToLogin`
  - 被踢者可立即以相同密碼重新登入
- **Client heartbeat**:每 15 秒打一次 `POST /send {type: 'heartbeat'}` 更新 lastSeen,獨立於 polling loop,更穩定的離線偵測
- Server 新增 `POST /admin/kick` endpoint
- Client 新增 `resetToLogin(reason)` 函式統一處理「被踢/token 失效」的狀態清理
- `presenceChange` event 擴充為 `{onlineCount, nicks: [...]}`(原本只有 onlineCount)
- `/auth` 回應新增 `nicks` 欄位供 client 初始化 roster

### 變更 (Changed)
- **`CLIENT_TIMEOUT_MS` 從 60 秒改為 30 秒**:reap 更靈敏
- **Token 永不過期**:移除 `exp` 欄位與檢查。Token 只在以下情況失效:使用者關閉視窗、client 被 reap、admin 踢人、admin 改密碼/刪房、server 重啟
- `reapOfflineClients` 偵測到離線 client 時一併刪除對應 token
- `/send leave` 一併刪除對應 token
- `touchClient` 判定新 client 加入時額外廣播 `presenceChange`(原本只有離開會廣播)

### 移除 (Removed)
- Token 的 `exp` 欄位與 TTL 檢查(原本 1 小時過期)

---

## [1.5.1] — 2026-04-22

### 新增 (Added)
- **Focus-based 已讀**:別人的訊息進來時加 `.unread` class(橘色左邊豎線),**不**立刻 scheduleBurn。使用者 focus 輸入框才觸發 `onUserRead()`:標為已讀 + 發送 read event + 開始倒數
- **自己訊息的條件倒數**:自己發的訊息要等「所有人都讀過」才開始倒數
  - Server `/send chat` 回應 event 新增 `expectedReaders = room.clients.size - 1` 欄位
  - Client 端 `pendingBurn: Map<msgId, {el, isMine, readersNeeded, readersGot}>` 追蹤每則訊息狀態
  - 每收到 `type: 'read'` 且 `reader !== nick` 時 `readersGot++`,達到 `readersNeeded` 就 scheduleBurn
  - 單人房 (`expectedReaders === 0`) 的訊息立刻倒數
- **C2 規則**:有人離開房間時(leave/reap),client 收到 `presenceChange` 會降低所有自己 pending 訊息的 `readersNeeded`,必要時立刻觸發燒
- CSS 新增 `.msg.unread` 橘色豎線樣式

### 變更 (Changed)
- 訊息進來不再立刻 scheduleBurn,而是進入 `pendingBurn` 狀態機等候觸發條件

---

## [1.5.0] — 2026-04-22

### 新增 (Added)
- **HTTP long polling 取代 WebSocket**:適用於 WebSocket 被封鎖的網路環境
  - 新增 `GET /poll?token=xxx&since=N` endpoint,hold 25 秒直到有新事件
  - 新增 `POST /send` endpoint 處理 chat/setBurn/read/leave
  - Server 為每個房間維護 `log[]`(最多 200 筆)+ `seq` 遞增 + `waiters[]`
  - Client 端用 `startPolling()` async loop + AbortController + 指數 backoff 重試
  - `beforeunload` 用 `navigator.sendBeacon('/send', {type:'leave'})` 通知離開
- **純 JS AES-GCM + PBKDF2 + SHA-256 fallback**:處理瀏覽器在 `http://192.168.x.x` 下 `crypto.subtle === undefined` 的問題
  - 三個 client(chat page + EXTENSION + MARKETPLACE)各自內嵌 ~10 KB 的純 JS 加密實作
  - WebCrypto 路徑 200k PBKDF2 迭代;純 JS 路徑 50k 迭代(~2-3 秒,UI 會稍停)
  - 兩種路徑的密文完全互通
- **E2E 加密**:AES-256-GCM,key 派生自房間密碼 (PBKDF2-SHA256),salt = `burnerchat-v1:<roomId>`
- **Windows port 80 支援**:`--port N` CLI 參數
- Server `EADDRINUSE / EACCES` 錯誤處理(含 Windows IIS/Skype 提示、Linux setcap 提示)
- VSCode CLI 可選:沒裝 VSCode 也能啟動 server(只是不會裝 extension)
- `--marketplace` CLI 參數產生可上架 VSCode Marketplace 的套件目錄

### 移除 (Removed)
- **WebSocket 完全移除** — `SimpleWS` class、`server.on('upgrade', ...)` handler 全部拿掉
- 原本短暫實作過的自簽 HTTPS 路徑,經使用者要求移除(改用純 JS crypto fallback 解決 secure context 問題)

### 安全性 (Security)
- Server 永遠看不到明文,只處理 `{ct, iv}` base64 密文
- 密文長度上限 14 KB(對應約 10 KB 明文),IV 長度上限 32

---

## [1.4.0]

### 新增 (Added)
- **Admin 後台**:紫色主題 `/admin` 頁面
  - `POST /admin/auth` — 登入
  - `GET /admin/rooms` — 列出所有房間(含密碼、線上人數、burnDuration)
  - `POST /admin/create-room` — 建立具名房間,自動產生 12 字隨機密碼
  - 一鍵複製「連結+密碼」到剪貼簿
- **多房間**:`rooms: Map` 結構化,每房間獨立密碼與 burnDuration
- Admin 密碼 20 字,只在 server 啟動時 console 印一次

---

## [1.3.0]

### 新增 (Added)
- **音效提示**:Teams 風格 G5 → C6 兩音符鐘聲(Web Audio API)
  - AudioContext 在使用者手勢下 prewarm
  - 右上角 🔔 開關
- **標題未讀計數**:`(3) 🔥 BurnerChat`
  - 只在 `document.hidden` 時增加
  - `visibilitychange` 切回前景時歸零

---

## [1.2.0]

### 新增 (Added)
- **自訂暱稱**:最大 20 字,`sanitizeNickname` 清理特殊字元
- **已讀回執**:Server 為每則訊息產 6-byte hex `msgId`,顯示 `✓ 已讀: 小明, 小華`,超過 3 人顯示 `+N`

---

## [1.1.0]

### 新增 (Added)
- **訊息焚毀倒數**:`setBurn` / `burnUpdate` event
- 倒數 UI:訊息下方 `🔥 Ns`,< 2s 加 `.burning` class 閃爍
- 倒數歸零 → 動畫淡出 → DOM 移除
- `burnDuration = 0` = 永不燃燒

---

## [1.0.0]

### 新增 (Added)
- 初始版本
- WebSocket 聊天、單房間、固定密碼

---

## 📝 編輯這份 CHANGELOG 的約定

### 新增變更時
在 `[Unreleased]` 下面加分類:

```markdown
## [Unreleased]

### 新增 (Added)
- 描述新功能

### 變更 (Changed)
- 描述行為變更

### 修正 (Fixed)
- 描述 bug 修正

### 移除 (Removed)
- 描述刪除的功能

### 安全性 (Security)
- 描述安全相關變更

### 棄用 (Deprecated)
- 描述即將移除但暫時保留的功能
```

### 發布新版本時
1. `[Unreleased]` 改成新版號 + 日期,例如 `## [1.6.0] — 2026-05-10`
2. 在上方插一個新的空白 `[Unreleased]` 區塊
3. 把同一份版號也更新到 `burner_chat_installer.py` 的 `EXTENSION_PACKAGE_JSON` 和 `MARKETPLACE_PACKAGE_JSON_TEMPLATE` 的 `"version"` 欄位
4. 同步更新 server 啟動 banner 的 `BurnerChat Server v1.x.x` 字串

### 版號規則(Semver)
- `1.x.0` — 新功能、向後相容的變更
- `1.0.x` — 只修 bug、不改行為
- `2.0.0` — 不相容的重大變更(例如再換一次傳輸協議)

一般開發過程中加功能用 **MINOR** 升級(`1.5.2 → 1.5.3 → 1.6.0`)。