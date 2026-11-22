import json
import os
import re
from collections import Counter
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import streamlit as st

from agents import Budget, CloudModel, Controller, History, MISSING, PARSE_VERSION, TaskError
from formulas import index_formulas, inspect_page, page_count


st.set_page_config(page_title="論文方法工作台", layout="wide")
st.title("論文方法工作台")
history = History(os.getenv("PAPER_DATA_DIR", "data"))
state = st.session_state
ollama = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")


@st.cache_data(ttl=15, max_entries=4, show_spinner=False)
def installed_models(endpoint):
    try:
        with urlopen(f"{endpoint}/api/tags", timeout=2) as response:
            payload = json.load(response)
    except (URLError, OSError, ValueError):
        return None
    return [model["name"] for model in payload.get("models", [])
            if isinstance(model.get("name"), str)
            and not model["name"].endswith(("-cloud", ":cloud"))
            and not model.get("remote_host")]


with st.sidebar:
    st.header("Ollama")
    if st.button("重新檢查連線"):
        installed_models.clear()
    models = installed_models(ollama)
    if models is None:
        st.warning("連不到 Ollama。請開啟 Ollama，再重新檢查。")
    elif not models:
        st.info("尚未安裝本機模型。可在 PowerShell 執行下方指令。")
        st.code("ollama pull qwen3:4b", language="powershell")
    model = st.selectbox("本機模型", sorted(models or [], key=lambda name: (name != "qwen3:4b", name)),
                         placeholder="等候本機模型")
    st.caption("PDF 和歷史紀錄保存在這份專案中。")

controller = (Controller(CloudModel(model=model, key="ollama", endpoint=ollama, ollama=True))
              if model else None)


def evidence(claim):
    st.write(claim["text"])
    st.caption(f'PDF 第 {claim["page"]} 頁 · {claim["section"]} · 距頁頂 {claim["top"]} pt')
    st.text(claim["quote"])


def finish(paper, budget):
    history.save_trace(paper, budget)
    state["trace"] = budget.trace


def report_markdown(name, steps):
    lines = [f"# {name}", ""]
    for index, step in enumerate(steps, 1):
        lines.extend((f"## 步驟 {index}", ""))
        for label, claim in step.items():
            lines.extend((f"### {label.title()}", ""))
            if claim:
                lines.extend((claim["text"], "",
                              f'> {claim["quote"]}', "",
                              f'出處：PDF 第 {claim["page"]} 頁 · {claim["section"]}', ""))
            else:
                lines.extend((MISSING, ""))
    return "\n".join(lines)


@st.cache_data(max_entries=32, show_spinner=False)
def cached_formula_page(raw, page, region=None, *, render=False):
    return inspect_page(raw, page, region, render=render)


@st.cache_data(max_entries=8, show_spinner="掃描每一頁的公式候選…")
def cached_index(raw):
    return index_formulas(raw)


