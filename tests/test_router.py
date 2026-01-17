"""分流路由模块测试"""
import pytest
from src.router import router_logic, get_relevance_tier


class TestRouterLogic:
    """测试分流路由逻辑"""

    def test_accepted_scores(self):
        """验证 4-10 分返回 ACCEPTED"""
        for score in range(4, 11):
            assert router_logic(score) == "ACCEPTED", f"Score {score} should be ACCEPTED"

    def test_human_review_score(self):
        """验证 3 分返回 HUMAN_REVIEW"""
        assert router_logic(3) == "HUMAN_REVIEW"

    def test_rejected_scores(self):
        """验证 1-2 分返回 REJECTED"""
        assert router_logic(1) == "REJECTED"
        assert router_logic(2) == "REJECTED"

    def test_boundary_score_3_vs_4(self):
        """验证边界值 3 和 4 的分流正确"""
        assert router_logic(3) == "HUMAN_REVIEW"
        assert router_logic(4) == "ACCEPTED"


class TestRelevanceTier:
    """测试 Tier 映射"""

    def test_core_tier(self):
        """验证 9-10 分返回 Core"""
        assert get_relevance_tier(10) == "Core"
        assert get_relevance_tier(9) == "Core"

    def test_strong_tier(self):
        """验证 7-8 分返回 Strong"""
        assert get_relevance_tier(8) == "Strong"
        assert get_relevance_tier(7) == "Strong"

    def test_general_tier(self):
        """验证 5-6 分返回 General"""
        assert get_relevance_tier(6) == "General"
        assert get_relevance_tier(5) == "General"

    def test_marginal_tier(self):
        """验证 4 分返回 Marginal"""
        assert get_relevance_tier(4) == "Marginal"

    def test_boundary_tier(self):
        """验证 3 分返回 Boundary"""
        assert get_relevance_tier(3) == "Boundary"

    def test_irrelevant_tier(self):
        """验证 1-2 分返回 Irrelevant"""
        assert get_relevance_tier(2) == "Irrelevant"
        assert get_relevance_tier(1) == "Irrelevant"
