# -*- coding: utf-8 -*-
"""
토요일(Weekly Review) 원문 -> 완성본 포맷.
원본은 순서가 섞여 있어서(대화 내용 -> 라벨 -> 날짜앵커 순), 앵커를 기준으로
서브데이(월~금 5개)를 나누고 각 줄을 패턴으로 분류해서 재조립한다.
"""
import re
import sys
from pathlib import Path

WEEKDAY_ABBR = re.compile(r"^(Mon|Tue|Wed|Thu|Fri)\.$")
BARE_NUM = re.compile(r"^\d$")
KOR_DIALOGUE = re.compile(r"^[가-힣]+ .+")
ENG_DIALOGUE = re.compile(r"^[A-Z][a-z]+\b")
ANSWER_LINE = re.compile(r"^대화\s*\d+\.")
YONGYONG_ITEM = re.compile(r"^응용\s*(\d)\s+(.*)$")
NOISE_LABELS = {"대화", "Easy English"}


SPLIT_KOR_ENG = re.compile(r"(?<=[.!?])\s+(?=[A-Z][a-z]+\s)")


def clean(lines):
    out = []
    for l in lines:
        l = l.strip()
        if not l:
            continue
        # 한글 대사 끝 + 영어 대사 시작이 한 줄에 붙어 나오는 원본 irregularity를 분리
        if re.search(r"[가-힣][.!?]?\s+[A-Z][a-z]+\s", l) and re.search(r"[가-힣]", l):
            parts = SPLIT_KOR_ENG.split(l)
            out.extend(p for p in parts if p)
        else:
            out.append(l)
    return out


def find_subday_anchors(lines):
    """day_num 줄 -> weekday_abbr 줄 -> title(한글) 줄 로 이어지는 지점들을 찾는다."""
    anchors = []
    for i in range(len(lines) - 2):
        if re.fullmatch(r"\d{2}", lines[i]) and WEEKDAY_ABBR.match(lines[i + 1]):
            anchors.append((i, lines[i], lines[i + 1], lines[i + 2]))
    return anchors


FULL_CAPS_WEEKDAY = re.compile(r"^(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY)$")
SHORT_KOR_PREFIX = re.compile(r"^[가-힣]{1,8}[,.]?\s")


def looks_like_dialogue_start(lines, i, window=8):
    """lines[i]가 실제 대화 시작인지: 짧은 화자-접두 패턴이고, 근처(window줄 안)에
    '1/2/3/4' 단독 숫자 블록(빈칸 번호)이 나오는지로 판단한다 (화자 이름 화이트리스트에 의존하지 않음)."""
    if not SHORT_KOR_PREFIX.match(lines[i]):
        return False
    for j in range(i, min(i + window, len(lines) - 3)):
        if all(re.fullmatch(r"\d", lines[j + k]) for k in range(4)) and \
           [lines[j], lines[j + 1], lines[j + 2], lines[j + 3]] == ["1", "2", "3", "4"]:
            return True
    return False


def extract_bled_essay_from_tail(weekday_lines):
    """평일 파일 끝에 다음 토요일의 인덱스+에세이가 새어 들어간 경우, 그 에세이 텍스트만 회수한다.
    (제목/인덱스는 차례에서 이미 확보하므로 필요 없음) 없으면 빈 문자열."""
    for i in range(len(weekday_lines) - 1):
        if re.fullmatch(r"\d{2}", weekday_lines[i]) and FULL_CAPS_WEEKDAY.match(weekday_lines[i + 1]):
            tail = weekday_lines[i:]
            j = 0
            while j + 1 < len(tail) and re.fullmatch(r"\d{2}", tail[j]) and FULL_CAPS_WEEKDAY.match(tail[j + 1]):
                j += 4
            return " ".join(tail[j:])
    return ""


def strip_index_and_essay(lines):
    """맨 앞 'Weekly Review 미니 인덱스'(일자+요일전체대문자+영문제목+한글제목)와
    그 뒤 에세이 문단을 걷어내고, 진짜 첫 서브데이 대화가 시작하는 지점부터 반환한다.
    인덱스에서 영문/한글 제목도 함께 추출해서 (일자,요일): (영문,한글) 딕셔너리로 반환한다."""
    index_titles = {}
    i = 0
    while i + 1 < len(lines) and re.fullmatch(r"\d{2}", lines[i]) and FULL_CAPS_WEEKDAY.match(lines[i + 1]):
        day, wd_full = lines[i], lines[i + 1]
        j = i + 2
        title_parts = []
        seen_kr = False
        while j < len(lines):
            if j + 1 < len(lines) and re.fullmatch(r"\d{2}", lines[j]) and FULL_CAPS_WEEKDAY.match(lines[j + 1]):
                break
            title_parts.append(lines[j])
            if re.search(r"[가-힣]", lines[j]):
                seen_kr = True
            j += 1
            # 한글 번역 줄까지 나왔고 마침표/물음표로 끝났으면 제목 블록은 여기서 끝
            if seen_kr and re.search(r"[.!?]$", title_parts[-1]):
                break
            if len(title_parts) >= 6:  # 안전장치
                break
        # 영문(대문자 시작)과 한글로 분리
        en_parts = [p for p in title_parts if re.match(r"^[A-Z]", p)]
        kr_parts = [p for p in title_parts if re.search(r"[가-힣]", p)]
        title_en = " ".join(en_parts).strip()
        title_kr = " ".join(kr_parts).strip()
        index_titles[day] = (title_en, title_kr)
        i = j

    if i == 0:
        return lines, "", {}  # 인덱스가 없는 형태(이미 걸러진 파일) -> 그대로 반환

    # 에세이 구간 건너뛰기: 짧은 화자-접두 패턴 + 근처 1/2/3/4 빈칸번호로 진짜 대화 시작을 찾는다
    for j in range(i, len(lines)):
        if looks_like_dialogue_start(lines, j):
            essay = " ".join(lines[i:j])
            return lines[j:], essay, index_titles
    return lines[i:], "", index_titles


