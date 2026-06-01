"""
ui/dashboard.py — Streamlit Cloud production dashboard.

Changes for Streamlit Cloud deployment:
  • API_BASE_URL read from st.secrets (Streamlit Cloud secret manager)
    with fallback to environment variable or sidebar input.
  • API_SECRET_KEY read from st.secrets — never hardcoded.
  • Sidebar shows deployment info (environment, version).
  • All other functionality identical to v2 (single + batch + history tabs).
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import requests
import streamlit as st

st.set_page_config(
    page_title="AI Resume Matcher",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Read secrets from Streamlit Cloud secret manager or env vars ──────────────
def _get_secret(key: str, default: str = "") -> str:
    """Read from st.secrets first (Streamlit Cloud), then env var, then default."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, default)

_DEFAULT_API_URL = _get_secret("API_BASE_URL", "http://localhost:8000")
_DEFAULT_API_KEY = _get_secret("API_SECRET_KEY", "")

# ── CSS (identical to v2) ─────────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&family=DM+Serif+Display:ital@0;1&display=swap');
:root{--bg:#080b10;--surface:#0e1219;--card:#131820;--card2:#181f2c;--border:#1e2838;--border2:#263044;--g:#00e5a0;--g2:#00b87a;--b:#29b6ff;--amber:#fbbf24;--rose:#f87171;--violet:#a78bfa;--text:#dde4f0;--text2:#6b7fa0;--text3:#3d4f6b;--mono:'DM Mono',monospace;--sans:'DM Sans',sans-serif;--display:'DM Serif Display',serif;--r:10px;--r-sm:6px;}
html,body,[class*="css"]{font-family:var(--sans)!important;background-color:var(--bg)!important;color:var(--text)!important;}
.stApp{background:var(--bg)!important;}
.block-container{padding:2rem 2.5rem!important;max-width:1300px!important;}
section[data-testid="stSidebar"]{background:var(--surface)!important;border-right:1px solid var(--border)!important;}
.stTabs [data-baseweb="tab-list"]{background:var(--surface)!important;border-radius:var(--r)!important;padding:4px!important;gap:4px!important;border:1px solid var(--border)!important;}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:var(--text2)!important;border-radius:var(--r-sm)!important;font-weight:500!important;font-size:0.875rem!important;padding:0.5rem 1.25rem!important;}
.stTabs [aria-selected="true"]{background:var(--card2)!important;color:var(--text)!important;border:1px solid var(--border)!important;}
.stButton>button{background:linear-gradient(135deg,var(--g),var(--g2))!important;color:#000!important;border:none!important;border-radius:var(--r-sm)!important;font-weight:700!important;font-size:0.875rem!important;padding:0.6rem 1.75rem!important;box-shadow:0 2px 16px rgba(0,229,160,0.2)!important;transition:all 0.2s!important;}
.stButton>button:hover{transform:translateY(-1px)!important;box-shadow:0 4px 24px rgba(0,229,160,0.35)!important;}
.stTextInput>div>div>input,.stTextArea>div>div>textarea{background:var(--card2)!important;border:1px solid var(--border)!important;border-radius:var(--r-sm)!important;color:var(--text)!important;font-family:var(--mono)!important;font-size:0.83rem!important;}
.stFileUploader>div{background:var(--card2)!important;border:1px dashed var(--border2)!important;border-radius:var(--r)!important;}
.stRadio>div>label{background:var(--card2)!important;border:1px solid var(--border)!important;border-radius:var(--r-sm)!important;padding:0.35rem 0.9rem!important;transition:all 0.15s!important;}
.stRadio>div>label:has(input:checked){border-color:var(--g)!important;color:var(--g)!important;}
.streamlit-expanderHeader{background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:var(--r-sm)!important;color:var(--text2)!important;font-weight:500!important;}
.streamlit-expanderContent{background:var(--card2)!important;border:1px solid var(--border)!important;border-top:none!important;border-radius:0 0 var(--r-sm) var(--r-sm)!important;}
[data-testid="stMetric"]{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--r)!important;padding:1rem 1.25rem!important;}
[data-testid="stMetricLabel"]{color:var(--text2)!important;font-size:0.72rem!important;text-transform:uppercase!important;letter-spacing:0.08em!important;}
[data-testid="stMetricValue"]{color:var(--text)!important;font-size:1.6rem!important;font-weight:700!important;font-family:var(--mono)!important;}
.stProgress>div>div>div>div{background:linear-gradient(90deg,var(--g),var(--b))!important;border-radius:100px!important;}
.stProgress>div>div{background:var(--card2)!important;border-radius:100px!important;}
.stTextArea label,.stTextInput label,.stFileUploader label,.stRadio label{color:var(--text2)!important;font-size:0.8rem!important;font-weight:500!important;letter-spacing:0.02em!important;}
.rm-hero{padding:2rem 0 1.5rem;border-bottom:1px solid var(--border);margin-bottom:2rem;}
.rm-hero h1{font-family:var(--display)!important;font-size:clamp(1.8rem,4vw,2.8rem)!important;font-weight:400!important;color:var(--text)!important;letter-spacing:-0.02em!important;line-height:1.1!important;margin-bottom:0.4rem!important;}
.rm-hero .sub{color:var(--text2);font-size:0.9rem;line-height:1.65;max-width:520px;}
.rm-badge-row{display:flex;gap:8px;margin-top:0.9rem;flex-wrap:wrap;}
.rm-badge{display:inline-flex;align-items:center;gap:5px;background:var(--card2);border:1px solid var(--border);border-radius:100px;padding:3px 10px;font-family:var(--mono);font-size:0.68rem;color:var(--text2);}
.rm-new{background:rgba(0,229,160,0.1);border-color:rgba(0,229,160,0.3);color:var(--g)!important;}
.sec-label{font-size:0.68rem;font-weight:600;text-transform:uppercase;letter-spacing:0.12em;color:var(--text3);margin-bottom:0.65rem;}
.score-ring-wrap{text-align:center;padding:0.75rem 0;}
.score-ring{display:inline-flex;flex-direction:column;align-items:center;justify-content:center;width:140px;height:140px;border-radius:50%;position:relative;background:conic-gradient(var(--ring-color,#00e5a0) var(--ring-deg,0deg),#1e2838 var(--ring-deg,0deg));box-shadow:0 0 28px rgba(0,229,160,0.12),inset 0 0 0 10px var(--surface);margin:0 auto;}
.score-inner{position:absolute;width:108px;height:108px;border-radius:50%;background:var(--surface);display:flex;flex-direction:column;align-items:center;justify-content:center;}
.score-num{font-family:var(--mono);font-size:2rem;font-weight:700;line-height:1;color:var(--text);}
.score-denom{font-size:0.6rem;color:var(--text3);font-family:var(--mono);margin-top:1px;}
.score-tier{display:inline-block;margin-top:6px;padding:2px 10px;border-radius:100px;font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;}
.tier-elite{background:rgba(0,229,160,0.12);color:#00e5a0;border:1px solid rgba(0,229,160,0.25);}
.tier-strong{background:rgba(41,182,255,0.10);color:#29b6ff;border:1px solid rgba(41,182,255,0.22);}
.tier-fair{background:rgba(251,191,36,0.10);color:#fbbf24;border:1px solid rgba(251,191,36,0.22);}
.tier-weak{background:rgba(248,113,113,0.10);color:#f87171;border:1px solid rgba(248,113,113,0.22);}
.bar-row{display:flex;align-items:center;gap:8px;margin-bottom:8px;}
.bar-lbl{font-size:0.75rem;color:var(--text2);width:120px;flex-shrink:0;}
.bar-track{flex:1;height:7px;background:var(--card2);border-radius:100px;overflow:hidden;border:1px solid var(--border);}
.bar-fill{height:100%;border-radius:100px;background:linear-gradient(90deg,var(--fs),var(--fe));}
.bar-val{font-family:var(--mono);font-size:0.75rem;color:var(--text);width:38px;text-align:right;}
.analysis-box{background:var(--card2);border:1px solid var(--border);border-left:2px solid var(--g);border-radius:var(--r-sm);padding:1rem 1.25rem;font-size:0.84rem;line-height:1.8;color:var(--text2);white-space:pre-wrap;font-family:var(--sans);}
.lb-header{display:grid;grid-template-columns:36px 1fr 70px 70px 70px 80px;gap:8px;padding:7px 14px;font-family:var(--mono);font-size:0.68rem;color:var(--text3);text-transform:uppercase;letter-spacing:0.1em;border-bottom:1px solid var(--border2);background:var(--card);}
.lb-row{display:grid;grid-template-columns:36px 1fr 70px 70px 70px 80px;gap:8px;padding:10px 14px;border-bottom:1px solid var(--border);align-items:center;transition:background 0.15s;}
.lb-row:hover{background:rgba(255,255,255,0.015);}
.lb-row:last-child{border-bottom:none;}
.lb-rank{font-family:var(--mono);font-size:1rem;font-weight:800;color:var(--text3);text-align:center;}
.lb-rank.r1{color:#ffd700;}.lb-rank.r2{color:#c0c0c0;}.lb-rank.r3{color:#cd7f32;}
.lb-name{font-family:var(--mono);font-size:0.8rem;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.lb-score{font-family:var(--mono);font-size:0.85rem;font-weight:700;text-align:right;}
.lb-badge{display:inline-block;padding:2px 8px;border-radius:100px;font-family:var(--mono);font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;text-align:center;}
.warn-box{background:rgba(251,191,36,0.07);border:1px solid rgba(251,191,36,0.25);border-radius:var(--r-sm);padding:0.55rem 0.85rem;font-size:0.78rem;color:#fbbf24;margin-top:6px;}
.hist-header{display:grid;grid-template-columns:1fr 150px 60px 60px 70px;gap:8px;padding:7px 12px;font-family:var(--mono);font-size:0.67rem;color:var(--text3);text-transform:uppercase;letter-spacing:0.1em;border-bottom:1px solid var(--border2);background:var(--card);}
.hist-row{display:grid;grid-template-columns:1fr 150px 60px 60px 70px;gap:8px;padding:9px 12px;border-bottom:1px solid var(--border);font-size:0.8rem;align-items:center;transition:background 0.15s;}
.hist-row:hover{background:rgba(255,255,255,0.015);}
.hist-row:last-child{border-bottom:none;}
.hist-file{font-family:var(--mono);font-size:0.78rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.hist-ts{font-family:var(--mono);font-size:0.7rem;color:var(--text2);}
.hist-score{font-family:var(--mono);font-weight:700;text-align:right;}
.loading-msg{text-align:center;padding:3.5rem 1rem;color:var(--text2);font-size:0.88rem;}
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:100px;}
#MainMenu,footer,header[data-testid="stHeader"]{display:none!important;}
</style>
"""

def _score_color(s: float) -> str:
    if s >= 75: return "#00e5a0"
    if s >= 55: return "#29b6ff"
    if s >= 35: return "#fbbf24"
    return "#f87171"

def _tier(s: float) -> tuple[str, str]:
    if s >= 75: return "Elite Match", "tier-elite"
    if s >= 55: return "Strong Match", "tier-strong"
    if s >= 35: return "Fair Match", "tier-fair"
    return "Weak Match", "tier-weak"

def _lb_badge(s: float) -> str:
    _, css = _tier(s)
    label, _ = _tier(s)
    return f'<span class="lb-badge {css}">{label}</span>'

def _bar(label: str, value: float, c1: str, c2: str) -> str:
    pct = min(100.0, max(0.0, value))
    return (f'<div class="bar-row"><span class="bar-lbl">{label}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%;--fs:{c1};--fe:{c2};"></div></div>'
            f'<span class="bar-val">{pct:.1f}</span></div>')

def _score_ring_html(score: float) -> str:
    color = _score_color(score)
    deg = score / 100 * 360
    tier_label, tier_css = _tier(score)
    return (f'<div class="score-ring-wrap"><div class="score-ring" style="--ring-color:{color};--ring-deg:{deg:.1f}deg;">'
            f'<div class="score-inner"><span class="score-num">{score:.0f}</span><span class="score-denom">/ 100</span></div></div>'
            f'<div><span class="score-tier {tier_css}">{tier_label}</span></div></div>')

def _render_single_result(result: dict) -> None:
    final = float(result.get("final_score", 0))
    vector = float(result.get("vector_score", 0))
    llm = float(result.get("llm_score", 0))
    analysis = result.get("analysis", "")
    warnings = result.get("warnings", [])
    filename = result.get("resume_filename", "resume")
    n_idx = result.get("chunks_indexed", 0)
    n_ret = result.get("chunks_retrieved", 0)

    st.markdown('<div class="sec-label">Match Results</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:0.77rem;color:var(--text2);margin-bottom:1.25rem;">File: <span style="font-family:var(--mono);color:var(--text)">{filename}</span> &nbsp;·&nbsp; <span style="color:var(--text3)">{n_idx} chunks indexed · {n_ret} retrieved</span></div>', unsafe_allow_html=True)

    col_badge, col_bars = st.columns([1, 2], gap="large")
    with col_badge:
        st.markdown(_score_ring_html(final), unsafe_allow_html=True)
    with col_bars:
        st.markdown('<div style="margin-top:1rem;"><div class="sec-label">Score Breakdown</div>', unsafe_allow_html=True)
        st.markdown(_bar("Vector (RAG)", vector, "#29b6ff", "#818cf8"), unsafe_allow_html=True)
        st.markdown(_bar("LLM Evaluation", llm, "#00e5a0", "#34d399"), unsafe_allow_html=True)
        st.markdown(_bar("Final Score", final, "#00e5a0", "#29b6ff"), unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:0.7rem;color:var(--text3);font-family:var(--mono);margin-top:8px;">Final = {vector:.1f}×0.35 + {llm:.1f}×0.65 = <b style="color:var(--text)">{final:.1f}</b></div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("📋 Full Recruiter Analysis", expanded=True):
        st.markdown(f'<div class="analysis-box">{analysis}</div>', unsafe_allow_html=True)
    for w in warnings:
        st.markdown(f'<div class="warn-box">⚠️ {w}</div>', unsafe_allow_html=True)

def _render_batch_leaderboard(results: list[dict], job_snippet: str) -> None:
    st.markdown('<div class="sec-label">Ranked Results</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:0.77rem;color:var(--text2);margin-bottom:1rem;">JD: <span style="font-family:var(--mono);color:var(--text)">"{job_snippet[:100]}{"…" if len(job_snippet)>100 else ""}"</span></div>', unsafe_allow_html=True)

    successful = [r for r in results if r.get("rank") is not None]
    if successful:
        scores = [float(r.get("final_score", 0)) for r in successful]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ranked", len(successful))
        c2.metric("Top Score", f"{max(scores):.1f}")
        c3.metric("Average", f"{sum(scores)/len(scores):.1f}")
        c4.metric("Elite (≥75)", sum(1 for s in scores if s >= 75))

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden;"><div class="lb-header"><span>#</span><span>Resume</span><span style="text-align:right">Vec</span><span style="text-align:right">LLM</span><span style="text-align:right">Final</span><span style="text-align:center">Tier</span></div>', unsafe_allow_html=True)

    for r in results:
        rank = r.get("rank")
        filename = r.get("resume_filename", "—")
        if r.get("error"):
            st.markdown(f'<div class="lb-row"><span class="lb-rank" style="color:var(--text3)">—</span><span class="lb-name" style="color:var(--text2)">{filename}</span><span style="color:#f87171;font-size:0.75rem;grid-column:3/7">{r["error"]}</span></div>', unsafe_allow_html=True)
            continue
        final = float(r.get("final_score", 0))
        color = _score_color(final)
        rank_css = f"r{rank}" if rank and rank <= 3 else ""
        st.markdown(f'<div class="lb-row"><span class="lb-rank {rank_css}">{rank}</span><span class="lb-name">{filename}</span><span class="lb-score" style="color:var(--text2)">{float(r.get("vector_score",0)):.1f}</span><span class="lb-score" style="color:var(--text2)">{float(r.get("llm_score",0)):.1f}</span><span class="lb-score" style="color:{color}">{final:.1f}</span><span style="text-align:center">{_lb_badge(final)}</span></div>', unsafe_allow_html=True)
    st.markdown("</div><br>", unsafe_allow_html=True)

    st.markdown('<div class="sec-label">Individual Analyses</div>', unsafe_allow_html=True)
    for r in results:
        if r.get("error"): continue
        rank = r.get("rank","?")
        filename = r.get("resume_filename","resume")
        final = float(r.get("final_score",0))
        tier_lbl, _ = _tier(final)
        with st.expander(f"#{rank} — {filename}  ({final:.1f}/100 · {tier_lbl})", expanded=False):
            col_l, col_r = st.columns([1,2], gap="large")
            with col_l:
                st.markdown(_score_ring_html(final), unsafe_allow_html=True)
            with col_r:
                st.markdown('<div class="sec-label">Score Breakdown</div>', unsafe_allow_html=True)
                st.markdown(_bar("Vector (RAG)", float(r.get("vector_score",0)), "#29b6ff","#818cf8"), unsafe_allow_html=True)
                st.markdown(_bar("LLM Evaluation", float(r.get("llm_score",0)), "#00e5a0","#34d399"), unsafe_allow_html=True)
                st.markdown(_bar("Final Score", final, "#00e5a0","#29b6ff"), unsafe_allow_html=True)
            analysis = r.get("analysis","")
            if analysis:
                st.markdown(f'<div class="analysis-box" style="margin-top:12px;">{analysis}</div>', unsafe_allow_html=True)

def _render_history(api_url: str, api_key: str) -> None:
    st.markdown('<div class="sec-label">Recent Runs</div>', unsafe_allow_html=True)
   #if st.button("🔄 Refresh", key="refresh_hist"):
        #st.cache_data.clear()
    col1, col2 = st.columns([1,1])

    with col1:
        if st.button("🔄 Refresh", key="refresh_hist"):
            st.cache_data.clear()

    with col2:
        if st.button("🗑 Delete History", key="delete_history"):

            try:
                resp = requests.delete(
                    f"{api_url.rstrip('/')}/api/v1/history",
                    headers={"X-API-KEY": api_key},
                    timeout=10,
                )

                if resp.status_code == 200:
                    st.success("History deleted successfully.")
                    st.rerun()

                else:
                    st.error("Failed to delete history.")

            except Exception as exc:
                st.error(f"Error: {exc}")
    
    try:
        resp = requests.get(f"{api_url.rstrip('/')}/api/v1/history", headers={"X-API-KEY": api_key}, params={"limit": 50}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API server.")
        return
    except Exception as exc:
        st.error(f"Error: {exc}")
        return

    records = data.get("records", [])
    if not records:
        st.markdown('<div class="loading-msg">No history yet.</div>', unsafe_allow_html=True)
        return

    st.markdown('<div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden;"><div class="hist-header"><span>Resume</span><span>Timestamp</span><span style="text-align:right">Vec</span><span style="text-align:right">LLM</span><span style="text-align:right">Final</span></div>', unsafe_allow_html=True)
    for row in records:
        final = float(row.get("final_score", 0))
        color = _score_color(final)
        st.markdown(f'<div class="hist-row"><span class="hist-file">{row.get("resume_filename","—")}</span><span class="hist-ts">{row.get("timestamp_utc","—")}</span><span class="hist-score" style="color:var(--text2)">{float(row.get("vector_similarity_score",0)):.1f}</span><span class="hist-score" style="color:var(--text2)">{float(row.get("llm_analysis_score",0)):.1f}</span><span class="hist-score" style="color:{color}">{final:.1f}</span></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def _jd_input_widget(key_prefix: str) -> tuple[str, Optional[Any]]:
    st.markdown('<div class="sec-label">Job Description</div>', unsafe_allow_html=True)
    mode = st.radio("JD mode", ["Paste text","Upload file"], horizontal=True, label_visibility="collapsed", key=f"{key_prefix}_jd_mode")
    jd_text, jd_file = "", None
    if mode == "Paste text":
        jd_text = st.text_area("Paste JD", height=220, placeholder="Paste the full job description here…", label_visibility="collapsed", key=f"{key_prefix}_jd_text")
    else:
        jd_file = st.file_uploader("Upload JD", type=["pdf","docx","txt"], label_visibility="collapsed", key=f"{key_prefix}_jd_file")
        if jd_file:
            st.markdown(f'<div style="font-size:0.75rem;color:var(--g);margin-top:3px;">✓ {jd_file.name}</div>', unsafe_allow_html=True)
    return jd_text, jd_file

def main() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown('<div class="rm-hero"><h1>AI Resume Matcher <em style="color:var(--g);font-style:normal;font-size:0.6em;vertical-align:middle;">v2</em></h1><p class="sub">True RAG pipeline — chunks indexed, retrieved, then evaluated by Gemini. Batch-match up to 20 resumes.</p><div class="rm-badge-row"><span class="rm-badge rm-new">✦ True RAG</span><span class="rm-badge rm-new">✦ Batch Matching</span><span class="rm-badge rm-new">✦ MLflow Tracked</span><span class="rm-badge">Qdrant Cloud</span><span class="rm-badge">Gemini 2.5 Flash</span></div></div>', unsafe_allow_html=True)

    with st.sidebar:
        st.markdown('<div class="sec-label" style="padding:1rem 0 0.5rem;">Connection</div>', unsafe_allow_html=True)
        api_url = "http://127.0.0.1:8000"
        st.text_input("API Base URL", value=api_url, key="api_url_display", disabled=True)
        api_key = st.text_input("X-API-KEY", value=_DEFAULT_API_KEY, type="password", key="api_key_input")
        st.markdown("---")
        st.markdown('<div style="font-size:0.7rem;color:var(--text2);line-height:1.9;"><b style="color:var(--text)">Deployed on:</b><br>Streamlit Cloud<br><br><b style="color:var(--text)">Backend:</b><br>Render / AWS EC2<br><br><b style="color:var(--text)">Vector DB:</b><br>Qdrant Cloud<br><br><b style="color:var(--text)">Tracking:</b><br>MLflow</div>', unsafe_allow_html=True)

    tab_single, tab_batch, tab_history = st.tabs(["🎯  Single Match","📦  Batch Match","📊  History"])

    with tab_single:
        col_in, col_out = st.columns([1,1], gap="large")
        with col_in:
            st.markdown('<div class="sec-label">Resume Upload</div>', unsafe_allow_html=True)
            resume_file = st.file_uploader("Upload resume", type=["pdf","docx","txt"], label_visibility="collapsed", key="single_resume")
            if resume_file:
                st.markdown(f'<div style="font-size:0.75rem;color:var(--g);margin-top:3px;">✓ {resume_file.name}</div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            jd_text, jd_file = _jd_input_widget("single")
            st.markdown("<br>", unsafe_allow_html=True)
            run_btn = st.button("⚡ Analyse Match", use_container_width=True, key="single_run")

        with col_out:
            result_ph = st.empty()
            if "single_result" in st.session_state:
                with result_ph.container():
                    _render_single_result(st.session_state["single_result"])
            else:
                result_ph.markdown('<div class="loading-msg" style="margin-top:3rem;"><div style="font-size:2rem;opacity:0.25;margin-bottom:0.5rem;">🎯</div>Upload a resume and job description,<br>then click <em>Analyse Match</em>.</div>', unsafe_allow_html=True)

        if run_btn:
            errors = []
            if not resume_file: errors.append("Please upload a resume file.")
            if not jd_text.strip() and not jd_file: errors.append("Please provide a job description.")
            if not api_key.strip(): errors.append("Enter your API key in the sidebar.")
            if errors:
                for e in errors: st.error(e)
            else:
                with result_ph.container():
                    st.markdown('<div class="loading-msg"><div style="font-size:1.4rem;margin-bottom:6px;">⚙️</div>Running RAG pipeline…<br><small style="color:var(--text3)">Chunking → Indexing → Retrieving → Gemini</small></div>', unsafe_allow_html=True)
                files = {"resume_file": (resume_file.name, resume_file.read(), resume_file.type or "application/octet-stream")}
                data = {}
                if jd_text.strip():
                    data["job_description_text"] = jd_text
                elif jd_file:
                    files["job_description_file"] = (jd_file.name, jd_file.read(), jd_file.type or "application/octet-stream")
                try:
                    t0 = time.time()

                    resp = requests.post(
                        f"{api_url.rstrip('/')}/api/v1/match",
                        headers={"X-API-KEY": api_key},
                        files=files,
                        data=data,
                        timeout=120
                    )

                    elapsed = time.time() - t0

                    #st.write("STATUS:", resp.status_code)
                    #st.write("RAW RESPONSE:")
                    #st.code(resp.text[:2000])

                    if resp.status_code == 200:

                        try:
                            result = resp.json()
                        except Exception as e:
                            st.error(f"JSON Parse Error: {e}")
                            st.stop()

                        st.session_state["single_result"] = result

                        with result_ph.container():
                            _render_single_result(result)

                    else:
                        try:
                            error_detail = resp.json().get("detail", "Request failed.")
                        except Exception:
                            error_detail = "Request failed."

                        st.error(error_detail)
                    #else:
                     #   st.error(f"API Error {resp.status_code}")
                      #  st.code(resp.text)

                except Exception as exc:
                    st.error(f"Error: {exc}")
    with tab_batch:
        st.markdown('<div style="background:rgba(0,229,160,0.05);border:1px solid rgba(0,229,160,0.15);border-radius:8px;padding:12px 16px;margin-bottom:1.5rem;font-size:0.82rem;color:var(--text2);">✦ <b style="color:var(--g)">Batch Mode</b> — Upload up to 20 resumes. Set the job description <b>once</b>. Get a ranked leaderboard.</div>', unsafe_allow_html=True)
        col_bin, col_bout = st.columns([1,1], gap="large")
        with col_bin:
            st.markdown('<div class="sec-label">Resume Files (up to 20)</div>', unsafe_allow_html=True)
            batch_files = st.file_uploader("Upload resumes", type=["pdf","docx","txt"], accept_multiple_files=True, label_visibility="collapsed", key="batch_resumes")
            if batch_files:
                st.markdown(f'<div style="font-size:0.75rem;color:var(--g);margin-top:3px;">✓ {len(batch_files)} file(s)</div>', unsafe_allow_html=True)
                for f in batch_files:
                    st.markdown(f'<div style="font-size:0.72rem;color:var(--text2);font-family:var(--mono);">  · {f.name}</div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            batch_jd_text, batch_jd_file = _jd_input_widget("batch")
            st.markdown("<br>", unsafe_allow_html=True)
            batch_run_btn = st.button("⚡ Match All Resumes", use_container_width=True, key="batch_run")

        with col_bout:
            batch_ph = st.empty()
            if "batch_result" in st.session_state:
                bdata = st.session_state["batch_result"]
                with batch_ph.container():
                    _render_batch_leaderboard(bdata.get("results",[]), bdata.get("job_description_snippet",""))
            else:
                batch_ph.markdown('<div class="loading-msg" style="margin-top:3rem;"><div style="font-size:2rem;opacity:0.25;margin-bottom:0.5rem;">📦</div>Upload multiple resumes and one job description,<br>then click <em>Match All Resumes</em>.</div>', unsafe_allow_html=True)

        if batch_run_btn:
            berrors = []
            if not batch_files: berrors.append("Upload at least one resume.")
            if len(batch_files or []) > 20: berrors.append("Maximum 20 resumes.")
            if not batch_jd_text.strip() and not batch_jd_file: berrors.append("Provide a job description.")
            if not api_key.strip(): berrors.append("Enter your API key in the sidebar.")
            if berrors:
                for e in berrors: st.error(e)
            else:
                n = len(batch_files)
                with batch_ph.container():
                    st.markdown(f'<div class="loading-msg"><div style="font-size:1.4rem;margin-bottom:6px;">⚙️</div>Processing {n} resume{"s" if n!=1 else ""}…<br><small style="color:var(--text3)">~{n*15}–{n*25}s estimated</small></div>', unsafe_allow_html=True)
                mfiles = [("resume_files",(f.name,f.read(),f.type or "application/octet-stream")) for f in batch_files]
                bdata_form = {}
                if batch_jd_text.strip():
                    bdata_form["job_description_text"] = batch_jd_text
                elif batch_jd_file:
                    mfiles.append(("job_description_file",(batch_jd_file.name,batch_jd_file.read(),batch_jd_file.type or "application/octet-stream")))
                try:
                    t0 = time.time()
                    resp = requests.post(f"{api_url.rstrip('/')}/api/v1/match/batch", headers={"X-API-KEY": api_key}, files=mfiles, data=bdata_form, timeout=300)
                    elapsed = time.time() - t0
                    if resp.status_code == 200:
                        bdata = resp.json()
                        st.session_state["batch_result"] = bdata
                        with batch_ph.container():
                            _render_batch_leaderboard(bdata.get("results",[]), bdata.get("job_description_snippet",""))
                            st.markdown(f'<div style="font-size:0.7rem;color:var(--text3);text-align:right;margin-top:6px;">⏱ {elapsed:.1f}s · {bdata.get("successful",0)} ok · {bdata.get("failed",0)} failed</div>', unsafe_allow_html=True)
                    else:
                        with batch_ph.container(): st.error(f"API {resp.status_code}: {resp.json().get('detail', resp.text)}")
                except Exception as exc:
                    with batch_ph.container(): st.error(f"Error: {exc}")

    with tab_history:
        if not api_key.strip():
            st.warning("Enter your API key in the sidebar to load history.")
        else:
            _render_history(api_url=api_url, api_key=api_key)

if __name__ == "__main__":
    main()
