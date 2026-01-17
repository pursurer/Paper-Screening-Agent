"""分流路由模块 - 根据 LLM 评分将论文分流至不同通道"""


def router_logic(score: int) -> str:
    """
    根据评分将论文分流至对应通道
    
    Args:
        score: LLM 评分 (1-10)
    
    Returns:
        分流结果: "ACCEPTED" | "HUMAN_REVIEW" | "REJECTED"
    """
    if score >= 4:
        return "ACCEPTED"
    elif score == 3:
        return "HUMAN_REVIEW"
    else:
        return "REJECTED"


def get_relevance_tier(score: int) -> str:
    """
    根据评分返回相关性等级
    
    Args:
        score: LLM 评分 (1-10)
    
    Returns:
        相关性等级: "Core" | "Strong" | "General" | "Marginal" | "Boundary" | "Irrelevant"
    """
    if score >= 9:
        return "Core"
    elif score >= 7:
        return "Strong"
    elif score >= 5:
        return "General"
    elif score == 4:
        return "Marginal"
    elif score == 3:
        return "Boundary"
    else:
        return "Irrelevant"
