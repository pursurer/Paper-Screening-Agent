"""LLM 判决模块 - 调用 LLM API 对论文进行 1-10 分评分"""
import json
import os
from dataclasses import dataclass, field
from typing import Optional

# 默认配置文件路径
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "prompts.json")

# 缓存已加载的配置
_prompt_config: Optional[dict] = None


@dataclass
class JudgeResult:
    """LLM 判决结果"""
    score: int = 3
    reasoning: str = field(default="默认进入人工复核")


def load_prompt_config(config_path: str = None) -> dict:
    """
    加载提示词配置文件
    
    Args:
        config_path: 配置文件路径，默认为 config/prompts.json
    
    Returns:
        配置字典
    """
    global _prompt_config
    
    if _prompt_config is not None and config_path is None:
        return _prompt_config
    
    path = config_path or DEFAULT_CONFIG_PATH
    
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
            if config_path is None:
                _prompt_config = config
            return config
    
    # 如果配置文件不存在，返回默认配置
    return get_default_config()


def get_default_config() -> dict:
    """返回默认配置（内置提示词）"""
    return {
        "screening_topic": "AI Memory",
        "system_prompt": """你是一名 AI 领域专家研究员。任务是筛选属于 '{topic}' 范畴的顶会论文，并进行精细化评分。

**核心任务**：
不仅要判断'是否相关'，还要区分'相关程度'。目标是**极高召回率**。

**评分标准 (1-10 分制) - 请严格对齐语义**：

**[Tier 1: 核心强相关 9-10]**
- **10分**: 标题即包含 'Memory', 'Long-term Agent', 'Generative Agents'，且以此为核心创新点。
- **9分**: 论文提出了一种新的 Memory 架构（如 Memory Bank, Parametric Memory）或解决了 Agent 遗忘问题。

**[Tier 2: 架构/隐式强相关 7-8]**
- **8分**: 强相关。虽标题未提 Memory，但核心机制是 'State Maintenance', 'KV Cache Compression', 'Experience Replay'。
- **7分**: 涉及 Infinite Context 或 SSM (Mamba)，明确提到是为了'保留历史信息'或'长期依赖'。

**[Tier 3: 一般/应用相关 5-6]**
- **6分**: 涉及 Skill Learning (技能库)、Tool-use history，或 RAG 的动态更新机制（Agentic RAG）。
- **5分**: 涉及 Long Context 评测或应用，提到了一些 Context 管理，但创新点主要在其他方面。

**[Tier 4: 勉强/边缘相关 4] - 自动收录底线**
- **4分**: **勉强符合**。提到了 Memory 关键词（如 GPU Memory, Replay Buffer）或 Prompt Context，你觉得它跟 Agent Memory 关系很弱，但不能完全排除。**根据高召回原则，给 4 分。**

**[Tier 5: 置信边界 3] - 人工复核区**
- **3分 (关键)**: **犹豫不决**。论文讨论了 Attention 机制或检索，你完全无法确定它是单纯计算优化还是服务于记忆。或者概念非常模糊。**凡是不确定的，打 3 分，不要打 2 分。**

**[Tier 6: 无关 1-2]**
- **2分**: 明确是硬件加速、底层算子优化，虽有 Memory 字样但指物理内存。
- **1分**: 完全无关（如图像生成、对抗攻击）。

**输出格式 (JSON Only)**：
{"confidence_score": int, "reasoning": "简短判决理由"}""",
        "user_prompt_template": "请评估以下论文与 '{topic}' 的相关性：\n\n**标题**: {title}\n\n**摘要**: {abstract}{keywords_section}\n\n请按照评分标准给出 1-10 分评分，并以 JSON 格式输出。",
        "keywords_section_template": "\n\n**关键词**: {keywords}"
    }


def build_system_prompt(config_path: str = None) -> str:
    """
    构建 System Prompt
    
    Args:
        config_path: 可选的配置文件路径
    
    Returns:
        System Prompt 字符串
    """
    config = load_prompt_config(config_path)
    topic = config.get("screening_topic", "AI Memory")
    template = config.get("system_prompt", get_default_config()["system_prompt"])
    return template.format(topic=topic)


def build_user_prompt(title: str, abstract: str, keywords: str = "", config_path: str = None) -> str:
    """
    构建 User Prompt
    
    Args:
        title: 论文标题
        abstract: 论文摘要
        keywords: 关键词 (可选)
        config_path: 可选的配置文件路径
    
    Returns:
        User Prompt 字符串
    """
    config = load_prompt_config(config_path)
    topic = config.get("screening_topic", "AI Memory")
    template = config.get("user_prompt_template", get_default_config()["user_prompt_template"])
    keywords_template = config.get("keywords_section_template", get_default_config()["keywords_section_template"])
    
    keywords_section = ""
    if keywords:
        keywords_section = keywords_template.format(keywords=keywords)
    
    return template.format(
        topic=topic,
        title=title,
        abstract=abstract,
        keywords_section=keywords_section
    )


def parse_llm_response(response: str) -> JudgeResult:
    """
    解析 LLM 响应
    
    Args:
        response: LLM 返回的原始字符串
    
    Returns:
        JudgeResult 对象
    """
    import re
    
    try:
        json_match = re.search(r'\{[^{}]*"confidence_score"[^{}]*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = response.strip()
            if json_str.startswith("```"):
                lines = json_str.split("\n")
                json_str = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        
        data = json.loads(json_str)
        
        score = data.get("confidence_score", 3)
        if isinstance(score, float):
            score = int(score)
        
        reasoning = data.get("reasoning", "无判决理由")
        
        return JudgeResult(score=score, reasoning=reasoning)
    
    except json.JSONDecodeError:
        return JudgeResult(score=3, reasoning="JSON 解析失败，进入人工复核")
    except Exception as e:
        return JudgeResult(score=3, reasoning=f"解析错误: {str(e)}")
