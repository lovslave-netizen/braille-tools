# -*- coding: utf-8 -*-
"""
점자(BRF ascii)를 파일로 열거나 붙여넣으면 역점역해서 글자 수를 세어준다.
마침표 같은 문장부호도 한 글자로 센다. (안녕하세요. -> 6글자)
공백/줄바꿈은 '공백 제외'에서는 빼고, '공백 포함'에서는 공백만 센다(줄바꿈 제외).

BRF 파일은 폼피드(\\f)로 쪽이 나뉘고, 쪽 맨 아래 줄 끝의 '#A', '#AAE' 같은 것이
점자 쪽번호다(a~j = 1~9,0). 번호는 앞면에만 찍혀 있어서, 번호 없는 쪽(뒷면)은
바로 앞 쪽번호 + 1 로 계산한다.
"""
import re
import tkinter as tk
from tkinter import filedialog, messagebox

from 역점역기 import reverse_translate_text, read_source_file, reverse_jydbt_text, dxb_to_brf_text, jydbt_available

FORM_FEED = "\f"
_PAGE_NUM_RE = re.compile(r"[ \t]*#([A-Ja-j]+)[ \t]*$")
_DIGIT = dict(zip("abcdefghij", "1234567890"))


def parse_time(text: str):
    """'2', '1.5', '1:33', '1분33초', '93초', '1m33s' -> 초. 숫자만 쓰면 분으로 본다."""
    t = text.strip().replace(" ", "")
    if not t:
        return None
    m = re.fullmatch(r"(\d+):(\d+(?:\.\d+)?)", t)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)(?:분|m|min))?(?:(\d+(?:\.\d+)?)(?:초|s|sec)?)?", t)
    if m and (m.group(1) or m.group(2)):
        if m.group(1) is None and re.fullmatch(r"\d+(?:\.\d+)?", t):
            return float(t) * 60  # 숫자만 -> 분
        return float(m.group(1) or 0) * 60 + float(m.group(2) or 0)
    return None


def split_pages(text: str, lines_per_page: int = 26):
    """폼피드가 있으면 그걸로, 없으면 lines_per_page 줄씩 쪽을 나눈다."""
    if FORM_FEED in text:
        pages = text.split(FORM_FEED)
    else:
        lines = text.splitlines()
        n = max(1, lines_per_page)
        pages = ["\n".join(lines[i:i + n]) for i in range(0, len(lines), n)]
    while pages and not pages[-1].strip():
        pages.pop()
    return pages


def _last_nonblank_index(lines):
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            return i
    return -1


def page_number_of(page: str):
    """쪽 맨 아래 줄 끝의 '#숫자'를 읽는다. 없으면 None."""
    lines = page.splitlines()
    i = _last_nonblank_index(lines)
    if i < 0:
        return None
    m = _PAGE_NUM_RE.search(lines[i])
    if not m:
        return None
    return int("".join(_DIGIT[c] for c in m.group(1).lower()))


def strip_page_number(page: str) -> str:
    """글자 수에 쪽번호가 섞이지 않게 맨 아래 줄 끝의 '#숫자'를 뺀다."""
    lines = page.splitlines()
    i = _last_nonblank_index(lines)
    if i >= 0:
        lines[i] = _PAGE_NUM_RE.sub("", lines[i])
    return "\n".join(lines)


def label_pages(pages):
    """쪽마다 점자 쪽번호를 매긴다. 번호 없는 쪽(뒷면)은 앞 쪽 번호 + 1.
    목차 등에서 엉뚱한 숫자가 걸리는 걸 막으려고, 앞 쪽 번호보다 1~2 큰 값이거나 1(번호 새로 시작)일
    때만 찍힌 번호를 믿고, 나머지는 무시한다."""
    labels = []
    prev = None
    for p in pages:
        found = page_number_of(p)
        derived = prev + 1 if prev is not None else None
        if found is not None and (prev is None or found == 1 or prev + 1 <= found <= prev + 2):
            n = found
        else:
            n = derived
        labels.append(n)
        prev = n if n is not None else prev
    return labels