def formula_view(paper, document):
    with st.container():
        path = history.root / f"{paper}.pdf"
        try:
            raw = path.read_bytes()
            count = document.get("page_count") or page_count(raw)
            if st.toggle("整篇公式索引", value=True, key=f"formula-index-{paper}"):
                indexed = cached_index(raw)
                search = st.text_input("搜尋公式或公式編號", key=f"formula-search-{paper}").strip().casefold()
                matches = [(number, region) for number, regions in indexed.items() for region in regions
                           if search in f'{region["number"]} {region["text"]}'.casefold()]
                choice = st.selectbox(
                    "公式候選", range(len(matches)), index=None, placeholder="選擇公式，或改看指定頁碼",
                    format_func=lambda i: f'第 {matches[i][0]} 頁 · {matches[i][1]["text"][:90]}',
                    key=f"formula-match-{paper}-{search}",
                )
                if choice is None:
                    number, region = None, None
                else:
                    number, region = matches[choice]
                if not matches:
                    st.info("找不到相符候選。你可以用下方 PDF 頁碼查看原圖。")
            else:
                number, region = None, None
            if number is None:
                number = st.number_input("PDF 頁碼", min_value=1, max_value=count, step=1,
                                         key=f"formula-page-{paper}")
                regions = cached_formula_page(raw, number)
            else:
                regions = []
            if region is None and regions:
                selected = st.selectbox(
                    "檢視範圍", range(len(regions) + 1),
                    format_func=lambda i: "整頁原圖" if i == 0 else regions[i - 1]["text"][:90],
                    key=f"formula-region-{paper}-{number}",
                )
                region = regions[selected - 1] if selected else None
            if region:
                extracted, original = st.columns(2)
                extracted.caption("擷取算式 · 請以原圖核對符號及跨行結構")
                extracted.code(region["text"], language=None)
                full = extracted.checkbox("顯示整頁", key=f"formula-full-{paper}")
                preview = cached_formula_page(raw, number, None if full else region["box"], render=True)
                original.image(preview, caption=f"PDF 第 {number} 頁")
            else:
                st.image(cached_formula_page(raw, number, render=True), caption=f"PDF 第 {number} 頁")
        except (OSError, ValueError, RuntimeError) as error:
            st.error(f"無法顯示公式或原頁：{error}")


with st.sidebar:
    upload = st.file_uploader("新增英文論文 PDF", type="pdf", help="最多 30 MB、50 頁")
    add_pdf = st.button("匯入論文", disabled=upload is None, type="primary")
    sample = st.button("開啟範例論文")
if add_pdf or sample:
    budget = Budget(300, 12)
    paper = None
    try:
        with st.spinner("解析 PDF 中…"):
            if sample:
                sample_path = Path(__file__).with_name("sample.pdf")
                paper = history.ingest(sample_path.read_bytes(), "範例論文.pdf", budget)
            else:
                paper = history.ingest(upload.getvalue(), upload.name, budget)
            state["paper_choice"] = paper
            budget.record("Controller", "stop", reason="匯入完成")
    except (TaskError, OSError) as error:
        budget.record("Controller", "stop", reason=str(error))
        st.error(str(error))
    finally:
        finish(paper, budget)

