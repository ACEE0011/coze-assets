#!/usr/bin/env python3
"""
Signal Discovery Agent - Standalone Version
Extracted from NVIDIA Quantitative Signal Discovery Agent blueprint
3-Agent loop: Signal Generator -> Code Generator -> Evaluator
Uses One API + NIM free keys, no NAT framework dependency

Usage:
  python3 signal_discovery.py "momentum signals"
  python3 signal_discovery.py "volatility signals"
  python3 signal_discovery.py --download
  python3 signal_discovery.py --test
"""

import json, re, sys, os, logging, warnings, traceback, inspect, asyncio
from datetime import datetime
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from scipy import stats
import requests

# ===== Config =====
ONE_API_URL = os.environ.get("ONE_API_URL", "http://localhost:3000/v1/chat/completions")
ONE_API_KEY = os.environ.get("ONE_API_KEY", "")

SIGNAL_MODEL = os.environ.get("SIGNAL_MODEL", "deepseek-ai/deepseek-v4-flash")
CODE_MODEL = os.environ.get("CODE_MODEL", "deepseek-ai/deepseek-v4-flash")
ADVISOR_MODEL = os.environ.get("ADVISOR_MODEL", "glm-4-flash")

IC_THRESHOLD = 0.02
P_VALUE_THRESHOLD = 0.05
MAX_ITERATIONS = 3
NUM_SIGNALS = 2
FORWARD_PERIODS = 5

REPO_DIR = Path(os.environ.get("REPO_DIR", "/home/coze/quantitative-signal-discovery-agent"))
TEMPLATE_DIR = Path(os.environ.get("TEMPLATE_DIR", str(REPO_DIR / "src" / "signal_discovery_workflow" / "template")))
DATA_DIR = Path(os.environ.get("DATA_DIR", str(REPO_DIR / "src" / "signal_discovery_workflow" / "data" / "sp500")))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/home/coze/mine_output/signals"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ===== LLM Call =====
def call_llm(model, messages, temperature=0.5, max_tokens=4000):
    headers = {"Authorization": f"Bearer {ONE_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}
    try:
        resp = requests.post(ONE_API_URL, headers=headers, json=payload, stream=True, timeout=300)
        resp.raise_for_status()
        parts = []
        for line in resp.iter_lines():
            if not line: continue
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data = line[6:]
                if data.strip() == "[DONE]": break
                try:
                    chunk = json.loads(data)
                    choices = chunk.get("choices", [])
                    if not choices: continue
                    text = choices[0].get("delta", {}).get("content", "")
                    if text: parts.append(text)
                except json.JSONDecodeError: continue
        return "".join(parts)
    except Exception as e:
        logger.error(f"LLM call failed model={model}: {e}")
        return ""

# ===== Template Loading =====
VALID_DATA_FIELDS = {"Open", "Close", "High", "Low", "Volume"}
PRIORITY_PREFIXES = ["TS_", "Rank", "Add", "Sub", "Mul", "Div", "Decay", "EMA", "CS_"]
OPERATOR_SYNONYMS = {
    "divide":"Div","div":"Div","multiply":"Mul","mul":"Mul","times":"Mul",
    "add":"Add","plus":"Add","sum":"Add","subtract":"Sub","sub":"Sub","minus":"Sub",
    "rank":"Rank","ranking":"Rank","abs":"Abs","absolute":"Abs","sign":"Sign",
    "log":"Log","ln":"Log","sqrt":"Sqrt","power":"Power","pow":"Power",
    "max":"Max","maximum":"Max","min":"Min","minimum":"Min","inv":"Inv","inverse":"Inv",
}

def load_calculator_operators():
    p = TEMPLATE_DIR / "calculator.json"
    if not p.exists():
        logger.error(f"calculator.json missing: {p}")
        return []
    with open(p) as f: return json.load(f)

def load_output_template():
    p = TEMPLATE_DIR / "signal_output_template.json"
    if not p.exists(): return {}
    with open(p) as f: return json.load(f)

def get_operator_code_map(operators): return {op["name"]: op["code"] for op in operators}

def get_operator_arities():
    operators = load_calculator_operators()
    ns = {"pd": pd, "np": np}
    arities = {}
    for op in operators:
        try: exec(op["code"], ns)
        except: continue
    for name, obj in ns.items():
        if not callable(obj) or name in ("pd","np"): continue
        try:
            sig = inspect.signature(obj)
            required = sum(1 for p in sig.parameters.values() if p.default is inspect.Parameter.empty and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD))
            has_va = any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values())
            max_a = -1 if has_va else len([p for p in sig.parameters.values() if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)])
            arities[name] = (required, max_a)
        except: continue
    return arities

