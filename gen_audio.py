#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate Japanese TTS audio for all words/examples -> audio/*.m4a

Regenerates an audio file only when its text changed since the last run
(tracked in audio_manifest.prev.tsv) or when the file is missing/empty.
Pass --all to force a full regeneration.
"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

MANIFEST = 'audio_manifest.tsv'
PREV = 'audio_manifest.prev.tsv'
VOICE = 'Kyoko'
AUDIO_DIR = 'audio'
os.makedirs(AUDIO_DIR, exist_ok=True)

FORCE = '--all' in sys.argv

entries = []
for ln in open(MANIFEST, encoding='utf-8'):
    ln = ln.rstrip('\n')
    if not ln.strip():
        continue
    parts = ln.split('\t', 1)
    if len(parts) < 2:
        continue
    stem, text = parts[0], parts[1].strip()
    if not text:
        continue
    entries.append((stem, text))

# previous text per stem (the text each existing audio file was generated from)
prev = {}
if os.path.exists(PREV):
    for ln in open(PREV, encoding='utf-8'):
        ln = ln.rstrip('\n')
        if not ln.strip():
            continue
        p = ln.split('\t', 1)
        if len(p) >= 2:
            prev[p[0]] = p[1].strip()

def gen(item):
    stem, text = item
    out = os.path.join(AUDIO_DIR, stem + '.m4a')
    if not FORCE and os.path.exists(out) and os.path.getsize(out) > 500 and prev.get(stem) == text:
        return (stem, 'skip')
    aiff = f'/tmp/tts_{stem}.aiff'
    try:
        r1 = subprocess.run(['say', '-v', VOICE, '-o', aiff, text],
                            capture_output=True, timeout=30)
        if r1.returncode != 0 or not os.path.exists(aiff):
            return (stem, 'fail_say')
        r2 = subprocess.run(['afconvert', aiff, out, '-f', 'm4af', '-d', 'aac', '-b', '64000'],
                            capture_output=True, timeout=30)
        if r2.returncode != 0 or not os.path.exists(out):
            return (stem, 'fail_convert')
        try:
            os.remove(aiff)
        except OSError:
            pass
        return (stem, 'ok')
    except Exception as e:
        return (stem, f'err:{e}')

total = len(entries)
print(f'generating audio with voice {VOICE} ({"ALL" if FORCE else "changed/missing"} mode), {total} entries ...', flush=True)
done = 0
results = {}
with ThreadPoolExecutor(max_workers=6) as ex:
    for stem, status in ex.map(gen, entries):
        results[stem] = status
        done += 1
        if status not in ('ok', 'skip'):
            print(f'[{done}/{total}] {stem}: {status}', flush=True)
        elif done % 200 == 0:
            print(f'[{done}/{total}] ...', flush=True)

# snapshot only the entries now correct on disk, so the next run can diff
with open(PREV, 'w', encoding='utf-8') as f:
    for stem, text in entries:
        if results.get(stem) in ('ok', 'skip'):
            f.write(f'{stem}\t{text}\n')

ok = sum(1 for s in results.values() if s == 'ok')
skip = sum(1 for s in results.values() if s == 'skip')
print(f'DONE {total} entries: {ok} regenerated, {skip} skipped', flush=True)
