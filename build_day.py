# -*- coding: utf-8 -*-
"""
segment_test.py가 뽑아낸 날짜별 원문(day txt)을 완성본 포맷으로 변환한다.
평일(월~금) 전용. 토요일은 별도 로직 필요.
"""
import re
import sys
from pathlib import Path

ANCHOR_TRANSLATE = "번역을 보고 영어로 생각해 보세요."
ANCHOR_BOLD = "진하게 표시된 단어들에 힘을 주어 약간 띄우듯 발음해 보세요."
ANCHOR_INOTHER = "같은 뜻을 다른 문장으로 바꾸어 만들어 봅니다."
ANCHOR_PRACTICE = "문장의 핵심 단어를 바꿔 가며 문장력을 길러 봅니다."

NOISE_EXACT = {"Easy English"}


PUA_BULLET = re.compile(r"^[-]\s*")


def clean(lines):
    out = []
    for l in lines:
        l = PUA_BULLET.sub("", l.strip())
        if l and l not in NOISE_EXACT:
            out.append(l)
    return out


def join_wrapped(lines):
    """마침표/물음표/느낌표로 끝나지 않는 줄은 다음 줄과 이어붙인다 (단순 워드랩 복원)."""
    out = []
    buf = ""
    for l in lines:
        buf = (buf + " " + l).strip() if buf else l
        if re.search(r"[.!?]$", buf) or re.search(r"[.!?][)\"']$", buf):
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


def split_by_anchor(lines, anchor):
    for i, l in enumerate(lines):
        s = l.strip()
        if s == anchor or (s.endswith(anchor) and len(s) - len(anchor) <= 6):
            return lines[:i], [anchor] + lines[i + 1:]
    raise ValueError(f"앵커를 찾지 못함: {anchor}")


def parse_learning_points(chunk):
    """[teaser 조각들...] + intro 문단 (앵커 이전)"""
    lines = clean(chunk)
    # 마지막 조인된 문단이 intro, 그 전 것들은 표지 teaser(이미 차례에서 처리됨)이므로
    # 여기서는 전체를 한 문단으로 합쳐서 intro로 취급한다.
    joined = join_wrapped(lines)
    return joined  # 리스트(문단들)


def parse_dialogue_and_vocab(chunk):
    """앵커(번역을...) 부터 다음 청크 시작 전까지: 한글대화 + Vocab + 영어대화"""
    lines = clean(chunk)
    assert lines[0].strip() == ANCHOR_TRANSLATE
    rest = lines[1:]

    # 한글 대화: "이름 대사" 형태 줄들이 연속으로 나오다가, Vocab 항목(콜론 포함)이 시작되면 끝
    kr_dialogue = []
    i = 0
    while i < len(rest) and ":" not in rest[i] and not re.match(r"^[a-zA-Z].*:", rest[i]):
        # 한글 대화 줄인지 판단: 첫 단어가 한글 이름이고 그 뒤에 대사가 이어짐
        if re.match(r"^[가-힣]+ ", rest[i]) or re.match(r"^[가-힣]+:", rest[i]):
            kr_dialogue.append(rest[i])
            i += 1
        else:
            break

    # Vocab: 소문자로 시작하는 단어+뜻 줄, 또는 대문자로 시작하는 예문(뒤에 한글 번역 포함) 줄.
    # 대화는 "Name 대문자시작문장" (이름+영어문장, 한글 번역 없음) 형태로 시작하면 끝.
    NAME_DIALOGUE = re.compile(r"^[A-Z][a-z]+ [A-Z].*[.?!]$")
    vocab = []
    while i < len(rest):
        l = rest[i].strip()
        if re.match(r"^[a-z]", l):  # 소문자 시작 = vocab 단어/뜻
            # 가끔 원본이 "단어 뜻 [예문불릿] 예문시작"을 한 줄에 붙여서 내보냄
            # (예: "item 개별 물품  This is the most popular item...") -> 분리.
            # 중간에 "예:" 불릿(PUA 특수문자, 보통 줄 맨 앞에서만 제거됨)이 끼어있거나
            # 스페이스 2개 이상인 경우 둘 다 분리 지점으로 본다.
            m = re.search(r"(?:\s{2,}|[-]+)\s*([A-Z].*)$", l)
            if m:
                vocab.append(l[:m.start()].rstrip())
                vocab.append(m.group(1))
            else:
                vocab.append(l)
            i += 1
        elif re.match(r"^[A-Z]", l) and re.search(r"[가-힣]", l):  # 예문(영어+한글 번역 같은 줄)
            vocab.append(l)
            i += 1
        elif NAME_DIALOGUE.match(l):
            break
        else:
            # 대문자로 시작하는 예문 줄은 "끝문장부호 + 한글 번역"이 둘 다 붙어야
            # 완성으로 본다 (예문 영어와 한글 번역이 서로 다른 원본 줄에 나뉘어
            # 나오는 경우가 있음). 그 외(단어:뜻 줄)는 끝문장부호 없이도 완성.
            if vocab and re.match(r"^[A-Z]", vocab[-1]):
                incomplete = not (re.search(r"[.!?]$", vocab[-1]) and re.search(r"[가-힣]", vocab[-1]))
            else:
                incomplete = vocab and not re.search(r"[.!?]$", vocab[-1])
            if incomplete:
                vocab[-1] = vocab[-1] + " " + l
                i += 1
            else:
                break

    easy_talk_en = join_wrapped(rest[i:])
    return kr_dialogue, vocab, easy_talk_en