# ===== Text Utils =====
def sanitize_unicode(text):
    return text.translate(str.maketrans({
        "\u2018":"'","\u2019":"'","\u201c":'"',"\u201d":'"',
        "\u2013":"-","\u2014":"-","\u2026":"...","\u00a0":" ",
    }))

def normalize_operator_names(code, valid_operators):
    valid_set = set(valid_operators)
    canonical = {op.lower(): op for op in valid_set}
    def repl(m):
        name, suffix = m.group(1), m.group(2)
        if name in valid_set: return name+suffix
        lo = name.lower()
        if lo in canonical: return canonical[lo]+suffix
        if lo in OPERATOR_SYNONYMS and OPERATOR_SYNONYMS[lo] in valid_set: return OPERATOR_SYNONYMS[lo]+suffix
        return name+suffix
    return re.sub(r"\b([A-Za-z_]\w*)(\s*\()", repl, code)

def extract_json_array(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    for fence in re.findall(r"```(?:json|JSON)?\s*([\[\{].*?[\]\}])\s*```", text, re.DOTALL):
        try:
            d = json.loads(fence); return d if isinstance(d,list) else [d]
        except: continue
    m = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(0))
        except: pass
    objs = []
    for t in _iter_braces(text):
        if '"formula"' not in t: continue
        try:
            o = json.loads(t)
            if isinstance(o,dict): objs.append(o)
        except: continue
    return objs

def _iter_braces(text):
    i,n = 0,len(text)
    while i<n:
        if text[i]!="{": i+=1; continue
        depth=in_s=esc=0
        for j in range(i,n):
            c=text[j]
            if esc: esc=False; continue
            if c=="\\": esc=True; continue
            if c=='"': in_s=not in_s; continue
            if in_s: continue
            if c=="{": depth+=1
            elif c=="}":
                depth-=1
                if depth==0: yield text[i:j+1]; i=j+1; break
        else: return

def extract_python_block(text):
    blocks = re.findall(r"```python\n(.*?)```", text, re.DOTALL)
    return blocks[0] if blocks else text

# ===== Prompt Building =====
def format_operators_for_prompt(operators, max_ops=30):
    pri,oth = [],[]
    for op in operators:
        if any(op["name"].startswith(p) or op["name"]==p for p in PRIORITY_PREFIXES): pri.append(op)
        else: oth.append(op)
    sel = pri[:max_ops]
    if len(sel)<max_ops: sel.extend(oth[:max_ops-len(sel)])
    lines=[]
    for op in sel:
        sig = op.get("signature",op["name"])
        if sig.startswith("def "): sig=sig[4:]
        lines.append(f"- {sig}")
        lines.append(f"  Description: {op['meanings']}")
    return "\n".join(lines)

def build_signal_template(n, template):
    st = template.get("signal_template")
    if not st: return "[]"
    item = json.dumps(st, indent=2)
    items = ",\n".join([item]*n)
    return f"```json\n[\n{items}\n]\n```"

def build_signal_prompt(request, num_signals, ops_list, template_block, feedback=None):
    fb = f"\n\nPREVIOUS FEEDBACK:\n{feedback}\n" if feedback else ""
    return f"""You are a senior quantitative researcher. Generate {num_signals} stock selection signals.

REQUEST: {request}
{fb}
DATA: Open, Close, High, Low, Volume

OPERATORS:
{ops_list}

STRICT RULES:
- Every operator call MUST match its signature exactly — same number of arguments, same order.
- Do NOT invent operators or pass extra arguments to single-arg operators.
- Use only the exact operator names shown above (case-sensitive).

Fill in this exact template at the END of your reply (inside a ```json block):

{template_block}

Generate {num_signals} signals now."""

# ===== Signal Spec Parsing =====
DATA_FIELD_ALIASES = {
    "adj_close":"Close","adjclose":"Close","adjusted_close":"Close","close_price":"Close",
    "closing_price":"Close","price":"Close","open_price":"Open","opening_price":"Open",
    "high_price":"High","low_price":"Low","trading_volume":"Volume","volume_traded":"Volume",
}

