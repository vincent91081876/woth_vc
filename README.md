# WOTH 動物族群掃描器 (Way of the Hunter Animal Population Scanner)

仿 theHunter: COTW「Animal Population Scanner」的 **Way of the Hunter 版**。
獨立程式、**唯讀**：只讀取存檔，不修改遊戲，也不需要遊戲在執行中。

## 安裝與啟動
1. 安裝 [Python 3.9+](https://www.python.org/downloads/)（勾選 *Add Python to PATH*）。
   WOTH 存檔使用 Oodle 壓縮，`run_windows.bat` 第一次執行會自動安裝隨附的 `vendor/pyooz`（Oodle 解壓縮器）。
2. 解壓縮整個資料夾到本機硬碟。
3. 雙擊 `run_windows.bat`，瀏覽器會自動打開 `http://127.0.0.1:8765/`。

存檔預設位置：`%LOCALAPPDATA%\WayOfTheHunter\Saved\SaveGames\`（會自動偵測，也可在上方輸入完整路徑）。

## 功能
| 分頁 | 內容 |
|---|---|
| 保護區中心 | v2.0 Reserve Vault：保存七地圖最後一次看見的唯讀狀態、跨地圖比較與 60 物種矩陣 |
| 總覽 | 各物種總數、存活、公/母、獸群數、最高/平均分數；分數分布直方圖 |
| 狩獵規劃 | 依遊戲時間、Drink/Feed/Sleep 活動與下一飲水時段規劃；點物種直達地圖熱區 |
| 全地圖百科 | 離線瀏覽 60 種動物與七個保護區 roster；依地圖、Tier、活動與名稱篩選 |
| 動物清單 | 依物種/性別/生命階段/Fitness/稀有/關注篩選；顯示離線物種知識 |
| 管理建議 | 依獸群分析高／低潛力公獸、稀有與性別比 |
| Fitness 策略 | 官方五段 Fitness 色帶、物種分布與個體觀察佇列；整合活動、下一飲水與詳情定位 |
| 棲地實驗室 | 依「物種 × 近似棲地」統計已知公獸；試算移除低於平均的成熟公獸後，觀察平均如何改變 |
| 族群觀測站 | 由全部去重快照建立年度／棲地成效卡、趨勢、個體 cohort 與證據信心 |
| 遠征路線 | 以存檔玩家位置、手動地圖釘或候選中心排序管理停靠點；顯示每段與累積直線距離 |
| 獸群 | 每群物種、數量、中心座標；點擊看成員 |
| 地圖 | 動物、獸群、territory、Drink／Feed／Sleep、玩家位置、手動 pin 與遠征路線圖層 |
| 即時事件 (Live) | 按「● Live 模式」後，遊戲每次存檔就自動重讀：綠 = 新生成、紅 = 消失/死亡 |
| 狩獵日誌 | 持久記錄相鄰存檔間的生成、消失、年度更替與管理品質；可重建及匯出 JSON |
| 快照比較 | 每次讀取會自動把存檔複製到 `snapshots/`，可與舊快照比較生成/死亡 |
| 名詞解釋 | 56 條離線名詞（Fitness、生命階段、exact／manual 位置、快照、年度更替…），可搜尋、依類別篩選，不需載入存檔 |
| 存檔結構 | 完整存檔樹 + 下載 JSON，用來找出欄位名稱 |
| 匯出 CSV | 動物清單 (Excel 可直接開啟) |

## 命令列
```
python woth_scanner.py --list                 # 列出偵測到的存檔
python woth_scanner.py --scan SaveData.sav    # 印出族群摘要
python woth_scanner.py --dump SaveData.sav --out dump.json   # 匯出完整結構
python woth_scanner.py --journal              # 印出狩獵日誌摘要
python woth_scanner.py --port 9000 --no-browser
```

## 讀到的資料（v1.1，依真實存檔逆向）
| 欄位 | 說明 |
|---|---|
| 物種 / 中文 | 由 Blueprint 類別的學名判斷（例：CervusCanadensis = 洛磯山馬鹿） |
| 性別 | 公 / 母 |
| 年齡 | 遊戲內部的年齡數值（單位未公開，數字越大越老） |
| Fitness | 公獸的基因/潛力 0~100%（母獸存檔中為 0，不顯示） |
| 評等 | 該公獸 Fitness 在同物種中的排名（例：同種前 0.5%） |
| 稀有 | 白化 (Albino)、黑化 (Melanistic) 等變種 |
| 獸群 / 座標 | 所屬獸群 ID 與世界座標（公分） |
| ID | 遊戲內唯一動物編號，Live 模式/快照比較用它判斷新生成與消失 |

存檔中**沒有**體重與分數欄位，所以這兩欄會是空的。
存檔目前只保存玩家所在保護區的族群（程式會自動判斷保護區）。

若之後遊戲更新改了格式，舊的通用 GVAS 模式仍可用：在「存檔結構」分頁或 `--dump` 找欄位，修改 `config.json`。

## 檔案
- `woth_scanner.py` 入口 / 本機伺服器 / CLI
- `gvas.py` 通用 GVAS 解析 + zlib/Oodle 解壓縮
- `woth_db.py` WOTH 自訂資料庫格式解析（動物、獸群、名稱表）
- `vendor/pyooz-*.whl` Oodle 解壓縮器（[pyooz](https://pypi.org/project/pyooz/)，第三方套件）
- `extract.py` 動物與獸群辨識、統計、差異比對
- `species.py` WOTH 物種表（英/中）
- `species_data.json` 離線 60 物種知識與作息
- `data/need_zones.json` 六地圖 territory／需求區／區域標籤資料
- `habitat.py` 棲地近似、territory 對應及管理試算
- `journal.py` 工具自有狩獵日誌
- `woth2.py` WOTH2 存檔偵測與安全格式 probe
- `player_state.py` 玩家位置／目前地圖證據與信心判定
- `observatory.py` 多快照族群觀測站、年度、棲地與 cohort
- `route_planner.py` 遠征停靠點與直線 2-opt 路線
- `methodology.py` 指標來源、證據等級與禁止推論清單
- `THIRD_PARTY_NOTICES.md` 第三方資料來源與授權
- `web/index.html` 介面
- `web/glossary.js` 名詞解釋內容與渲染
- `tests/` 合成存檔產生器與單元測試（`python tests/test_scanner.py`）
- `SPEC.md` 規格書

本工具為全新撰寫，未使用原 COTW 掃描器的程式碼或素材。

## v1.2 地圖定位
- 「地圖」分頁會自動載入 **Nez Perce Valley** 底圖，將存檔中的世界座標換算到地圖位置。
- 可依物種篩選、切換單隻/獸群顯示；滑鼠移到標記上可看物種、性別、年齡、Fitness、ID 與獸群。
- 滾輪縮放、拖曳平移；左下角顯示 1 km 比例尺。經真實存檔中的水鳥位置驗證座標方向（91% 在底圖水域 100 m 內）。
- 目前只有 Nez Perce Valley 經真實存檔校正。其他保護區仍顯示座標散點；取得該區真實存檔後可加入/驗證底圖。
- 底圖來源：[Way of the Hunter Toolbox](https://toolbox.byteset.io/maps/nez-perce-valley)（v4.0.5 起；先前為 codeaid/woth-toolbox）。

## v1.3 全地圖版
已內建《Way of the Hunter》第一代全部 7 個保護區底圖與各自座標範圍：

| 保護區 | 內部地圖 | 座標範圍（約） |
|---|---|---|
| Nez Perce Valley | Idaho | 12 × 12 km |
| Transylvania | Transylvania | 11.87 × 11.87 km |
| Aurora Shores | Alaska | 8.07 × 8.07 km |
| Tikamoon Plains | Africa | 10 × 10 km |
| Matariki Park | New Zealand | 8.13 × 8.13 km |
| Lintukoto Reserve | Finland | 8.13 × 8.13 km |
| Elkcrest Island | Elkcrest | 8.13 × 8.13 km |

程式會從存檔中的物種組合判斷目前保護區並自動切換底圖；Elkcrest 以 Merriam's Wild Turkey，或 Kodiak Bear + Cougar 組合辨識。每張圖使用獨立的 X/Y 校正，不能互換。
底圖與座標範圍來源：[Way of the Hunter Toolbox](https://toolbox.byteset.io/maps)。Nez Perce Valley 已用真實存檔驗證；其他六張使用 Toolbox 公開的精確 3D 場景範圍，待取得各區真實存檔後可再做交叉驗證。

## v1.4 族群管理與目標定位
- 新增「管理建議」：以可調整的高/低 Fitness 門檻分析每個獸群的公獸平均、最高潛力、稀有數與性別比。
- 動物清單新增高潛力、低潛力觀察、稀有與已關注快速篩選。
- 點擊個體會開啟詳情卡，可加入永久關注或一鍵在地圖置中；關注資料只保存在本機瀏覽器。
- 地圖新增個體、獸群、熱區三種模式；被關注個體有黃色外框。
- 快照比較新增各物種新增、消失與淨變化摘要。
- 用語修正：Fitness 是生成時的潛力；同種百分位不是目前 Trophy 星級。本工具不在缺乏可靠公式時虛構體重、分數或星級。

## v1.5 歷史趨勢、健康檢查與安全快照
- 「歷史與健康」會以快照畫出物種總數、公獸數、平均 Fitness、高／低潛力與稀有數趨勢。
- 健康檢查包含：解析警告、重複 ID、未知物種、無法對應獸群、無效座標、超出地圖範圍與大幅族群變動。
- 相同內容的快照以 SHA-1 去重；新檔名包含雜湊；每個來源預設最多保留 100 份，可在 `config.json` 的 `max_snapshots` 調整。
- 若總族群變化達 20%，或單一物種達 30%，只顯示「注意」，不直接判定存檔損壞。
- 關注個體現在保存最後看見時間，並標示仍存在或已消失。
- 可匯出管理報告 JSON，包含健康檢查、門檻、獸群統計和關注狀態；不包含原始存檔內容。
- 為避免遊戲或 Steam Cloud 同步時覆寫資料，程式刻意不提供自動還原；原始存檔依舊只讀。

## v1.6 已驗證生命階段與物種知識庫
- 內建 60 種動物的離線資料：公／母 Young、Adult、Mature 年齡及體重範圍、Tier、棲地、建議命中能量、Trophy 類型與五段分數範圍。
- 存檔的 age 現在依「物種 + 性別」正確轉為生命階段；清單與總覽可按幼年／成年／成熟篩選及統計。
- 「階段體重範圍」是公開物種資料，不是個體精確體重；程式不做虛假內插。
- 每筆顯示資料信心：`verified-table`、`proxy` 或 `unknown`。Eastern Wild Turkey 暫用 Merriam's Wild Turkey 年齡表並明確標為 proxy。
- 個體詳情新增物種知識卡與來源連結。
- CSV 新增原始年齡、生命階段、中文階段、階段體重範圍及資料信心。
- 快照比較新增同 ID 個體的年齡增加、生命階段變化、換獸群、Fitness 變化及移動距離摘要。
- 離線資料來源：[Way of the Hunter Toolbox Animals](https://toolbox.byteset.io/animals)，擷取後隨程式保存，執行時不需網路。


## v1.7 Offline Hunt Planner 與活動週期
- 新增「狩獵規劃」：以 0–23 時遊戲時間篩選 Drink／飲水、Feed／覓食、Sleep／休息中的物種。
- 內建 60 種動物的 24 小時離線作息，可顯示目前時段、下一活動與下一飲水時間；可按目前活動、下一飲水或高潛力數量排序。
- 每列結合目前存檔的動物數、獸群數、高／低潛力與稀有數；點擊物種會直接切到該物種地圖熱區。
- 個體知識卡同步顯示所選規劃時間的活動與全天週期。
- 活動時段不等於固定座標：動物可能在 need zones 間移動，同一獸群也可能輪替不同區域，因此程式只將作息與存檔中的實際獸群位置結合，不虛構 need-zone 座標。
- 作息資料離線保存，執行時不需網路。研究來源：[Way of the Hunter Toolbox — Mule Deer](https://toolbox.byteset.io/animals/mule-deer)；need-zone 行為交叉參考：[Steam 社群討論](https://steamcommunity.com/app/1288320/discussions/0/5533260453835959170?ctp=2&l=brazilian)。

## v1.8 全地圖物種百科
- 新增「全地圖百科」，不需先擁有每張地圖的存檔即可離線查閱全部 60 種動物。
- 完整支援 Nez Perce Valley、Transylvania、Aurora Shores、Tikamoon Plains、Matariki Park、Lintukoto Reserve、Elkcrest Island 的物種 roster。
- 可依保護區、Tier、目前 Drink／Feed／Sleep 活動及英文／中文／學名搜尋；遊戲時間與狩獵規劃同步。
- 比較表整合學名、保護區、棲地、Trophy 類型、建議命中能量、下一飲水時間，以及該物種在目前存檔中的實際數量。
- 點擊物種可查看公／母生命階段、體重範圍、五段 Trophy 範圍及完整作息；若目前存檔有該物種，可直接開啟地圖熱區。
- 保護區 roster 與物種資料來源：[Way of the Hunter Toolbox](https://toolbox.byteset.io/maps)。官方遊戲頁說明 Trophy 會受 Fitness 與年齡等多項因素影響，並具有 24 小時日夜循環：[Way of the Hunter 官方網站](https://wayofthehunter.thqnordic.com/)。
- 保護區名單不是精確 need-zone；公開 Trophy 範圍也不會被用來反推出個體目前星級或分數。

## v1.9 Fitness 策略面板
- 依 Nine Rocks Games Update 1.26.7 公開區間顯示五段 Fitness：0–19.99%、20–39.99%、40–59.99%、60–79.99%、80–100%。
- 新增每物種公獸樣本數、觀察平均、五段數量、高／低門檻數、目前活動與下一飲水時間。
- 個體觀察佇列分為「稀有關注」「低潛力觀察」「成熟高潛力」「成長保護」「持續觀察」；高／低門檻與管理建議同步。
- 高潛力 Young／Adult 與 Mature 分開標示；不對雌獸產生低 Fitness 管理建議。點擊個體可開啟既有詳情並前往地圖。
- CSV 新增 `fitness_band`，方便外部整理。
- 官方說明指出，完整遊戲年度後的管理影響作用於同物種、同棲地，並區分 Primary／Secondary／Private habitat。[Nine Rocks Games：Update 1.26.7](https://ninerocksgames.com/posts/update-1-26-7-strategic-habitat-management-and-herd-fitness)
- 目前存檔未提供可可靠對應的官方棲地區塊與 Fitness Potential 圖表，因此本頁明確標示為「存檔公獸觀察統計」，不冒充遊戲 Hunting Map 指標。50% 預設低門檻與 caller 行為交叉參考：[Steam 社群討論](https://steamcommunity.com/app/1288320/discussions/0/766309862211653033/)。

## v2.0 Multi-Reserve Command Center
這是架構級更新：掃描器由「一次查看一個存檔」升級為七保護區長期管理中心。

- 新增預設首頁「保護區中心」，以七張卡片顯示 Nez Perce Valley、Transylvania、Aurora Shores、Tikamoon Plains、Matariki Park、Lintukoto Reserve 與 Elkcrest Island。
- Reserve Vault 會唯讀檢查目前 `.sav` 與程式自己的去重快照，按保護區保存最新狀態。當玩家日後切換地圖並完成存檔，該地圖會自動加入 Vault。
- 每張卡片顯示最後看見時間、目前檔案／快照來源、動物、獸群、實際／預期物種、平均 Fitness、80%+、稀有、健康及 SHA-1。
- 新增七地圖比較表與完整 60 物種矩陣；「未掃描」與 0 隻分開處理，不把未知資料顯示成零。
- 可唯讀開啟任一保護區的最後狀態，繼續使用總覽、Fitness 策略、狩獵規劃、地圖、歷史與 CSV。
- 可重新掃描 Vault 或匯出精簡 JSON；匯出不含存檔二進位內容及完整個體清單。
- 舊快照永遠標示為「最後看見」，不宣稱是未載入地圖的即時狀態。
- Toolbox 的地圖工具以獨立地圖、territory、need-zone 與物種資料管理，亦支援依活動時間篩選：[Way of the Hunter Toolbox Help](https://toolbox.byteset.io/help)。
- Story 與 Free Hunt 使用相同的單人地圖族群；多人模式可能建立不同群體，因此 v2.0 Vault 只管理本機 `.sav` 與自己的快照：[社群說明](https://www.reddit.com/r/WayOfTheHunter/comments/19dgcb3/free_hunt_question/)。

## v3.0 Habitat Genetics Lab、Need-Zone Navigator 與 Hunt Journal
v3.0 把官方「同物種、同棲地、跨年度」的管理概念，連接到存檔中可驗證的個體、獸群及歷史變化。

- **棲地實驗室**：依物種與近似棲地顯示公獸樣本、觀察平均、低於平均個體與成熟候選；試算器只會重算移除候選後的平均，不會預測下一年生成結果。
- **需求區導航**：六張有開放資料的保護區可在既有底圖疊加 territory 及 Drink／Feed／Sleep 點位；獸群以最近同物種 territory 對應，健康檢查顯示對應率及中位距離。Elkcrest Island 目前沒有此資料。
- **年齡上限提醒**：依公開 Mature 年齡表標示已達或距離上限一年的個體；這是公開階段上限，不是死亡倒數。
- **狩獵日誌**：把相鄰快照中的 ID 消失、生成、年齡增加與推定年度更替寫入工具自己的 `journal/journal.json`。`removed` 只表示兩次存檔間不見，可能是獵殺、自然死亡或年度更替。
- **WOTH2 安全偵測**：可尋找 `%LOCALAPPDATA%\WOTH2\Saved\SaveGames\Account_*\*.nrgs` 並顯示大小、檔頭及熵；格式未公開，因此不解析、不修改。
- 官方說明：新個體在遊戲年度開始時補充，生成 Fitness 受同物種、同棲地平均值影響，但高平均只提高機率，不保證結果；建議跨多個獸群管理低於平均個體。[Nine Rocks Games：End-of-year Q&A](https://ninerocksgames.com/posts/end-of-the-year-q-and-a)
- 五段 Fitness、Primary／Secondary／Private habitat 與「完整遊戲年度後才看見影響」來自 [Update 1.26.7](https://ninerocksgames.com/posts/update-1-26-7-strategic-habitat-management-and-herd-fitness)。Update 1.31 之後另有 herd genetics 修正：[Patch for Update 1.31](https://ninerocksgames.com/posts/patch-for-the-update-1-31)。
- WOTH2 路徑依 Steam Cloud 設定交叉確認：[SteamDB app 2543830 — UFS](https://steamdb.info/app/2543830/ufs/)。

### 第三方需求區資料
`data/need_zones.json` 是從 [codeaid/woth-toolbox](https://github.com/codeaid/woth-toolbox) 的地圖／動物資料轉換而來，來源版本 `a0a73f84cd7506b4a813ec3b79e36f363d12655a`（2026-03-28），依原專案 **GPL-3.0** 授權。程式把 0–1 圖像座標轉成 WOTH 世界公分；六張舊地圖與內附底圖經 SIFT/RANSAC 校準為 identity transform。近似棲地取最近的區域標籤，不是遊戲內部棲地多邊形。

## v4.0 Field Operations & Population Observatory
v4.0 是第二次架構級更新：地圖現在同時是「證據地圖」與「野外作業台」，歷史資料則提升成跨快照的 Population Observatory。

### 玩家位置研究結果
- 新增 `player_state`：對 tagged GVAS 遞迴尋找語意明確的 `PlayerLocation`／`PlayerTransform` Vector；只有座標落在目前地圖範圍內時才標為 `exact` 並自動畫在地圖。
- 使用者提供的真實 v1.31 `SaveData.sav` 已唯讀解壓與分析：2,777 隻、482 群、Nez Perce Valley，territory 對應率 93.78%、中位距離 263.9 m。
- 該真實 Database 格式可確認目前地圖代碼 `Idaho_01`，但 name table 與 framed records 沒有命名為 Player／Pawn／Character 的 transform；只有一個狀態時，無法證明任何匿名 12-byte float 是玩家座標。
- 因此本版不把地圖中心或匿名 float 冒充「你在這裡」。此格式會誠實顯示「玩家座標未驗證」，並提供只存於瀏覽器 localStorage 的手動地圖釘。
- 若要完成目前 Database 格式的 exact 解析，需要同一地圖「只移動玩家 300 m 以上、不要快旅行／獵殺／切圖」後的第二份存檔，以差分鎖定匿名欄位；之後仍要跨地圖驗證。

社群回報指出離開時會保存最後位置，但這只能證明遊戲能恢復狀態，不能證明座標以可命名明文 Vector 儲存。[Steam 討論](https://steamcommunity.com/app/1288320/discussions/0/3791506516132297414/) WOTH 官方網站說明前兩張地圖各為 144 km²，亦是本版加入遠征規劃的原因之一。[官方遊戲網站](https://wayofthehunter.thqnordic.com/)

### 遠征路線
- 可依物種、近似棲地、Drink／Feed／Sleep、成熟、Fitness 上限、稀有排除及最多站數產生管理候選。
- 起點依序可使用 exact 存檔位置、手動地圖釘或候選中心；先採最近鄰，再以 deterministic 2-opt 縮短。
- 路線顯示每段、累積距離及總直線公里，並可直接畫到既有地圖與匯出 JSON。
- 路線不包含道路、地形、風向、私人土地、狩獵壓力或動物移動；候選不是獵殺指令。

### Population Observatory
- 讀取同來源全部 SHA-1 去重快照，產生 state、transition、推定年度更替及 species × habitat trend。
- 棲地成效卡顯示首次／目前平均、淨變化、消失、新出現、新出現公獸平均及低於平均消失率。
- 每張卡標為 `snapshot-only`、`one-year` 或 `multi-year`，避免用單次快照冒充年度成效。
- Cohort Ledger 追蹤每個 ID 的 first／last seen、觀察次數、年齡增加、換群、近似棲地變化及 present／gone。
- 內建 methodology registry，區分 `saved`、`derived`、`approximation`、`heuristic`、`observed-delta` 與 `planning-aid`。

完整需求、玩家位置信心模型與禁止推論界線見 `SPEC.md` 第 18 節。

### v4.0.2 玩家位置修正
- WOTH Database 格式現在可解析經移動前／後存檔差分驗證的角色 Transform；通過結構與地圖範圍檢查後顯示 `exact`。
- Live 模式會以 SHA-1 確認內容更新、繞過舊掃描快取，立即移動「你在這裡（存檔）」並記錄新 XYZ。
- 玩家位置改變後會清除舊起點的遠征路線。所有存檔操作仍為唯讀。

### v4.0.3 玩家位置改讀正確欄位
- 修正：v4.0.2 讀的「地圖代碼旁 Transform」實際是停放的載具／固定物件，玩家走動時不會變，所以地圖上的「你在這裡」會錯位且 Live 不更新。
- 現在改讀 Database 尾端的玩家位置紀錄（固定前後綴、位於名稱表前約 3.6 KB）。以走動約 400 m 的兩份真實存檔及遊戲內地圖箭頭交叉驗證。
- 舊欄位保留在 API 的 `player_state.vehicle`，僅供診斷，不會畫成「你在這裡」。

### v4.0.4 名詞解釋與檢修
- 新增「名詞解釋」分頁（`web/glossary.js`）。
- 修正：地圖在目前篩選沒有任何動物時，「你在這裡」與手動地圖釘不會顯示，也無法點選手動位置。
- 清理未使用的匯入。已逐頁載入真實存檔、呼叫全部 API，無 JS 錯誤或 HTTP 錯誤。

### v4.0.5 底圖改為 Toolbox 樣式
- 七張底圖改用 [Toolbox](https://toolbox.byteset.io/maps/) 的地圖素材（`base` 衛星貼圖 + `normal` 法線貼圖 + `mask` 遮罩）合成：加入**地形陰影、藍色水域、黃色道路**，並把地圖外緣壓暗，辨識度明顯提高。
- 座標範圍與 Toolbox 3D 網格 `mesh.gltf` 的頂點範圍逐一核對，七張皆完全相同，因此玩家/動物/領地/需求區位置**不需重新校正**。
- 重建：`python3 tools/build_maps.py`（需連網、numpy、Pillow）。Toolbox 的區域邊界線與地名標籤是網站程式碼繪製、不在圖片內，故未包含。

### v4.0.6 詳細比例尺與距離量測
- **比例尺**：依縮放自動選 1／2／5 × 10ⁿ 的整齊長度，黑白分段、每段標刻度（同一單位，太擠時自動隔格標示），並顯示「1 像素 ≈ 幾公尺」「縮放倍率」「地圖全幅公里數」。
- **📏 量測距離**：按鈕開啟後在地圖上依序點選位置，會畫出黃色路徑，每段標長度，右上角面板顯示總長、起終點直線距離、ΔX／ΔY（公尺）與圖上方向。
  - 預設「從我的位置起算」（存檔位置或手動位置），可取消勾選改為自選起點。
  - 點到動物／獸群／標記會自動吸附並顯示名稱；拖曳仍可平移，`復原一點`／Backspace 復原，`清除量測`清空，Esc 結束。各保護區各自保存量測點（僅存在頁面，重新整理即清除）。
  - 滑鼠移到動物上，提示框會多一行「距離我 X m」。
- 距離是**水平直線距離**（世界座標公分 ÷ 100），不含高低差，不等於實際步行路徑。方向只描述「畫面上」的方向，不宣稱正北。
- 純計算函式在 `web/measure.js`，由 `tests/test_measure.py` 以 node 測試（沒有 node 時自動略過）。
