# -*- coding: utf-8 -*-
"""
점자(BRF ascii)를 역점역하는 모듈. 글자수세기.py가 불러다 쓴다.
단독 실행하면 파일을 선택해 같은 폴더에 "원본이름(역점역).txt"로 저장한다.
"""
import ctypes
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

# exe로 묶였으면 안에 들어있는 DLL(BrailleTransLibrary)을 쓰고,
# 소스로 돌릴 땐 이 폴더 옆의 BrailleTransLibrary(없으면 설치된 점사랑7)를 쓴다.
if getattr(sys, "frozen", False):
    BASE = os.path.join(sys._MEIPASS, "BrailleTransLibrary")
else:
    _here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BrailleTransLibrary")
    BASE = os.environ.get(
        "BRL_BASE",
        _here if os.path.isdir(_here) else r"C:\Program Files (x86)\Jeomsarang7",
    )
os.add_dll_directory(BASE)
_dll = ctypes.CDLL(os.path.join(BASE, "BrailleTransMain.dll"))

_rev = _dll.BrailleTransBrailleToString
_rev.restype = ctypes.c_int
_rev.argtypes = [ctypes.c_char_p, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_int]


def reverse_translate_line(line: str, mode: int = 0) -> str:
    """BRF ascii 한 줄을 역점역. 소문자로 바꿔야 정상 동작함(중요).
    mode: 0=기본 한글(영어표시 만나면 영어), 1=기본 영어."""
    if not line.strip():
        # 빈 줄(공백만 있는 줄 포함)을 그대로 넣으면 DLL이 쓰레기값을 내놓음 -> 건너뜀
        return line
    lowered = line.lower()
    buf = ctypes.create_unicode_buffer(max(256, len(lowered) * 4 + 64))
    _rev(lowered.encode("latin-1", errors="replace"), buf, len(buf), mode)
    return buf.value


# 역점역 결과에 항상 깨져서 나오는 고정 패턴 -> 실제 의미로 자동 교정.
# 여기 계속 추가하면 됨.
REVERSE_CORRECTIONS = {
    "ㅍㅍㅍ": "...",
    ".ㅍ.": "...",
    "ㅅㅎ": ")",
    "닾": "다.",
}

# ㅍ받침은 마침표와 점형이 같아서 "몰라요."가 "몰라욮"으로 읽힌다.
# 진짜 ㅍ받침 글자(앞, 옆, 숲, 잎, 깊, 높 ...)만 남기고 나머지는 "받침 뺀 글자 + 마침표"로 고친다.
_REAL_PIEUP = set("앞옆숲잎깊높덮갚짚엎읊릎겊늪섶앺옾")


def _is_word_char(ch: str) -> bool:
    return ch.isalnum()  # 한글/영문/숫자


def _pieup_to_period(text: str) -> str:
    """ㅍ받침 글자를 마침표로 되돌린다.
    진짜 ㅍ받침 글자(앞, 옆 ...)는 뒤에 (공백/줄바꿈 건너뛴) 글자가 이어지면 그대로 두고,
    뒤에 기호만 있거나 아무것도 없으면 '받침 뺀 글자 + .' 으로 고친다(예: 앞 -> 아.)."""
    out = []
    n = len(text)
    for i, ch in enumerate(text):
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172 and code % 28 == 26:
            keep = False
            if ch in _REAL_PIEUP:
                j = i + 1
                while j < n and text[j].isspace():
                    j += 1
                keep = j < n and _is_word_char(text[j])
            if not keep:
                out.append(chr(0xAC00 + code - 26) + ".")
                continue
        out.append(ch)
    return "".join(out)


def apply_reverse_corrections(text: str) -> str:
    for wrong, right in REVERSE_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return _pieup_to_period(text)


_SYMBOLS = set("^$|#[]{}@&*<>_~`")


