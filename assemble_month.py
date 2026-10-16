# -*- coding: utf-8 -*-
"""
한 달치 전체 완성본 조립: 표지(front_matter_builder 결과) + 차례(고정 템플릿, contents만 교체)
+ 본문(평일 build_day + 토요일 build_saturday) + 부록.
페이지 번호(@@pN)는 순서대로 자동 매긴다.
"""
import re
import sys
import json
import glob
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import build_day
import build_saturday
import build_appendix
import extract_contents
import docx

FIXED_TIPS_PAGE = """    구성 및 학습 Tips!

    Learning Points! (이것이 포인트!)
  오늘 학습에서 어떤 요소를 중점적으로 익힐지 학습 포인트를 알려 줍니다. 아래 번역문을 보면서 영작에 도전해 보세요. 모르는 단어나 표현들은 우리말로 채우면서 완성시켜 보세요.

    Easy Talk (상황별 대화)
  그날의 학습 포인트가 상황 맥락 속에서 자연스럽게 소개된 대화를 제시합니다. 또한 영어 발음의 패턴 원칙을 적용하여 힘을 주어 발음할 단어는 진하게 표시되어 있어서, 영어의 억양 원칙에 익숙해질 수 있도록 연습하는 것을 도와줍니다. 실제 상황을 떠올리며 들으면서 큰 소리로 따라 말하는 것을 연습해 보세요.

    Sentence Pattern (말문을 여는 패턴)
  그날의 내용에서 가장 주요한 어법이나 문법이 적용된 문장들을 중심으로 자세히 살펴봅니다. 주요 문장 두 개를 분해하여 '영어 - 우리말' 어순에 자연스럽게 익숙해지도록 하는 코너입니다. 또 두 문장에 적용되어 있는 유용한 패턴들을 학습하고 응용까지 해 봅니다.

    In Other Words (같은 뜻 다른 표현)
  본문에 나온 세 개의 문장을 골라 같은 뜻을 다른 문장으로 바꾸어 만들어 봅니다. 하나의 문장을 다른 쉬운 단어와 문장들로 표현하는 법을 익히는 것은 회화를 할 때 꼭 필요한 기술입니다. 같은 뜻을 다르게 표현해 보면서 다양한 표현들을 익혀 보세요.

    Useful Tip
  그날의 학습에서 놓치기 쉬운 포인트를 따로 코너로 마련했습니다. 단어나 표현법의 뉘앙스, 문화의 차이로 인한 표현 방식의 차이, 기본 에티켓 등 알아 두면 반드시 쓸모 있는 다양한 학습 팁이 제공됩니다.

    Practice Makes Perfect! (일취월장 문장력!)
  회화에서 가장 필요한 학습 훈련법의 하나입니다. 본문에서 두 개의 문장을 뽑아 그 핵심 단어를 바꿔 가며 문장력을 키우는 코너입니다. 기본 문장 패턴의 반복과 핵심 단어의 대체 훈련은 문장력을 일취월장시켜 드립니다.

    Now You Talk! (여러분이 말해 보세요!)
  그날 다룬 주요 표현들과 이디엄 표현, 어휘들을 응용하여 다양한 문장들을 만들어 보는 영작 코너입니다. 그날의 내용을 정리하고 자신의 것으로 확실히 만들기 위한 과정입니다. 큰 소리로 읽으면서 자신 있게 써 보세요.

    Weekly Review
  이보영의 영어 & 영어 공부 이야기
  영어를 공부하면서 해야 할 것과 하지 말아야 할 것, 하지 않아도 되는 것들에 대한 이야기들을 정리하거나, 생활 영어 표현 속에 얽힌 이야기, 영어 공부의 경험 등에 대해 공감하기 쉬운 이야기들을 공유합니다. <Easy English>가 영어 공부의 동반자가 되어 여러분이 오랫동안 질리지 않고 공부하는 데 도움이 되고자 합니다.
  토요일 리뷰에서는 각 요일의 대화문을 복습하면서, 주요 표현이나 이디엄을 다룬 문장을 영문으로 옮기는 연습을 해 봅니다. 그리고 주요 어법이나 문법, 표현 등을 응용해서 영작까지 해 봅니다. 이 리뷰는 꼭 예습해 보세요!"""


def load_segmented(days_dir):
    with open(Path(days_dir) / "segmented.json", encoding="utf-8") as f:
        return json.load(f)


WD_FULL = {"Mon": "MONDAY", "Tue": "TUESDAY", "Wed": "WEDNESDAY",
           "Thu": "THURSDAY", "Fri": "FRIDAY"}


