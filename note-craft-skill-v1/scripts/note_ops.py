#!/usr/bin/env python3
"""Inventory, cache assets, and verify note-craft artifacts; no rewriting or OCR."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path


ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+.*|[ \t]*)$")
OPEN_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\n]*)$")
SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
REF = re.compile(r"^ {0,3}\[([^\]]+)\]:[ \t]*(<[^>]+>|\S+)")
MAX_IMAGE_BYTES = 25 * 1024 * 1024


def read(path):
    return Path(path).read_text(encoding="utf-8-sig")


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref_key(s):
    return " ".join(s.split()).casefold()


def destination(s):
    s = s.strip()
    if s.startswith("<") and ">" in s:
        return s[1:s.index(">")]
    # A title follows whitespace; escaped spaces belong to the destination.
    return re.split(r"(?<!\\)\s", s, maxsplit=1)[0].replace("\\(", "(").replace("\\)", ")").replace("\\ ", " ")


def balanced(text, start, opening, closing):
    depth = 0
    for j in range(start, len(text)):
        if j and text[j - 1] == "\\":
            continue
        if text[j] == opening:
            depth += 1
        elif text[j] == closing:
            depth -= 1
            if depth == 0:
                return j
    return None


def images_in_line(line, refs):
    # Ignore inline code without changing offsets.
    masked = re.sub(r"(`+)(.*?)\1", lambda m: " " * len(m.group()), line)
    result = []
    pos = 0
    while True:
        i = masked.find("![", pos)
        if i < 0:
            break
        pos = i + 2
        if i and masked[i - 1] == "\\":
            continue
        end = balanced(masked, i + 1, "[", "]")
        if end is None:
            continue
        alt = line[i + 2:end]
        j = end + 1
        url, final = None, j
        if j < len(masked) and masked[j] == "(":
            close = balanced(masked, j, "(", ")")
            if close is not None:
                url, final = destination(line[j + 1:close]), close + 1
        elif j < len(masked) and masked[j] == "[":
            close = balanced(masked, j, "[", "]")
            if close is not None:
                url = refs.get(ref_key(line[j + 1:close] or alt))
                final = close + 1
        else:
            url = refs.get(ref_key(alt))
        result.append({"alt": alt, "url": url, "raw": line[i:final]})
        pos = max(final, pos)
    for m in re.finditer(r"<img\b[^>]*\bsrc\s*=\s*(['\"])(.*?)\1[^>]*>", line, re.I):
        result.append({"alt": "", "url": m.group(2), "raw": m.group()})
    return result


def scan(text):
    lines = text.splitlines(keepends=True)
    headings, codes, warnings = [], [], []
    outside = set()
    fence = None
    start = None
    info = ""
    content = []
    for i, raw in enumerate(lines):
        line = raw.rstrip("\r\n")
        m = OPEN_FENCE.match(line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2).strip():
                codes.append({"id": f"code-{len(codes) + 1:03d}", "line": start + 1,
                              "end_line": i + 1, "info": info, "content": "".join(content), "closed": True})
                fence, content = None, []
            else:
                content.append(raw)
            continue
        if m:
            fence, start, info = m.group(1), i, m.group(2).strip()
            continue
        outside.add(i)
        if re.match(r"^\s*(?:>|[-+*]\s|\d+[.)]\s).*?(?:`{3,}|~{3,})", line):
            warnings.append({"line": i + 1, "reason": "容器内围栏需人工核对，不按顶层围栏自动处理"})
        if re.match(r"^\s*>\s*#{1,6}\s", line):
            warnings.append({"line": i + 1, "reason": "引用内标题需人工确认其保留方式"})
        if ATX.match(line):
            headings.append({"line": i + 1, "end_line": i + 1, "level": len(ATX.match(line).group(1)), "raw": line})
        elif SETEXT.match(line) and i > 0 and i - 1 in outside:
            prev = lines[i - 1].rstrip("\r\n")
            if prev.strip() and not prev.lstrip().startswith(("#", ">", "|")) and not re.match(r"^\s*(?:[-+*]|\d+[.)])\s", prev):
                headings.append({"line": i, "end_line": i + 1, "level": 1 if line.lstrip().startswith("=") else 2,
                                 "raw": prev + "\n" + line})
    if fence:
        codes.append({"id": f"code-{len(codes) + 1:03d}", "line": start + 1, "end_line": len(lines),
                      "info": info, "content": "".join(content), "closed": False})
        warnings.append({"line": start + 1, "reason": "代码围栏未闭合"})
    refs = {}
    for i in sorted(outside):
        m = REF.match(lines[i])
        if m:
            refs[ref_key(m.group(1))] = destination(m.group(2))
    images = []
    for i in sorted(outside):
        for item in images_in_line(lines[i], refs):
            item.update({"id": f"img-{len(images) + 1:03d}", "line": i + 1})
            images.append(item)
            if not item["url"]:
                warnings.append({"line": i + 1, "reason": "图片引用未能解析，需核对原文"})
    return {"headings": headings, "codes": codes, "images": images, "warnings": warnings}


def clean_notes(text):
    """Conservative candidate, not a semantic rewriting engine."""
    text = re.sub(r"\[([^\]\n]+)\]\([^\n]*?\)", r"\1", text)
    text = re.sub(r"(?m)^ {0,3}#{1,6}[ \t]+", "", text)
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    text = re.sub(r"(?m)^\s*(?:[-+*]|\d+[.)])[ \t]+", "", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<!\w)(\*|_)([^\n]+?)\1(?!\w)", r"\2", text)
    text = re.sub(r"(`+)([^\n]*?)\1", r"\2", text)
    text = re.sub(r"(?m)^ {0,3}(?:-{3,}|\*{3,}|_{3,})[ \t]*$", "", text)
    return text


def prepare(args):
    source, work = Path(args.source).resolve(), Path(args.work).resolve()
    text = read(source)
    # Store work outside the input path; never overwrite the input file.
    work.mkdir(parents=True, exist_ok=True)
    (work / "sections").mkdir(exist_ok=True)
    (work / "codes").mkdir(exist_ok=True)
    data = scan(text)
    lines = text.splitlines(keepends=True)
    starts = sorted({0, *[h["line"] - 1 for h in data["headings"]]})
    sections = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        p = work / "sections" / f"{n + 1:03d}.md"
        p.write_text("".join(lines[start:end]), encoding="utf-8")
        sections.append({"path": str(p), "start_line": start + 1, "end_line": end})
    for item in data["codes"]:
        raw = work / "codes" / f"{item['id']}.raw.txt"
        cleaned = work / "codes" / f"{item['id']}.notes.txt"
        content = item.pop("content")
        raw.write_text(content, encoding="utf-8")
        cleaned.write_text(clean_notes(content), encoding="utf-8")
        item["raw_file"], item["notes_file"] = str(raw), str(cleaned)
        item["sha256"] = digest(raw)
    coverage = {
        "source_sha256": digest(source),
        "images": [{"id": i["id"], "status": "pending", "evidence": ""} for i in data["images"]],
        "codes": [{"id": c["id"], "kind": "pending"} for c in data["codes"]],
        "topics": [{"source_heading": h["raw"], "report_heading": ""} for h in data["headings"]],
        "exceptions": [],
    }
    data.update({"version": 1, "source": str(source), "source_sha256": digest(source), "work": str(work), "sections": sections})
    save_json(work / "manifest.json", data)
    save_json(work / "inventory.json", {
        "headings": data["headings"], "sections": sections,
        "images": [{k: i[k] for k in ("id", "line", "alt")} for i in data["images"]],
        "codes": data["codes"], "warnings": data["warnings"],
    })
    ledger = work / "coverage.json"
    if not ledger.exists():
        save_json(ledger, coverage)
    else:
        save_json(work / "coverage-template.json", coverage)
    print(json.dumps({"manifest": str(work / "manifest.json"), "inventory": str(work / "inventory.json"), "headings": len(data["headings"]),
                      "images": len(data["images"]), "codes": len(data["codes"]), "warnings": data["warnings"]}, ensure_ascii=False))
    return 0


def load_manifest(path):
    p = Path(path).resolve()
    data = json.loads(read(p))
    return p, data


def rules(args):
    _, manifest = load_manifest(args.manifest)
    wanted = {"core", "text", "research", "delivery", "scripts"}
    if manifest["images"]:
        wanted.add("media")
    if manifest["codes"]:
        wanted.add("code")
    ref = read(Path(__file__).resolve().parents[1] / "reference.md")
    chunks = re.split(r"(?m)(?=^## [a-z]+$)", ref)
    print("\n".join(c.strip() for c in chunks if c and c.splitlines()[0].removeprefix("## ") in wanted))
    return 0


def image_suffix(data, content_type):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if content_type == "image/svg+xml" or b"<svg" in data[:2048]:
        return ".svg"
    if content_type.startswith("image/"):
        return ".img"
    raise ValueError("下载结果不是可识别的图片")


def fetch_one(item, source, work, timeout, attempts):
    imgdir = work / "images"
    cache_key = item["id"] + "-" + hashlib.sha256((item.get("url") or "").encode()).hexdigest()[:12]
    for existing in sorted(imgdir.glob(cache_key + ".*")):
        if existing.is_file() and existing.stat().st_size:
            return {"id": item["id"], "status": "cached", "path": str(existing), "bytes": existing.stat().st_size}
    url = item.get("url")
    if not url:
        return {"id": item["id"], "status": "error", "error": "图片引用未解析"}
    last = "unknown"
    for attempt in range(attempts):
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme in ("http", "https"):
                request = urllib.request.Request(url, headers={"User-Agent": "note-craft-skill-v1"})
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    data = response.read(MAX_IMAGE_BYTES + 1)
                    content_type = response.headers.get_content_type()
            elif parsed.scheme in ("", "file"):
                p = Path(urllib.parse.unquote(parsed.path))
                if not p.is_absolute():
                    p = source.parent / p
                with p.open("rb") as stream:
                    data = stream.read(MAX_IMAGE_BYTES + 1)
                content_type = ""
            else:
                raise ValueError("仅支持HTTP(S)或本地图片路径")
            if not data or len(data) > MAX_IMAGE_BYTES:
                raise ValueError("图片为空或超过25MiB")
            out = imgdir / (cache_key + image_suffix(data, content_type))
            out.write_bytes(data)
            return {"id": item["id"], "status": "downloaded", "path": str(out), "bytes": len(data)}
        except Exception as exc:
            # Do not expose signed URLs through exception messages.
            last = f"{type(exc).__name__}" + (f" HTTP {exc.code}" if hasattr(exc, "code") else "")
    return {"id": item["id"], "status": "error", "error": last, "attempts": attempts}


def fetch(args):
    path, manifest = load_manifest(args.manifest)
    work, source = Path(manifest["work"]), Path(manifest["source"])
    (work / "images").mkdir(exist_ok=True)
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_one, i, source, work, args.timeout, args.attempts): i["id"] for i in manifest["images"]}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results[result["id"]] = result
            print(json.dumps(result, ensure_ascii=False), flush=True)
    for item in manifest["images"]:
        item["download"] = results[item["id"]]
    save_json(path, manifest)
    inventory_path = work / "inventory.json"
    if inventory_path.is_file():
        inventory = json.loads(read(inventory_path))
        for item in inventory["images"]:
            item["download"] = results[item["id"]]
        save_json(inventory_path, inventory)
    return int(any(i["status"] == "error" for i in results.values()))


def table_cells(line):
    cells, buf, escaped, in_code = [], [], False, False
    for ch in line.strip():
        if escaped:
            buf.extend(("\\", ch))
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == "`":
            in_code = not in_code
            buf.append(ch)
        elif ch == "|" and not in_code:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if escaped:
        buf.append("\\")
    cells.append("".join(buf).strip())
    if line.strip().startswith("|"):
        cells = cells[1:]
    if line.strip().endswith("|"):
        cells = cells[:-1]
    return cells


def check(args):
    path, manifest = load_manifest(args.manifest)
    basic, report = read(args.basic), read(args.report)
    coverage = json.loads(read(args.coverage))
    errors, warnings = [], []

    def fail(rule, message):
        errors.append({"rule": rule, "message": message})

    if coverage.get("source_sha256") != manifest["source_sha256"]:
        fail("COVERAGE_SOURCE", "coverage记录不属于本次输入；使用prepare生成的新模板")
    if Path(args.basic).resolve() == Path(args.report).resolve():
        fail("OUTPUT_SEPARATION", "两份产物不能使用同一个文件")
    source = Path(manifest["source"])
    if not source.is_file() or digest(source) != manifest["source_sha256"]:
        fail("SOURCE_CHANGED", "输入文件缺失或prepare后发生变化")
    for w in manifest["warnings"]:
        fail("SOURCE_REVIEW", f"原文第{w['line']}行：{w['reason']}")
    expected = [h["raw"] for h in manifest["headings"]]
    actual = [h["raw"] for h in scan(basic)["headings"]]
    if expected != actual:
        fail("HEADINGS", "基础版标题文字、层级、数量或顺序与原文不一致")
    heading_lines = set()
    for h in scan(basic)["headings"]:
        heading_lines.update(range(h["line"], h["end_line"] + 1))
    body = "\n".join(l for n, l in enumerate(basic.splitlines(), 1) if n not in heading_lines)
    patterns = {
        "FMT_FENCE": r"(?m)^ {0,3}(?:`{3,}|~{3,})",
        "FMT_IMAGE": r"(?<!\\)!\[",
        "FMT_LINK": r"\[[^\]\n]+\]\([^\n]+\)|\[[^\]\n]+\]\[[^\]\n]*\]|(?m:^ {0,3}\[[^\]\n]+\]:)",
        "FMT_LIST": r"(?m)^\s*(?:[-+*]|\d+[.)])[ \t]+",
        "FMT_QUOTE": r"(?m)^\s*>[ \t]?",
        "FMT_EMPHASIS": r"(?<!\\)(?:\*\*[^\n]+?\*\*|__[^\n]+?__|(?<!\w)\*[^\n]+?\*(?!\w))",
        "FMT_INLINE_CODE": r"(?<!\\)`[^\n]+?`",
        "FMT_HTML": r"</?[A-Za-z][^>]*>",
        "FMT_FOOTNOTE": r"\[\^[^\]\n]+\]",
        "FMT_RULE": r"(?m)^ {0,3}(?:-{3,}|\*{3,}|_{3,})[ \t]*$",
        "FMT_INDENTED_CODE": r"(?m)^(?: {4}|\t)\S",
    }
    for rule, pattern in patterns.items():
        if re.search(pattern, body):
            fail(rule, "基础版残留不允许的Markdown或多媒体语法")
    # URLs inside preserved literal code are program data, not hyperlinks.
    prose = body
    codes_by_id = {c["id"]: c for c in manifest["codes"]}
    code_contents = {}
    for code_id, item in codes_by_id.items():
        raw = Path(item["raw_file"])
        if not raw.is_file() or digest(raw) != item["sha256"]:
            fail("CODE_SOURCE", f"{code_id}的工作副本缺失或发生变化")
            code_contents[code_id] = ""
        else:
            code_contents[code_id] = read(raw)
    for c in coverage.get("codes", []):
        if c.get("kind") == "literal" and c.get("id") in codes_by_id:
            prose = prose.replace(code_contents[c["id"]].rstrip("\r\n"), "")
    if re.search(r"https?://\S+", prose):
        fail("FMT_URL", "基础版正文残留网页地址")
    table_width = None
    table_start = None
    for n, line in enumerate(basic.splitlines() + [""], 1):
        if line.lstrip().startswith("|"):
            width = len(table_cells(line))
            if table_width is None:
                table_width, table_start = width, n
                if width < 1:
                    fail("TABLE_WIDTH", f"第{n}行表格没有有效列")
            elif width != table_width:
                fail("TABLE_WIDTH", f"第{n}行表格列数与第{table_start}行不同")
            if n == table_start + 1 and not all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in table_cells(line)):
                fail("TABLE_SEPARATOR", f"第{n}行缺少有效表头分隔行")
        else:
            table_width, table_start = None, None
    image_records = coverage.get("images", [])
    image_ids = [i.get("id") for i in image_records]
    if len(image_ids) != len(set(image_ids)) or set(image_ids) != {i["id"] for i in manifest["images"]}:
        fail("IMAGE_COVERAGE", "图片ID遗漏、重复或额外添加")
    for item in image_records:
        if item.get("status") not in ("ocr", "diagram", "table", "unavailable"):
            fail("IMAGE_PENDING", f"{item.get('id')}尚未完成")
        if not item.get("evidence") or item["evidence"] not in basic:
            fail("IMAGE_EVIDENCE", f"{item.get('id')}缺少基础版中可定位的证据片段")
        if item.get("status") == "unavailable":
            fail("IMAGE_UNAVAILABLE", f"{item.get('id')}不可读取：{item.get('reason', '原因未记录')}")
        if item.get("status") == "table" and item.get("table_reviewed") is not True:
            fail("TABLE_REVIEW", f"{item.get('id')}未完成行列与数字人工核对")
    code_records = coverage.get("codes", [])
    code_ids = [i.get("id") for i in code_records]
    if len(code_ids) != len(set(code_ids)) or set(code_ids) != set(codes_by_id):
        fail("CODE_COVERAGE", "代码块ID遗漏、重复或额外添加")
    for item in code_records:
        source_code = codes_by_id.get(item.get("id"))
        if not source_code:
            continue
        if item.get("kind") == "literal":
            retained = code_contents[item["id"]].rstrip("\r\n")
        elif item.get("kind") == "notes":
            retained = item.get("expected_text", clean_notes(code_contents[item["id"]])).rstrip("\r\n")
            if "expected_text" in item and not item.get("reason"):
                fail("CODE_REASON", f"{item['id']}自定义清理文本未说明原因")
        else:
            fail("CODE_PENDING", f"{item.get('id')}未选择notes或literal")
            continue
        if retained and retained not in basic:
            fail("CODE_CONTENT", f"{item.get('id')}的内容缺失、改写或拆散")
    report_headings = {h["raw"] for h in scan(report)["headings"]}
    topic_records = coverage.get("topics", [])
    if sorted(t.get("source_heading", "") for t in topic_records) != sorted(expected):
        fail("TOPIC_COVERAGE", "原章节映射遗漏或重复")
    for item in topic_records:
        if item.get("report_heading") not in report_headings:
            fail("TOPIC_TARGET", f"研究版中没有对应标题：{item.get('source_heading')}")
    if not report.strip() or not report_headings:
        fail("REPORT_EMPTY", "研究版没有有效正文与标题")
    if not re.search(r"\[[^\]\n]+\]\(https?://[^\s)]+\)", report):
        fail("REPORT_SOURCES", "研究版缺少可定位的来源链接")
    if scan(report)["warnings"]:
        fail("REPORT_FORMAT", "研究版存在需核对的代码或标题结构")
    waived = []
    for exception in coverage.get("exceptions", []):
        if not all(exception.get(k) for k in ("rule", "reason", "authorization")):
            fail("EXCEPTION_INVALID", "格式例外缺少规则、原因或用户授权记录")
            continue
        matches = [e for e in errors if e["rule"] == exception["rule"]]
        if exception["rule"] in ("SOURCE_CHANGED", "COVERAGE_SOURCE", "CODE_SOURCE", "CODE_COVERAGE", "IMAGE_COVERAGE", "TOPIC_COVERAGE"):
            fail("EXCEPTION_INVALID", "不能以格式例外忽略输入变化或项目遗漏")
            continue
        for e in matches:
            errors.remove(e)
            waived.append({**e, "authorization": exception["authorization"], "reason": exception["reason"]})
    warnings.append("机械检查不验证OCR真实性、内容语义、引用真实性或用户授权；交付前需人工复核。")
    result = {"passed": not errors, "errors": errors, "exceptions": waived, "warnings": warnings,
              "basic": str(Path(args.basic).resolve()), "report": str(Path(args.report).resolve())}
    save_json(path.parent / "check-result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("source")
    p.add_argument("--work", required=True)
    p.set_defaults(run=prepare)
    p = sub.add_parser("rules")
    p.add_argument("--manifest", required=True)
    p.set_defaults(run=rules)
    p = sub.add_parser("fetch")
    p.add_argument("--manifest", required=True)
    p.add_argument("--timeout", type=float, default=12)
    p.add_argument("--attempts", type=int, choices=(1, 2), default=2)
    p.set_defaults(run=fetch)
    p = sub.add_parser("check")
    for flag in ("manifest", "basic", "report", "coverage"):
        p.add_argument("--" + flag, required=True)
    p.set_defaults(run=check)
    args = parser.parse_args()
    try:
        return args.run(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"{type(exc).__name__}: 无法完成{args.command}；检查文件、参数和JSON格式。", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