def _pyfn_name(name, idx):
    base = re.sub(r"[^A-Za-z0-9_]+","_",(name or f"signal_{idx+1}").lower()).strip("_")
    if not base: base=f"signal_{idx+1}"
    if not base.startswith("signal"): base=f"signal_{base}"
    if base[0].isdigit(): base=f"signal_{base}"
    return base

def _infer_fields(formula): return [f for f in ("Open","Close","High","Low","Volume") if re.search(rf"\b{f}\b",formula)]

def _norm_fields(text):
    can = {f.lower():f for f in VALID_DATA_FIELDS}
    def r(m):
        lo=m.group(0).lower()
        return can.get(lo) or DATA_FIELD_ALIASES.get(lo) or m.group(0)
    return re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b",r,text)

def _norm_declared(fields):
    r=[]
    for f in fields:
        if not isinstance(f,str): continue
        c=_norm_fields(f).strip()
        if c in VALID_DATA_FIELDS and c not in r: r.append(c)
    return r

def _check_arity(formula, arities):
    import ast
    try: tree=ast.parse(formula,mode="eval")
    except: return None
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Name): continue
        name=node.func.id
        if name not in arities: continue
        mn,mx=arities[name]; na=len(node.args)
        if na<mn or (mx>=0 and na>mx):
            exp=str(mn) if mn==mx else f"{mn}-{mx}" if mx>=0 else f"at least {mn}"
            return f"{name} expects {exp} arg(s), got {na}"
    return None

def parse_signal_specs(signal_json, valid_operators):
    import ast
    san = sanitize_unicode(signal_json)
    try: data=json.loads(san)
    except: data=extract_json_array(san)
    if not isinstance(data,list): data=[data] if isinstance(data,dict) else []
    if not data: return [],["no valid JSON"]
    template=load_output_template()
    req=template.get("validation_rules",{}).get("required_fields",["name","formula","meaning"])
    arities=get_operator_arities()
    specs,skipped=[],[]
    for idx,sg in enumerate(data):
        if not isinstance(sg,dict): skipped.append(f"#{idx} not dict"); continue
        missing=[f for f in req if not sg.get(f)]
        if missing: skipped.append(f"#{idx} ({sg.get('name','?')}: missing {missing})"); continue
        formula=normalize_operator_names(sanitize_unicode(sg["formula"]).strip(),valid_operators)
        formula=_norm_fields(formula)
        ae=_check_arity(formula,arities)
        if ae: skipped.append(f"#{idx} ({sg.get('name','?')}: {ae})"); continue
        ff=_infer_fields(formula); df=_norm_declared(sg.get("data_fields_used") or [])
        fields=[]
        for f in [*ff,*df]:
            if f not in fields: fields.append(f)
        if not fields: fields=["Close"]
        specs.append({"name":_pyfn_name(sg.get("name"),idx),"formula":formula,"fields":fields,"doc":sg.get("meaning") or sg.get("name","Signal")})
    if skipped: logger.warning(f"Skipped {len(skipped)} signals: {skipped}")
    return specs,skipped

def collect_operator_code(specs, code_map):
    used=set()
    for s in specs: used.update(re.findall(r"\b([A-Za-z_]\w*)\s*\(",s["formula"]))
    valid=sorted(op for op in used if op in code_map)
    return "\n".join(code_map[op] for op in valid)

# ===== Agent 1: Signal Generator =====
async def generate_signal_json(request, num_signals, operators, feedback=None):
    template=load_output_template()
    prompt=build_signal_prompt(request,num_signals,format_operators_for_prompt(operators),build_signal_template(num_signals,template),feedback)
    msgs=[{"role":"system","content":"detailed thinking off"},{"role":"user","content":prompt}]
    logger.info(f"Signal Agent: generating (model={SIGNAL_MODEL})")
    content=call_llm(SIGNAL_MODEL,msgs,temperature=0.8,max_tokens=4000)
    if not content.strip(): logger.warning("Signal Agent returned empty")
    return content