def _english_looks_valid(s: str) -> bool:
    """영어로 읽은 결과가 말이 되는지 대충 판별(깨진 한글점자를 영어로 읽으면 기호/대문자가 섞여 나옴)."""
    body = s.strip()
    if not body or any(ch in _SYMBOLS for ch in body):
        return False
    words = [w.strip(".,;:!?\"'()-") for w in body.split()]
    words = [w for w in words if w]
    if not words:
        return False
    if sum(c.isalpha() for c in body) < 4:
        return False  # 너무 짧으면 영어라고 확신 못 함 -> 한글로
    for w in words:
        if any(not (c.isalnum() or c in "'-,.") for c in w):
            return False
        if not (w.isascii() and any(c.isalpha() or c.isdigit() for c in w)):
            return False
        if any(c.isupper() for c in w[1:]) and not w.isupper():
            return False  # 단어 중간 대문자 -> 깨진 결과
        if w.isalpha() and len(w) > 2 and not any(c in "aeiouyAEIOUY" for c in w):
            return False
        if w.isalpha() and not _word_plausible(w.lower()):
            return False
    return True


_VOWELS = set("aeiouy")


def _word_plausible(w: str) -> bool:
    """영어 단어로 보이는지 대충 검사(같은 글자 3연속, 자음 5연속 이상, 말이 안 되는 j/q 조합 등)."""
    run = 0
    for i, c in enumerate(w):
        if i >= 2 and w[i - 2] == w[i - 1] == c:
            return False
        run = 0 if c in _VOWELS else run + 1
        if run >= 5:
            return False
        if c == "j" and (i + 1 == len(w) or w[i + 1] not in _VOWELS):
            return False
        if c == "j" and i > 0 and w[i - 1] not in _VOWELS and w[i - 1] != " ":
            return False
        if c == "q" and (i + 1 == len(w) or w[i + 1] != "u"):
            return False
    return True


def reverse_translate_auto(text: str) -> str:
    """줄마다 영어로 읽어서 말이 되면 영어, 아니면 한글 기준으로 읽는다."""
    out = []
    for line in text.splitlines():
        if not line.strip():
            out.append(line)
            continue
        eng = reverse_translate_line(line, 1)
        if _english_looks_valid(eng):
            out.append(eng)
        else:
            out.append(apply_reverse_corrections(reverse_translate_line(line, 0)))
    return "\n".join(out)


def reverse_translate_text(text: str, mode: int = 0) -> str:
    """mode: 0=한글 기본, 1=영어 기본, 2=자동판별."""
    if mode == 2:
        return reverse_translate_auto(text)
    # 한 번에 넣으면 개행이 사라지므로, 줄 단위로 처리해서 다시 이어붙인다.
    joined = "\n".join(reverse_translate_line(line, mode) for line in text.splitlines())
    return apply_reverse_corrections(joined) if mode == 0 else joined


def read_source_file(path: str) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(path, "r", encoding="latin-1", errors="replace") as f:
        return f.read()


def process_file(src_path: str) -> str:
    text = read_source_file(src_path)
    result = reverse_translate_text(text, 0)

    base, _ext = os.path.splitext(src_path)
    out_path = f"{base}(역점역).txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)
    return out_path


def on_pick_file():
    src_path = filedialog.askopenfilename(
        title="역점역할 파일 선택",
        filetypes=[("텍스트 파일", "*.txt;*.brf;*.blb;*.blt"), ("모든 파일", "*.*")],
    )
    if not src_path:
        return
    try:
        out_path = process_file(src_path)
    except Exception as e:
        messagebox.showerror("오류", f"처리 중 오류가 발생했습니다:\n{e}")
        return
    messagebox.showinfo("완료", f"역점역 완료:\n{out_path}")


def main():
    root = tk.Tk()
    root.title("점역 역점역기")
    root.geometry("300x120")

    tk.Label(root, text="점자(BRF) 텍스트 파일을 선택하면\n같은 폴더에 (역점역).txt로 저장합니다.",
             justify="center").pack(pady=10)
    tk.Button(root, text="파일 선택", width=20, height=2, command=on_pick_file).pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    main()