def parse_range(spec: str):
    """'5', '3-5', '3~5' -> (시작, 끝). 비우면 None(전체)."""
    spec = spec.strip()
    if not spec:
        return None
    m = re.fullmatch(r"(\d+)\s*[-~]\s*(\d+)", spec) or re.fullmatch(r"(\d+)()", spec)
    if not m:
        raise ValueError("쪽은 5 또는 3-5 형식으로 입력하세요")
    a = int(m.group(1))
    b = int(m.group(2)) if m.group(2) else a
    return (a, b) if a <= b else (b, a)


def select_pages(pages, spec: str, by_label: bool):
    """(선택된 쪽 목록, 설명) 을 돌려준다.
    by_label=True: 점자 쪽번호 기준(같은 번호가 여러 번이면 마지막 것=본문), False: 파일 순서(1부터)."""
    rng = parse_range(spec)
    if rng is None:
        return pages, f"전체 {len(pages)}쪽"
    a, b = rng
    if not by_label:
        if a < 1 or a > len(pages):
            raise ValueError(f"쪽 범위를 벗어났습니다 (파일 순서 1~{len(pages)})")
        b = min(b, len(pages))
        return pages[a - 1:b], f"파일 순서 {a}~{b}쪽 (전체 {len(pages)}쪽)"
    labels = label_pages(pages)
    index = {}
    for i, n in enumerate(labels):
        if n is not None:
            index[n] = i  # 중복이면 뒤의 것(본문)이 이긴다
    nums = sorted(index)
    if not nums:  # 쪽번호가 하나도 없는 파일 -> 파일 순서로 대신 찾는다
        return select_pages(pages, spec, False)[0], "쪽번호가 없는 파일이라 파일 순서로 찾았습니다 (" + select_pages(pages, spec, False)[1] + ")"
    if a not in index or b not in index:
        raise ValueError(f"그 쪽번호가 없습니다 (점자 쪽번호 {nums[0]}~{nums[-1]})")
    i, j = index[a], index[b]
    return pages[i:j + 1], f"점자 {a}~{b}쪽 (파일 {i + 1}~{j + 1}번째 쪽)"


def count_chars(text: str):
    no_space = sum(1 for ch in text if not ch.isspace())
    with_space = sum(1 for ch in text if ch == " " or not ch.isspace())
    return no_space, with_space


