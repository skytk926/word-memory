#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clean up raw extraction -> final data.js + audio manifest."""
import json, re, hashlib

raw = json.load(open('words_raw.json', encoding='utf-8'))

HIRA = 'ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞただちぢつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほぼぽまみむめもやゆよらりるれろわをんっゃゅょー'
KATA = 'ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポマミムメモヤユヨラリルレロワヲンッャュョー'

def is_kana(s):
    if not s:
        return False
    return all(c in HIRA + KATA + '・ー〜' or c == ' ' for c in s)

def has_kana(s):
    return any(c in HIRA or c in KATA for c in s)

def dedup_word(w):
    """あいにくあいにく -> あいにく"""
    if len(w) >= 2 and len(w) % 2 == 0:
        half = w[:len(w)//2]
        if w == half + half:
            return half
    return w

def strip_noise(s):
    if not s:
        return s
    # remove header fragments that leaked
    for tok in ['釋乂', '釋义', '释义', '例句翻洋', '例句翻', '例句', '例旬', '翻洋']:
        s = s.replace(tok, '')
    s = re.sub(r'^\s*[・、。\s]+', '', s)
    return s.strip()

def clean_reading(reading, word):
    reading = dedup_word(strip_noise(reading))
    # reading sometimes captured accent/pos ("⓪ 名", "② 形")
    if reading and (re.search(r'[⓪①②③④⑤]', reading) or re.search(r'^[名動効形副連自他]', reading)):
        reading = ''
    return reading

KANJI_RE = re.compile(r'[一-龥㐀-䶿]')
KANA = HIRA + KATA
def has_kanji(s):
    return bool(KANJI_RE.search(s))

def split_word_reading(word):
    """含まれるふくまれる -> (含まれる, ふくまれる); 擦れ違う すれちがう -> (擦れ違う, すれちがう)."""
    # space / 。 separated
    parts = [p for p in re.split(r'[ 　。．]+', word) if p.strip()]
    if len(parts) >= 2 and all(c in KANA for c in parts[-1]) and has_kanji(parts[0]):
        return parts[0], parts[-1]
    # merged kanji+okurigana + full-kana-reading: split where prefix ends with
    # the same kana as the suffix, prefix has kanji, suffix is all-kana
    for i in range(2, len(word) - 1):
        X, Y = word[:i], word[i:]
        if not (has_kanji(X) and all(c in KANA for c in Y)):
            continue
        if not (X[-1] in KANA and X[-1] == Y[-1]):
            continue
        if not (3 <= len(Y) <= 8):
            continue
        return X, Y
    return word, ''

# OCR missed the kana column for a handful of short words; supply the readings.
FALLBACK_READING = {
    '組む': 'くむ', '畳む': 'たたむ', '刻む': 'きざむ', '萎む': 'しぼむ',
    '縮む': 'ちぢむ', '睨む': 'にらむ', '正直': 'しょうじき',
}

def tts_text(word, reading):
    """Text to feed the Japanese TTS for the word."""
    r = reading
    if r and is_kana(r) and has_kana(r):
        return r
    return dedup_word(word)

out = []
sections = [
    ('basic', '基础词汇', '基础词汇', raw['基础词汇'], False),
    ('kanji', '核心词汇', '汉字', raw['核心词汇_汉字'], True),
    ('verb', '核心词汇', '动词', raw['核心词汇_动词'], True),
    ('adj', '核心词汇', '形容词', raw['核心词汇_形容词'], True),
    ('loan', '核心词汇', '外来词', raw['核心词汇_外来词'], True),
    ('adv', '核心词汇', '副词', raw['核心词汇_副词'], True),
]

manifest = []  # list of (file_stem, tts_text)
for sec_id, parent, title, words, has_ex in sections:
    sec_words = []
    for i, w in enumerate(words):
        word = dedup_word(strip_noise(w.get('word', '')))
        if not word:
            continue
        reading = clean_reading(w.get('reading', ''), word)
        if not reading and word in FALLBACK_READING:
            reading = FALLBACK_READING[word]
        if not reading and (has_kanji(word) or ' ' in word or '。' in word):
            w2, r2 = split_word_reading(word)
            if r2:
                word, reading = w2, r2
        accent = strip_noise(w.get('accent', ''))
        pos = strip_noise(w.get('pos', ''))
        meaning = strip_noise(w.get('meaning', ''))
        example = strip_noise(w.get('example', '')) if has_ex else ''
        # OCR often misreads 一 as a leading hyphen (e.g. 一定の間隔 -> -定の間隔)
        if example.startswith('-'):
            example = '一' + example[1:]
        example_cn = strip_noise(w.get('example_cn', '')) if has_ex else ''

        # word audio
        wtxt = tts_text(word, reading)
        wstem = f'{sec_id}_w{i}'
        manifest.append((wstem, wtxt))

        # example audio
        exstem = ''
        if has_ex and example:
            exstem = f'{sec_id}_e{i}'
            manifest.append((exstem, example))

        sec_words.append({
            'w': word,
            'r': reading,
            'a': accent,
            'p': pos,
            'm': meaning,
            'e': example,
            'ec': example_cn,
            'wa': f'audio/{wstem}.m4a',
            'ea': f'audio/{exstem}.m4a' if exstem else '',
        })
    out.append({'id': sec_id, 'parent': parent, 'title': title, 'words': sec_words})
    print(f'{parent} · {title}: {len(sec_words)} words')

# write data.js
js = 'const SECTIONS = ' + json.dumps(out, ensure_ascii=False, indent=0) + ';\n'
open('data.js', 'w', encoding='utf-8').write(js)

# write audio manifest (tsv: stem \t text)
with open('audio_manifest.tsv', 'w', encoding='utf-8') as f:
    for stem, txt in manifest:
        f.write(f'{stem}\t{txt}\n')

print(f'total words: {sum(len(s["words"]) for s in out)}')
print(f'total audio files: {len(manifest)}')
