"""批量处理多会议论文筛选"""
import argparse
import asyncio
import os
import sys
from typing import Dict, List

from dotenv import load_dotenv

from src.async_main import run_pipeline_async


# 会议配置：会议名称 -> CSV 文件路径
CONFERENCE_CONFIG: Dict[str, str] = {
    "AAAI": "/Users/huigu/论文系统/顶会论文信息/AAAI/aaai_papers.csv",
    "ACL": "/Users/huigu/论文系统/顶会论文信息/ACL/acl_papers.csv",
    "EMNLP": "/Users/huigu/论文系统/顶会论文信息/EMNLP/emnlp_papers.csv",
    "ICLR": "/Users/huigu/论文系统/顶会论文信息/ICLR/iclr_papers.csv",
    "ICML": "/Users/huigu/论文系统/顶会论文信息/ICML/icml_papers.csv",
    "IJCAI": "/Users/huigu/论文系统/顶会论文信息/IJCAI/ijcai_papers.csv",
    "NAACL": "/Users/huigu/论文系统/顶会论文信息/NAACL/naacl_papers.csv",
    "AISTATS": "/Users/huigu/论文系统/顶会论文信息/AISTATS/aistats_papers.csv",
    "AAMAS": "/Users/huigu/论文系统/顶会论文信息/AAMAS/aamas_2025_unified.csv",
}


async def process_conference(
    conference: str,
    input_path: str,
    output_base: str,
    api_key: str,
    model: str,
    concurrency: int,
    resume: bool = True,
) -> Dict:
    """
    处理单个会议的论文筛选
    
    Returns:
        包含统计信息的字典
    """
    output_dir = os.path.join(output_base, conference)
    
    print(f"\n{'='*60}")
    print(f"🎯 开始处理: {conference}")
    print(f"{'='*60}")
    
    graded_papers = await run_pipeline_async(
        input_path=input_path,
        output_dir=output_dir,
        api_key=api_key,
        model=model,
        concurrency=concurrency,
        resume=resume,
    )
    
    # 统计结果
    accepted = sum(1 for p in graded_papers if p.score >= 4)
    review = sum(1 for p in graded_papers if p.score == 3)
    rejected = sum(1 for p in graded_papers if p.score <= 2)
    
    return {
        "conference": conference,
        "total": len(graded_papers),
        "accepted": accepted,
        "review": review,
        "rejected": rejected,
    }


async def batch_process(
    conferences: List[str],
    output_base: str,
    api_key: str,
    model: str,
    concurrency: int,
    skip_completed: bool = False,
) -> List[Dict]:
    """
    批量处理多个会议
    
    Args:
        conferences: 会议名称列表
        output_base: 输出根目录
        api_key: Gemini API Key
        model: 模型名称
        concurrency: 并发数
        skip_completed: 是否跳过已完成的会议
    
    Returns:
        各会议统计结果列表
    """
    results = []
    
    for conference in conferences:
        if conference not in CONFERENCE_CONFIG:
            print(f"⚠️ 未知会议: {conference}，跳过")
            continue
        
        input_path = CONFERENCE_CONFIG[conference]
        output_dir = os.path.join(output_base, conference)
        graded_file = os.path.join(output_dir, "ai_memory_papers_graded.csv")
        
        # 检查是否已完成
        if skip_completed and os.path.exists(graded_file):
            print(f"⏭️ 跳过已完成: {conference}")
            continue
        
        # 检查输入文件是否存在
        if not os.path.exists(input_path):
            print(f"❌ 输入文件不存在: {input_path}")
            continue
        
        result = await process_conference(
            conference=conference,
            input_path=input_path,
            output_base=output_base,
            api_key=api_key,
            model=model,
            concurrency=concurrency,
            resume=True,
        )
        results.append(result)
    
    return results


def print_summary(results: List[Dict]):
    """打印汇总统计"""
    print("\n" + "=" * 60)
    print("📊 批量处理汇总")
    print("=" * 60)
    print(f"{'会议':<10} {'总数':>8} {'Accepted':>10} {'Review':>8} {'Rejected':>10}")
    print("-" * 60)
    
    total_all = 0
    accepted_all = 0
    review_all = 0
    rejected_all = 0
    
    for r in results:
        print(f"{r['conference']:<10} {r['total']:>8} {r['accepted']:>10} {r['review']:>8} {r['rejected']:>10}")
        total_all += r['total']
        accepted_all += r['accepted']
        review_all += r['review']
        rejected_all += r['rejected']
    
    print("-" * 60)
    print(f"{'合计':<10} {total_all:>8} {accepted_all:>10} {review_all:>8} {rejected_all:>10}")
    print("=" * 60)


def main():
    """主程序入口"""
    load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="批量处理多会议论文筛选"
    )
    parser.add_argument(
        "--conferences",
        nargs="+",
        help="指定要处理的会议列表",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="处理所有会议",
    )
    parser.add_argument(
        "-o", "--output",
        default="output",
        help="输出根目录 (默认: output)",
    )
    parser.add_argument(
        "-c", "--concurrency",
        type=int,
        default=50,
        help="并发数 (默认: 50)",
    )
    parser.add_argument(
        "--skip-completed",
        action="store_true",
        help="跳过已完成的会议",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("GEMINI_API_KEY"),
        help="Gemini API Key",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
        help="模型名称",
    )
    
    args = parser.parse_args()
    
    # 确定要处理的会议列表
    if args.all:
        conferences = list(CONFERENCE_CONFIG.keys())
    elif args.conferences:
        conferences = args.conferences
    else:
        print("❌ 请指定 --conferences 或 --all")
        sys.exit(1)
    
    if not args.api_key:
        print("❌ 未配置 API Key")
        sys.exit(1)
    
    print(f"📋 待处理会议: {', '.join(conferences)}")
    print(f"⚡ 并发数: {args.concurrency}")
    
    # 运行批量处理
    results = asyncio.run(batch_process(
        conferences=conferences,
        output_base=args.output,
        api_key=args.api_key,
        model=args.model,
        concurrency=args.concurrency,
        skip_completed=args.skip_completed,
    ))
    
    # 打印汇总
    if results:
        print_summary(results)


if __name__ == "__main__":
    main()
