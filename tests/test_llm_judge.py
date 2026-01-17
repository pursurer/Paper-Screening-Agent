"""LLM 判决模块测试"""
import pytest
import json
from src.llm_judge import (
    JudgeResult,
    parse_llm_response,
    build_system_prompt,
    build_user_prompt,
)


class TestParseResponse:
    """测试 LLM 响应解析"""

    def test_parse_valid_response(self):
        """验证正常 JSON 解析"""
        response = '{"confidence_score": 8, "reasoning": "涉及 KV Cache 压缩"}'
        result = parse_llm_response(response)
        assert result.score == 8
        assert result.reasoning == "涉及 KV Cache 压缩"

    def test_parse_float_score(self):
        """验证 7.5 → 7 的整数处理"""
        response = '{"confidence_score": 7.5, "reasoning": "部分相关"}'
        result = parse_llm_response(response)
        assert result.score == 7
        assert isinstance(result.score, int)

    def test_parse_float_score_9_8(self):
        """验证 9.8 → 9 的整数处理"""
        response = '{"confidence_score": 9.8, "reasoning": "核心相关"}'
        result = parse_llm_response(response)
        assert result.score == 9

    def test_parse_invalid_json(self):
        """验证 JSON 解析失败返回默认值 (score=3 进入人工复核)"""
        response = "这不是有效的 JSON"
        result = parse_llm_response(response)
        assert result.score == 3
        assert "解析失败" in result.reasoning or "error" in result.reasoning.lower()

    def test_parse_missing_score(self):
        """验证缺少 score 字段返回默认值"""
        response = '{"reasoning": "只有理由没有分数"}'
        result = parse_llm_response(response)
        assert result.score == 3

    def test_parse_missing_reasoning(self):
        """验证缺少 reasoning 字段使用默认理由"""
        response = '{"confidence_score": 6}'
        result = parse_llm_response(response)
        assert result.score == 6
        assert result.reasoning != ""


class TestBuildPrompt:
    """测试 Prompt 构建"""

    def test_build_system_prompt_contains_scoring_criteria(self):
        """验证 System Prompt 包含关键评分标准"""
        prompt = build_system_prompt()
        assert "1-10" in prompt or "10" in prompt
        assert "Memory" in prompt
        assert "AI" in prompt

    def test_build_system_prompt_contains_tier_definitions(self):
        """验证 System Prompt 包含 Tier 定义"""
        prompt = build_system_prompt()
        assert "9" in prompt or "10" in prompt
        assert "3" in prompt

    def test_build_user_prompt(self):
        """验证 User Prompt 包含论文信息"""
        prompt = build_user_prompt(
            title="Memory-Augmented Neural Networks",
            abstract="This paper proposes a new memory architecture...",
            keywords='["Memory", "Neural Networks"]'
        )
        assert "Memory-Augmented Neural Networks" in prompt
        assert "memory architecture" in prompt


class TestJudgeResult:
    """测试 JudgeResult 数据类"""

    def test_judge_result_creation(self):
        """验证 JudgeResult 创建"""
        result = JudgeResult(score=8, reasoning="强相关")
        assert result.score == 8
        assert result.reasoning == "强相关"

    def test_judge_result_default_values(self):
        """验证 JudgeResult 默认值"""
        result = JudgeResult()
        assert result.score == 3
        assert result.reasoning != ""
