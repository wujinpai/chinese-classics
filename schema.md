# 数据格式说明 schema

## 0. 目录：诗/词/曲分开

每个朝代按体裁拆为 `<朝代>诗/`、`<朝代>词/` 两个目录（元另有 `元曲/`）。
词以词牌名识别：`rhythmic` 字段（词牌名）或标题中的词牌名；其余为诗。

## 1. 作者作品集 `<朝代>诗/<作者>.json`（词/曲同理）

```json
{
  "dynasty": "唐",            // 具体朝代：唐 / 北宋 / 南宋 / 春秋 / 战国 / 东汉 …
  "author": "李白",
  "author_desc": "作者小传（可选）",
  "works": [
    {
      "title": "静夜思",
      "paragraphs": ["床前明月光，", "疑是地上霜。"],
      "rhythmic": "…",        // 词牌名（词曲可选）
      "strains": [],          // 格律（可选）
      "chapter": "…",         // 诗经类：国风；楚辞类：篇名（可选）
      "section": "…",         // 诗经类：周南（可选）
      "annotations": []       // 见第 3 节
    }
  ]
}
```

`title` / `author` / `paragraphs` 与 chinese-poetry 字段名一致，可直接复用其生态工具。

## 2. 典籍单行本 `<大朝代>/<书名>.json`

```json
{
  "title": "论语",
  "dynasty": "春秋",
  "author": "孔子弟子及再传弟子",
  "chapters": [
    {
      "chapter": "学而篇",
      "paragraphs": ["子曰：…"],
      "annotations": []
    }
  ]
}
```

## 3. 释义 `annotations`

```json
"annotations": [
  {
    "notes": ["床——…", "疑——…"],   // 逐句/逐词注释
    "translation": "…",              // 译文
    "appreciation": "…"             // 赏析
  }
]
```

字段均为可选，有什么存什么，只保留干净的内容字段。

## 4. 名篇索引 `名篇索引/<选本>.json`

```json
[{"title": "静夜思", "author": "李白"}]
```

仅篇目不附正文，正文在朝代/作者文件中。用于释义抓取排期。
