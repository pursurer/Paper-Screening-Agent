"""主程序 - 论文筛选管道入口"""
import argparse
import os
import sys
from typing import List, Optional

from dotenv import load_dotenv

from src.paper_parser import Paper, parse_csv
from src.llm_judge import (
    JudgeResult,
    build_system_prompt,
    build_user_prompt,
    parse_llm_response,
)
from src.router import router_logic, get_relevance_tier
from src.output_generator import GradedPaper, write_graded_csv, write_review_csv
from src.statistics import print_statistics


def call_llm_api(
    title: str,
    abstract: str,
    keywords: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> JudgeResult:
    """
    调用 Gemini API 进行论文判决
    
    Args:
        title: 论文标题
        abstract: 论文摘要
        keywords: 关键词
        api_key: Gemini API Key
        model: 模型名称
    
    Returns:
        JudgeResult 对象
    """
    if not api_key:
        return JudgeResult(score=3, reasoning="API Key 未配置，进入人工复核")
    
    try:
        from google import genai
        
        client = genai.Client(api_key=api_key)
        
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(title, abstract, keywords)
        
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        response = client.models.generate_content(
            model=model or "gemini-3-flash-preview",
            contents=full_prompt,
        )
        
        content = response.text
        return parse_llm_response(content)
    
    except Exception as e:
        return JudgeResult(score=3, reasoning=f"API 调用失败: {str(e)}")


def process_paper(
    paper: Paper,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> GradedPaper:
    """
    处理单篇论文: LLM 判决 → 分流路由 → 生成 GradedPaper
    
    Args:
        paper: Paper 对象
        api_key: Gemini API Key
        model: 模型名称
    
    Returns:
        GradedPaper 对象
    """
    result = call_llm_api(
        title=paper.title,
        abstract=paper.abstract,
        keywords=paper.keywords,
        api_key=api_key,
        model=model,
    )
    
    tier = get_relevance_tier(result.score)
    
    return GradedPaper(
        score=result.score,
        relevance_tier=tier,
        id=paper.id,
        title=paper.title,
        keywords=paper.keywords,
        reasoning=result.reasoning,
        abstract=paper.abstract,
        pdf=paper.pdf,
        forum=paper.forum,
        year=paper.year,
        presentation_type=paper.presentation_type,
    )


def run_pipeline(
    input_path: str,
    output_dir: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[GradedPaper]:
    """
    运行完整筛选管道
    
    Args:
        input_path: 输入 CSV 文件路径
        output_dir: 输出目录
        api_key: Gemini API Key
        model: 模型名称
        limit: 限制处理论文数量 (用于测试)
    
    Returns:
        GradedPaper 列表
    """
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"📂 读取论文: {input_path}")
    papers = parse_csv(input_path)
    
    if limit:
        papers = papers[:limit]
    
    print(f"📝 共 {len(papers)} 篇论文待处理")
    
    graded_papers: List[GradedPaper] = []
    accepted_papers: List[GradedPaper] = []
    review_papers: List[GradedPaper] = []
    
    for i, paper in enumerate(papers):
        print(f"  [{i+1}/{len(papers)}] {paper.title[:50]}...")
        
        graded = process_paper(paper, api_key, model)
        graded_papers.append(graded)
        
        route = router_logic(graded.score)
        if route == "ACCEPTED":
            accepted_papers.append(graded)
        elif route == "HUMAN_REVIEW":
            review_papers.append(graded)
    
    graded_path = os.path.join(output_dir, "ai_memory_papers_graded.csv")
    review_path = os.path.join(output_dir, "human_review_boundary.csv")
    
    print(f"\n📊 写入主数据库: {graded_path}")
    write_graded_csv(accepted_papers, graded_path)
    
    print(f"📋 写入边界复核: {review_path}")
    write_review_csv(review_papers, review_path)
    
    print("\n" + "=" * 50)
    print("📈 统计结果:")
    print_statistics(graded_papers)
    print("=" * 50)
    
    return graded_papers


def main():
    """主程序入口"""
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="高精度分级 AI Memory 论文筛选系统"
    )
    parser.add_argument(
        "input",
        help="输入论文 CSV 文件路径",
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="输出目录 (默认: output)",
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        help="限制处理论文数量 (用于测试)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("GEMINI_API_KEY"),
        help="Gemini API Key (默认从环境变量读取)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
        help="模型名称 (默认: gemini-2.0-flash)",
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"❌ 输入文件不存在: {args.input}")
        sys.exit(1)
    
    run_pipeline(
        input_path=args.input,
        output_dir=args.output,
        api_key=args.api_key,
        model=args.model,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