def parse_sentence_pattern(chunk):
    """앵커(진하게...) 부터: 패턴 2개. 각 패턴은 '「...」' 헤더 -> 뜻풀이 -> '숫자'(prefix) -> 예문+번역 -> 설명 -> 예시 2쌍"""
    lines = clean(chunk)
    assert lines[0].strip() == ANCHOR_BOLD
    rest = lines[1:]

    patterns = []
    idx = [i for i, l in enumerate(rest) if l.startswith("「")]
    idx.append(len(rest))
    for n in range(len(idx) - 1):
        seg = rest[idx[n]:idx[n + 1]]
        patterns.append(seg)
    return patterns


def parse_in_other_words(chunk):
    """앵커(같은 뜻을...) 부터: intro + item*3(대체1,대체2,원문,번역, 그리고 뒤에 번호) + Useful Tip"""
    lines = clean(chunk)
    assert lines[0].strip() == ANCHOR_INOTHER
    rest = lines[1:]

    items = []
    buf = []
    for l in rest:
        if re.fullmatch(r"\d", l.strip()):
            items.append(buf)
            buf = []
        else:
            buf.append(l)
    # buf에 남은 것 = Useful Tip 부분 (item 3의 번호 "3"이 나온 뒤 이어지는 설명)
    useful_tip = buf
    return items, useful_tip


def parse_practice_challenge(chunk):
    """앵커(문장의 핵심...) 부터: Practice(2) + Challenge(N) + Now You Talk(5) + Answers"""
    lines = clean(chunk)
    assert lines[0].strip() == ANCHOR_PRACTICE
    return lines[1:]


def build_day(raw_lines):
    lines = clean(raw_lines)
    chunk_lp, rest = split_by_anchor(lines, ANCHOR_TRANSLATE)
    chunk_dv, rest = split_by_anchor(rest, ANCHOR_BOLD)  # chunk_dv: 번역~ 대화/vocab
    chunk_sp, rest = split_by_anchor(rest, ANCHOR_INOTHER)
    chunk_iow, rest = split_by_anchor(rest, ANCHOR_PRACTICE)
    chunk_prac = rest

    intro = parse_learning_points(chunk_lp)
    kr_dialogue, vocab, easy_talk_en = parse_dialogue_and_vocab(chunk_dv)
    patterns = parse_sentence_pattern(chunk_sp)
    iow_items, useful_tip = parse_in_other_words(chunk_iow)
    tail = parse_practice_challenge(chunk_prac)

    return {
        "intro": intro,
        "kr_dialogue": kr_dialogue,
        "vocab": vocab,
        "easy_talk_en": easy_talk_en,
        "patterns": patterns,
        "iow_items": iow_items,
        "useful_tip": useful_tip,
        "tail_raw": tail,
    }


def format_vocab(vocab_lines):
    """vocab: ['word 뜻', ..., '예문(영어+한글)', ...] -> '단어: 뜻' + '예: 영어 (한글)' 줄로 변환"""
    out = []
    for l in vocab_lines:
        if re.match(r"^[A-Z]", l) and re.search(r"[.!?]\s", l) and re.search(r"[가-힣]", l):
            # 예문: "영어문장. 한글번역." -> "예: 영어문장. (한글번역.)"
            m2 = re.match(r"^(.*?[.!?])\s+(.*)$", l)
            if m2:
                out.append(f"예: {m2.group(1)} ({m2.group(2)})")
                continue
        m = re.search(r"[~가-힣]", l)
        if m:
            cut = m.start()
            eng = l[:cut].rstrip()
            kor = l[cut:].strip()
            out.append(f"{eng}: {kor}")
        else:
            out.append(l)
    return out


def format_in_other_words(items):
    """각 item: [대체1, 대체2, 원문, 번역(괄호)] -> '숫자 원문 (번역)' + 대체1 + 대체2"""
    out = []
    for n, item in enumerate(items, 1):
        if len(item) < 4:
            out.append(" / ".join(item))
            continue
        alt1, alt2, orig, trans = item[0], item[1], item[2], item[3]
        out.append(f"{n} {orig} {trans}")
        out.append(alt1)
        out.append(alt2)
    return out


