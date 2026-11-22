"""Local formula inspection from the PDF's glyph geometry."""
from io import BytesIO
import re
from statistics import median

import pdfplumber


OPERATORS = re.compile(r"[=≠≈≃≡≤≥∑∏∫√∂∇∞±×÷→∥⋅]|\(cid:\d+\)")
EQUATION_NUMBER = re.compile(r"\(\d+(?:\.\d+)*[a-z]?\)\s*$", re.I)


def bounds(chars):
    return (min(c["x0"] for c in chars), min(c["top"] for c in chars),
            max(c["x1"] for c in chars), max(c["bottom"] for c in chars))


def expression(chars, baseline, size):
    """Recover small, vertically offset glyph groups as explicit scripts."""
    output = []
    script = ""
    last = None
    for char in sorted(chars, key=lambda c: (c["x0"], c["top"])):
        value = char["text"]
        shift = char["bottom"] - baseline
        marker = ""
        if char["size"] <= .86 * size and abs(shift) > .12 * size:
            marker = "^" if shift < 0 else "_"
        if marker != script:
            if script:
                output.append("}")
            if marker:
                output.append(marker + "{")
            script = marker
        if last and not marker and char["x0"] - last["x1"] > .27 * size:
            output.append(" ")
        output.append(value)
        last = char
    if script:
        output.append("}")
    return "".join(output).strip()


def text_rows(page):
    words = page.extract_words(return_chars=True)
    rows = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if not rows or word["top"] - rows[-1][0]["top"] > 3:
            rows.append([])
        rows[-1].append(word)
    for row in rows:
        segment = []
        for word in sorted(row, key=lambda w: w["x0"]):
            if segment and word["x0"] - segment[-1]["x1"] > 27:
                yield segment
                segment = []
            segment.append(word)
        if segment:
            yield segment


def candidates(page):
    chars = [c for c in page.chars if c["text"].strip()]
    regions = []
    rows = list(text_rows(page))
    labels = [(words[0]["x0"], words[0]["top"], words[0]["text"]) for words in rows
              if len(words) == 1 and EQUATION_NUMBER.fullmatch(words[0]["text"])]
    for words in rows:
        raw = " ".join(w["text"] for w in words)
        if not OPERATORS.search(raw):
            continue
        main = [c for word in words for c in word["chars"] if c["text"].strip()]
        size = median(c["size"] for c in main)
        base = median(c["bottom"] for c in main if c["size"] >= .9 * size)
        x0, top, x1, bottom = bounds(main)
        selected = [c for c in chars if c["x0"] >= x0 - 1 and c["x1"] <= x1 + .75 * size
                    and c["top"] >= top - .55 * size and c["bottom"] <= bottom + .45 * size
                    and (abs(c["bottom"] - base) <= .14 * size or c["size"] <= .86 * size)]
        if selected:
            inline_number = EQUATION_NUMBER.search(raw)
            adjacent = [label for label in labels
                        if abs(label[1] - top) <= 3 and 0 <= label[0] - x1 <= 240]
            regions.append(dict(box=bounds(selected), text=expression(selected, base, size),
                                kind="算式候選", number=(inline_number.group() if inline_number else
                                    min(adjacent)[2] if adjacent else "")))

    # A short horizontal rule with compact text directly above and below it.
    rules = [*page.lines, *[r for r in page.rects if r["height"] <= 1.5]]
    for rule in rules:
        x0, x1, top = rule["x0"], rule["x1"], rule["top"]
        if not 5 <= x1 - x0 <= 120 or rule["bottom"] - top > 1.5:
            continue
        nearby = [c for c in chars if x0 - 1 <= (c["x0"] + c["x1"]) / 2 <= x1 + 1
                  and top - 17 <= c["top"] and c["bottom"] <= top + 17]
        above = [c for c in nearby if 0 <= top - c["bottom"] <= 6]
        below = [c for c in nearby if 0 <= c["top"] - top <= 7]
        if not above or not below:
            continue
        parts = ["".join(c["text"] for c in sorted(row, key=lambda c: c["x0"]))
                 for row in (above, below)]
        if any(len(part) > 18 or not re.search(r"\w", part) for part in parts):
            continue
        regions.append(dict(box=bounds([*above, *below]), text=f"({parts[0]})/({parts[1]})",
                            kind="分式候選", number=""))
    return sorted(regions, key=lambda item: (round(item["box"][1] / 4), item["box"][0]))


def page_count(raw):
    with pdfplumber.open(BytesIO(raw)) as pdf:
        return len(pdf.pages)


def index_formulas(raw):
    with pdfplumber.open(BytesIO(raw)) as pdf:
        return {page.page_number: candidates(page) for page in pdf.pages}


def inspect_page(raw, number, region=None, *, render=False):
    with pdfplumber.open(BytesIO(raw)) as pdf:
        page = pdf.pages[number - 1]
        if not render:
            return candidates(page)
        if region is not None:
            x0, top, x1, bottom = region
            left, upper, right, lower = page.bbox
            page = page.crop((max(left, x0 - 12), max(upper, top - 12),
                              min(right, x1 + 12), min(lower, bottom + 12)))
        preview = BytesIO()
        page.to_image(resolution=170 if region else 130).original.save(preview, format="PNG")
        return preview.getvalue()
