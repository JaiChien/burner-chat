# 🔥 BurnerChat Changelog

所有值得記錄的版本變更都寫在這裡。

格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/),版號遵循 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

未來新增功能或修 bug 時,請把變動記在最上方的 **[Unreleased]** 區塊。發版時把 `[Unreleased]` 改成新版號並寫上日期。

---

## [Unreleased]

### 新增 (Added)
- **系統訊息獨立折疊區 (`#sys-log`)**:所有系統訊息(XXX 加入/離開/踢出/改密碼通知等)不再穿插於主訊息區,改到聊天室頂端的獨立區域(位於 roster 下方、burn-bar 上方)
  - 預設折疊,只顯示最後一則
  - 按 `▼ 展開 N 則` 可看完整列表(最大高度 10vh,超過 scroll)
  - 保留最新 10 則,超過自動丟最舊的
  - 單則時不顯示展開按鈕
  - 不受反黑遮罩影響(維持原規格)
- **訊息倒數依年齡遞增**:當使用者 focus 輸入框觸發 `onUserRead()` 批次 scheduleBurn 時,按訊息年齡遞增 delay
  - 最舊的訊息 = `burnDuration` 秒
  - 次舊 = `burnDuration + 1` 秒,以此類推
  - 避免堆疊大量訊息時同時消失
  - `scheduleBurn(el, extraDelay)` 簽章加入可選的第二參數
  - 單獨觸發(如自己訊息 `expectedReaders=0` 立刻燒、`tickMineReaders` 湊齊)**不遞增**,維持原樣

### 變更 (Changed)
- `addSys` / `addSysMsg` 改為呼叫 `addSysEntry(text)`,不再建 DOM 進入主訊息區
- 三個 client 新增狀態變數:`sysMsgs: []`, `MAX_SYS_MSGS = 10`, `sysExpanded: false`
- 三個 client 新增函式:`addSysEntry / renderSysLog / toggleSysLog`

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