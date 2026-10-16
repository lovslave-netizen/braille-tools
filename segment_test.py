# -*- coding: utf-8 -*-
"""
하루 단위 구간 분리 테스트: 실제 본문 시작점부터 요일 경계를 찾아
day별로 원문 paragraph를 잘라서 JSON으로 덤프한다.
(섹션 내부 포맷팅은 아직 안 함 - 경계 탐지만 검증)
"""
import sys
import re
import json
from pathlib import Path
import docx

WEEKDAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"}

FOOTER_PATTERNS = [
    re.compile(r"^\d{1,3}\s+Easy English$"),
    re.compile(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)\s+\d{2}\s+\d{1,3}$"),
]


def is_footer(line):
    return any(p.match(line) for p in FOOTER_PATTERNS)


DAY_TAIL = re.compile(r"^(.*?)(?:\s|^)(\d{2})$")
APPENDIX_HEADER = re.compile(r"핵심\s*패턴\s*리뷰")


def find_appendix_start(paras):
    for i, p in enumerate(paras):
        if APPENDIX_HEADER.search(p):
            return i
    return None


def find_real_start(paras):
    """'구성 및 학습 Tips!' 고정 샘플 이후, 진짜 반복되는 요일 패턴이 시작하는 지점을 찾는다.
    날짜 숫자가 앞 문단 끝에 붙어버린 경우도 인식한다 (예: '...넣어 봐. 12')."""
    hits = []  # (day_start_idx, day_num, prefix_leftover_or_None)
    for i in range(len(paras) - 1):
        if paras[i + 1] not in WEEKDAYS:
            continue
        if re.fullmatch(r"\d{2}", paras[i]):
            hits.append((i, paras[i], None))
        else:
            m = DAY_TAIL.match(paras[i])
            if m:
                hits.append((i, m.group(2), m.group(1).strip()))
    if len(hits) < 2:
        raise ValueError("요일 시작 패턴을 충분히 찾지 못했습니다.")
    return hits[1], hits


def _extract_title(paras, idx, leftover):
    """요일 시작 앵커(idx)보다 바로 앞에 있는 영문 제목/한글 번역을 뽑는다.
    (날짜 숫자가 한글 번역 줄 끝에 붙어버린 경우 - leftover - 는 그 줄 자체가
    한글 번역이고, 그 앞줄(들)이 영문 제목이다.) 영문 제목이 여러 줄로
    줄바꿈되어 있는 경우를 대비해, 영문으로 시작하는 줄을 계속 거슬러 올라가며
    합친다."""
    if leftover:
        title_kr = leftover
        en_end = idx - 1
    else:
        title_kr = paras[idx - 1].strip() if idx - 1 >= 0 else ""
        en_end = idx - 2

    en_parts = []
    k = en_end
    while k >= 0 and re.match(r"^[A-Za-z]", paras[k].strip()) and not is_footer(paras[k].strip()):
        en_parts.insert(0, paras[k].strip())
        k -= 1
    title_en = " ".join(en_parts)
    return title_en.strip(), title_kr.strip()


def segment_days(paras, start_idx, hits, appendix_idx):
    days = []
    boundaries = [h for h in hits if h[0] >= start_idx]
    doc_end = appendix_idx if appendix_idx is not None else len(paras)
    for n, (idx, day_num, leftover) in enumerate(boundaries):
        end = boundaries[n + 1][0] if n + 1 < len(boundaries) else doc_end
        weekday = paras[idx + 1]
        content = [p for p in paras[idx + 2:end] if p and not is_footer(p)]
        title_en, title_kr = _extract_title(paras, idx, leftover)
        days.append({
            "day": day_num, "weekday": weekday, "leftover_prefix": leftover,
            "title_en": title_en, "title_kr": title_kr, "lines": content,
        })
    return days


def main():
    path = sys.argv[1]
    d = docx.Document(path)
    paras = [p.text.strip() for p in d.paragraphs]
    paras = [p for p in paras if p]

    start_hit, hits = find_real_start(paras)
    start_idx = start_hit[0]
    print(f"[{path}] 요일 시작 후보 개수: {len(hits)}")
    print(f"[{path}] 실제 시작 인덱스: {start_idx}")

    appendix_idx = find_appendix_start(paras)
    print(f"[{path}] 부록 시작 인덱스: {appendix_idx}")

    days = segment_days(paras, start_idx, hits, appendix_idx)
    print(f"[{path}] 분리된 day 개수: {len(days)}")

    src_stem = Path(path).stem
    days_dir = Path(path).parent / "days" / f"출력_{src_stem}"
    days_dir.mkdir(parents=True, exist_ok=True)
    out_dir = days_dir

    for day in days:
        print(f"  {day['day']} {day['weekday']}: {len(day['lines'])} 줄, 첫줄='{day['lines'][0][:30]}'")
        fname = f"{day['day']}_{day['weekday']}.txt"
        with open(days_dir / fname, "w", encoding="utf-8") as f:
            f.write("\n".join(day["lines"]))

    json_path = out_dir / "segmented.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(days, f, ensure_ascii=False, indent=2)
    print(f"저장 폴더: {out_dir}")


if __name__ == "__main__":
    main()