papers = dict(history.papers())
if papers:
    paper = st.sidebar.selectbox("已匯入的論文", list(papers), format_func=papers.get,
                                 key="paper_choice")
    document, result = history.load(paper)
    error_key = f"analysis-error-{paper}"
    st.subheader(papers[paper])
    view = st.radio("檢視", ["方法分析", "公式與原頁"], horizontal=True, label_visibility="collapsed")
    if view == "公式與原頁":
        formula_view(paper, document)
        st.stop()
    failed = bool(result and not result["steps"] and not result["needs_range"])
    if (result is None or failed) and st.button(
        "重新擷取並分析" if failed else "分析研究方法", type="primary", disabled=controller is None
    ):
        budget = Budget(300, 12)
        try:
            with st.spinner("Ollama 正在整理與查核原文…"):
                if failed or document.get("parse_version") != PARSE_VERSION:
                    document = history.refresh_parse(paper, budget)
                result = controller.analyze(document, budget)
                history.save_result(paper, result)
                state.pop(error_key, None)
        except (TaskError, OSError) as error:
            budget.record("Controller", "stop", reason=str(error))
            state[error_key] = str(error)
        finally:
            finish(paper, budget)
    if (result is None or failed) and controller is None:
        st.info("連上 Ollama 並選擇模型後，即可分析。你也可以先切換到「公式與原頁」。")
    if state.get(error_key):
        st.error(f"上次分析失敗：{state[error_key]}")
    warnings = document["warnings"]
    if warnings:
        formula_pages = Counter()
        other_warnings = []
        for warning in warnings:
            match = re.match(r"PDF 第 (\d+) 頁.*公式可能解析不完整", warning)
            if match:
                formula_pages[int(match.group(1))] += 1
            else:
                other_warnings.append(warning)
        with st.expander(f"PDF 解析提醒（{len(warnings)} 則）"):
            if formula_pages:
                pages = "、".join(str(page) for page in sorted(formula_pages))
                st.info(f"第 {pages} 頁有公式可能擷取不完整。可切換至「公式與原頁」核對。")
            for warning in dict.fromkeys(other_warnings):
                st.write(warning)
    if result and result["needs_range"]:
        max_page = document.get("page_count", max(c["page"] for c in document["chunks"]))
        with st.form(f"range-{paper}"):
            interval = (st.slider("PDF 頁碼範圍", 1, max_page, (1, max_page))
                        if max_page > 1 else (1, 1))
            section = st.selectbox("章節", ["", *dict.fromkeys(c["section"] for c in document["chunks"])],
                                   format_func=lambda value: value or "所有章節")
            submitted = st.form_submit_button("在指定範圍重試一次", disabled=controller is None)
        if submitted:
            budget = Budget(result.get("remaining_seconds", 300),
                            result.get("remaining_calls", 12))
            allowed = {c["id"] for c in document["chunks"]
                       if interval[0] <= c["page"] <= interval[1]
                       and (not section or c["section"] == section)}
            try:
                with st.spinner("重新定位方法…"):
                    result = controller.analyze(document, budget, allowed=allowed, hint=section,
                                                retry=True)
            except TaskError as error:
                budget.record("Controller", "stop", reason=str(error))
                result = dict(locations=[], steps=[], issues=[str(error)], needs_range=False)
            history.save_result(paper, result)
            finish(paper, budget)
            st.rerun()
    if result:
        for issue in result["issues"]:
            st.info(issue)
        if result["locations"]:
            with st.expander("方法位置與原文", expanded=not result["steps"]):
                for location in result["locations"]:
                    evidence(location)
        for index, step in enumerate(result["steps"], 1):
            with st.expander(f'{index}. {step["what"]["text"]}', expanded=index == 1):
                for label, claim in step.items():
                    st.markdown(f"**{label.title()}**")
                    if claim:
                        evidence(claim)
                    else:
                        st.write(MISSING)
        if result["steps"]:
            st.download_button("下載方法筆記", report_markdown(papers[paper], result["steps"]),
                               "method-notes.md", "text/markdown")
            st.subheader("針對步驟追問")
            with st.form(f"question-{paper}", clear_on_submit=True):
                step_index = st.selectbox(
                    "步驟", range(len(result["steps"])),
                    format_func=lambda i: f'{i + 1}. {result["steps"][i]["what"]["text"]}',
                )
                question = st.text_input("問題", max_chars=500)
                ask = st.form_submit_button("送出", disabled=controller is None)
            if ask and question.strip():
                budget = Budget(120, 6)
                with st.spinner("搜尋並驗證論文原文…"):
                    answer = controller.answer(document, result, result["steps"][step_index],
                                               question.strip(), budget)
                history.save_chat(paper, step_index, question.strip(), answer)
                finish(paper, budget)
        for step_index, question, answer in history.chats(paper):
            with st.chat_message("user"):
                st.text(f"步驟 {step_index + 1} · {question}")
            with st.chat_message("assistant"):
                for claim in answer["claims"]:
                    evidence(claim)
                if answer["limit"]:
                    st.info(answer["limit"])
    saved_traces = dict(history.traces(paper))
    if saved_traces:
        with st.expander("這篇論文的歷史執行紀錄"):
            task = st.selectbox("任務", list(saved_traces), key=f"trace-{paper}")
            events = saved_traces[task]
            st.json(events, expanded=False)
            st.download_button("下載歷史 trace", json.dumps(events, ensure_ascii=False, indent=2),
                               f"{task}.json", "application/json")

else:
    st.info("從左側匯入一篇 PDF，或開啟範例試用公式瀏覽。")

if state.get("trace"):
    with st.expander("最近一次執行紀錄"):
        st.json(state["trace"], expanded=False)
        st.download_button("下載 trace", json.dumps(state["trace"], ensure_ascii=False, indent=2),
                           "trace.json", "application/json")