def build_month_pages(days_dir, contents_lookup, prev_contents_lookup=None):
    """days_dir: segment_test.py가 만든 days\\출력_.../ 폴더.
    contents_lookup: {일자: (영문제목, 한글제목, 시작페이지)}
    각 요일은 고정 6페이지이므로, 차례의 시작 페이지를 기준으로 @@pN을 정확히 매긴다.
    반환: [(page_num, page_text), ...]"""
    days = load_segmented(days_dir)
    result = []
    prev_raw_lines = None
    for day in days:
        num, weekday = day["day"], day["weekday"]
        fname = Path(days_dir) / f"{num}_{weekday}.txt"
        raw_lines = fname.read_text(encoding="utf-8").splitlines()

        if weekday == "Saturday":
            _title_en, _title_kr, start_page = contents_lookup.get(num, ("", "", None))
            essay, day_list, subday_pages, index_titles = build_saturday.build_saturday(raw_lines)
            if not essay and prev_raw_lines is not None:
                essay = build_saturday.extract_bled_essay_from_tail(prev_raw_lines)

            index_lines = []
            nums = [int(d) for d, _ in day_list]
            wrapped = any(nums[k] > nums[k + 1] for k in range(len(nums) - 1))
            for k, (d, wd_abbr) in enumerate(day_list):
                wd_full = WD_FULL[wd_abbr.rstrip(".")]
                lookup = contents_lookup
                if wrapped and prev_contents_lookup and nums[k] > nums[-1]:
                    lookup = prev_contents_lookup
                # 원본 인덱스 자체에서 뽑은 제목을 최우선으로 쓰고(항상 이 토요일 고유의 정확한 값),
                # 없을 때만 차례 정보로 보완한다 (같은 날짜 번호가 다른 달에도 있어 차례만으론 헷갈릴 수 있음).
                title_en, title_kr = index_titles.get(d, (None, None))
                if not title_en:
                    title_en, title_kr, _ = lookup.get(d, ("(제목 미상)", "", None))
                index_lines.append(f"  {d} {wd_full} {title_en}")
                index_lines.append(f"  {title_kr}")
            page0 = (
                f"    {num} Saturday\n    Weekly Review\n\n"
                + "\n".join(index_lines)
                + "\n\n    이보영의 영어 & 영어 공부 이야기\n  " + essay
            )
            pages = [page0] + subday_pages
        else:
            _title_en, _title_kr, start_page = contents_lookup.get(num, (None, None, None))
            # 차례(완성본)에서 못 가져오면 원본 docx 자체에서 직접 뽑은 제목을 쓴다
            title_en = _title_en or day.get("title_en") or "(제목 미상)"
            title_kr = _title_kr or day.get("title_kr") or ""
            parsed = build_day.build_day(raw_lines)
            pages = build_day.assemble_day_pages(parsed, title_en, title_kr, f"{num} {weekday}")

        if start_page is None:
            start_page = result[-1][0] + 1 if result else 8
        for k, page_text in enumerate(pages):
            result.append((start_page + k, page_text))

        prev_raw_lines = raw_lines
    return result


def append_appendix_pages(pages, docx_path, contents_lookup, month_label):
    """부록을 원본 docx에서 직접 뽑아 pages 리스트 끝에 추가한다.
    (원본 인쇄본의 정확한 페이지 분할 정보는 없어서, 부록 전체를 시작 페이지 하나에 담는다.)"""
    appendix_page = contents_lookup.get("_appendix_page")
    if appendix_page is None:
        appendix_page = pages[-1][0] + 1 if pages else 170
    d = docx.Document(docx_path)
    paras = [p.text.strip() for p in d.paragraphs if p.text.strip()]
    text = build_appendix.build_appendix(paras, month_label)
    pages.append((appendix_page, text))
    return pages


def build_month_body(days_dir, contents_lookup, prev_contents_lookup=None):
    """하위호환용: (page_num, text) 리스트 대신 텍스트 리스트만 필요할 때."""
    pages = build_month_pages(days_dir, contents_lookup, prev_contents_lookup)
    return [t for _, t in pages]


def renumber_pages(pages):
    """pages: [(page_num, text), ...] -> '@@pN\\n텍스트' 형태로 이어붙인다."""
    out = []
    for p, text in pages:
        out.append(f"@@p{p}")
        out.append(text)
    return "\n".join(out)


if __name__ == "__main__":
    days_dir = sys.argv[1]
    reference_txt = sys.argv[2]
    contents_lookup = extract_contents.extract(reference_txt)
    pages = build_month_pages(days_dir, contents_lookup)
    print(renumber_pages(pages))
