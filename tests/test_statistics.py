"""统计与日志模块测试"""
import pytest
from src.statistics import Statistics, compute_statistics, format_statistics
from src.output_generator import GradedPaper


def _create_graded_paper(score: int, tier: str) -> GradedPaper:
    """辅助函数：创建测试用 GradedPaper"""
    return GradedPaper(
        score=score,
        relevance_tier=tier,
        id=f"test_{score}",
        title=f"Test Paper {score}",
        keywords="[]",
        reasoning="Test reasoning",
        abstract="Test abstract",
        pdf="pdf_url",
        forum="forum_url",
        year=2025,
        presentation_type="Oral"
    )


class TestStatistics:
    """测试 Statistics 数据类"""

    def test_statistics_creation(self):
        """验证 Statistics 创建"""
        stats = Statistics(
            total=100,
            accepted=80,
            review=10,
            rejected=10,
            core=20,
            strong=30,
            general=20,
            marginal=10
        )
        assert stats.total == 100
        assert stats.accepted == 80
        assert stats.review == 10
        assert stats.rejected == 10

    def test_statistics_tier_breakdown(self):
        """验证 Tier 细分字段"""
        stats = Statistics(
            total=50,
            accepted=40,
            review=5,
            rejected=5,
            core=10,
            strong=15,
            general=10,
            marginal=5
        )
        assert stats.core == 10
        assert stats.strong == 15
        assert stats.general == 10
        assert stats.marginal == 5


class TestComputeStatistics:
    """测试统计计算"""

    def test_compute_statistics(self):
        """验证统计计算正确"""
        papers = [
            _create_graded_paper(10, "Core"),
            _create_graded_paper(9, "Core"),
            _create_graded_paper(8, "Strong"),
            _create_graded_paper(7, "Strong"),
            _create_graded_paper(6, "General"),
            _create_graded_paper(5, "General"),
            _create_graded_paper(4, "Marginal"),
            _create_graded_paper(3, "Boundary"),
            _create_graded_paper(2, "Irrelevant"),
            _create_graded_paper(1, "Irrelevant"),
        ]
        
        stats = compute_statistics(papers)
        
        assert stats.total == 10
        assert stats.accepted == 7
        assert stats.review == 1
        assert stats.rejected == 2

    def test_tier_breakdown(self):
        """验证 Tier 细分正确"""
        papers = [
            _create_graded_paper(10, "Core"),
            _create_graded_paper(9, "Core"),
            _create_graded_paper(8, "Strong"),
            _create_graded_paper(6, "General"),
            _create_graded_paper(4, "Marginal"),
        ]
        
        stats = compute_statistics(papers)
        
        assert stats.core == 2
        assert stats.strong == 1
        assert stats.general == 1
        assert stats.marginal == 1

    def test_empty_papers(self):
        """验证空列表处理"""
        stats = compute_statistics([])
        
        assert stats.total == 0
        assert stats.accepted == 0
        assert stats.review == 0
        assert stats.rejected == 0
        assert stats.core == 0
        assert stats.strong == 0
        assert stats.general == 0
        assert stats.marginal == 0

    def test_all_same_score(self):
        """验证全部同一分数"""
        papers = [
            _create_graded_paper(10, "Core"),
            _create_graded_paper(10, "Core"),
            _create_graded_paper(10, "Core"),
        ]
        
        stats = compute_statistics(papers)
        
        assert stats.total == 3
        assert stats.accepted == 3
        assert stats.core == 3
        assert stats.strong == 0
        assert stats.general == 0
        assert stats.marginal == 0


class TestFormatStatistics:
    """测试统计格式化输出"""

    def test_format_statistics(self):
        """验证输出格式正确"""
        stats = Statistics(
            total=100,
            accepted=80,
            review=10,
            rejected=10,
            core=20,
            strong=30,
            general=20,
            marginal=10
        )
        
        output = format_statistics(stats)
        
        assert "Accepted (>=4): 80" in output
        assert "Core: 20" in output
        assert "Strong: 30" in output
        assert "General: 20" in output
        assert "Marginal: 10" in output
        assert "Review (3): 10" in output
        assert "Rejected (<=2): 10" in output

    def test_format_empty_statistics(self):
        """验证空统计格式化"""
        stats = Statistics(
            total=0,
            accepted=0,
            review=0,
            rejected=0,
            core=0,
            strong=0,
            general=0,
            marginal=0
        )
        
        output = format_statistics(stats)
        
        assert "Accepted (>=4): 0" in output
        assert "Review (3): 0" in output
        assert "Rejected (<=2): 0" in output
