"""Offline, source-attributed animal knowledge and life-stage annotation."""
import json, os, re
HERE=os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE,'species_data.json'),encoding='utf-8') as f:
    _DATA=json.load(f)
ANIMALS=_DATA['animals']

def norm(s): return re.sub(r'[^a-z0-9]','',str(s).lower())
BY_NAME={norm(x['name']):x for x in ANIMALS}
BY_LATIN={norm(x['latin']):x for x in ANIMALS}
ALIASES={
    'moose':'western-moose','rockymountainelk':'rocky-mountain-elk',
    'cougar':'north-american-cougar','wolverine':'eurasian-wolverine',
    'wildboar':'wild-boar','easternwildturkey':'merriams-wild-turkey',
    'eurasianlynx':'northern-lynx','alaskamoose':'alaska-moose','barrengroundcaribou':'barren-ground-caribou',
    'plainszebra':None, # not yet present in the published Toolbox index
}
BY_SLUG={x['slug']:x for x in ANIMALS}
ZH={'Young':'幼年','Adult':'成年','Mature':'成熟'}

def fitness_band(value):
    """Official Update 1.26.7 percentage bands, applied to a known value."""
    if value is None:
        return None
    v=float(value)
    if v < .20:return "very-low"
    if v < .40:return "low"
    if v < .60:return "moderate"
    if v < .80:return "high"
    return "very-high"

def lookup(latin=None,species=None):
    nl=norm(latin); ns=norm(species)
    # Exact/compatible scientific names are the strongest match. Prefix
    # matching handles saves that omit a published subspecies suffix.
    if nl:
        exact=BY_LATIN.get(nl)
        if exact:return exact,'verified-table'
    if ns in ALIASES:
        slug=ALIASES[ns]
        if slug:
            return BY_SLUG[slug],('proxy' if ns=='easternwildturkey' else 'verified-table')
    if ns in BY_NAME:return BY_NAME[ns],'verified-table'
    if nl:
        matches=[(len(k),v) for k,v in BY_LATIN.items() if nl.startswith(k) or k.startswith(nl)]
        if matches:return max(matches,key=lambda z:z[0])[1],'verified-table'
    return None,'unknown'

def _stage_for(info,sex,age):
    if age is None or sex not in ('M','F') or not info:return None
    stages=info.get('stages') or {}; order=[x for x in ('Young','Adult','Mature') if x in stages]
    if not order:return None
    ranges=[stages[x][sex].get('age') for x in order]
    if any(not r for r in ranges):return None
    # Published ranges can have fractional gaps (for example 1.4 to 2.4).
    # Use the midpoint only as the boundary between two published stages.
    bounds=[(ranges[i][1]+ranges[i+1][0])/2 for i in range(len(ranges)-1)]
    idx=0
    while idx<len(bounds) and age>bounds[idx]:idx+=1
    return order[min(idx,len(order)-1)]

def annotate(animal):
    info,confidence=lookup(animal.get('latin'),animal.get('species'))
    stage=_stage_for(info,animal.get('gender'),animal.get('age'))
    animal['age_stage']=stage
    animal['age_stage_zh']=ZH.get(stage,'')
    animal['age_label']=(f"{stage}／{ZH[stage]} ({int(animal['age'])} 年)" if stage else
                         (f"{int(animal['age'])} 年" if animal.get('age') is not None else ''))
    animal['knowledge_confidence']=confidence
    animal['fitness_band']=fitness_band(animal.get('fitness'))
    animal['knowledge_slug']=info['slug'] if info else None
    animal['stage_weight_range']=None
    # v3.0: published Mature upper age for this sex (not a guaranteed death age).
    animal['age_limit']=None; animal['years_to_limit']=None; animal['age_limit_status']=None
    if info and animal.get('gender') in ('M','F') and animal.get('age') is not None:
        mat=(info.get('stages') or {}).get('Mature',{}).get(animal['gender'],{}).get('age')
        if mat:
            animal['age_limit']=mat[1]
            left=mat[1]-float(animal['age'])
            animal['years_to_limit']=round(left,1)
            animal['age_limit_status']=('at-limit' if left<=0 else 'near-limit' if left<=1 else None)
    if info and stage and animal.get('gender') in ('M','F'):
        animal['stage_weight_range']=info['stages'][stage][animal['gender']].get('weight_text')
    return animal

def public_info_for(animals):
    out={}
    for a in animals:
        info,confidence=lookup(a.get('latin'),a.get('species'))
        if info and a['species'] not in out:
            out[a['species']]={**info,'confidence':confidence}
    return out

def catalog():
    """Complete offline field guide, independent of the loaded save."""
    return {
        "animals": ANIMALS,
        "reserves": _DATA.get("reserve_index", []),
        "source": _DATA.get("source"),
        "reserve_source": _DATA.get("reserve_source"),
    }

def activity_at(info, hour):
    """Return current activity window for a 0..23 game hour."""
    schedule=(info or {}).get("schedule") or []
    if not schedule:return None
    hour=float(hour)%24
    idx=max((i for i,e in enumerate(schedule) if e["time"]<=hour),default=len(schedule)-1)
    cur=schedule[idx];nxt=schedule[(idx+1)%len(schedule)]
    start=cur["time"] if cur["time"]<=hour else cur["time"]-24
    end=nxt["time"]
    if end<=start:end+=24
    if end<=hour:end+=24
    return {"activity":cur["activity"],"start":start%24,"end":end%24,
            "duration_until":round(end-hour,2),"next_activity":nxt["activity"]}

def next_activity(info, hour, activity):
    """Hours until the next start of a requested activity, including now."""
    schedule=(info or {}).get("schedule") or []
    if not schedule:return None
    hour=float(hour)%24
    cur=activity_at(info,hour)
    if cur and cur["activity"]==activity:return 0.0
    waits=[(e["time"]-hour)%24 for e in schedule if e["activity"]==activity]
    return min(waits) if waits else None