ANSWER_SUMMARY = re.compile(r"^1\.\s")


def format_tail(tail_lines):
    """tail_raw = [Challenge용 한글+힌트 2개] + [Practice 슬롯 2개] + [NowYouTalk 한글+힌트 5개]
    + [Challenge답 요약] + [NowYouTalk답 요약] + (다음날 제목 bleed, 버림)"""
    lines = list(tail_lines)

    # 1) 뒤쪽의 정답 요약 문단(“1. ...”로 시작) 2개를 찾아 분리, 그 뒤는 다음날 bleed로 버림
    ans_idx = [i for i, l in enumerate(lines) if ANSWER_SUMMARY.match(l)]
    if len(ans_idx) >= 2:
        challenge_ans = " ".join(lines[ans_idx[0]:ans_idx[1]])
        # Now You Talk는 항상 5개 항목 -> "5." 표시가 나오는 줄까지만 이어붙이고 그 뒤(다음날 bleed)는 버림
        j = ans_idx[1]
        nyt_parts = []
        while j < len(lines):
            nyt_parts.append(lines[j])
            if re.search(r"5\.", lines[j]):
                break
            j += 1
        nyt_ans = " ".join(nyt_parts)
        head = lines[:ans_idx[0]]
    else:
        challenge_ans, nyt_ans, head = "", "", lines

    # 2) head를 세 블록으로: Challenge용(한글+힌트 쌍), Practice 슬롯(번호 뒤 여러줄), NowYouTalk용(한글+힌트 5쌍)
    # Practice 슬롯 블록은 "≐≐"로 시작하는 줄들을 포함하는 구간
    prac_start = next((i for i, l in enumerate(head) if l.startswith("≐≐")), None)
    if prac_start is not None:
        # 슬롯 블록의 시작은 그 앞의 "숫자 " 로 시작하는 줄부터
        n = prac_start
        while n > 0 and not re.match(r"^[12] ", head[n]):
            n -= 1
        challenge_hint_lines = head[:n]
        # 슬롯 블록 끝: 마지막 ≐≐ 줄 다음부터 NowYouTalk 시작
        m = len(head)
        for i in range(len(head) - 1, -1, -1):
            if head[i].startswith("≐≐"):
                m = i + 1
                break
        practice_lines = head[n:m]
        nyt_hint_lines = head[m:]
    else:
        challenge_hint_lines, practice_lines, nyt_hint_lines = head, [], []

    # Challenge: "N 한글" + "(힌트)" 쌍 -> "N 한글 (힌트)" + "--------"
    challenge_out = []
    i = 0
    while i < len(challenge_hint_lines) - 1:
        kor, hint = challenge_hint_lines[i], challenge_hint_lines[i + 1]
        challenge_out.append(f"{kor} {hint}")
        challenge_out.append("--------")
        i += 2

    # Practice: 번호 블록마다 [영어조각들.../대체어들...] + [≐≐한글...] -> "N 영어(대체/옵션) ..." + 한글들
    practice_out = []
    blocks = []
    cur = []
    for l in practice_lines:
        if re.match(r"^[12] ", l) and cur:
            blocks.append(cur)
            cur = [l]
        else:
            cur.append(l)
    if cur:
        blocks.append(cur)
    for block in blocks:
        eng_lines = [l for l in block if not l.startswith("≐≐")]
        kor_lines = [l[2:].strip() for l in block if l.startswith("≐≐")]
        num = eng_lines[0][0]
        eng_lines[0] = eng_lines[0][2:]
        n_slots = len(kor_lines)
        cols = [eng_lines[i::n_slots] if n_slots else eng_lines for i in range(max(n_slots, 1))]
        # eng_lines는 "베이스 조각, 옵션1a, 옵션1b, 옵션2a, 옵션2b..." 식으로 슬롯별 세로 나열됨
        # 슬롯 개수만큼 그룹으로 묶어서 (a/b/c) 형태로 합친다
        slot_count = len(eng_lines) // n_slots if n_slots else 1
        groups = [eng_lines[g * n_slots:(g + 1) * n_slots] for g in range(slot_count)]
        sentence = " ".join(g[0] if len(g) == 1 else "(" + "/".join(g) + ")" for g in groups)
        practice_out.append(f"{num} {sentence}")
        practice_out.extend(kor_lines)

    # Now You Talk: "N 한글" + "(힌트)" 쌍 (마지막 5번은 예외: 힌트 없이 완성된 영어 문장이 옴)
    nyt_out = []
    i = 0
    item5_sentence = None
    while i < len(nyt_hint_lines):
        l = nyt_hint_lines[i]
        if i + 1 < len(nyt_hint_lines) and nyt_hint_lines[i + 1].startswith("("):
            nyt_out.append(f"{l} {nyt_hint_lines[i + 1]}")
            nyt_out.append("--------")
            i += 2
        else:
            nyt_out.append(l)
            if i + 1 < len(nyt_hint_lines):
                item5_sentence = nyt_hint_lines[i + 1]
                nyt_out.append(item5_sentence)
                i += 2
            else:
                i += 1

    # 5번 항목: 정답 요약("5. word1, word2")에 나온 단어들을 문장에서 "----"로 치환
    if item5_sentence is not None:
        m = re.search(r"5\.\s*([^.]+)", nyt_ans)
        if m:
            words = [w.strip() for w in m.group(1).split(",")]
            sent = item5_sentence
            for w in words:
                sent = re.sub(rf"\b{re.escape(w)}\b", "----", sent, count=1)
            nyt_out[-1] = sent.strip()

    return challenge_out, practice_out, nyt_out, challenge_ans, nyt_ans


