# 记单词（word-memory）— N2 词汇王炸套餐

从扫描版 PDF《N2词汇王炸套餐背词版.pdf》中提取、分类并生成发音的背词网页。

## 页面

- 打开 `index.html` 即可使用（推荐起本地静态服务器，见下）。
- 单词按文档原有结构分类：
  - 基础词汇（376 词）
  - 核心词汇 · 汉字（433 词）
  - 核心词汇 · 动词（263 词）
  - 核心词汇 · 形容词（175 词）
  - 核心词汇 · 外来词（129 词）
  - 核心词汇 · 副词（48 词）
- **点击单词** 或单词旁的喇叭按钮播放读音；**点击例句** 播放例句发音。
- 音频文件存放在 `audio/` 目录（`.m4a`），由 macOS 日语语音 `Kyoko` 离线合成。
- 页面为“互联式”风格：动态节点连线背景 + 节点式分类导航。

## 手动修正 + 重新生成音频

OCR 提取可能存在缺读音（假名）、释义/例句翻译错字等问题。可在浏览器里手动修正：

1. 打开页面，点单词卡片右上角 **✎** 按钮，修改「读音 / 假名」「释义」「例句（日文）」「例句释义（中文）」等字段（改动即时显示在卡片上，带绿色「已改」角标）。
2. 改完后点顶部的 **「导出修改」**，下载 `manual_overrides.json`，放进项目根目录。
3. 运行 `python3 finalize.py && python3 gen_audio.py`，把修改写入 `data.js` 并只重新生成文本变化过的音频。
4. 刷新页面，点 **「清除本地修改」**（此时修改已固化到 `data.js`，无需本地覆盖）。

> `gen_audio.py` 通过 `audio_manifest.prev.tsv` 记录上次生成的文本，只重生成有变化的音频；加 `--all` 可强制全量重生成。

## 运行

```bash
cd word-memory
python3 -m http.server 8000
```

访问 http://localhost:8000 。

## 数据与音频

- `data.js` — 由 `finalize.py` 生成，`const SECTIONS = [...]`，每个词含 `w/r/a/p/m/e/ec/wa/ea` 字段。
- `audio_manifest.tsv` — 音频文件名与待合成文本的对应表。
- `audio/*.m4a` — 由 `gen_audio.py` 合成的发音文件。

## 重新生成流程

1. OCR 扫描页 → `/tmp/all_ocr_paged.tsv`（`ocr.swift`，macOS Vision）。
2. 解析结构 → `words_raw.json`：`python3 extract.py`。
3. 清洗并输出 `data.js` + `audio_manifest.tsv`：`python3 finalize.py`。
4. 合成音频：`python3 gen_audio.py`（需 macOS `say -v Kyoko` 与 `afconvert`）。