def split_subdays(lines):
    anchors = find_subday_anchors(lines)
    chunks = []
    start = 0
    for (idx, day_num, weekday_abbr, title_kr) in anchors:
        end = idx + 3
        chunks.append({
            "day_num": day_num,
            "weekday_abbr": weekday_abbr,
            "title_kr": title_kr,
            "lines": lines[start:idx],  # 앵커 이전까지가 이 서브데이의 내용
        })
        start = end
    return chunks, lines[start:]  # 마지막 잔여(다음 섹션 시작 등)


YONGYONG_ANSWER_ONLY = re.compile(r"^응용\s+\d+\.\s")
BARE_ITEM = re.compile(r"^(\d)\s+(.*)$")


def classify_subday(lines):
    kr_dialogue = []
    en_dialogue = []
    yongyong_items = []
    answer_dae = ""
    answer_yong = ""
    in_yongyong = False

    for l in lines:
        if l in NOISE_LABELS:
            continue
        if BARE_NUM.fullmatch(l):
            continue
        if ANSWER_LINE.match(l):
            if "응용" in l:
                dae_part, yong_part = l.split("응용", 1)
                answer_dae = dae_part.replace("대화", "").strip()
                answer_yong = yong_part.strip()
            else:
                answer_dae = l.replace("대화", "").strip()
            in_yongyong = False
            continue
        if YONGYONG_ANSWER_ONLY.match(l):
            answer_yong = l[len("응용"):].strip()
            in_yongyong = False
            continue
        m = YONGYONG_ITEM.match(l)
        if m:
            yongyong_items.append((m.group(1), m.group(2)))
            in_yongyong = True
            continue
        if in_yongyong:
            m2 = BARE_ITEM.match(l)
            if m2:
                yongyong_items.append((m2.group(1), m2.group(2)))
                continue
        if ENG_DIALOGUE.match(l):
            en_dialogue.append(l)
            continue
        if KOR_DIALOGUE.match(l):
            kr_dialogue.append(l)
            continue
        # 그 외 줄바꿈 조각(문장 이어지는 부분)은 직전 항목에 이어붙인다
        if en_dialogue and not kr_dialogue_is_last(kr_dialogue, en_dialogue):
            en_dialogue[-1] = en_dialogue[-1] + " " + l
        elif kr_dialogue:
            kr_dialogue[-1] = kr_dialogue[-1] + " " + l

    return {
        "kr_dialogue": kr_dialogue,
        "en_dialogue": en_dialogue,
        "yongyong": yongyong_items,
        "answer_dae": answer_dae,
        "answer_yong": answer_yong,
    }


def kr_dialogue_is_last(kr, en):
    return False  # en_dialogue 우선 병합 (대부분 en 뒤에 wrap됨)


def _fix_indent(line):
    """섹션 헤더(4칸)와 빈 줄은 그대로, 그 외 본문 줄은 2칸 들여쓰기로 맞춘다."""
    if not line or line.startswith("    ") or line.startswith("  "):
        return line
    return "  " + line


def format_subday(day_num, weekday_abbr, title_kr, parsed):
    out = [f"    {day_num} {weekday_abbr} {title_kr}", "    (대화)"]
    out.extend(parsed["kr_dialogue"])
    out.append("")
    out.extend(parsed["en_dialogue"])
    out.append("")
    out.append("    (응용)")
    for num, text in parsed["yongyong"]:
        out.append(f"{num} {text}")
        out.append("--------")
    out.append("")
    out.append("    ANSWERS")
    out.append(f"  (대화) {parsed['answer_dae']}")
    out.append(f"  (응용) {parsed['answer_yong']}")
    out = [_fix_indent(l) for l in out]
    return "\n".join(out)


def build_saturday(raw_lines):
    lines = clean(raw_lines)
    lines, essay, index_titles = strip_index_and_essay(lines)
    chunks, remainder = split_subdays(lines)

    # chunks[i]["lines"]에는 chunks[i]의 대화 + chunks[i-1]의 응용/ANSWERS가 섞여 있음
    # (응용/ANSWERS가 한 칸 뒤로 밀려서 나오는 구조) -> 한 칸씩 당겨서 재배치한다.
    parsed_list = [classify_subday(c["lines"]) for c in chunks]
    remainder_parsed = classify_subday(remainder)

    outputs = []
    for i, c in enumerate(chunks):
        dialogue_part = parsed_list[i]
        yy_part = parsed_list[i + 1] if i + 1 < len(chunks) else remainder_parsed
        merged = {
            "kr_dialogue": dialogue_part["kr_dialogue"],
            "en_dialogue": dialogue_part["en_dialogue"],
            "yongyong": yy_part["yongyong"],
            "answer_dae": yy_part["answer_dae"],
            "answer_yong": yy_part["answer_yong"],
        }
        outputs.append(format_subday(c["day_num"], c["weekday_abbr"], c["title_kr"], merged))
    day_list = [(c["day_num"], c["weekday_abbr"]) for c in chunks]
    return essay, day_list, outputs, index_titles  # outputs: 서브데이 1개당 1페이지짜리 문자열 리스트


if __name__ == "__main__":
    path = Path(sys.argv[1])
    raw = path.read_text(encoding="utf-8").splitlines()
    essay, day_list, pages, index_titles = build_saturday(raw)
    print("[에세이]", essay)
    print("[요일목록]", day_list)
    print("\n\n".join(pages))