# ===== Agent 2: Code Generator =====
async def generate_signal_code(signal_json, operators, errors_out=None):
    code_map=get_operator_code_map(operators)
    specs,pe=parse_signal_specs(signal_json,code_map.keys())
    if errors_out is not None: errors_out.extend(pe)
    if not specs: return "import pandas as pd\nimport numpy as np\n\n# No valid signals\n"

    sig_map={op["name"]:op.get("signature",op["name"]) for op in operators}
    used_ops=sorted({op for s in specs for op in re.findall(r"\b([A-Za-z_]\w*)\s*\(",s["formula"]) if op in sig_map})
    op_sigs="\n".join(f"- {sig_map[op]}" for op in used_ops)
    spec_block="\n".join(f"{i+1}. name={s['name']}, fields={s['fields']}, formula={s['formula']}" for i,s in enumerate(specs))

    sys_msg="You translate signal specifications into Python functions. Output ONLY the function definitions in a single ```python block. Use the exact operator names from the formula verbatim (case-sensitive). Do NOT redefine operators. Do NOT add helper functions. Do NOT add imports."
    user_msg=f"""Operator signatures (already defined, just call):
{op_sigs}

Generate one function per spec below. The function body must be `return <formula>`.

EXAMPLE INPUT:
1. name=signal_momentum, fields=['Close'], formula=TS_Return(Close, 20)

EXAMPLE OUTPUT:
```python
def signal_momentum(Close: pd.DataFrame) -> pd.DataFrame:
    \"\"\"20-day momentum\"\"\"
    return TS_Return(Close, 20)
```

SPECS:
{spec_block}"""

    msgs=[{"role":"system","content":"detailed thinking off"},{"role":"system","content":sys_msg},{"role":"user","content":user_msg}]
    logger.info(f"Code Agent: generating (model={CODE_MODEL})")
    raw=call_llm(CODE_MODEL,msgs,temperature=0.0,max_tokens=3000)
    code=extract_python_block(raw)
    fn_code=normalize_operator_names(sanitize_unicode(code),{op["name"] for op in operators})
    op_code=collect_operator_code(specs,code_map)
    return f"import pandas as pd\nimport numpy as np\n\n{op_code}\n\n{fn_code}\n"

# ===== Agent 3: Evaluator =====
STANDARD_FIELDS=["Close","Volume","High","Low","Open"]
OPERATOR_NAMES=set()

def _load_op_names():
    ops=load_calculator_operators()
    ns={"pd":pd,"np":np}
    for op in ops:
        try: exec(op["code"],ns)
        except: pass
    global OPERATOR_NAMES
    OPERATOR_NAMES={n for n,o in ns.items() if callable(o) and n not in ("pd","np")}

def load_stock_data():
    data={}
    for f in ["Open","Close","High","Low","Volume"]:
        fp=DATA_DIR/f"{f}.csv"
        if fp.exists():
            try:
                df=pd.read_csv(fp,index_col=0,parse_dates=True)
                data[f]=df
                logger.info(f"Loaded {f}.csv shape={df.shape}")
            except Exception as e: logger.warning(f"Failed {f}.csv: {e}")
        else: logger.warning(f"Missing: {fp}")
    return data

def compute_forward_returns(close,periods=5): return close.shift(-periods)/close-1

def compute_rank_ic(sv,fr):
    cd=sv.index.intersection(fr.index); cs=sv.columns.intersection(fr.columns)
    if len(cd)==0 or len(cs)==0: return {"mean_ic":None,"error":"No common dates/stocks"}
    sa=sv.loc[cd,cs]; ra=fr.loc[cd,cs]
    with np.errstate(invalid="ignore",divide="ignore"),warnings.catch_warnings():
        warnings.filterwarnings("ignore",category=RuntimeWarning)
        ics=[]
        for d in cd:
            sr=sa.loc[d].dropna(); rr=ra.loc[d].dropna()
            cm=sr.index.intersection(rr.index)
            if len(cm)<10: continue
            s_v=sr[cm].values; r_v=rr[cm].values
            if np.std(s_v)<1e-10 or np.std(r_v)<1e-10: continue
            try:
                c,_=stats.spearmanr(s_v,r_v)
                if not np.isnan(c): ics.append(c)
            except: continue
        if not ics: return {"mean_ic":None,"error":"No IC computed"}
        ia=np.array(ics); mi=float(np.mean(ia)); isd=float(np.std(ia)); np_=len(ics)
        ir=mi/isd if isd>0 else None
        ts=mi/(isd/np.sqrt(np_)) if isd>0 else None
        pv=float(2*(1-stats.t.cdf(abs(ts),df=np_-1))) if ts is not None else None
        return {"mean_ic":mi,"ic_std":isd,"ic_ir":ir,"t_stat":ts,"p_value":pv,"num_periods":np_,"positive_ic_ratio":float(np.mean(ia>0))}

