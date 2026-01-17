"""统计与日志模块 - 统计分流结果并格式化输出"""
from dataclasses import dataclass
from typing import List
from src.output_generator import GradedPaper


@dataclass
class Statistics:
    """统计数据类"""
    total: int
    accepted: int
    review: int
    rejected: int
    core: int
    strong: int
    general: int
    marginal: int


def compute_statistics(graded_papers: List[GradedPaper]) -> Statistics:
    """
    计算分流统计数据
    
    Args:
        graded_papers: GradedPaper 对象列表
    
    Returns:
        Statistics 对象
    """
    total = len(graded_papers)
    accepted = 0
    review = 0
    rejected = 0
    core = 0
    strong = 0
    general = 0
    marginal = 0
    
    for paper in graded_papers:
        score = paper.score
        
        if score >= 4:
            accepted += 1
            if score >= 9:
                core += 1
            elif score >= 7:
                strong += 1
            elif score >= 5:
                general += 1
            else:
                marginal += 1
        elif score == 3:
            review += 1
        else:
            rejected += 1
    
    return Statistics(
        total=total,
        accepted=accepted,
        review=review,
        rejected=rejected,
        core=core,
        strong=strong,
        general=general,
        marginal=marginal
    )


def format_statistics(stats: Statistics) -> str:
    """
    格式化统计数据为日志字符串
    
    Args:
        stats: Statistics 对象
    
    Returns:
        格式化的统计字符串
    """
    lines = [
        f"Accepted (>=4): {stats.accepted} (Core: {stats.core}, Strong: {stats.strong}, General: {stats.general}, Marginal: {stats.marginal})",
        f"Review (3): {stats.review}",
        f"Rejected (<=2): {stats.rejected}",
    ]
    return "\n".join(lines)


def print_statistics(graded_papers: List[GradedPaper]) -> None:
    """
    计算并打印统计数据
    
    Args:
        graded_papers: GradedPaper 对象列表
    """
    stats = compute_statistics(graded_papers)
    print(format_statistics(stats))
