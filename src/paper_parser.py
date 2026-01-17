"""论文输入解析模块 - 读取顶会论文 CSV 文件"""
import csv
import os
from dataclasses import dataclass
from typing import List


@dataclass
class Paper:
    """论文数据类"""
    id: str
    title: str
    keywords: str
    abstract: str
    pdf: str
    forum: str
    year: int
    presentation_type: str


def parse_csv(file_path: str) -> List[Paper]:
    """
    解析论文 CSV 文件
    
    Args:
        file_path: CSV 文件路径
    
    Returns:
        Paper 对象列表
    
    Raises:
        FileNotFoundError: 文件不存在
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    papers = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            year_str = row.get('year', '0')
            try:
                year = int(year_str) if year_str else 0
            except ValueError:
                year = 0
            
            paper = Paper(
                id=row.get('id', ''),
                title=row.get('title', ''),
                keywords=row.get('keywords', ''),
                abstract=row.get('abstract', ''),
                pdf=row.get('pdf', ''),
                forum=row.get('forum', ''),
                year=year,
                presentation_type=row.get('presentation_type', '')
            )
            papers.append(paper)
    
    return papers