def _is_df_param(p):
    a=p.annotation
    if a is pd.DataFrame: return True
    if isinstance(a,str) and "DataFrame" in a: return True
    if a is inspect.Parameter.empty: return p.default is inspect.Parameter.empty or isinstance(p.default,(type(None),pd.DataFrame))
    return False

def _resolve_args(sig,sd):
    avail=[f for f in STANDARD_FIELDS if f in sd]
    dfp=[n for n,p in sig.parameters.items() if _is_df_param(p)]
    kw={}; used=set(); unmatched=[]
    for p in dfp:
        pl=p.lower(); m=None
        for f in avail:
            fl=f.lower()
            if pl==fl or fl in pl or pl in fl: m=f; break
        if m and m not in used: kw[p]=sd[m]; used.add(m)
        else: unmatched.append(p)
    fb=[f for f in avail if f not in used]
    for p in unmatched:
        if not fb: break
        kw[p]=sd[fb.pop(0)]
    return kw

def extract_code(resp):
    bs=re.findall(r"```python\n(.*?)```",resp,re.DOTALL)
    if bs: return "\n".join(bs)
    bs=re.findall(r"```\n(.*?)```",resp,re.DOTALL)
    if bs: return "\n".join(bs)
    return resp

def execute_signal_code(code,stock_data,sel_periods=5):
    SU=str.maketrans({"‘":"'","’":"'","“":"\"","”":"\"","–":"-","—":"-"," ":" "})
    ns={}
    try:
        exec(code.translate(SU),ns)
        cands=[(n,o) for n,o in ns.items() if not n.startswith("_") and callable(o) and hasattr(o,"__code__") and n not in OPERATOR_NAMES]
        if not cands: logger.warning("No signal functions found"); return None
        names={n for n,_ in cands}; helpers=set()
        for _,fn in cands:
            try: src=inspect.getsource(fn)
            except: continue
            for n in names:
                if n!=fn.__name__ and re.search(rf"\b{re.escape(n)}\s*\(",src): helpers.add(n)
        sfs=[(n,f) for n,f in cands if n not in helpers] or cands
        logger.info(f"Found {len(sfs)} signal(s): {[f[0] for f in sfs]}")
        br,bi,bn=None,None,None
        with np.errstate(invalid="ignore",divide="ignore"),warnings.catch_warnings():
            warnings.filterwarnings("ignore",category=RuntimeWarning)
            for fn,sf in sfs:
                try:
                    sig=inspect.signature(sf); kw=_resolve_args(sig,stock_data)
                    dpc=sum(1 for p in sig.parameters.values() if _is_df_param(p))
                    if len(kw)==dpc: result=sf(**kw)
                    elif len(sig.parameters)==0: result=sf()
                    else: continue
                    if isinstance(result,pd.Series): result=result.to_frame()
                    if not isinstance(result,pd.DataFrame): continue
                    fwr=stock_data["Close"].shift(-sel_periods)/stock_data["Close"]-1
                    vd=result.dropna(how="all").index; sics=[]
                    for d in vd:
                        if d not in fwr.index: continue
                        fr=result.loc[d].dropna(); rr=fwr.loc[d].dropna()
                        cm=fr.index.intersection(rr.index)
                        if len(cm)<10: continue
                        fv=fr[cm].values; rv=rr[cm].values
                        if np.std(fv)<1e-10 or np.std(rv)<1e-10: continue
                        try:
                            c,_=stats.spearmanr(fv,rv)
                            if not np.isnan(c): sics.append(c)
                        except: pass
                    if sics:
                        mic=abs(np.mean(sics))
                        logger.info(f"  {fn}: |IC|={mic:.4f}")
                        if bi is None or mic>bi: bi=mic; br=result; bn=fn
                    elif br is None: br=result; bn=fn
                except Exception as e: logger.warning(f"Error {fn}: {e}"); continue
        if br is not None:
            logger.info(f"Best signal: {bn} |IC|={bi:.4f}" if bi else f"Best signal: {bn}")
            return br,bn
        return None
    except SyntaxError as e: logger.error(f"SyntaxError: {e}"); return None
    except Exception as e: logger.error(f"Exec error: {e}"); return None

