// 名詞解釋：離線靜態內容，不需載入存檔。用語與各分頁、methodology.py 保持一致。
const GLOSSARY_CATS=['動物數值','地圖與座標','玩家位置','存檔與快照','分析與管理','日誌與觀測','資料可信度'];
const GLOSSARY=[
// ---- 動物數值
{c:0,t:'Fitness（基因潛力）',en:'Fitness',d:'存檔中「公獸」的基因潛力，範圍 0–100%，於動物生成時決定。母獸在存檔裡固定為 0，所以不顯示。',n:'不是目前的 Trophy 分數、體重或星級；本工具不會由它反推這些數值。',w:'動物清單、Fitness 策略'},
{c:0,t:'Fitness 五段區間',en:'Fitness bands',d:'官方公開的五段：極低 0–19.99%、低 20–39.99%、中等 40–59.99%、高 60–79.99%、極高 80–100%。介面用顏色標籤表示。',w:'Fitness 策略'},
{c:0,t:'高／低潛力門檻',d:'管理建議與 Fitness 策略共用的兩個可調數字，預設高 90%、低 50%。高於高門檻算「高潛力」，低於低門檻算「低潛力觀察」。',n:'50% 是社群常用的參考值，不是官方規則。',w:'管理建議'},
{c:0,t:'同種百分位（評等）',d:'某公獸的 Fitness 在同一物種所有已知公獸中的排名，例如「同種前 0.5%」。',n:'只是排名，不等於 Trophy 星級。',w:'動物清單'},
{c:0,t:'年齡（age）',d:'遊戲內部的年齡數值，單位未公開，數字越大越老；每個遊戲年度增加。',w:'動物清單'},
{c:0,t:'生命階段',en:'Young／Adult／Mature',d:'幼年、成年、成熟。由原始 age 依「物種＋性別」對照公開年齡表換算。',n:'Eastern Wild Turkey 暫借用 Merriam\'s Wild Turkey 的年齡表，會標示為 proxy。',w:'總覽、動物清單'},
{c:0,t:'年齡上限提醒',en:'at-limit／near-limit',d:'依公開 Mature 年齡範圍的上限：已達上限標「已達公開上限」，距離上限一年內標「1 年內」。',n:'這是公開的階段上限，不是死亡倒數。',w:'棲地實驗室'},
{c:0,t:'Tier（等級）',d:'物種的分級（Toolbox 公開資料），用於百科比較，不代表個體品質。',w:'全地圖百科'},
{c:0,t:'稀有變種',en:'Albino／Melanistic',d:'白化、黑化等稀有外觀個體。「稀有」統計就是這些個體的數量。',w:'總覽、觀察佇列'},
{c:0,t:'Trophy（獎盃）',d:'遊戲對獵物的評價，會受 Fitness、年齡等多項因素影響。本工具只顯示公開的五段分數範圍。',n:'存檔沒有個體 Trophy 分數，所以「分數」「體重」欄位是空的。',w:'全地圖百科'},
{c:0,t:'獸群',en:'Herd／Animal group',d:'一起活動的同種動物群。每群有 ID、中心座標和成員；動物的「獸群 ID」指向它所屬的群。',w:'獸群'},
{c:0,t:'動物 ID',d:'存檔中每隻動物的唯一編號。Live、快照比較與日誌都靠 ID 判斷「新出現」或「消失」。',w:'動物清單'},
{c:0,t:'建議命中能量',d:'公開資料建議獵殺該物種所需的命中能量，用於選武器的參考。',w:'全地圖百科'},
// ---- 地圖與座標
{c:1,t:'保護區',en:'Reserve',d:'遊戲中的七張地圖：Nez Perce Valley、Transylvania、Aurora Shores、Tikamoon Plains、Matariki Park、Lintukoto Reserve、Elkcrest Island。存檔一次只有目前載入的那一張。',w:'保護區中心'},
{c:1,t:'世界座標（X／Y／Z）',d:'Unreal 引擎的位置，單位為公分。100,000 = 1 公里；X 向右、Y 向下（地圖上），Z 是高度。',n:'不是經緯度。每張地圖有各自的範圍，不可互換。',w:'地圖'},
{c:1,t:'Y 軸反轉',d:'地圖分頁的選項。Nez Perce Valley 已驗證不需反轉；其他地圖若發現南北顛倒，可勾選檢查。',w:'地圖'},
{c:1,t:'Territory（領域）',d:'動物獸群固定活動的範圍中心。工具把每個獸群對應到同物種最近的 territory。',w:'地圖、獸群'},
{c:1,t:'需求區',en:'Need zone：Drink／Feed／Sleep',d:'動物依時段前往的地點：Drink 飲水、Feed 覓食、Sleep 休息。地圖可依規劃時間顯示。',n:'同一獸群會在不同需求區輪替，位置不是固定座標。Elkcrest Island 沒有開放資料。',w:'地圖、狩獵規劃'},
{c:1,t:'活動作息與下一飲水',d:'每種動物 24 小時內的 Drink／Feed／Sleep 時段（離線資料）。「下一飲水」是從所選遊戲時間起算，距離下一次飲水的小時數。',w:'狩獵規劃'},
{c:1,t:'近似棲地',en:'Habitat（approx.）',d:'以獸群座標最近的公開區域標籤推定的棲地類型，如 Swamps、Mountains。',n:'不是遊戲內部的棲地多邊形，也不是官方 Hunting Map 的 Fitness Potential。',w:'棲地實驗室'},
{c:1,t:'Primary／Secondary／Private habitat',d:'官方棲地管理的三種棲地。管理效果作用於「同物種、同棲地」，且要等完整遊戲年度後才會看見。本工具無法判斷你的棲地屬於哪一種。',w:'Fitness 策略'},
{c:1,t:'Territory 對應率／中位距離',d:'健康檢查用來判斷底圖校準是否可靠：有多少獸群找得到同物種 territory，以及獸群到它的中位距離。距離 ≤300 m 為 high、≤1500 m 為 medium，超過不對應。',w:'歷史與健康'},
// ---- 玩家位置
{c:2,t:'玩家位置（存檔）',d:'存檔最後一次寫入的玩家世界座標，地圖上以「你在這裡（存檔）」顯示。',n:'是「最後存檔」的位置，不是遊戲執行中的即時 GPS；要再存檔一次才會更新。目前只在 Nez Perce Valley 驗證。',w:'地圖'},
{c:2,t:'exact',d:'座標通過結構檢查、唯一命中且落在目前地圖範圍內，才會標 exact，並可作為遠征路線起點。',w:'地圖、遠征路線'},
{c:2,t:'candidate',d:'欄位名稱像玩家位置，但座標不在地圖範圍內或未經驗證。只在診斷區顯示，不畫到地圖。',w:'檔案資訊'},
{c:2,t:'手動地圖釘',en:'manual',d:'你在地圖上自己點的「我的位置」。只存在瀏覽器（localStorage），不寫入存檔或伺服器。',w:'地圖'},
{c:2,t:'unavailable',d:'找不到通過驗證的玩家座標時的狀態。工具不會拿地圖中心或不明數字冒充你的位置。',w:'地圖'},
{c:2,t:'載具座標（vehicle）',d:'存檔中另一組位置，玩家走動時不會變，推測是停放的載具或固定物件。只出現在診斷資料，不會畫成「你在這裡」。',w:'檔案資訊'},
// ---- 存檔與快照
{c:3,t:'SaveData.sav',d:'遊戲主存檔，位於 %LOCALAPPDATA%\\WayOfTheHunter\\Saved\\SaveGames\\。本工具永遠以唯讀方式開啟。',w:'檔案資訊'},
{c:3,t:'BackupData.sav',d:'同資料夾中的另一份存檔，內容是上一次的存檔狀態（推測為遊戲自動備份）。可用來比較，但一般請看 SaveData.sav。',w:'快照比較'},
{c:3,t:'GVAS／Database 存檔',d:'GVAS 是 Unreal 通用存檔格式；WOTH 的 SaveData.sav 外層是 GVAS，內部含遊戲自訂的二進位資料庫（動物、獸群、名稱表等）。',w:'存檔結構'},
{c:3,t:'Oodle 壓縮',d:'WOTH 存檔使用 Oodle 壓縮，所以需要 pyooz（run_windows.bat 會自動安裝）才能解壓縮。',w:'檔案資訊'},
{c:3,t:'快照',en:'Snapshot',d:'每次讀取存檔，工具會把它複製到自己的 snapshots/ 資料夾，供比較、歷史和日誌使用。相同內容只保留一份，每個來源預設最多 100 份。',w:'快照比較'},
{c:3,t:'SHA-1',d:'存檔內容的指紋。內容相同就一樣，用來去重；即使檔案大小、時間沒變，SHA-1 改變就視為新狀態。',w:'檔案資訊'},
{c:3,t:'Live 模式',d:'每隔數秒檢查存檔是否更新，有變化就自動重讀：新出現標綠、消失標紅，並移動「你在這裡」。',w:'即時事件'},
{c:3,t:'Reserve Vault（保護區中心）',d:'掃描目前存檔與工具自己的快照，為七個保護區各保留「最後一次看見」的狀態，方便跨地圖比較。',n:'未掃描的地圖顯示「未掃描」，不是 0 隻。',w:'保護區中心'},
{c:3,t:'最後看見（last-known）',d:'非目前檔案的資料都是舊快照，只代表當時狀態，不代表現在。',w:'保護區中心'},
{c:3,t:'WOTH2（.nrgs）',d:'Way of the Hunter 2 的存檔。格式未公開，本工具只偵測檔案，不解析。',w:'檔案資訊'},
// ---- 分析與管理
{c:4,t:'觀察平均',d:'目前存檔中「已知公獸」Fitness 的算術平均（依物種或物種×近似棲地）。',n:'不是官方的棲地 Fitness Potential。',w:'Fitness 策略、棲地實驗室'},
{c:4,t:'低於平均個體',d:'Fitness 低於該物種／棲地觀察平均的公獸；官方建議跨多個獸群、以成熟低星個體為管理方向。',w:'棲地實驗室'},
{c:4,t:'觀察佇列',d:'把公獸分成五類：稀有關注、低潛力觀察、成熟高潛力、成長保護、持續觀察。',n:'只是觀察候選，不是必須獵殺的清單，也不保證 caller 能吸引到指定個體。',w:'Fitness 策略'},
{c:4,t:'成長保護',d:'高潛力但還是 Young／Adult 的公獸，建議先讓牠長大。',w:'Fitness 策略'},
{c:4,t:'成熟高潛力',d:'高潛力且已 Mature 的公獸，是值得優先觀察的對象。',w:'Fitness 策略'},
{c:4,t:'管理試算',d:'假設移除一批低於平均的成熟公獸，重算觀察平均會怎麼變。只做算術平均，不模擬遊戲亂數。',n:'不預測下一年生成結果。',w:'棲地實驗室'},
{c:4,t:'Caller（誘獵器）',d:'遊戲中的叫聲／誘引機制。社群把它當作辨識低 Fitness 個體的參考（常以 50% 為分界），但不保證每次都有回應。',w:'Fitness 策略'},
{c:4,t:'遠征路線',d:'依你選的條件挑出候選，用「最近鄰」排序再以 2-opt 縮短的直線路線；顯示每段與累積距離，最多 50 站。',n:'不含道路、地形、風向、土地權限、狩獵壓力與動物移動。',w:'遠征路線'},
// ---- 日誌與觀測
{c:5,t:'狩獵日誌',en:'Journal',d:'工具自己保存的紀錄，記下相鄰兩份存檔之間的新出現、消失、年齡增加與年度更替。',w:'狩獵日誌'},
{c:5,t:'消失／新出現',en:'removed／spawned',d:'某動物 ID 在後一份存檔不見（消失），或首次出現（新出現）。',n:'消失可能是獵殺、自然死亡、年度更替，遊戲也可能重新生成動物（例如鴨、雉雞、狼）；工具不判斷原因。',w:'即時事件、狩獵日誌'},
{c:5,t:'年度更替',en:'Year turn',d:'相鄰兩份存檔中，至少 50% 持續存在的個體年齡增加，就判定中間經過一個遊戲年度。',n:'這是推測，不是讀取遊戲的年份欄位。',w:'狩獵日誌、族群觀測站'},
{c:5,t:'族群觀測站',en:'Population Observatory',d:'把同一來源的所有去重快照按時間串起來，得到年度、棲地成效卡、趨勢與個體 cohort。',w:'族群觀測站'},
{c:5,t:'成效卡信心',en:'snapshot-only／one-year／multi-year',d:'只有單一快照、跨越一個年度、或跨越多個年度。愈往右證據愈可靠。',w:'族群觀測站'},
{c:5,t:'Cohort Ledger',d:'依動物 ID 列出首次／最後看見、觀察次數、年齡增加、換群與 present（仍在）／gone（不見）。',n:'gone 不等於被獵殺。',w:'族群觀測站'},
{c:5,t:'健康檢查',d:'檢查解析警告、重複 ID、未知物種、找不到獸群、無效座標、超出地圖範圍，以及族群大幅變動（總數 ±20%、單一物種 ±30% 只顯示「注意」）。',w:'歷史與健康'},
// ---- 資料可信度
{c:6,t:'指標分類',en:'saved／derived／approximation／heuristic／observed-delta／planning-aid',d:'saved 存檔原值；derived 由存檔值對照公開表換算；approximation 近似值；heuristic 啟發式推測；observed-delta 兩次觀察之間的差異；planning-aid 規劃輔助。可信度大致由左至右遞減。',w:'族群觀測站（方法論）'},
{c:6,t:'資料信心',en:'verified-table／proxy／unknown',d:'物種知識的可信程度：verified-table 有公開對照表；proxy 借用相近物種的資料；unknown 沒有資料。',w:'動物清單'},
{c:6,t:'唯讀保證',d:'工具只以 rb 開啟遊戲存檔，不修改、不還原、不刪除；快照、日誌、手動地圖釘都存在工具自己的資料夾或瀏覽器。',w:'全部'},
];
let glossCat=-1;
function renderGlossary(){
 const q=($('#glossq')?.value||'').trim().toLowerCase();
 $('#glosscats').innerHTML=['全部',...GLOSSARY_CATS].map((n,i)=>`<button data-gc="${i-1}" class="${glossCat===i-1?'on':''}">${esc(n)}</button>`).join('');
 $$('#glosscats [data-gc]').forEach(b=>b.onclick=()=>{glossCat=+b.dataset.gc;renderGlossary()});
 const rows=GLOSSARY.filter(g=>(glossCat<0||g.c===glossCat)&&(!q||`${g.t} ${g.en||''} ${g.d} ${g.n||''} ${g.w||''}`.toLowerCase().includes(q)));
 $('#glosscount').textContent=`${rows.length} / ${GLOSSARY.length} 條`;
 let html='',last=-1;
 for(const g of rows){
  if(g.c!==last){last=g.c;html+=`<h3 class="glosshead">${esc(GLOSSARY_CATS[g.c])}</h3>`}
  html+=`<div class="card gloss"><b>${esc(g.t)}</b>${g.en?` <span class="mut">${esc(g.en)}</span>`:''}<div>${esc(g.d)}</div>${g.n?`<div class="warn">⚠ ${esc(g.n)}</div>`:''}${g.w?`<div class="mut">出現位置：${esc(g.w)}</div>`:''}</div>`;
 }
 $('#glosslist').innerHTML=html||'<div class="mut">沒有符合的名詞。</div>';
}
$('#glossq').addEventListener('input',renderGlossary);
