"""
多 API Key 并行批处理脚本
每个 API Key 运行独立的工作池，实现真正的 N×50 并发
"""

import argparse
import asyncio
import csv
import os
from typing import List, Set
from dataclasses import dataclass
import threading

from src.paper_parser import Paper, parse_csv
from src.llm_judge import (
    JudgeResult,
    build_system_prompt,
    build_user_prompt,
    parse_llm_response,
)
from src.router import get_relevance_tier
from src.output_generator import GradedPaper

CSV_FIELDNAMES = [
    "Score", "Relevance_Tier", "id", "title", "keywords",
    "Reasoning", "abstract", "pdf", "forum", "year", "presentation_type"
]


def load_processed_ids(file_path: str) -> Set[str]:
    """加载已处理论文的 ID"""
    processed = set()
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("id"):
                    processed.add(row["id"])
    return processed


@dataclass
class KeyStats:
    """API Key 统计"""
    key_id: int
    total: int = 0
    success: int = 0
    errors: int = 0


class ThreadSafeWriter:
    """线程安全的 CSV 写入器"""
    
    def __init__(self, graded_path: str, review_path: str):
        self.graded_path = graded_path
        self.review_path = review_path
        self.lock = threading.Lock()
        self._init_files()
    
    def _init_files(self):
        for path in [self.graded_path, self.review_path]:
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
                    writer.writeheader()
    
    def write(self, graded_paper: GradedPaper):
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


from concurrent.futures import ThreadPoolExecutor

async def call_llm_single(
    api_key: str,
    paper: Paper,
    model: str,
    semaphore: asyncio.Semaphore,
    stats: KeyStats,
    executor: ThreadPoolExecutor,
    retry_count: int = 3,
) -> JudgeResult:
    """单个 API 调用（带信号量控制和独立线程池）"""
    async with semaphore:
        for attempt in range(retry_count):
            try:
                from google import genai
                
                client = genai.Client(api_key=api_key)
                system_prompt = build_system_prompt()
                user_prompt = build_user_prompt(paper.title, paper.abstract, paper.keywords)
                full_prompt = f"{system_prompt}\n\n{user_prompt}"
                
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    executor,  # 使用独立的线程池
                    lambda: client.models.generate_content(model=model, contents=full_prompt)
                )
                
                stats.success += 1
                return parse_llm_response(response.text)
            
            except Exception as e:
                if attempt < retry_count - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    stats.errors += 1
                    return JudgeResult(score=3, reasoning=f"API 调用失败: {str(e)}")
        
        return JudgeResult(score=3, reasoning="未知错误")