def evaluate_ic(signal_code,stock_data,fp=5):
    if not stock_data: return {"error":"No stock data","mean_ic":None}
    cc=extract_code(signal_code)
    er=execute_signal_code(cc,stock_data,sel_periods=fp)
    if er is None: return {"error":"Code execution failed","mean_ic":None}
    sv,sel=er
    close=stock_data.get("Close")
    if close is None: return {"error":"No Close data","mean_ic":None}
    with np.errstate(invalid="ignore",divide="ignore"),warnings.catch_warnings():
        warnings.filterwarnings("ignore",category=RuntimeWarning)
        fwr=compute_forward_returns(close,periods=fp)
        ic=compute_rank_ic(sv,fwr)
    ic["selected_signal"]=sel
    return ic

# ===== Advisor Agent =====
async def generate_feedback(signal_json,ic_results,iteration):
    mi=ic_results.get("mean_ic"); pv=ic_results.get("p_value")
    mis=f"{mi:.4f}" if mi is not None else "N/A"
    pvs=f"{pv:.4f}" if pv is not None else "N/A"
    err=ic_results.get("error",""); el=f"- Error: {err}\n" if err else ""
    prompt=f"""Iteration {iteration}:
- Mean IC: {mis} (target >= {IC_THRESHOLD})
- P-value: {pvs} (target <= {P_VALUE_THRESHOLD})
{el}
SIGNALS TRIED:
{signal_json[:2000]}

Output exactly 3 bullet points, max 15 words each, suggesting concrete changes.
No prose, no preamble. Format:
- <change 1>
- <change 2>
- <change 3>"""
    msgs=[{"role":"system","content":"detailed thinking off"},{"role":"system","content":"You are a senior quant providing concise signal optimization advice."},{"role":"user","content":prompt}]
    logger.info(f"Advisor Agent: feedback (model={ADVISOR_MODEL})")
    fb=call_llm(ADVISOR_MODEL,msgs,temperature=0.5,max_tokens=2000)
    return fb[:500].strip()

# ===== Main Loop =====
def _compose_fb(advice,best_result,best_ic):
    if not best_result or best_ic is None: return advice
    try:
        bs=extract_json_array(best_result["signal_json"])
        items=bs if bs else [json.loads(best_result["signal_json"])]
        summ="\n".join(f"- {f.get('name','?')}: {f.get('formula','?')}" for f in items if isinstance(f,dict))
    except: summ="(parse failed)"
    return f"BEST SO FAR (iter {best_result.get('iteration','?')}, |IC|={abs(best_ic):.4f}):\n{summ}\n\nADVICE:\n{advice}\n\nTry to BEAT the best |IC| above."

def save_result(signal_json,signal_code,ic_results,iteration,request):
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
    ts=datetime.now().strftime("%Y%m%d_%H%M%S")
    fp=OUTPUT_DIR/f"signal_{ts}_iter{iteration}.json"
    metrics={k:v for k,v in ic_results.items() if k!="selected_signal"}
    payload={"timestamp":ts,"request":request,"iteration":iteration,"selected_signal":ic_results.get("selected_signal"),"signal_description":signal_json[:5000],"signal_code":signal_code,"metrics":metrics}
    with open(fp,"w") as f: json.dump(payload,f,indent=2,default=str)
    logger.info(f"Saved to {fp}")
    return str(fp)

