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

# exe로 묶였으면 안에 들어있는 jydbt\trans (점사랑 DLL)를 쓰고,
# 소스로 돌릴 땐 이 폴더 옆의 BrailleTransLibrary(없으면 설치된 점사랑7)를 쓴다.
if getattr(sys, "frozen", False):
    BASE = os.path.join(sys._MEIPASS, "jydbt", "trans")
else:
    _here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BrailleTransLibrary")
    BASE = os.environ.get(
        "BRL_BASE",
        _here if os.path.isdir(_here) else r"C:\Program Files (x86)\Jeomsarang7",
    )
# 예전 점사랑 DLL 방식 (JYDBT 엔진을 못 쓸 때만). 못 읽어도 JYDBT 쪽은 그대로 동작한다.
_rev = None
try:
    os.add_dll_directory(BASE)
    _dll = ctypes.CDLL(os.path.join(BASE, "BrailleTransMain.dll"))
    _rev = _dll.BrailleTransBrailleToString
    _rev.restype = ctypes.c_int
    _rev.argtypes = [ctypes.c_char_p, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_int]
except OSError:
    _rev = None


def reverse_translate_line(line: str, mode: int = 0) -> str:
    """BRF ascii 한 줄을 역점역. 소문자로 바꿔야 정상 동작함(중요).
    mode: 0=기본 한글(영어표시 만나면 영어), 1=기본 영어."""
    if not line.strip():
        # 빈 줄(공백만 있는 줄 포함)을 그대로 넣으면 DLL이 쓰레기값을 내놓음 -> 건너뜀
        return line
    if _rev is None:
        raise RuntimeError("예전 점사랑 DLL 을 읽지 못했습니다 (JYDBT 엔진을 쓰세요)")
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


# ---- JYDBT 엔진 (jydbt-rev.exe 호출). 찾지 못하면 None -> 예전 DLL 방식으로 돌아간다 ----
def _jydbt_rev_exe():
    cands = []
    if os.environ.get("JYDBT_REV"):
        cands.append(os.environ["JYDBT_REV"])
    if getattr(sys, "frozen", False):
        cands.append(os.path.join(sys._MEIPASS, "jydbt", "jydbt-rev.exe"))  # exe 안에 묶인 것
        cands.append(os.path.join(os.path.dirname(sys.executable), "jydbt-rev.exe"))
    here = os.path.dirname(os.path.abspath(__file__))
    cands.append(os.path.join(here, "jydbt", "jydbt-rev.exe"))  # 소스로 돌릴 때 (exe 와 같은 묶음 폴더)
    cands.append(os.path.join(here, "jydbt-rev.exe"))
    cands.append(r"E:\파이썬\JYDBT\target\release\jydbt-rev.exe")  # 개발 PC 의 빌드 위치
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def jydbt_available() -> bool:
    return _jydbt_rev_exe() is not None


def _jydbt_env():
    """묶인 점사랑 도우미(32비트 jydbt-trans.exe)의 위치를 jydbt-rev 에 알려 준다. 설치된 JYDBT 가 필요 없게."""
    env = dict(os.environ)
    base = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    trans = os.path.join(base, "jydbt", "trans", "jydbt-trans.exe")
    if os.path.isfile(trans):
        env["JYDBT_TRANS_EXE"] = trans
    return env


def _run_jydbt(args):
    import subprocess
    exe = _jydbt_rev_exe()
    if exe is None:
        raise RuntimeError("jydbt-rev.exe 를 찾지 못했습니다")
    r = subprocess.run([exe] + args, capture_output=True, env=_jydbt_env())
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip() or "JYDBT 도구 오류")


def reverse_jydbt_text(text: str) -> str:
    """BRF 글(상자에 있는 글)을 JYDBT 엔진으로 역점역한다."""
    import tempfile
    fd, brf = tempfile.mkstemp(suffix=".brf")
    os.close(fd)
    fd2, out = tempfile.mkstemp(suffix=".txt")
    os.close(fd2)
    try:
        with open(brf, "wb") as f:
            f.write(text.encode("latin-1", errors="replace"))
        _run_jydbt([brf, out])
        with open(out, "r", encoding="utf-8") as f:
            return f.read()
    finally:
        for x in (brf, out):
            try:
                os.remove(x)
            except OSError:
                pass


def dxb_to_brf_text(path: str) -> str:
    """dxb 파일을 BRF 글(쪽 나눔 포함)로 바꾼다. 글자수세기 화면이 BRF 처럼 쪽을 고르게 하려고."""
    import tempfile
    fd, out = tempfile.mkstemp(suffix=".brf")
    os.close(fd)
    try:
        _run_jydbt(["--brf", path, out])
        with open(out, "rb") as f:
            return f.read().decode("latin-1")
    finally:
        try:
            os.remove(out)
        except OSError:
            pass


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