async def process_paper_with_key(
    api_key: str,
    paper: Paper,
    model: str,
    semaphore: asyncio.Semaphore,
    writer: ThreadSafeWriter,
    progress: dict,
    stats: KeyStats,
    executor: ThreadPoolExecutor,
) -> GradedPaper:
    """使用指定 Key 处理单篇论文"""
    stats.total += 1
    result = await call_llm_single(api_key, paper, model, semaphore, stats, executor)
    
    tier = get_relevance_tier(result.score)
    graded = GradedPaper(
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
    
    writer.write(graded)
    
    with threading.Lock():
        progress["done"] += 1
        print(f"  [{progress['done']}/{progress['total']}] Key{stats.key_id} Score={result.score} | {paper.title[:45]}...")
    
    return graded


async def run_worker_pool(
    api_key: str,
    key_id: int,
    papers: List[Paper],
    model: str,
    concurrency: int,
    writer: ThreadSafeWriter,
    progress: dict,
) -> List[GradedPaper]:
    """运行单个 API Key 的工作池（独立线程池）"""
    semaphore = asyncio.Semaphore(concurrency)
    stats = KeyStats(key_id=key_id)
    
    # 为每个 Key 创建独立的线程池，大小等于并发数
    executor = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix=f"Key{key_id}")
    
    try:
        tasks = [
            process_paper_with_key(api_key, paper, model, semaphore, writer, progress, stats, executor)
            for paper in papers
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        print(f"📊 Key{key_id}: 总计={stats.total}, 成功={stats.success}, 失败={stats.errors}")
        
        return [r for r in results if isinstance(r, GradedPaper)]
    finally:
        executor.shutdown(wait=False)


async def run_multi_api_pipeline(
    input_path: str,
    output_dir: str,
    api_keys: List[str],
    model: str = "gemini-2.5-flash",
    concurrency_per_key: int = 50,
):
    """运行多 API 并行处理管道 - 每个 Key 独立工作池"""
    os.makedirs(output_dir, exist_ok=True)
    
    graded_path = os.path.join(output_dir, "ai_memory_papers_graded.csv")
    review_path = os.path.join(output_dir, "human_review_boundary.csv")
    
    print(f"📂 读取论文: {input_path}")
    all_papers = parse_csv(input_path)
    
    processed_ids = load_processed_ids(graded_path) | load_processed_ids(review_path)
    if processed_ids:
        print(f"🔄 断点续传: 已跳过 {len(processed_ids)} 篇已处理论文")
    
    papers = [p for p in all_papers if p.id not in processed_ids]
    
    if not papers:
        print("✅ 所有论文已处理完成")
        return []
    
    num_keys = len(api_keys)
    total_concurrency = num_keys * concurrency_per_key
    
    print(f"📝 共 {len(papers)} 篇论文待处理")
    print(f"🔑 使用 {num_keys} 个 API Key，每个 {concurrency_per_key} 并发，总并发: {total_concurrency}")
    
    # 将论文平均分配给各个 Key
    paper_chunks = [[] for _ in range(num_keys)]
    for i, paper in enumerate(papers):
        paper_chunks[i % num_keys].append(paper)
    
    for i, chunk in enumerate(paper_chunks):
        print(f"  Key{i+1}: 分配 {len(chunk)} 篇论文")
    
    writer = ThreadSafeWriter(graded_path, review_path)
    progress = {"done": 0, "total": len(papers)}
    
    # 每个 Key 独立运行工作池
    pool_tasks = [
        run_worker_pool(
            api_key=api_keys[i],
            key_id=i + 1,
            papers=paper_chunks[i],
            model=model,
            concurrency=concurrency_per_key,
            writer=writer,
            progress=progress,
        )
        for i in range(num_keys)
    ]
    
    all_results = await asyncio.gather(*pool_tasks)
    
    # 合并结果
    results = []
    for pool_result in all_results:
        results.extend(pool_result)
    
    accepted = sum(1 for r in results if r.score >= 4)
    review = sum(1 for r in results if r.score == 3)
    rejected = sum(1 for r in results if r.score <= 2)
    
    print(f"\n{'='*50}")
    print(f"📈 统计结果:")
    print(f"Accepted (>=4): {accepted}")
    print(f"Review (3): {review}")
    print(f"Rejected (<=2): {rejected}")
    print(f"{'='*50}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="多 API Key 并行论文筛选")
    parser.add_argument("--input", "-i", required=True, help="输入 CSV 文件路径")
    parser.add_argument("--output", "-o", required=True, help="输出目录")
    parser.add_argument("--api-keys", required=True, help="API Keys (逗号分隔)")
    parser.add_argument("--model", default="gemini-2.5-flash", help="模型名称")
    parser.add_argument("--concurrency", "-c", type=int, default=50, help="每个 Key 的并发数")
    
    args = parser.parse_args()
    
    api_keys = [k.strip() for k in args.api_keys.split(",") if k.strip()]
    
    asyncio.run(run_multi_api_pipeline(
        input_path=args.input,
        output_dir=args.output,
        api_keys=api_keys,
        model=args.model,
        concurrency_per_key=args.concurrency,
    ))


if __name__ == "__main__":
    main()
