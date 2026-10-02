#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate Japanese TTS audio for all words/examples -> audio/*.m4a"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

MANIFEST = 'audio_manifest.tsv'
VOICE = 'Kyoko'
AUDIO_DIR = 'audio'
os.makedirs(AUDIO_DIR, exist_ok=True)

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

def gen(item):
    stem, text = item
    out = os.path.join(AUDIO_DIR, stem + '.m4a')
    if os.path.exists(out) and os.path.getsize(out) > 500:
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
print(f'generating {total} audio files with voice {VOICE} ...', flush=True)
done = 0
with ThreadPoolExecutor(max_workers=6) as ex:
    for stem, status in ex.map(gen, entries):
        done += 1
        if status != 'ok' and status != 'skip':
            print(f'[{done}/{total}] {stem}: {status}', flush=True)
        elif done % 200 == 0:
            print(f'[{done}/{total}] ...', flush=True)
print(f'DONE {total} entries', flush=True)
