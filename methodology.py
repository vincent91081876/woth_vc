"""Machine-readable provenance and interpretation boundaries for v4 metrics."""

SOURCES = [
    {"title": "End of the year Q&A", "publisher": "Nine Rocks Games",
     "url": "https://ninerocksgames.com/posts/end-of-the-year-q-and-a",
     "supports": ["age cadence", "habitat management", "spawn probability"]},
    {"title": "Update 1.26.7: Strategic Habitat Management & Herd Fitness",
     "publisher": "Nine Rocks Games",
     "url": "https://ninerocksgames.com/posts/update-1-26-7-strategic-habitat-management-and-herd-fitness",
     "supports": ["fitness bands", "habitat quality", "year-over-year effect"]},
    {"title": "Update 1.31: Free DLC Map and Cougar", "publisher": "Nine Rocks Games",
     "url": "https://ninerocksgames.com/posts/update-1-31-free-dlc-map-and-cougar",
     "supports": ["Elkcrest", "cougar", "recovery year turn", "rare compensation"]},
    {"title": "Patch for Update 1.31", "publisher": "Nine Rocks Games",
     "url": "https://ninerocksgames.com/posts/patch-for-the-update-1-31",
     "supports": ["herd genetics bug fix"]},
    {"title": "codeaid/woth-toolbox", "publisher": "codeaid",
     "url": "https://github.com/codeaid/woth-toolbox",
     "supports": ["need zones", "territories", "area labels"], "license": "GPL-3.0"},
]

METRICS = [
    {"key": "fitness", "label": "Fitness", "class": "saved",
     "definition": "WOTH Database 存檔中的公獸 Fitness；雌獸不顯示。",
     "limits": "不是目前 Trophy score、體重或星級。"},
    {"key": "age_stage", "label": "生命階段", "class": "derived",
     "definition": "原始 age 對照公開物種與性別年齡表。",
     "limits": "proxy 或未知資料會明確標示。"},
    {"key": "habitat", "label": "近似棲地", "class": "approximation",
     "definition": "獸群世界座標最近的 Toolbox 區域標籤。",
     "limits": "不是遊戲內部 habitat polygon 或 Fitness Potential。"},
    {"key": "territory_match", "label": "Territory 對應", "class": "approximation",
     "definition": "同物種最近 territory；300 m 內 high、1500 m 內 medium。",
     "limits": "需要以真實存檔的對應率與中位距離驗證。"},
    {"key": "year_turn", "label": "年度更替", "class": "heuristic",
     "definition": "相鄰狀態中至少 50% 持續個體 age 增加。",
     "limits": "不是直接讀取遊戲年份欄位。"},
    {"key": "removed", "label": "消失", "class": "observed-delta",
     "definition": "動物 ID 在相鄰狀態間不再存在。",
     "limits": "可能是獵殺、自然死亡或年度更替。"},
    {"key": "spawned", "label": "新出現", "class": "observed-delta",
     "definition": "動物 ID 首次出現在後一狀態。",
     "limits": "若快照缺漏，首次看見不必然等於剛生成。"},
    {"key": "route", "label": "遠征路線", "class": "planning-aid",
     "definition": "世界座標的最近鄰路線，再以 2-opt 縮短。",
     "limits": "不含道路、地形、風向、土地權限、壓力與動物移動。"},
]


def report():
    return {"version": 1, "principle": "saved > derived > approximation > heuristic",
            "metrics": METRICS, "sources": SOURCES,
            "never_infer": ["individual trophy score", "individual precise weight",
                            "individual star rating", "female fitness", "cause of disappearance",
                            "future spawn RNG"]}