async def run_signal_discovery(request):
    _load_op_names()
    operators=load_calculator_operators()
    if not operators: return json.dumps({"status":"failed","error":"calculator.json missing"})
    stock_data=load_stock_data()
    if not stock_data: return json.dumps({"status":"failed","error":"No stock data. Run --download first."})

    best_result=None; best_ic=None; feedback=None
    for iteration in range(1,MAX_ITERATIONS+1):
        logger.info(f"=== Iteration {iteration}/{MAX_ITERATIONS} ===")
        signal_json=await generate_signal_json(request,NUM_SIGNALS,operators,feedback)
        codegen_errors=[]
        signal_code=await generate_signal_code(signal_json,operators,errors_out=codegen_errors)
        ic_results=evaluate_ic(signal_code,stock_data,FORWARD_PERIODS)
        mean_ic=ic_results.get("mean_ic")
        if ic_results.get("error"): logger.warning(f"Eval error: {ic_results['error']}")
        if mean_ic is not None:
            logger.info(f"Mean IC: {mean_ic:.4f}, p-value: {ic_results.get('p_value','N/A')}")
            if best_ic is None or abs(mean_ic)>abs(best_ic):
                best_ic=mean_ic
                best_result={"signal_json":signal_json,"signal_code":signal_code,"ic_results":ic_results,"iteration":iteration}
        if mean_ic is not None and abs(mean_ic)>=IC_THRESHOLD:
            pv=ic_results.get("p_value")
            if pv is None or pv<=P_VALUE_THRESHOLD:
                logger.info("Signal ACCEPTED!")
                sp=save_result(signal_json,signal_code,ic_results,iteration,request)
                return json.dumps({"status":"accepted","request":request,"iteration":iteration,"mean_ic":mean_ic,"p_value":pv,"selected_signal":ic_results.get("selected_signal"),"saved_path":sp},indent=2,default=str)
        if codegen_errors and mean_ic is None:
            advice="Signals ALL REJECTED: "+" ; ".join(codegen_errors)
        else:
            advice=await generate_feedback(signal_json,ic_results,iteration)
        feedback=_compose_fb(advice,best_result,best_ic)
    if best_result:
        sp=save_result(best_result["signal_json"],best_result["signal_code"],best_result["ic_results"],best_result["iteration"],request)
        return json.dumps({"status":"best_effort","request":request,"iteration":best_result["iteration"],"mean_ic":best_ic,"selected_signal":best_result["ic_results"].get("selected_signal"),"saved_path":sp},indent=2,default=str)
    return json.dumps({"status":"failed","request":request,"error":"No valid signals"},indent=2)

# ===== Data Download =====
def download_sp500_data(start="2012-01-01",end="2025-12-31"):
    import yfinance as yf
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    tickers=['AAPL','MSFT','AMZN','GOOGL','GOOG','META','NVDA','TSLA','BRK-B','UNH',
        'JPM','V','JNJ','WMT','XOM','MA','PG','HD','CVX','MRK','ABBV','PEP','KO','AVGO','COST',
        'CSCO','MCD','ADBE','NKE','CRM','WFC','LIN','AMD','AMGN','TMO','INTC','ORCL','QCOM','TXN','UPS',
        'RTX','LLY','SBUX','AMT','COP','SPGI','IBM','GS','CAT','BLK','ISRG','DE','AXP','SYK','LRCX',
        'SCHW','MDLZ','ADI','BKNG','PGR','MMC','CB','PLD','ELV','CME','NOW','CI','MO','TJX','EOG',
        'REGN','DUK','SO','SLB','PNC','VRTX','NOC','BSX','HCA','EQIX','SHW','MSI','CL','FDX','ECL',
        'APD','TGT','ITW','ICE','PFE','AIG','MET','PYPL','FIS','CCI']
    logger.info(f"Downloading {len(tickers)} S&P500 stocks {start}~{end}...")
    raw=yf.download(tickers,start=start,end=end,group_by="column",auto_adjust=True)
    for field in ["Open","Close","High","Low","Volume"]:
        if field in raw.columns.get_level_values(0):
            df=raw[field].copy(); df.index.name="Date"; df=df.dropna(axis=1,how="all")
            df.to_csv(DATA_DIR/f"{field}.csv")
            logger.info(f"Saved {field}.csv shape={df.shape}")

if __name__=="__main__":
    if len(sys.argv)<2:
        print("Usage: python3 signal_discovery.py <signal_request>")
        print("  python3 signal_discovery.py 'momentum signals'")
        print("  python3 signal_discovery.py --download")
        print("  python3 signal_discovery.py --test")
        sys.exit(1)
    if sys.argv[1]=="--download":
        download_sp500_data()
    elif sys.argv[1]=="--test":
        print(f"Testing One API: {ONE_API_URL}")
        r=call_llm("glm-4-flash",[{"role":"user","content":"Say OK"}],temperature=0,max_tokens=10)
        print(f"Response: {r}")
        print("OK" if r.strip() else "FAILED")
    else:
        request=" ".join(sys.argv[1:])
        print(f"Signal Discovery: {request}")
        result=asyncio.run(run_signal_discovery(request))
        print(result)