def _fix_indent(line):
    """섹션 헤더(4칸 들여쓰기)와 빈 줄은 그대로 두고, 그 외 본문 줄은 전부
    2칸 들여쓰기로 맞춘다 (완성본은 본문 줄마다 '  ' 접두가 붙어 있음)."""
    if not line or line.startswith("    ") or line.startswith("  "):
        return line
    return "  " + line


def _clean_punct(lines):
    lines = [_fix_indent(l) for l in lines]
    text = "\n".join(lines)
    text = re.sub(r"\s+([.,?!])", r"\1", text)
    return text.split("\n")


def assemble_day_pages(parsed, title_en, title_kr, day_label):
    """평일 하루치를 6개의 인쇄 페이지 단위(리스트)로 나눠서 반환한다."""
    page1 = [f"    {day_label}", f"  {title_en} ({title_kr})", "",
             "    Learning Points! (이것이 포인트!)"]
    page1.extend(parsed["intro"])
    page1.append("")
    page1.append("  번역을 보고 영어로 생각해 보세요.")
    page1.extend(parsed["kr_dialogue"])

    page2 = ["    Vocab (미리 알고 가세요.)"]
    page2.extend(format_vocab(parsed["vocab"]))
    page2.append("")
    page2.append("    Easy Talk (상황별 대화)")
    page2.append("  진하게 표시된 단어들에 힘을 주어 약간 띄우듯 발음해 보세요.")
    page2.extend(parsed["easy_talk_en"])

    page3 = ["    Sentence Pattern (말문을 여는 패턴)"]
    for n, pat in enumerate(parsed["patterns"], 1):
        body = [l for l in pat if not re.fullmatch(r"\d", l)]
        m = re.match(r"^(「[^」]+」)\s*(.*)$", body[0])
        header = m.group(1)
        if m.group(2):
            trans, tail_lines = m.group(2), body[1:]
        else:
            trans, tail_lines = body[1], body[2:]
        page3.append(f"{n} {header}: {trans}")
        page3.extend(tail_lines)
        page3.append("")

    page4 = ["    In Other Words (같은 뜻 다른 표현)",
             "  같은 뜻을 다른 문장으로 바꾸어 만들어 봅니다."]
    page4.extend(format_in_other_words(parsed["iow_items"]))
    page4.append("")
    page4.append("    Useful Tip")
    page4.extend(parsed["useful_tip"])

    challenge_out, practice_out, nyt_out, challenge_ans, nyt_ans = format_tail(parsed["tail_raw"])
    page5 = ["    Practice Makes Perfect! (일취월장 문장력!)",
             "  문장의 핵심 단어를 바꿔 가며 문장력을 길러 봅니다."]
    page5.extend(practice_out)
    page5.append("")
    page5.append("    Challenge! (문장력 훈련!)")
    page5.extend(challenge_out)

    page6 = ["    Now You Talk! (여러분이 말해 보세요!)"]
    page6.extend(nyt_out)
    page6.append("")
    page6.append("    Answers")
    page6.append(f"  Challenge {challenge_ans}")
    page6.append(f"  Now You Talk {nyt_ans}")

    pages = [page1, page2, page3, page4, page5, page6]
    return ["\n".join(_clean_punct(p)) for p in pages]


def assemble_day(parsed, title_en, title_kr, day_label):
    """하위호환용: 6페이지를 하나로 이어붙인 문자열."""
    return "\n\n".join(assemble_day_pages(parsed, title_en, title_kr, day_label))


if __name__ == "__main__":
    path = Path(sys.argv[1])
    raw = path.read_text(encoding="utf-8").splitlines()
    result = build_day(raw)
    if len(sys.argv) > 2 and sys.argv[2] == "--json":
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(assemble_day(result, "That sounds easy enough.", "생각보다 쉽겠어요.", "01 Tuesday"))
