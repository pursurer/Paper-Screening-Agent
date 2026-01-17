"""输出交付模块 - 生成评分后的论文 CSV 文件"""
import csv
from dataclasses import dataclass
from typing import List


CSV_FIELD_ORDER = [
    'Score', 'Relevance_Tier', 'id', 'title', 'keywords',
    'Reasoning', 'abstract', 'pdf', 'forum', 'year', 'presentation_type'
]


@dataclass
class GradedPaper:
    """评分后的论文数据类"""
    score: int
    relevance_tier: str
    id: str
    title: str
    keywords: str
    reasoning: str
    abstract: str
    pdf: str
    forum: str
    year: int
    presentation_type: str


def _paper_to_row(paper: GradedPaper) -> dict:
    """
    将 GradedPaper 转换为 CSV 行字典
    
    Args:
        paper: GradedPaper 对象
    
    Returns:
        字段名到值的字典
    """
    return {
        'Score': paper.score,
        'Relevance_Tier': paper.relevance_tier,
        'id': paper.id,
        'title': paper.title,
        'keywords': paper.keywords,
        'Reasoning': paper.reasoning,
        'abstract': paper.abstract,
        'pdf': paper.pdf,
        'forum': paper.forum,
        'year': paper.year,
        'presentation_type': paper.presentation_type,
    }


def write_graded_csv(papers: List[GradedPaper], output_path: str) -> None:
    """
    写入主数据库 CSV 文件 (Score >= 4)
    
    Args:
        papers: GradedPaper 对象列表
        output_path: 输出文件路径
    """
    sorted_papers = sorted(papers, key=lambda p: p.score, reverse=True)
    
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELD_ORDER)
        writer.writeheader()
        
        for paper in sorted_papers:
            writer.writerow(_paper_to_row(paper))


def write_review_csv(papers: List[GradedPaper], output_path: str) -> None:
    """
    写入边界复核 CSV 文件 (Score = 3)
    
    Args:
        papers: GradedPaper 对象列表 (应仅包含 Score = 3 的论文)
        output_path: 输出文件路径
    """
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELD_ORDER)
        writer.writeheader()
        
        for paper in papers:
            writer.writerow(_paper_to_row(paper))
