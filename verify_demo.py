"""Exercise the real PDF, evidence, routing, and history code with model fixtures."""
import json
import platform
import sys
from importlib.metadata import version
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from reportlab.pdfgen import canvas

from agents import Budget, Controller, History, PDFProcessing, TaskError


METHOD = "We normalized each measurement using the training set mean."
DETAIL = "We subtracted the training set mean from each measurement."
WHY = "We used the training set mean to avoid leakage from test data."


def make_pdf(columns, variant, blank=False):
    stream = BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(612, 792))
    if not blank:
        pdf.drawString(48, 750, "Introduction")
        pdf.drawString(48, 728, WHY)
        pdf.showPage()
        pdf.setFont("Helvetica", 9 if columns == 2 else 11)
        pdf.drawString(48, 750, "2. Methods")
        pdf.drawString(48, 728, METHOD)
        pdf.drawString(48, 714, DETAIL)
        pdf.drawString(48, 700, f"We recorded the normalized values for dataset {variant}.")
        pdf.drawString(48, 685, "The transformation was applied independently.")
        x = 334 if columns == 2 else 48
        y = 750 if columns == 2 else 650
        pdf.drawString(x, y, "3. Results")
        pdf.drawString(x, y - 22, "The validation error decreased.")
        pdf.drawString(x, y - 36, "The threshold was fixed before evaluation.")
        pdf.drawString(x, y - 50, "Full results are provided in the appendix.")
    pdf.showPage()
    pdf.save()
    return stream.getvalue()


class ModelFixture:
    def __init__(self, mode="success"):
        self.mode = mode

    def ask(self, role, task, instructions, data, budget):
        budget.remaining()
        assert budget.calls < budget.limit
        budget.calls += 1
        budget.record(role, task, status="fixture")
        if task == "check_support":
            return {"supported": [key for key, claim in data.items()
                                  if claim["text"] != "原文未支持的說明"]}

        def claim(quote, text):
            source = next((c for c in data["excerpts"] if quote in c["text"]), None)
            return {"id": source["id"], "text": text, "quote": quote} if source else None

        what = claim(METHOD, "使用訓練集平均值正規化量測值。")
        if task == "locate":
            if self.mode == "bad_source" and what:
                what["quote"] = "This line does not exist in the PDF."
            return {"locations": [what] if what else []}
        if task == "steps":
            return {"steps": [dict(what=what, why=None, how=claim(DETAIL, "從每筆量測值減去訓練集平均值。"))]}
        if task == "repair_steps":
            return {"claims": {"0.why": claim(WHY, "避免測試資料洩漏。")}}
        answer = claim(WHY, "原文未支持的說明" if self.mode == "unsupported" else "避免測試資料洩漏。")
        return {"complete": bool(answer), "claims": [answer] if answer else []}


def run(target):
    target.mkdir(parents=True, exist_ok=True)

    def emit(name, trace):
        (target / name).write_text(json.dumps(trace, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")

    cases = []
    with TemporaryDirectory() as temp:
        history = History(temp)
        controller = Controller(ModelFixture())
        papers = []
        for columns, variant in ((1, "A"), (1, "B"), (2, "C"), (2, "D")):
            budget = Budget(300, 12)
            paper = history.ingest(make_pdf(columns, variant), f"fixture-{variant}.pdf", budget)
            papers.append(paper)
            document, _ = history.load(paper)
            page = [c for c in document["chunks"] if c["page"] == 2]
            assert any(f"dataset {variant}" in entry["text"] for entry in page)
            page_text = " ".join(c["text"] for c in page)
            assert page_text.index(METHOD) < page_text.index("3. Results")
            assert next(e for e in budget.trace if e.get("page") == 2)["columns"] == columns
            result = controller.analyze(document, budget)
            step = result["steps"][0]
            assert [step[k]["page"] for k in ("what", "why", "how")] == [2, 1, 2]
            history.save_result(paper, result)
            history.save_trace(paper, budget)
            followup = Budget(120, 6)
            answer = controller.answer(document, result, step, "為什麼使用訓練集平均值？", followup)
            assert not answer["limit"] and answer["claims"][0]["quote"] == WHY
            assert [e["scope"] for e in followup.trace if e["agent"] == "Retrieval"] == [
                "步驟及方法章節", "同篇全文"]
            history.save_chat(paper, 0, "為什麼使用訓練集平均值？", answer)
            reopened = History(temp)
            assert reopened.load(paper)[1] == result
            assert len(reopened.chats(paper)) == 1
            if len(papers) > 1:
                assert reopened.chats(papers[0]) == history.chats(papers[0])
                assert reopened.load(papers[0])[0] != document
            cases.append(dict(sample=variant, columns=columns, status="pass",
                              analysis_calls=budget.calls, analysis_s=budget.trace[-1]["elapsed_s"],
                              followup_calls=followup.calls, followup_s=followup.trace[-1]["elapsed_s"]))
            if variant == "C":
                emit("success.json", dict(analysis=budget.trace, followup=followup.trace))

        doc, result = history.load(papers[-1])
        invalid = Controller(ModelFixture("bad_source"))
        unstructured = dict(doc, chunks=[dict(c, heading=False) for c in doc["chunks"]])
        first = Budget(300, 12)
        assert invalid.analyze(unstructured, first)["needs_range"]
        retry = Budget(300, 12)
        allowed = {c["id"] for c in doc["chunks"] if c["page"] == 2}
        failed = invalid.analyze(unstructured, retry, allowed=allowed, retry=True)
        assert not failed["needs_range"] and not failed["locations"]
        assert any(e.get("exact") is False for e in retry.trace)
        emit("failure_bad_citation.json", dict(initial=first.trace, retry=retry.trace))

        budget = Budget(120, 6)
        limited = Controller(ModelFixture("unsupported")).answer(
            doc, result, result["steps"][0], "為什麼使用訓練集平均值？", budget)
        assert limited["limit"] and not limited["claims"]
        assert any(e.get("exact") is True for e in budget.trace)
        assert any(e.get("supported") == [] for e in budget.trace)
        emit("failure_unsupported.json", budget.trace)

        budget = Budget(300, 12)
        try:
            PDFProcessing().parse(make_pdf(1, "blank", blank=True), budget)
        except TaskError as error:
            budget.record("Controller", "stop", reason=str(error))
            assert "無可用文字" in str(error)
        else:
            raise AssertionError("empty PDF was accepted")
        emit("failure_no_text.json", budget.trace)

    emit("test_results.json", dict(python=platform.python_version(), system=platform.platform(),
                                   pdfplumber=version("pdfplumber"), model="fixture", cases=cases))
    print("PASS: 2 single-column + 2 double-column fixtures, 3 failure scenarios")


if __name__ == "__main__":
    run(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("trace"))
