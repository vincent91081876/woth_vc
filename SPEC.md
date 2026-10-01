# WOTH Animal Population Scanner — 規格書 (Spec v1.0)

## 1. 目標
為《Way of the Hunter》(WOTH，Nine Rocks Games，Unreal Engine 4) 製作一個與 theHunter: COTW
「Animal Population Scanner」(Nexus mod #41) 功能對等的**獨立、唯讀**工具：
讀取玩家存檔，顯示每張地圖上的動物族群（物種、性別、年齡、體重、分數/星級、基因/Fitness、位置、所屬獸群），
並提供即時模式（Live mode）觀察獵殺與重生。

> 本工具為全新撰寫，不使用原 mod 任何程式碼或素材（原 mod 禁止轉換到其他遊戲）。

## 2. 限制與假設
- WOTH 存檔位置：`%LOCALAPPDATA%\WayOfTheHunter\Saved\SaveGames\`（含 `Account_<id>\` 子資料夾）；Steam Play/Linux 為 `compatdata/1288320/pfx/...`。
- 存檔為 UE4 **GVAS** 格式（`.sav`），可能以 UE 壓縮區塊 (tag `0x9E2A83C1`, zlib) 或整檔 zlib 壓縮包裝。
- WOTH 的動物欄位名稱**沒有公開文件**，因此：
  1. 解析器必須是**通用 GVAS 解析器**，遇到未知型別以 size 跳過，永不崩潰。
  2. 動物/獸群辨識採**啟發式欄位比對**（正規表示式），且可由 `config.json` 覆寫。
  3. 提供「存檔結構瀏覽 / JSON 匯出」讓使用者找出正確欄位並回填設定。
- 僅用 Python 3.9+ 標準函式庫，免安裝套件。介面為本機網頁 (127.0.0.1)，自動開啟瀏覽器。
- 絕不寫入原始存檔：以 `rb` 讀取；快照複製到工具自己的 `snapshots/`。

## 3. 功能需求
| ID | 功能 | 說明 |
|---|---|---|
| F1 | 自動偵測存檔 | 掃描預設路徑與 OneDrive/自訂路徑，列出所有 `.sav`（修改時間、大小）。可手動指定路徑。 |
| F2 | 通用 GVAS 解析 | Header、CustomVersions、所有常見 Property（Int/Int64/UInt/Float/Double/Bool/Byte/Enum/Str/Name/Text/Object/SoftObject/Struct/Array/Map/Set），Vector/Rotator/Quat/Guid/DateTime 等原生 struct；byte 陣列內嵌的 property 串流自動遞迴解析。 |
| F3 | 解壓縮 | 支援原始 GVAS、UE 壓縮區塊 (zlib)、整檔 zlib/gzip。 |
| F4 | 動物辨識 | 在樹中尋找「元素 ≥2 且欄位符合 ≥2 類動物屬性」的 struct 清單；上層含有此清單者視為獸群 (Herd)。擷取：物種、性別、年齡、體重、分數、Fitness、位置、ID、是否死亡。 |
| F5 | 物種正規化 | 從 class 路徑/列舉值（如 `BP_RedDeer_C`, `ESpecies::RedDeer`）轉為易讀名稱與中文名稱。 |
| F6 | 族群總覽 | 每物種：總數、公/母、各年齡層、平均/最高分數、獸群數。 |
| F7 | 動物清單 | 可排序、依物種/性別/年齡/分數篩選；顯示所屬獸群、座標。 |
| F8 | 星級/評等預估 | 依 `config.json` 的物種分數門檻給星級；未設定者以同物種百分位數顯示（Top 1%/5%/…）。 |
| F9 | 分布圖 | 分數直方圖（每物種）。 |
| F10 | 地圖 | 以 X/Y 座標畫出動物/獸群位置，可依物種過濾；可選擇地圖底圖 + 校正範圍。 |
| F11 | Live mode | 每 N 秒檢查存檔修改時間，重解析並與上次比對：新生成 = 綠色、消失(獵殺/死亡) = 紅色，累計事件紀錄。 |
| F12 | 快照比較 | 每次讀取自動存快照；可選擇任一舊快照與目前比較。 |
| F13 | 結構瀏覽 | 可折疊的存檔樹，路徑搜尋；匯出完整 JSON；CLI `--dump`。 |
| F14 | 匯出 | 動物清單匯出 CSV。 |
| F15 | CLI | `python woth_scanner.py --scan <file>` 輸出族群摘要，便於除錯/無 GUI 使用。 |

## 4. 架構
```
woth_scanner/
  woth_scanner.py   # 入口：CLI + 本機 HTTP 伺服器
  gvas.py           # 通用 GVAS 讀取器（含解壓縮）
  extract.py        # 動物/獸群啟發式擷取、物種正規化、統計、差異比對
  species.py        # WOTH 物種表（英文/中文/等級）
  web/index.html    # 單頁 UI（原生 JS + Canvas）
  config.json       # 欄位規則、分數門檻、地圖校正、輪詢秒數
  tests/            # 合成 GVAS 產生器 + 單元測試
  run_windows.bat   # 雙擊啟動
  README.md
```
### API（本機）
- `GET /api/saves` → 存檔清單
- `GET /api/scan?path=...` → {header, herds, animals, summary, warnings}
- `GET /api/live?path=...&since=<mtime>` → 若檔案有變化回傳新掃描 + diff
- `GET /api/snapshots`、`GET /api/diff?a=..&b=..`
- `GET /api/tree?path=...` → 結構樹（截斷大型陣列）
- `GET /api/export.csv?path=...`

## 5. 資料模型
Animal: `{id, species, species_zh, gender(M/F/?), age, age_class, weight, score, fitness, x, y, z, herd_id, dead, path, raw}`
Herd: `{id, species, size, x, y, path}`

## 6. 驗收
1. 以測試產生的合成 WOTH 風格存檔（含壓縮版、嵌入 byte 陣列版）能正確擷取所有動物。
2. 未知/損毀 property 不中斷解析，產生 warning。
3. 原始檔案 hash 在掃描前後不變。
4. 網頁 UI 在 headless Chromium 可載入並顯示總覽、清單、地圖；Live mode diff 正確標示新增/移除。
5. CLI `--scan` 與 `--dump` 正常。

---
## 7. v1.1 修訂（依真實存檔逆向分析）
真實 `SaveData.sav`（WOTH，UE 4.27.2）結構：
1. **外層**：`int64 未壓縮大小` + `int32` + UE 壓縮區塊（tag `0x9E2A83C1`，區塊 128 KB），區塊使用 **Oodle** 壓縮。
   → 以 `pyooz`（隨附 Windows wheel）或遊戲的 `oo2core_*_win64.dll` 解壓縮。
2. **內層**：GVAS 標頭（類別 `/Script/WayOfTheHunter.DatabaseSaveHeader`，屬性 `m_databaseCodeVersion`、`m_isMigrated`），
   其後是自訂二進位資料庫 `[u32 0][u32 大小][資料]`，最後是**名稱表** `u32 數量 + {u64 雜湊, u32 長度, UTF-16}`。
3. **動物紀錄**以其 Blueprint 類別雜湊開頭（例：`BP_CervusCanadensis_M_C`，性別/變種寫在類別名）：
   `+20 u32 年齡`、`+24 f32 Fitness（公獸 0~1，母獸 0）`、`+28 u8 性別 (1=公, 2=母)`、`+29 u32 動物 ID（唯一）`、`+33 f32×3 座標`、`+45 f32×3 旋轉`。
4. **獸群紀錄**以 `AIC_*AnimalGroup_<學名>_C` 雜湊開頭：`+20 GUID`、`+36 f32×3 座標`；其後的動物紀錄屬於該群。
5. 物種以**學名**對應（例：CervusCanadensis → Rocky Mountain Elk / 洛磯山馬鹿），變種：Albino 白化、Melanistic 黑化…
6. 存檔中沒有直接的體重/分數欄位（遊戲似乎由年齡 + Fitness 推算），因此評等改以「同物種公獸 Fitness 百分位」顯示。
7. 驗收：使用者真實存檔解析出 17 物種、2,827 隻、483 群，0 警告，約 0.2 秒；ID 全部唯一。

## 8. v1.2 修訂（真實地圖定位）
1. 內建 Nez Perce Valley 4096×4096 底圖（發行版轉為 WebP），世界座標範圍校正為 X/Y `-600000..600000` cm。
2. 存檔 X 軸由左至右、Y 軸由上至下；預設不反轉 Y。保留手動 Y 軸反轉供其他地圖校正。
3. 單一保護區時自動選擇該地圖，無須使用者先操作地圖下拉選單。
4. 標記可依物種篩選、單隻/獸群切換、縮放、平移、懸停顯示詳情；顯示 1 km 比例尺與位置數量。
5. 校正驗證：以真實存檔 271 隻 Wild Duck / Lesser Scaup / Ross's Goose 座標比對底圖水域，91% 位於水域 100 m 內，證實方向與尺度合理。

## 9. v1.3 修訂（全部保護區）
1. 內建第一代遊戲全部七個保護區：Nez Perce Valley、Transylvania、Aurora Shores、Tikamoon Plains、Matariki Park、Lintukoto Reserve、Elkcrest Island。
2. 每張圖使用 Toolbox 3D 場景公開的 `coords` 獨立換算為 Unreal 世界座標（公分），不可假設所有地圖皆為 ±600000 cm。
3. 新增 Elkcrest Island 辨識：優先使用 Merriam's Wild Turkey 的學名；以 Kodiak Bear + Cougar 組合作為備援。
4. 保留目前存檔單一保護區自動選擇；載入未來其他地圖存檔時自動顯示對應底圖。
5. 測試必須確認七個設定皆存在、底圖檔案存在、座標最小值小於最大值，且 Merriam's Wild Turkey 對應 Elkcrest Island。

## 10. v1.4 規格 — Herd Management & Target Finder

### 10.1 研究結論
- 原 COTW Scanner 的核心價值不是只列資料，而是 Live mode、跨快照辨識生成/消失，以及快速找到值得關注的個體。
- WOTH 的 Fitness 在生成時固定，Trophy/星級會隨年齡成長；因此本工具只把 Fitness 當作「潛力」，不得把百分位誤稱為目前 Trophy 星級。
- 2,000–3,000 個點同時顯示時，單純散點難以判讀；需要獸群分析、熱區模式和個體定位。

### 10.2 功能需求
| ID | 功能 | 驗收標準 |
|---|---|---|
| V14-1 | 管理建議分頁 | 顯示高潛力門檻、低潛力門檻、稀有數、候選個體數，以及每群公獸平均/最高 Fitness。 |
| V14-2 | 獸群健康分析 | 每群列出高潛力、低潛力、稀有、性別比與簡短建議；門檻可即時調整，預設 90% / 50%。 |
| V14-3 | 目標篩選 | 動物清單新增「高潛力 / 低潛力 / 稀有 / 已關注」快速篩選。Fitness 僅套用於有值的公獸。 |
| V14-4 | 關注清單 | 可將個體加入/移除關注；以地圖+ID 儲存在瀏覽器 localStorage，重開程式仍保留。Live/快照消失時仍能辨識。 |
| V14-5 | 個體詳情與定位 | 點擊清單不再使用 alert；顯示詳情卡，可一鍵前往地圖並置中、放大、高亮該個體。 |
| V14-6 | 地圖熱區 | 地圖新增「個體 / 獸群 / 熱區」三種模式；熱區使用離線 Canvas 密度渲染，不新增外部依賴。 |
| V14-7 | 快照物種摘要 | 比較快照時，除逐筆清單外，顯示每物種新增、消失與淨變化。 |
| V14-8 | 用語正確 | UI 將 Fitness 明確標為「潛力」；百分位標成同物種排名，不宣稱是實際 Trophy 星級。 |
| V14-9 | 相容與效能 | 真實 2,827 隻存檔初次解析 < 1 秒；七張地圖可載入；既有 Live、CSV、CLI 與只讀保證不回歸。 |

### 10.3 不在本版範圍
- 不寫入或修改存檔。
- 不在缺乏已驗證公式時推算體重、Trophy 分數或星級。
- 不把「低 Fitness」直接標示成必須獵殺，只提供可調整的觀察候選建議。

## 11. v1.5 規格 — Population History, Save Health & Safe Snapshots

### 11.1 研究結論
- WOTH 的動物族群會跨故事／Free Hunt 共用，且遊戲更新曾出現族群異常案例；單次畫面不足以判斷是正常年度更替、獵殺重生或大規模重置。
- 原 Population Scanner 以舊 population file 比較生成個體；本程式已有逐一快照，但缺少多時間點趨勢與異常提示。
- 備份價值高，但重複備份會累積；掃描器必須以內容雜湊去重、限制數量，而且始終不可覆寫遊戲原檔。

### 11.2 功能需求
| ID | 功能 | 驗收標準 |
|---|---|---|
| V15-1 | 安全快照 v2 | 快照檔名含時間與 SHA-1 前綴；相同內容不重複建立；每個存檔最多保留 `max_snapshots`（預設 100）份。只刪工具自己的舊快照。 |
| V15-2 | 歷史 API | `/api/history?path=` 回傳最多 100 個快照及目前檔案的精簡統計，不回傳完整動物陣列。 |
| V15-3 | 趨勢分頁 | 可依物種與指標查看總數、公獸數、平均 Fitness、90% 以上、50% 以下及稀有數的折線趨勢。無歷史時提供明確說明。 |
| V15-4 | 存檔健康檢查 | 檢查解析警告、重複 ID、未知物種、無獸群個體、非有限座標、超出目前地圖校正範圍及族群大幅變動。每項顯示 OK／注意／錯誤。 |
| V15-5 | 大幅變動偵測 | 有至少兩份不同快照時，若總族群變化 ≥20% 或單一物種變化 ≥30%，顯示注意，不自動斷言存檔損壞。 |
| V15-6 | 關注狀態 | 關注資料除了 key 也保存物種、Fitness、獸群與最後看見時間；管理頁列出「仍存在／已消失」，可移除失效項目。 |
| V15-7 | 報告匯出 | 可下載目前管理摘要 JSON（版本、存檔雜湊、健康檢查、門檻、獸群統計、關注狀態），不包含存檔二進位內容。 |
| V15-8 | 回歸與效能 | 真實存檔掃描 <1 秒；100 個快照歷史採逐檔快取；原檔 SHA-1 掃描前後不變；既有 7 地圖、Live、熱區、CSV 均正常。 |

### 11.3 安全界線
- 不提供「還原快照」按鈕，避免在遊戲或 Steam Cloud 同步期間覆蓋原檔。
- 健康檢查是資料一致性提示，不宣稱可診斷所有遊戲存檔損壞。
- 快照留存與清除只作用於程式資料夾內 `snapshots/`。

## 12. v1.6 規格 — Verified Life Stages & Animal Knowledge

### 12.1 研究結論
- 真實存檔的 `age` 是物種生命週期使用的年度值；不同物種、不同性別的 Young／Adult／Mature 邊界並不相同，不能再只顯示裸數字或套用單一門檻。
- Way of the Hunter Toolbox 的 60 個物種頁面均提供狩獵等級、建議命中能量、棲地、Trophy 類型與五段分數範圍，以及公母各自的三階段年齡／體重範圍，可做成離線知識庫。
- 存檔沒有精確體重或當前 Trophy 分數；只能顯示「該生命階段的公開體重範圍」，不得偽裝成個體實測值。

### 12.2 功能需求
| ID | 功能 | 驗收標準 |
|---|---|---|
| V16-1 | 離線物種知識庫 | 隨程式附帶 60 物種資料；執行時不需網路。每筆保留來源 URL。 |
| V16-2 | 性別化生命階段 | 依物種、性別與存檔 age 標示 Young／Adult／Mature 及中文；使用各物種公開範圍，不使用全域猜測。 |
| V16-3 | 資料信心 | 精確物種對應標 `verified-table`；以相近亞種暫代時標 `proxy`；無資料標 `unknown`。目前 Eastern Wild Turkey 使用 Merriam's Wild Turkey 年齡表作 proxy，UI 必須明示。 |
| V16-4 | 體重範圍 | 顯示該階段公開的公／母體重範圍，欄名必須是「階段體重範圍」，不得稱為個體體重。 |
| V16-5 | 物種知識卡 | 動物詳情顯示 Tier、生命階段、年齡表、棲地、建議命中能量、Trophy 類型與五段分數範圍。 |
| V16-6 | 年齡篩選／統計 | 清單可按 Young／Adult／Mature 篩選；總覽顯示各階段數量；CSV 加入階段、體重範圍與資料信心。 |
| V16-7 | 跨快照年度變化 | Diff 除新增／消失外，辨識相同 ID 的年齡增加、獸群變更、Fitness 變更與位置移動；比較頁顯示摘要。 |
| V16-8 | 相容性 | 找不到知識資料時保留原始 age 並顯示 unknown，不阻止存檔解析。60 筆資料結構與所有年齡範圍需通過測試。 |

### 12.3 禁止推論
- 不從 Fitness 推算當前 Trophy 分數或星級。
- 不在體重範圍內插值出假精確體重。
- 不把公開階段最大年齡宣稱為保證死亡時間。

## 13. v1.7 規格 — Offline Hunt Planner & Activity Cycles

### 13.1 研究結論
- Toolbox 的 60 個物種資料實際引用 10 組生命週期 profile；每組由時間與活動代碼構成。以公開頁面及已知作息交叉驗證：`2=Sleep`、`3=Feed`、`4=Drink`。
- 作息時間代表活動週期，不代表獸群會在整段時間固定站在同一個 need zone；同一獸群可在多個餵食、休息、飲水區輪替。
- 因此規劃器可以回答「這個遊戲時間哪些物種通常在做什麼」，但不得聲稱精確到達某個 zone 的時間或保證出現。

### 13.2 功能需求
| ID | 功能 | 驗收標準 |
|---|---|---|
| V17-1 | 離線作息資料 | 60 物種全部具有 profile 與至少一個時段；只允許 Sleep／Feed／Drink 三種已驗證活動。 |
| V17-2 | 狩獵規劃分頁 | 使用者可設定 0–23 時遊戲時間，查看目前保護區所有物種的當前活動、開始／結束時間、下一活動、數量及獸群數。 |
| V17-3 | 活動篩選 | 可只顯示 Drink、Feed、Sleep；提供「下一個飲水時段」排序，方便規劃水邊觀察。 |
| V17-4 | 目標品質 | 規劃表同時顯示該物種高潛力、低潛力觀察與稀有數，沿用使用者設定的門檻。 |
| V17-5 | 地圖整合 | 點擊規劃表物種後，自動切到該物種地圖熱區；不虛構 need zone 座標。 |
| V17-6 | 知識卡作息 | 個體詳情顯示該物種完整 24 小時活動切換表與目前選定時間的活動。 |
| V17-7 | 資料警語 | UI 固定顯示「作息是活動週期，不保證整段時間停留於同一 need zone」。 |
| V17-8 | 測試 | 驗證 60 物種 schedule、午夜循環、當前活動、下一活動及下一飲水時間；瀏覽器測試規劃表與地圖跳轉。 |

### 13.3 不在本版範圍
- 不推測尚未解出的 need zone 座標或玩家尚未發現的 zone。
- 不保證動物準時抵達；地形、移動路徑與多 zone 選擇可能造成延遲。
- 不把 Sleep／Feed／Drink 時段當作射擊建議，只提供觀察規劃資訊。

## 14. v1.8 規格 — 全地圖物種百科與保護區比較

### 14.1 研究結論
- Toolbox 公開物種資料的每筆記錄都帶有保護區索引；索引 `0..6` 對應 Nez Perce Valley、Transylvania、Aurora Shores、Tikamoon Plains、Matariki Park、Lintukoto Reserve、Elkcrest Island，可得到包含新地圖在內的完整物種 roster。
- 官方遊戲說明確認 Trophy 由 Fitness 與年齡等多因素形成，並有 24 小時日夜循環；百科應把 Tier、命中能量、生命階段、Trophy 範圍、作息與地圖位置放在同一處，但不能把 Fitness 直接換算成當前 Trophy 星級。
- 使用者未必已在每張地圖建立存檔，因此百科必須獨立於目前存檔，離線顯示全部 60 種，並另外標示「目前存檔有幾隻」。

### 14.2 功能需求
| ID | 功能 | 驗收標準 |
|---|---|---|
| V18-1 | 完整保護區 roster | 60 種物種全部具有至少一個 `reserves`；七個保護區都可篩選，Elkcrest Island 不得缺漏。 |
| V18-2 | 全地圖百科分頁 | 未載入任何存檔也可瀏覽 60 種；載入存檔後顯示目前存檔數量與是否存在。 |
| V18-3 | 多條件篩選 | 支援保護區、Tier、目前活動及英文／中文／學名搜尋；使用與狩獵規劃相同的遊戲時間。 |
| V18-4 | 比較表 | 顯示英文、中文、學名、保護區、Tier、目前活動、下一飲水、棲地、Trophy 類型、建議命中能量及目前存檔數。 |
| V18-5 | 百科詳情 | 點擊物種顯示完整保護區、生命階段公母年齡／體重、五段 Trophy 範圍與 24 小時作息，並保留來源連結與資料限制警語。 |
| V18-6 | 地圖整合 | 若該物種存在目前存檔，可一鍵開啟該物種地圖熱區；不存在時不提供假座標。 |
| V18-7 | 離線與相容 | 執行時不連網；既有存檔解析、七地圖、規劃器、Live、快照及 CSV 不回歸。 |
| V18-8 | 測試 | 驗證 60 種都有 reserve、七地圖均非空、典型單地圖／跨地圖物種及百科瀏覽器互動。 |

### 14.3 禁止推論
- 不把「出現在某保護區」解讀為精確 need-zone 座標。
- 不以 Trophy 公開範圍反推出個體當前星級或精確分數。
- 不把百科 roster 當成目前存檔實際存在數量；兩者必須分欄顯示。

## 15. v1.9 規格 — Fitness 策略面板與觀察佇列

### 15.1 研究結論
- Nine Rocks Games 在 Update 1.26.7 公開五個 Fitness Potential 指標區間：0–19.99%、20–39.99%、40–59.99%、60–79.99%、80–100%，並說明狩獵影響會在完整遊戲年度後反映到「同物種、同棲地」的所有群體。
- 官方同時區分 Primary、Secondary、Private habitats；存檔目前能可靠讀出個體、獸群與座標，但未解出官方 Hunting Map 的棲地區塊或其 Fitness Potential 圖表。程式只能計算「已讀取公獸的觀察平均」，不可冒充遊戲內棲地指標。
- 社群實測與遊戲討論普遍把 50% 作為低 Fitness caller 的分界；此值可作為預設觀察門檻，但 caller 不保證每次回應，因此只能提供觀察候選，不是必然獵殺指令。
- 高 Fitness 的 Young／Adult 尚有成長空間；高 Fitness Mature 與稀有變種具有不同的觀察目的，應分開標示，不能只用單一「高／低」欄位。

### 15.2 功能需求
| ID | 功能 | 驗收標準 |
|---|---|---|
| V19-1 | 官方五段 Fitness 區間 | 依 0–19.99、20–39.99、40–59.99、60–79.99、80–100% 分類；邊界值需測試。 |
| V19-2 | 策略面板 | 新增獨立分頁，顯示五段公獸數、可觀察候選數、成長保護數、成熟高潛力數及稀有關注數。 |
| V19-3 | 物種分布表 | 每物種列出公獸樣本數、觀察平均、五段數量、低門檻數、高門檻數、目前活動與下一飲水時間。 |
| V19-4 | 觀察佇列 | 將個體分為「稀有關注」「低潛力觀察」「成熟高潛力」「成長保護」「持續觀察」；可依分類與物種篩選。 |
| V19-5 | 年齡語意 | 成長保護只套用 Young／Adult 高潛力公獸；成熟高潛力只套用 Mature；未知生命階段不得假分類。 |
| V19-6 | 地圖／詳情整合 | 點擊佇列個體開啟既有詳情卡，可再前往地圖置中；保留 ID、獸群、Fitness、活動及下一飲水。 |
| V19-7 | 門檻同步 | 沿用管理建議的高／低 Fitness 門檻並即時重算；預設 90%／50%。 |
| V19-8 | 透明限制 | 固定顯示「本頁是存檔中公獸的觀察統計，不是官方棲地 Fitness Potential」；不推測 Primary／Secondary／Private 區塊。 |
| V19-9 | 離線與回歸 | 不新增網路依賴；真實 2,827 隻存檔可互動；既有七地圖、百科、規劃、Live、快照、CSV 不回歸。 |

### 15.3 禁止推論
- 不把獸群平均或全物種平均冒充遊戲內棲地 Fitness Potential。
- 不把低 Fitness 候選寫成「必須獵殺」，不對雌獸產生獵殺建議。
- 不保證 caller 會吸引任何指定個體，也不從 Fitness 推算當前 Trophy 星級。

## 16. v2.0 規格 — Multi-Reserve Command Center

### 16.1 大版本目標
v2.0 不只是再加一個分析表，而是把單一存檔檢視器升級為「七保護區長期管理中心」：程式持續從目前存檔與自己的唯讀快照中保存各保護區最後一次看見的族群狀態，讓玩家切換地圖後仍可在同一介面比較所有地圖。

### 16.2 研究結論
- Way of the Hunter 第一代目前有七個保護區，每張地圖有不同物種 roster；Toolbox 亦以獨立地圖、territory、need-zone 與物種資料管理。
- 真實 `SaveData.sav` 的族群資料只代表目前載入的保護區；切換地圖後，同一檔案會呈現另一個保護區，而不是同時帶回七張地圖完整族群。
- 現有安全快照已按內容 SHA-1 去重，正好可作為「最後看見的保護區狀態」。但非目前地圖只能稱為 last-known snapshot，不能宣稱仍是即時狀態或在未載入該地圖時自行演化。
- Story 與 Free Hunt 的單人地圖族群是共享狀態；多人模式可能產生不同群體，不應混入本機單人保護區 Vault。

### 16.3 功能需求
| ID | 功能 | 驗收標準 |
|---|---|---|
| V20-1 | Reserve Vault | 掃描目前可見 `.sav` 與工具自己的快照，按 SHA-1 去重，為七個保護區各保留最新一筆可讀狀態。 |
| V20-2 | 精簡 Vault API | `/api/vault` 回傳七地圖覆蓋率、來源類型、最後看見時間、檔案路徑、SHA-1、動物／獸群／物種／稀有／高低潛力及每物種摘要；不得回傳完整個體陣列。 |
| V20-3 | 保護區中心首頁 | v2.0 預設首頁顯示七張保護區卡片；有資料者顯示統計與最後看見，無資料者提示「進入該地圖並讓遊戲存檔」。 |
| V20-4 | 跨地圖比較 | 表格比較七地圖總動物、獸群、物種、公獸樣本、平均 Fitness、80%+、50% 以下、稀有及健康狀態。 |
| V20-5 | 物種矩陣 | 依完整 roster 顯示物種在七地圖的最新實際數量；不在該地圖 roster 顯示空白，尚無該地圖存檔顯示「未掃描」。 |
| V20-6 | 開啟歷史狀態 | 點擊有資料的保護區可唯讀載入該 current save 或 snapshot，沿用所有既有分析、地圖與百科功能；不得覆寫遊戲存檔。 |
| V20-7 | 更新與匯出 | 提供重新掃描 Vault 與匯出精簡 JSON；匯出不含二進位存檔或完整個體資料。 |
| V20-8 | 狀態語意 | current 標「目前檔案」，snapshot 標「最後看見」；顯示確切時間，不把舊快照宣稱為即時資料。 |
| V20-9 | 效能與容錯 | 利用現有解析快取；單一檔案錯誤不得阻止其他保護區；最多檢查每來源留存上限內的快照，介面顯示錯誤數。 |
| V20-10 | 相容與回歸 | 保留 v1.9 全部功能；真實 2,827 隻存檔解析、七底圖、策略、規劃、百科、Live、歷史、CSV 全部通過。 |

### 16.4 安全與資料界線
- Reserve Vault 永遠唯讀；「開啟」只讀取指定檔案，不提供還原、覆寫或刪除遊戲存檔。
- 不把不同保護區的 Fitness 合成遊戲官方棲地 Fitness Potential。
- 不把尚未掃描的地圖顯示為 0 隻；必須顯示未知／未掃描。
- 不把多人臨時族群與本機單人 Vault 混為同一份長期族群。

## 17. v3.0 規格 — Habitat Genetics Lab, Need-Zone Navigator & Hunt Journal

### 17.1 大版本目標
在完全不修改遊戲存檔的前提下，把 v2.0 的「最後看見狀態」提升為可追蹤的棲地管理工作流：玩家能看見獸群附近已知 territory／need zones、用同物種同棲地的已知公獸試算管理方向，並從相鄰快照持久記錄生成、消失與年度更替。

### 17.2 研究結論
- Nine Rocks Games 說明，新個體在每個遊戲年度開始時補上死亡個體；其 Fitness 機率受同物種、同棲地在年度更替時的平均 Fitness 影響。較高平均只是提高機率，不是結果保證。官方建議跨同棲地的多個獸群移除低於平均個體，1★ Mature 是較安全的判斷方向，且效果需要耐心等待完整年度。
- Update 1.26.7 公開五段 Fitness，並區分 Primary、Secondary、Private habitat；管理效果在完整遊戲年度後出現。
- Update 1.31 加入 Elkcrest Island 與 cougar，並包含一次補償性年度更替；後續 patch 修正 herd genetics 未正確回應管理的問題。因此 v3.0 不以早期版本單次觀察宣稱管理機制失效。
- 社群開發者回覆強調應維持獸群平均 Fitness，低 Fitness caller 不是 100% 可靠；工具不能把 caller 或外觀當成確定基因值。
- `codeaid/woth-toolbox` 提供六張保護區的 territory 與 Drink／Feed／Sleep 點位。其圖像座標與本工具內附底圖以 SIFT/RANSAC 檢查後為 identity transform；資料轉換成 Unreal 世界公分並離線保存。Elkcrest Island 尚無對應開放資料。
- Way of the Hunter 2 的 Steam Cloud 設定指出存檔位於 `WOTH2/Saved/SaveGames/Account_*/*.nrgs`；格式未公開，所以本版只能偵測與探測檔案特徵。

研究來源：
- https://ninerocksgames.com/posts/end-of-the-year-q-and-a
- https://ninerocksgames.com/posts/update-1-26-7-strategic-habitat-management-and-herd-fitness
- https://ninerocksgames.com/posts/patch-for-the-update-1-31
- https://steamcommunity.com/app/1288320/discussions/0/3801650943424546029/
- https://github.com/codeaid/woth-toolbox
- https://steamdb.info/app/2543830/ufs/

### 17.3 功能需求
| ID | 功能 | 驗收標準 |
|---|---|---|
| V30-1 | 離線 territory／need-zone 資料 | 六張保護區包含 territory 中心、物種 slug、Drink／Feed／Sleep 點位及區域／棲地標籤；所有座標落在既有地圖校準範圍。 |
| V30-2 | 資料授權與建置 | 保存來源 URL、GPL-3.0、來源 commit 與校準說明；`tools/build_need_zones.py` 可由上游資料重建輸出。 |
| V30-3 | 獸群 territory 對應 | 每個獸群只在同物種 slug 中尋找最近 territory；≤300 m 標 high、≤1500 m 標 medium，超過則不對應。 |
| V30-4 | 近似棲地註記 | 以保護區最近區域標籤為獸群及個體加入 area／habitat；介面一律稱「近似棲地」。 |
| V30-5 | 對應健康檢查 | 掃描結果與健康頁顯示可用性、對應率、high 數量、中位距離及 territory 總數，供真實存檔驗證校準品質。 |
| V30-6 | 地圖需求區圖層 | 地圖可切換關閉、territory、全部需求區、規劃時間活動需求區；顏色區分 Drink／Feed／Sleep，游標顯示座標與 territory。 |
| V30-7 | 獸群／個體導航 | 獸群表顯示棲地、區域及對應距離；個體詳情可聚焦其獸群 territory，並顯示目前活動最近需求區距離。 |
| V30-8 | 棲地實驗室 | 依物種 × 近似棲地統計全部動物、獸群、已知公獸、觀察平均、低於平均、成熟低於平均與低門檻數。 |
| V30-9 | 管理試算 | 僅從低於目前觀察平均的已知公獸挑選；可限制 Mature、低門檻、數量並輪流分散獸群；回傳移除前後平均與涉及獸群。 |
| V30-10 | 年齡上限提醒 | 由公開 Mature 年齡範圍上限計算 `age_limit` 與 `years_to_limit`；只標示已達上限或一年內。 |
| V30-11 | 持久狩獵日誌 | `journal/journal.json` 保存相鄰不同 SHA-1 狀態的 transition 與事件；同一 transition 重建時冪等。 |
| V30-12 | 年度更替判定 | 若持續存在個體中至少 50% 年齡增加，該 transition 標為年度更替；事件保留當時棲地平均及低於平均判定。 |
| V30-13 | 日誌介面與 API | `/api/journal` 支援保護區與數量；介面顯示摘要、物種統計、時間軸及事件，可重建及匯出 JSON。 |
| V30-14 | WOTH2 唯讀偵測 | `/api/woth2` 搜尋已知 `.nrgs`／`.sav` 路徑，只回傳大小、時間、magic、熵與是否可能壓縮；`parsed=false`。 |
| V30-15 | 匯出與相容 | CSV 新增 habitat、area、territory、年齡上限欄位；保留 v2.0 全部分頁、API、快照與唯讀保證。 |
| V30-16 | 自動驗收 | 測試涵蓋六地圖資料完整性、座標範圍、slug、獸群對應、試算、年齡提醒、日誌、年度更替、WOTH2 probe 及 v3 API。 |

### 17.4 安全、語意與資料界線
- **遊戲存檔永遠唯讀。** 快照與日誌只寫入工具自己的資料夾；不還原、不覆寫、不刪除遊戲檔案。
- `habitat` 是最近公開區域標籤的**近似值**，不是遊戲內部棲地多邊形，也不能冒充 Hunting Map 的 Fitness Potential。
- 試算器只重算目前已知公獸樣本的算術平均；不模擬遊戲 RNG、不預測新個體 Fitness、不保證 Trophy 結果。
- 日誌的 `removed` 只表示動物 ID 在相鄰狀態間消失；不得斷言為玩家獵殺，亦可能是自然死亡或年度更替。
- 年度更替為快照差異的啟發式判斷，不是讀取遊戲內年份欄位；必須顯示判定門檻。
- Mature 公開上限是物種知識資料，不是死亡時間；不得顯示精確死亡倒數。
- Elkcrest Island 沒有上游 need-zone 資料時顯示「無資料」，不得自行生成點位。
- WOTH2 只做檔案偵測；格式未公開前不解析、不修改，也不把 WOTH1 解析器硬套到 `.nrgs`。
- 不虛構個體 Trophy score、體重、星級或雌獸 Fitness。

### 17.5 第三方資料授權
`data/need_zones.json` 衍生自 `codeaid/woth-toolbox`（來源 commit `a0a73f84cd7506b4a813ec3b79e36f363d12655a`，2026-03-28），依上游 **GPL-3.0** 授權。發行包必須保留來源、授權、commit 與轉換說明。

## 18. v4.0 規格 — Field Operations & Population Observatory

### 18.1 大版本目標
v4.0 把掃描器從「單次族群分析」升級為可驗證的長期野外作業中心：

1. 從存檔中尋找玩家／獵人的最後位置，只有在欄位與數值通過驗證時才畫在地圖。
2. 以玩家位置或手動地圖釘為起點，建立同物種、同近似棲地的遠征停靠順序。
3. 把多份快照轉成年度、棲地、cohort 與個體的 Population Observatory。
4. 讓每個數字都能回答「是存檔值、推導值、近似值，還是啟發式判定」。

### 18.2 先行設計審查
v3.0 已有七地圖 Reserve Vault、真實 WOTH Database 動物／獸群解析、60 物種離線知識、六地圖 territory／need zones、Fitness 策略、棲地試算、狩獵日誌、歷史、Live、CSV、健康檢查及 WOTH2 安全偵測。v4.0 必須沿用這些功能，不另造互相矛盾的統計口徑。

目前地圖使用 Unreal 世界公分，動物與獸群可直接疊在底圖；因此玩家位置若同樣是世界座標，必須走相同 `x_min/x_max/y_min/y_max` 轉換，不能另做目測校正。

### 18.3 玩家位置逆向研究
- 使用者提供的真實 `SaveData.sav` 為 `DatabaseSaveHeader`、code version 84，外層為 WOTH + UE chunks + Oodle；解壓後約 4.8 MB。
- 此樣本可穩定解析 2,777 隻動物、482 群，判定為 Nez Perce Valley；territory 對應率 93.78%、中位距離 263.9 m。
- tagged GVAS header 只有 `m_databaseCodeVersion` 與 `m_isMigrated`，沒有 `PlayerLocation`。
- custom database 的 name table 共 2,430 筆；可確認目前地圖值 `Idaho_01`，但沒有命名為 Player／Pawn／Character 的 world-transform record。已知 framed records 是動物、AnimalGroupPawn、spawn／mission 資料、設定及使用者進度。
- 因只有一個真實狀態，未能以「移動前／後」差分證明任何匿名 12-byte 向量就是玩家位置。v4.0 不得把未驗證的 float 三元組畫成「你在這裡」。
- 舊版／其他格式的 tagged GVAS 可能直接出現 `PlayerLocation`、`LastLocation`、`PlayerTransform` 等 Vector；這類欄位可高信心支援。
- 要完成目前 Database 格式的匿名欄位驗證，需要同一存檔在只移動玩家後的第二份樣本；移動距離最好超過 300 m，期間不要快旅行、獵殺或切換地圖。

### 18.4 遊戲內容研究
- 社群實測說明離開遊戲後會保存最後位置，但這只證明遊戲能恢復位置，不等於位置必然以可命名的明文 Vector 存在。
- 官方說明 WOTH 地圖為大規模開放世界，Nez Perce Valley 與 Transylvania 各 144 km²；遠征路線因此有實際用途。
- 官方年度管理規則不變：新個體在年度開始時補充，Fitness 機率受同物種、同棲地平均影響；高平均不保證高 Fitness。
- Update 1.26.7 的五段 Fitness、Primary／Secondary／Private habitat 與完整年度生效界線仍是 v4 分析的依據。

研究來源：
- https://steamcommunity.com/app/1288320/discussions/0/3791506516132297414/
- https://wayofthehunter.thqnordic.com/
- https://ninerocksgames.com/posts/end-of-the-year-q-and-a
- https://ninerocksgames.com/posts/update-1-26-7-strategic-habitat-management-and-herd-fitness
- https://github.com/codeaid/woth-toolbox
- https://github.com/zao/pyooz

### 18.5 功能需求
| ID | 功能 | 驗收標準 |
|---|---|---|
| V40-1 | Player State Extractor | 對 tagged GVAS 遞迴尋找語意明確的 Player／Hunter + Location／Position／Transform Vector，回傳 x/y/z、來源 path 與 confidence。 |
| V40-2 | Database current-map evidence | Database 格式回傳已確認的目前地圖代碼與解析證據；找不到已驗證 transform 時，`available=false`，不得猜座標。 |
| V40-3 | 玩家位置健康檢查 | 顯示 exact／candidate／unavailable、欄位 path、是否在目前地圖範圍、最近 area／territory 與需要何種驗證。 |
| V40-4 | 地圖「我的位置」 | exact 位置以獨立高對比圖示顯示；無 exact 時可在地圖點選手動 pin，必須明標「手動、未寫入存檔」。 |
| V40-5 | 手動位置保存 | 手動 pin 只進瀏覽器 localStorage，可清除、拖動或重新設定；伺服器及遊戲存檔皆不寫入。 |
| V40-6 | Field Expedition Planner | 以 exact 玩家位置、手動 pin 或候選中心為起點；依 Fitness、成熟、稀有排除、物種、棲地、活動及數量建立停靠點。 |
| V40-7 | 路線演算法 | 最近鄰後做 deterministic 2-opt；顯示每段與累積直線距離，最多 50 站。 |
| V40-8 | 路線誠實界線 | 路線不宣稱考慮道路、地形、風向、私人土地、狩獵壓力或動物移動；候選不是獵殺指令。 |
| V40-9 | Population Observatory | 讀取同來源所有去重快照，依時間建立 states、transitions、year turns、species × habitat trend 與 scorecard。 |
| V40-10 | 年度與棲地成效卡 | 顯示首次／目前平均、淨變化、移除、新生、新生公獸平均及低於平均移除率；依 snapshot-only／one-year／multi-year 標信心。 |
| V40-11 | Cohort Ledger | 依動物 ID 顯示 first/last seen、觀察次數、年齡增加、換群、近似棲地變化及 present/gone；不得把 gone 寫成 harvest。 |
| V40-12 | Observatory Watchlist | 匯總稀有、80%+ 或接近公開 Mature 上限的目前個體，可連到既有詳情與地圖。 |
| V40-13 | Methodology Registry | 提供 saved／derived／approximation／heuristic／observed-delta／planning-aid 六類定義、限制與來源。 |
| V40-14 | API | 新增 `/api/player-state`、`/api/observatory`、`/api/route`、`/api/methodology`；錯誤不得影響既有掃描 API。 |
| V40-15 | 匯出 | Observatory 與 route 可匯出 JSON；輸出包含版本、來源 SHA-1、filters、method note 與 caveat。 |
| V40-16 | 真實存檔驗收 | 隨附測試不得包含使用者真實存檔；開發時以其 SHA-1／數量／對應率記錄驗證結果，發行前移除解壓資料。 |
| V40-17 | 自動測試 | 覆蓋 tagged player vector、Database unavailable 語意、bounds、手動起點路線、2-opt、observatory year turn、cohort、API 與瀏覽器互動。 |

### 18.6 玩家位置信心模型
| 等級 | 條件 | 地圖行為 |
|---|---|---|
| `exact` | 欄位名稱具 Player／Hunter 語意，值為有限 Vector，且落在目前 reserve bounds | 自動畫「你在這裡」並可作為路線起點 |
| `candidate` | 匿名欄位只經雙存檔差分符合移動，尚未由第二個人／地圖交叉驗證 | 只在診斷區顯示，不預設畫在地圖 |
| `manual` | 使用者在地圖自行放 pin | 畫在地圖，明標手動；只存 localStorage |
| `unavailable` | 沒有通過驗證的欄位 | 不畫假位置，顯示取得第二份移動後存檔的驗證指引 |

### 18.7 安全與解釋界線
- 所有遊戲 `.sav` 仍以 `rb` 開啟；v4.0 不提供 teleport、位置修改或存檔寫回。
- 「目前位置」實際是最後一次寫入該 save 的位置，不保證等於遊戲仍開著時的即時位置。
- current-map 代碼不等於 exact coordinate；只知道 `Idaho_01` 時不得把地圖中心冒充玩家位置。
- Snapshot Observatory 是觀察性資料。平均上升與管理事件同時發生，不足以證明單一獵殺造成結果。
- Fitness 仍不是個體 Trophy score、體重或星級；雌獸 Fitness 不推測。
- `removed`／`gone` 仍可能是獵殺、自然死亡、年度更替或快照缺漏。
- 自動路線是直線規劃輔助，不是安全導航或土地進入許可。

### 18.8 Database 玩家 Transform 與 Live 修正
- 雙存檔差分確認 `Idaho_01` state trailer 內含旋轉與 XYZ；解析器以地圖雜湊、固定欄位排列、後續 `AnimalGroupPawn`、唯一候選及地圖 bounds 五項條件驗證。
- Live 每次確認 SHA-1 改變後必須繞過掃描快取並重新解析 `player_state`；不能只刷新動物事件。
- 即使時間戳和檔案大小相同，SHA-1 改變仍視為新狀態。
- 新位置立即更新地圖圖釘與即時事件；玩家移動後清除使用舊起點的遠征路線。
- `exact` 是最近一次寫入存檔的位置，不是遊戲執行中的每幀 GPS；存檔維持唯讀。

### 18.9 v4.0.3 更正
- 18.8 的「地圖代碼 state trailer」經三份真實存檔（玩家走動約 400 m）驗證：其 XYZ 不隨玩家移動，判定為停放載具／固定物件，不得作為玩家位置。
- 玩家位置為 Database 本體尾端的固定形狀紀錄：`01 08 00 00 00 01 00 00 00 00 00 00 00 00 02 00 00 00 01 02 00 00 00` + 3×f32（用途未明）+ XYZ（f32，Unreal cm）+ `01 00 00 00 00 02 02 00 00 00`。需唯一命中且座標在地圖範圍內才標 `exact`。
- 驗證依據：兩個不同位置的存檔各有一筆，走動距離 ≈ 394 m，且與遊戲內地圖玩家箭頭位置相符（X 差約 10 px）。目前只在 Nez Perce Valley 驗證；其他地圖需各自取得走動前後存檔確認。
- 已知限制：3 個前置 f32 的意義未知（不使用）；Z 在部分狀態為 -79270 附近，僅供參考，不用於繪圖。
