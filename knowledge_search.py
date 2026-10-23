"""第八、九课共用的本地关键词检索，不调用模型或读取凭证。"""

import re
from pathlib import Path


KNOWLEDGE_DIR = Path(__file__).parent / "knowledge" / "lesson08"
# 减少常见问法和产品名称带来的无关匹配；这是教学用的简易规则。
STOP_TERMS = {"什么", "怎么", "如何", "是否", "可以", "能否", "支持", "请问", "哪些", "青禾", "禾报", "报表"}


def tokenize(text: str) -> set[str]:
    """英文按单词，连续中文按相邻两个字拆分；不是专业中文分词。"""
    terms = set(re.findall(r"[a-z0-9]+", text.lower()))
    for word in re.findall(r"[一-鿿]+", text):
        terms.update(word[index:index + 2] for index in range(len(word) - 1))
    return terms - STOP_TERMS


def load_chunks() -> list[dict[str, str]]:
    """只读取本课目录的 Markdown，按二级标题切成带来源的小段。"""
    chunks = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for section in re.split(r"\n(?=## )", text):
            if not section.startswith("## "):
                continue
            heading = section.splitlines()[0][3:].strip()
            chunks.append({"source": f"{path.name}#{heading}", "text": section.strip()})
    if not chunks:
        raise SystemExit("未找到资料段落，请检查 knowledge/lesson08 中的示例文件和二级标题。")
    return chunks


def retrieve(question: str, chunks: list[dict[str, str]], top_k: int = 3) -> list[dict[str, str]]:
    """按问题与段落的词项重合数排序，只保留有匹配的前几个段落。"""
    query_terms = tokenize(question)
    scored = [(len(query_terms & tokenize(chunk["text"])), chunk) for chunk in chunks]
    scored = [(score, chunk) for score, chunk in scored if score > 0]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]
