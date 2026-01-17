"""异步高并发主程序 - 50并发论文筛选 (增量写入版)"""
import argparse
import asyncio
import csv
import os
import sys
import threading
from typing import List, Optional, Set

from dotenv import load_dotenv

from src.paper_parser import Paper, parse_csv
from src.llm_judge import (
    JudgeResult,
    build_system_prompt,
    build_user_prompt,
    parse_llm_response,
)
from src.router import router_logic, get_relevance_tier
from src.output_generator import GradedPaper
from src.statistics import compute_statistics, format_statistics


# CSV 字段顺序
CSV_FIELDNAMES = [
    "Score", "Relevance_Tier", "id", "title", "keywords",
    "Reasoning", "abstract", "pdf", "forum", "year", "presentation_type"
]


def load_processed_ids(file_path: str) -> Set[str]:
    """加载已处理论文的 ID 集合（用于断点续传）"""
    processed = set()
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("id"):
                    processed.add(row["id"])
                elif row.get("title"):
                    processed.add(row["title"])
    return processed


class IncrementalWriter:
    """线程安全的增量 CSV 写入器"""
    
    def __init__(self, graded_path: str, review_path: str):
        self.graded_path = graded_path
        self.review_path = review_path
        self.lock = threading.Lock()
        self._init_files()
    
    def _init_files(self):
        """初始化 CSV 文件（如果不存在则创建表头）"""
        for path in [self.graded_path, self.review_path]:
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                    writer.writeheader()
    
    def write(self, graded_paper: GradedPaper):
        """根据分数写入对应文件"""
        row = {
            "Score": graded_paper.score,
            "Relevance_Tier": graded_paper.relevance_tier,
            "id": graded_paper.id,
            "title": graded_paper.title,
            "keywords": graded_paper.keywords,
            "Reasoning": graded_paper.reasoning,
            "abstract": graded_paper.abstract,
            "pdf": graded_paper.pdf,
            "forum": graded_paper.forum,
            "year": graded_paper.year,
            "presentation_type": graded_paper.presentation_type,
        }
        
        with self.lock:
            if graded_paper.score >= 4:
                with open(self.graded_path, "a", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                    writer.writerow(row)
            elif graded_paper.score == 3:
                with open(self.review_path, "a", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                    writer.writerow(row)


async def async_call_llm_api(
    title: str,
    abstract: str,
    keywords: str,
    api_key: str,
    model: str,
    semaphore: asyncio.Semaphore,
    retry_count: int = 3,
) -> JudgeResult:
    """
    异步调用 Gemini API 进行论文判决
    
    Args:
        title: 论文标题
        abstract: 论文摘要
        keywords: 关键词
        api_key: Gemini API Key
        model: 模型名称
        semaphore: 并发控制信号量
        retry_count: 重试次数
    
    Returns:
        JudgeResult 对象
    """
    async with semaphore:
        for attempt in range(retry_count):
            try:
                from google import genai
                
                client = genai.Client(api_key=api_key)
                
                system_prompt = build_system_prompt()
                user_prompt = build_user_prompt(title, abstract, keywords)
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model=model,
                        contents=full_prompt,
                    )
                )
                
                content = response.text
                return parse_llm_response(content)
            
            except Exception as e:
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    return JudgeResult(score=3, reasoning=f"API 调用失败: {str(e)}")
    
    return JudgeResult(score=3, reasoning="未知错误")


async def process_paper_async(
    paper: Paper,
    api_key: str,
    model: str,
    semaphore: asyncio.Semaphore,
    progress: dict,
    writer: IncrementalWriter,
) -> GradedPaper:
    """
    异步处理单篇论文并立即写入文件
    
    Args:
        paper: Paper 对象
        api_key: Gemini API Key
        model: 模型名称
        semaphore: 并发控制信号量
        progress: 进度字典
        writer: 增量写入器
    
    Returns:
        GradedPaper 对象
    """
    result = await async_call_llm_api(
        title=paper.title,
        abstract=paper.abstract,
        keywords=paper.keywords,
        api_key=api_key,
        model=model,
        semaphore=semaphore,
    )
    
    tier = get_relevance_tier(result.score)
    
    graded_paper = GradedPaper(
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
    
    writer.write(graded_paper)
    
    progress["completed"] += 1
    print(f"  [{progress['completed']}/{progress['total']}] Score={result.score} | {paper.title[:50]}...")
    
    return graded_paper


async def run_pipeline_async(
    input_path: str,
    output_dir: str,
    api_key: str,
    model: str,
    concurrency: int = 50,
    limit: Optional[int] = None,
    resume: bool = True,
) -> List[GradedPaper]:
    """
    异步运行完整筛选管道（支持增量写入和断点续传）
    
    Args:
        input_path: 输入 CSV 文件路径
        output_dir: 输出目录
        api_key: Gemini API Key
        model: 模型名称
        concurrency: 并发数 (默认 50)
        limit: 限制处理论文数量 (用于测试)
        resume: 是否启用断点续传 (默认 True)
    
    Returns:
        GradedPaper 列表
    """
    os.makedirs(output_dir, exist_ok=True)
    
    graded_path = os.path.join(output_dir, "ai_memory_papers_graded.csv")
    review_path = os.path.join(output_dir, "human_review_boundary.csv")
    
    print(f"📂 读取论文: {input_path}")
    all_papers = parse_csv(input_path)
    
    if limit:
        all_papers = all_papers[:limit]
    
    processed_ids: Set[str] = set()
    if resume:
        processed_ids = load_processed_ids(graded_path) | load_processed_ids(review_path)
        if processed_ids:
            print(f"🔄 断点续传: 已跳过 {len(processed_ids)} 篇已处理论文")
    
    papers = [
        p for p in all_papers
        if (p.id not in processed_ids and p.title not in processed_ids)
    ]
    
    if not papers:
        print("✅ 所有论文已处理完成")
        return []
    
    print(f"📝 共 {len(papers)} 篇论文待处理 (并发数: {concurrency})")
    
    writer = IncrementalWriter(graded_path, review_path)
    semaphore = asyncio.Semaphore(concurrency)
    progress = {"completed": 0, "total": len(papers)}
    
    tasks = [
        process_paper_async(paper, api_key, model, semaphore, progress, writer)
        for paper in papers
    ]
    
    graded_papers = await asyncio.gather(*tasks)
    
    print("\n" + "=" * 50)
    print("📈 统计结果:")
    stats = compute_statistics(list(graded_papers))
    print(format_statistics(stats))
    print("=" * 50)
    
    return list(graded_papers)


def main():
    """主程序入口"""
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="高精度分级 AI Memory 论文筛选系统 (高并发版)"
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
        "-c", "--concurrency",
        type=int,
        default=50,
        help="并发数 (默认: 50)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("GEMINI_API_KEY"),
        help="Gemini API Key (默认从环境变量读取)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
        help="模型名称 (默认: gemini-3-flash-preview)",
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"❌ 输入文件不存在: {args.input}")
        sys.exit(1)
    
    if not args.api_key:
        print("❌ 未配置 API Key，请设置 GEMINI_API_KEY 环境变量或使用 --api-key 参数")
        sys.exit(1)
    
    asyncio.run(run_pipeline_async(
        input_path=args.input,
        output_dir=args.output,
        api_key=args.api_key,
        model=args.model,
        concurrency=args.concurrency,
        limit=args.limit,
    ))


if __name__ == "__main__":
    main()