def main():
    root = tk.Tk()
    root.title("점자 글자수 세기")
    root.geometry("860x720")

    tk.Label(root, text="점자(BRF) 텍스트를 아래에 붙여넣거나 파일을 여세요. (일부만 붙여넣어도 됩니다)").pack(pady=(8, 2))

    src = tk.Text(root, height=10, wrap="word")
    src.pack(fill="x", padx=8)

    result_var = tk.StringVar(value="글자 수: -")
    tk.Label(root, textvariable=result_var, font=("맑은 고딕", 16, "bold"), fg="#1a5fb4").pack(pady=6)
    sub_var = tk.StringVar(value="")
    tk.Label(root, textvariable=sub_var).pack()

    page_row = tk.Frame(root)
    page_row.pack(pady=2)
    tk.Label(page_row, text="쪽 (예: 5 또는 3-5, 비우면 전체):").pack(side="left")
    page_var = tk.StringVar(value="")
    page_entry = tk.Entry(page_row, textvariable=page_var, width=8)
    page_entry.pack(side="left", padx=4)
    page_entry.bind("<Return>", lambda e: load_pages())
    label_var = tk.IntVar(value=1)
    tk.Radiobutton(page_row, text="점자 쪽번호", variable=label_var, value=1).pack(side="left")
    tk.Radiobutton(page_row, text="파일 순서", variable=label_var, value=0).pack(side="left")
    tk.Label(page_row, text="쪽당 줄수:").pack(side="left", padx=(8, 0))
    lines_var = tk.StringVar(value="26")
    tk.Entry(page_row, textvariable=lines_var, width=4).pack(side="left", padx=4)
    tk.Button(page_row, text="불러오기", command=lambda: load_pages()).pack(side="left", padx=4)
    page_info = tk.StringVar(value="")
    tk.Label(root, textvariable=page_info, fg="#555").pack()

    lang_row = tk.Frame(root)
    lang_row.pack(pady=2)
    tk.Label(lang_row, text="기본 언어:").pack(side="left")
    lang_var = tk.IntVar(value=2)
    for txt, val in (("자동판별", 2), ("한글", 0), ("영어", 1)):
        tk.Radiobutton(lang_row, text=txt, variable=lang_var, value=val,
                       command=lambda: run()).pack(side="left", padx=4)

    time_row = tk.Frame(root)
    time_row.pack(pady=2)
    tk.Label(time_row, text="읽은 시간 (예: 2 / 1:33 / 1분33초 / 93초):").pack(side="left")
    minutes_var = tk.StringVar(value="2")
    tk.Entry(time_row, textvariable=minutes_var, width=10).pack(side="left", padx=4)
    rate_var = tk.StringVar(value="")
    tk.Label(root, textvariable=rate_var, font=("맑은 고딕", 13, "bold"), fg="#26a269").pack()

    tk.Label(root, text="역점역 결과 (확인용)").pack(pady=(8, 2))
    out = tk.Text(root, height=12, wrap="word")
    out.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    last = {"n": 0, "w": 0}

    def update_rate(_evt=None):
        secs = parse_time(minutes_var.get())
        if not secs or secs <= 0:
            rate_var.set("읽은 시간을 2 / 1:33 / 1분33초 형식으로 입력하세요")
            return
        m = secs / 60
        if not last["n"]:
            rate_var.set("")
            return
        rate_var.set(f"{int(secs // 60)}분 {secs % 60:g}초 기준 → 1분당 약 {last['n'] / m:,.0f}자 (공백 포함 {last['w'] / m:,.0f}자)")

    minutes_var.trace_add("write", lambda *a: update_rate())

    def run(_evt=None):
        raw = src.get("1.0", "end-1c")
        if not raw.strip():
            last["n"] = last["w"] = 0
            result_var.set("글자 수: -")
            sub_var.set("")
            rate_var.set("")
            out.delete("1.0", "end")
            return
        try:
            if jydbt_available():
                text = reverse_jydbt_text(raw)  # JYDBT 엔진 (영어·한글 자동 판별, 한글 모드 선택은 아직 안 쓴다)
            else:
                text = reverse_translate_text(raw, lang_var.get())
        except Exception as e:
            messagebox.showerror("오류", f"역점역 중 오류:\n{e}")
            return
        no_space, with_space = count_chars(text)
        last["n"], last["w"] = no_space, with_space
        result_var.set(f"글자 수: {no_space:,}")
        sub_var.set(f"(공백 제외 {no_space:,}자 / 공백 포함 {with_space:,}자)")
        update_rate()
        out.delete("1.0", "end")
        out.insert("1.0", text)

    loaded = {"raw": None}

    def load_pages():
        if loaded["raw"] is None:
            messagebox.showinfo("안내", "먼저 [파일 열기]로 BRF 파일을 여세요.")
            return
        try:
            pages = split_pages(loaded["raw"], int(lines_var.get() or 26))
            chosen, desc = select_pages(pages, page_var.get(), bool(label_var.get()))
        except ValueError as e:
            messagebox.showerror("오류", str(e))
            return
        page_info.set(desc)
        src.delete("1.0", "end")
        src.insert("1.0", "\n".join(strip_page_number(p) for p in chosen))
        run()

    def open_file():
        path = filedialog.askopenfilename(
            title="BRF 파일 선택",
            filetypes=[("점자 문서", "*.brf;*.dxb;*.txt;*.blb;*.blt"), ("모든 파일", "*.*")],
        )
        if not path:
            return
        try:
            if path.lower().endswith(".dxb"):
                loaded["raw"] = dxb_to_brf_text(path)  # dxb 는 먼저 BRF 글로 바꿔서 쪽 고르기에 넣는다
            else:
                loaded["raw"] = read_source_file(path)
        except Exception as e:
            messagebox.showerror("오류", f"파일을 열 수 없습니다:\n{e}")
            return
        page_var.set("")
        load_pages()

    bar = tk.Frame(root)
    bar.pack(before=src, pady=2)
    tk.Button(bar, text="파일 열기", width=12, command=open_file).pack(side="left", padx=4)
    tk.Button(bar, text="글자수 세기", width=12, command=run).pack(side="left", padx=4)
    tk.Button(bar, text="지우기", width=8,
              command=lambda: (src.delete("1.0", "end"), run())).pack(side="left", padx=4)

    src.bind("<<Paste>>", lambda e: root.after(50, run))
    src.bind("<KeyRelease>", lambda e: run())
    root.mainloop()


if __name__ == "__main__":
    main()
