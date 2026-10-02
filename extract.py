#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse OCR output into structured vocabulary data.

Document layout (Vision coords: y=0 bottom, y=1 top):
  Basic-vocab pages (2-10): 序号 单词 读音 声调 词性 释义   (no examples)
  Core-vocab pages (12-49): 序号+单词 读音 声调 词性 释义 例句日 例句中
"""
import re, json

OCR = '/tmp/all_ocr_paged.tsv'

pages = {}
cur = -1
for ln in open(OCR):
    ln = ln.rstrip('\n')
    if ln.startswith('PAGE '):
        cur = int(ln.split()[1])
        pages[cur] = []
        continue
    p = ln.split('\t')
    if len(p) < 5:
        continue
    try:
        x, y, w, h = float(p[0]), float(p[1]), float(p[2]), float(p[3])
    except ValueError:
        continue
    t = p[4].strip()
    if t:
        pages[cur].append((x, y, w, h, t))

NUM_RE = re.compile(r'^\d{1,3}')
ACCT_RE = re.compile(r'[⓪①②③④⑤]')
HEADER_TOKENS = {'序号', '単詞', '单词', '単司', '瑛音', '读音', '声週', '声凋', '声调',
                 '詞性', '词性', '釋乂', '釋义', '释义', '例句', '例旬', '例句翻洋',
                 '例句翻', '翻洋', '汊字', '劫司', '劫河', '形容司', '外来司', '副司',
                 '効河', '名・効3', '名・形', '名・効3名'}

def is_header(l):
    x, y, w, h, t = l
    if y > 0.955:
        return True
    if h > 0.024:
        return True
    if re.search(r'(关注公|回复|跟着|学日|欢迎|欧迎|炊迎)', t) and y > 0.90:
        return True
    if t.strip() in HEADER_TOKENS:
        return True
    return False

def clean_word(s):
    s = re.sub(r'^[\s・.、]+', '', s)
    s = re.sub(r'[\s・.、]+$', '', s)
    return s

def get(lines, x0, x1, ay, tol=0.016):
    """return text of the line within [x0,x1] nearest to ay (topmost preference)."""
    best = None
    for l in lines:
        x, y, w, h, t = l
        if x0 <= x < x1 and abs(y - ay) <= tol:
            if best is None or y > best[1]:
                best = (t, y)
    return best[0] if best else ''

def parse_page(pidx, has_examples):
    lines = [l for l in pages.get(pidx, []) if not is_header(l)]
    # row anchors: lines in number/word column starting with digits
    anchors = [l for l in lines if l[0] < 0.16 and NUM_RE.match(l[4])]
    # dedupe anchors that share nearly same y (number & word split across lines)
    anchors.sort(key=lambda l: -l[1])
    dedup = []
    for l in anchors:
        if dedup and abs(dedup[-1][1] - l[1]) < 0.014:
            # keep the one whose text carries the word (longer / has non-digits)
            prev = dedup[-1]
            if len(l[4]) > len(prev[4]) or (NUM_RE.sub('', l[4]) and not NUM_RE.sub('', prev[4])):
                dedup[-1] = l
            continue
        dedup.append(l)
    anchors = dedup

    rows = []
    for i, a in enumerate(anchors):
        ay = a[1]
        prev_y = anchors[i-1][1] if i > 0 else ay + 0.035
        next_y = anchors[i+1][1] if i+1 < len(anchors) else 0.0
        y_hi = (prev_y + ay) / 2
        y_lo = (ay + next_y) / 2

        head = a[4]
        num = NUM_RE.match(head).group(0)
        rest = NUM_RE.sub('', head, count=1)
        word = clean_word(rest)
        if not word:
            # word is a separate line at same y, x in 0.075-0.16
            for l in lines:
                if 0.075 <= l[0] < 0.16 and abs(l[1]-ay) <= 0.014 and not NUM_RE.match(l[4]):
                    word = clean_word(l[4])
                    break

        # reading (kana/english) — leftmost line in reading column band
        reading = ''
        for l in lines:
            if 0.14 <= l[0] < 0.27 and abs(l[1]-ay) <= 0.014:
                t = clean_word(l[4])
                if t and not ACCT_RE.search(t) and not re.fullmatch(r'[名動効形副連自他・]*', t):
                    reading = t
                    break

        # accent (声调) and pos (词性)
        accent = ''
        pos = ''
        band = [l for l in lines if y_lo <= l[1] <= y_hi]

        def split_jp(s):
            """split '中文释义+日语例句' at first kana; return (meaning, jp_rest)."""
            m = re.search(r'[ぁ-んァ-ン]', s)
            if m:
                return s[:m.start()], s[m.start():]
            return s, ''

        meaning = ''
        ex_jp = ''
        ex_cn = ''
        if has_examples:
            m, ej, ec = [], [], []
            exj_extra = []
            for l in band:
                x, y, w, h, t = l
                if 0.26 <= x < 0.30:
                    a = ''.join(ch for ch in t if ch in '⓪①②③④⑤')
                    if a:
                        accent = accent + a
                    rest = re.sub(r'[⓪①②③④⑤\s・；：]+', '', t)
                    if rest and re.search(r'[名動効形副連自他]', rest):
                        pos = pos + rest
                elif 0.30 <= x < 0.365:
                    if re.search(r'[名動効形副連自他]', t) or t.strip() in ('名', '形', '副'):
                        pos = pos + t
                elif 0.365 <= x < 0.475:
                    # meaning column; may contain trailing Japanese example
                    mm, jp = split_jp(t)
                    if mm.strip():
                        m.append((y, mm))
                    if jp.strip():
                        exj_extra.append(jp)
                elif 0.475 <= x < 0.73:
                    ej.append((y, t))
                elif 0.73 <= x < 0.97:
                    ec.append((y, t))
            m.sort(key=lambda p: -p[0]); ej.sort(key=lambda p: -p[0]); ec.sort(key=lambda p: -p[0])
            meaning = ''.join(p[1] for p in m)
            ex_jp = ''.join(exj_extra) + ''.join(p[1] for p in ej)
            ex_cn = ''.join(p[1] for p in ec)
        else:
            # basic pages: accent [0.30,0.42], pos [0.42,0.60], meaning [0.60,0.97]
            # all on the SAME line as the anchor -> use a tight band
            for l in lines:
                x, y, w, h, t = l
                if abs(y - ay) > 0.014:
                    continue
                if 0.30 <= x < 0.42 and ACCT_RE.search(t):
                    accent = t
                elif 0.42 <= x < 0.60 and re.search(r'[名動効形副連自他]', t):
                    pos = (pos or '') + t
                elif 0.60 <= x < 0.97:
                    if t not in HEADER_TOKENS:
                        meaning = (meaning or '') + t

        if not word:
            continue
        rec = {'num': num, 'word': word, 'reading': reading, 'accent': accent,
               'pos': pos, 'meaning': meaning.strip()}
        if has_examples:
            rec['example'] = ex_jp.strip()
            rec['example_cn'] = ex_cn.strip()
        rows.append(rec)
    return rows

SECTIONS = [
    ('基础词汇', list(range(2, 11)), False),
    ('核心词汇_汉字', list(range(12, 26)), True),
    ('核心词汇_动词', list(range(26, 34)), True),
    ('核心词汇_形容词', list(range(34, 42)), True),
    ('核心词汇_外来词', list(range(42, 47)), True),
    ('核心词汇_副词', list(range(47, 50)), True),
]

result = {}
for name, pr, has_ex in SECTIONS:
    rows = []
    for pidx in pr:
        rows.extend(parse_page(pidx, has_ex))
    result[name] = rows
    print(f'{name}: {len(rows)} rows')

json.dump(result, open('words_raw.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('written words_raw.json')
