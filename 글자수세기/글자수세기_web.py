# -*- coding: utf-8 -*-
"""글자수세기 - 웹 화면 시험판 (pywebview).
계산은 원래 글자수세기.py 의 함수를 그대로 쓰고, 화면만 HTML 로 바꿨다.
원래 프로그램(글자수세기.py)은 건드리지 않는다."""
import importlib.util
import os

import webview

HERE = os.path.dirname(os.path.abspath(__file__))
import sys
if HERE not in sys.path:
    sys.path.insert(0, HERE)  # 원래 글자수세기.py 가 같은 폴더의 역점역기.py 를 가져온다
_spec = importlib.util.spec_from_file_location("count_core", os.path.join(HERE, "글자수세기.py"))
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)


class Api:
    def count(self, text, spec, lines, by_label):
        """본문, 쪽 범위, 쪽당 줄수, 쪽번호 기준 여부 -> 결과 사전."""
        try:
            n = int(str(lines).strip() or "26")
            pages = core.split_pages(text, n)
            chosen, desc = core.select_pages(pages, spec or "", bool(by_label))
            body = "\n".join(chosen)
            no_space, with_space = core.count_chars(body)
            return {"ok": True, "no_space": no_space, "with_space": with_space,
                    "pages": len(chosen), "desc": desc}
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:  # 시험판이라 어떤 오류든 화면에 보여 준다
            return {"ok": False, "error": f"오류: {e}"}

    def open_file(self):
        """파일 열기 대화상자 -> 파일 내용 (utf-8 또는 cp949 로 읽는다)."""
        win = webview.windows[0]
        picked = win.create_file_dialog(webview.OPEN_DIALOG, file_types=("점자 문서 (*.brf;*.txt)", "모든 파일 (*.*)"))
        if not picked:
            return None
        path = picked[0]
        raw = open(path, "rb").read()
        for enc in ("utf-8", "cp949"):
            try:
                return {"name": os.path.basename(path), "text": raw.decode(enc)}
            except UnicodeDecodeError:
                continue
        return {"name": os.path.basename(path), "text": raw.decode("latin-1")}


HTML = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<style>
  :root { --bg:#f2f2f2; --panel:#ffffff; --line:#c8c8c8; --text:#222; --muted:#6b6b6b; --accent:#3a3a3a; }
  * { box-sizing: border-box; border-radius: 0; }
  body { margin:0; padding:20px 24px; background:var(--bg); color:var(--text);
         font-family: "Noto Sans KR", "Malgun Gothic", sans-serif; font-size:14px; }
  h1 { font-size:16px; font-weight:600; margin:0 0 14px; }
  .panel { background:var(--panel); border:1px solid var(--line); padding:12px; margin-bottom:12px; }
  label.small { color:var(--muted); font-size:12px; display:block; margin-bottom:6px; }
  textarea { width:100%; height:200px; border:1px solid var(--line); padding:8px; font:inherit; resize:vertical; background:#fff; }
  .row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
  input[type=text] { border:1px solid var(--line); padding:5px 7px; font:inherit; width:90px; background:#fff; }
  input[type=text]:focus, textarea:focus { outline:none; border-color:var(--accent); }
  button { border:1px solid var(--line); background:#fafafa; padding:6px 14px; font:inherit; cursor:pointer; color:var(--text); }
  button:hover { background:#ececec; }
  button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
  button.primary:hover { background:#262626; }
  .result { display:flex; gap:24px; align-items:baseline; }
  .big { font-size:28px; font-weight:600; font-variant-numeric: tabular-nums; }
  .big small { font-size:13px; color:var(--muted); font-weight:400; margin-left:4px; }
  .desc { color:var(--muted); font-size:12px; margin-top:8px; min-height:16px; }
  .err { color:#8a2b2b; font-size:13px; margin-top:8px; min-height:16px; }
  label.radio { font-size:13px; color:var(--text); display:flex; gap:4px; align-items:center; }
</style></head>
<body>
  <h1>글자 수 세기</h1>

  <div class="panel">
    <label class="small">점자(BRF) 텍스트를 붙여넣거나 파일을 여세요. 일부만 붙여넣어도 됩니다.</label>
    <textarea id="src" placeholder="여기에 붙여넣기"></textarea>
    <div class="row" style="margin-top:8px">
      <button id="btnOpen">파일 열기</button>
      <span id="fname" class="small" style="margin:0"></span>
    </div>
  </div>

  <div class="panel">
    <div class="row">
      <span>쪽</span>
      <input type="text" id="spec" placeholder="5 또는 3-5">
      <span class="small" style="margin:0">비우면 전체</span>
      <label class="radio"><input type="radio" name="by" value="1" checked> 점자 쪽번호</label>
      <label class="radio"><input type="radio" name="by" value="0"> 파일 순서</label>
      <span>쪽당 줄수</span>
      <input type="text" id="lines" value="26" style="width:60px">
    </div>
  </div>

  <div class="panel">
    <div class="result">
      <div class="big" id="total">-<small>글자 (띄어쓰기 제외)</small></div>
      <div class="big" id="total2" style="font-size:20px">-<small>띄어쓰기 포함</small></div>
    </div>
    <div class="desc" id="desc"></div>
    <div class="err" id="err"></div>
    <div class="row" style="margin-top:10px">
      <button class="primary" id="btnRun">글자수 세기</button>
      <button id="btnClear">지우기</button>
    </div>
  </div>

<script>
  const $ = (id) => document.getElementById(id);
  const api = () => window.pywebview.api;

  async function run() {
    $('err').textContent = '';
    const by = document.querySelector('input[name=by]:checked').value === '1';
    const res = await api().count($('src').value, $('spec').value, $('lines').value, by);
    if (!res.ok) { $('err').textContent = res.error; $('total').firstChild.textContent = '-'; $('total2').firstChild.textContent = '-'; $('desc').textContent = ''; return; }
    $('total').firstChild.textContent = res.no_space.toLocaleString();
    $('total2').firstChild.textContent = res.with_space.toLocaleString();
    $('desc').textContent = res.desc + ' · ' + res.pages + '쪽';
  }

  $('btnRun').onclick = run;
  $('btnClear').onclick = () => { $('src').value = ''; $('spec').value = ''; $('fname').textContent = ''; $('err').textContent = ''; $('desc').textContent = ''; };
  $('btnOpen').onclick = async () => {
    const f = await api().open_file();
    if (!f) return;
    $('src').value = f.text; $('fname').textContent = f.name; run();
  };
  window.addEventListener('pywebviewready', () => {});
</script>
</body></html>
"""


if __name__ == "__main__":
    webview.create_window("글자 수 세기 (웹 시험판)", html=HTML, js_api=Api(), width=760, height=720)
    webview.start()
