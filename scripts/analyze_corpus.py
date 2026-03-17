# -*- coding: utf-8 -*-
"""分析 data 目录下的语料库结构和内容"""
from pathlib import Path
import os

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


def main():
    data_dir = Path(__file__).parent.parent / "data"
    if not data_dir.exists():
        print("data 目录不存在")
        return

    files = sorted([f for f in os.listdir(data_dir) if f.endswith((".docx", ".doc"))])
    docx_files = [f for f in files if f.endswith(".docx")]
    doc_files = [f for f in files if f.endswith(".doc")]

    lines = []
    lines.append("=== EverGrow 语料库分析报告 ===\n")
    lines.append(f"总文件数: {len(files)}")
    lines.append(f"  - .docx: {len(docx_files)}")
    lines.append(f"  - .doc:  {len(doc_files)}")
    lines.append("\n--- 文件名列表 (前50个) ---\n")

    for f in files[:50]:
        lines.append(f"  {f}")

    if HAS_DOCX and docx_files:
        lines.append("\n--- 文件内容结构样本 ---\n")
        for idx, fn in enumerate([docx_files[0], docx_files[min(30, len(docx_files)-1)], docx_files[min(100, len(docx_files)-1)]]):
            try:
                doc = Document(str(data_dir / fn))
                paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
                lines.append(f"\n=== 样本 {idx+1}: {fn} ===")
                lines.append(f"段落数: {len(paras)}")
                for i, t in enumerate(paras[:15]):
                    lines.append(f"  [{i}] {t[:150]}{'...' if len(t) > 150 else ''}")
            except Exception as e:
                lines.append(f"\n[读取失败 {fn}]: {e}")

    out_path = Path(__file__).parent.parent / "docs" / "语料库分析报告.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"已保存至: {out_path}")


if __name__ == "__main__":
    main()
