"""使用新提示词对多个会议 CSV 进行 0-100 打分重筛。"""

import argparse
import csv
import json
import os
import random
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Tuple

from google import genai
from google.genai import types


# 数据根目录：顶会论文 CSV 所在目录，可用 PAPERS_DATA_ROOT 覆盖
DATA_ROOT = os.environ.get("PAPERS_DATA_ROOT", "../top-ai-conference-papers")

DEFAULT_INPUTS = {
    # 用户要求 ICLR 使用 2025 年版本（约 3000+ 篇）
    "ICLR": os.path.join(DATA_ROOT, "ICLR/iclr_papers_2025.csv"),
    "ICLR_2026": os.path.join(DATA_ROOT, "ICLR/iclr_papers_2026.csv"),
    "ICML": os.path.join(DATA_ROOT, "ICML/icml_papers.csv"),
    "NeurIPS": os.path.join(DATA_ROOT, "NeurIPS/neurips_papers.csv"),
}


DEFAULT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "matched_dimensions": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["score", "matched_dimensions", "reason"],
}


def bucket(score: int) -> str:
    """按新提示词规则分桶。"""
    if score >= 80:
        return "Priority1_80_100"
    if score >= 60:
        return "Priority2_60_79"
    if score >= 40:
        return "Priority3_40_59"
    return "Priority4_lt40"


def build_query(base_prompt: str, title: str, abstract: str, keywords: str) -> str:
    """构建单篇论文的查询提示词。"""
    return (
        f"{base_prompt}\n\n"
        "---\n"
        "现在仅评估下面这一篇论文，请不要复述规则文本。\n"
        f"论文标题: {title}\n"
        f"论文摘要: {abstract}\n"
        f"关键词: {keywords}\n\n"
        "请严格只输出一行 JSON（不要 Markdown、不要额外文字）：\n"
        '{"score": 0-100之间的整数, "matched_dimensions": "如 Forms-.../Functions-.../Dynamics-.../Frontier-...", "reason": "一句话理由；若40-59请写明需人工复核"}'
    )


def parse_response(text: str) -> Tuple[int, str, str, bool]:
    """解析模型输出，保证返回可用分数。"""
    text = (text or "").strip()
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            score = data.get("score", None)
            if isinstance(score, float):
                score = int(score)
            if isinstance(score, str) and score.strip().isdigit():
                score = int(score.strip())
            if isinstance(score, int):
                score = max(0, min(100, score))
                dims = str(data.get("matched_dimensions", ""))
                reason = str(data.get("reason", ""))
                return score, dims, reason, True
        except Exception:
            pass

    number_match = re.search(r"(?<!\d)(100|[1-9]?\d)(?!\d)", text)
    if number_match:
        score = int(number_match.group(1))
        return score, "", text.replace("\n", " ")[:500], False

    return 50, "", "解析失败，默认50", False


def load_processed_keys(raw_path: Path) -> set:
    """读取已处理记录 key，支持断点续跑。"""
    processed = set()
    if not raw_path.exists():
        return processed

    with raw_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = row.get("_resume_key", "")
            if key:
                processed.add(key)
    return processed


def make_resume_key(row: Dict[str, str]) -> str:
    """生成稳定的断点 key。"""
    rid = (row.get("id") or "").strip()
    title = (row.get("title") or "").strip()
    if rid:
        return f"id:{rid}"
    return f"title:{title}"


def score_one(
    row: Dict[str, str],
    key_idx: int,
    api_keys: List[str],
    model: str,
    max_retries: int,
    base_prompt: str,
    generation_config: types.GenerateContentConfig,
) -> Dict[str, str]:
    """评分单篇论文。"""
    api_key = api_keys[key_idx % len(api_keys)]
    title = row.get("title", "")
    abstract = row.get("abstract", "")
    keywords = row.get("keywords", "")
    query = build_query(base_prompt, title, abstract, keywords)

    last_err = ""
    for attempt in range(max_retries):
        try:
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model=model,
                contents=query,
                config=generation_config,
            )
            text = resp.text or ""
            score, dims, reason, parse_ok = parse_response(text)
            return {
                **row,
                "_resume_key": make_resume_key(row),
                "score_100": str(score),
                "priority_bucket": bucket(score),
                "matched_dimensions": dims,
                "reason": reason,
                "parse_ok": "1" if parse_ok else "0",
            }
        except Exception as exc:
            last_err = str(exc)
            backoff = min(30.0, 2**attempt) + random.uniform(0.0, 0.5)
            time.sleep(backoff)

    return {
        **row,
        "_resume_key": make_resume_key(row),
        "score_100": "50",
        "priority_bucket": bucket(50),
        "matched_dimensions": "",
        "reason": f"调用失败默认50: {last_err}",
        "parse_ok": "0",
    }


def build_generation_config(
    args: argparse.Namespace,
) -> Tuple[types.GenerateContentConfig, Dict[str, Any]]:
    """根据 CLI 参数构建可复现的生成配置。"""
    use_schema = not args.disable_response_schema

    thinking_kwargs: Dict[str, Any] = {"include_thoughts": args.include_thoughts}
    if args.thinking_level:
        # Gemini API 限制：thinking_level 与 thinking_budget 只能二选一。
        thinking_kwargs["thinking_level"] = args.thinking_level
    elif args.thinking_budget >= 0:
        thinking_kwargs["thinking_budget"] = args.thinking_budget

    config_kwargs: Dict[str, Any] = {
        "temperature": args.temperature,
        "top_p": args.top_p,
        "candidate_count": args.candidate_count,
        "max_output_tokens": args.max_output_tokens,
        "seed": args.seed,
        "presence_penalty": args.presence_penalty,
        "frequency_penalty": args.frequency_penalty,
        "response_mime_type": args.response_mime_type,
        "response_logprobs": args.response_logprobs,
        "thinking_config": types.ThinkingConfig(**thinking_kwargs),
    }

    if args.top_k >= 0:
        config_kwargs["top_k"] = args.top_k
    if args.response_logprobs:
        config_kwargs["logprobs"] = args.logprobs
    if use_schema:
        config_kwargs["response_schema"] = DEFAULT_RESPONSE_SCHEMA

    config = types.GenerateContentConfig(**config_kwargs)
    snapshot = {
        "temperature": args.temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "seed": args.seed,
        "candidate_count": args.candidate_count,
        "max_output_tokens": args.max_output_tokens,
        "presence_penalty": args.presence_penalty,
        "frequency_penalty": args.frequency_penalty,
        "response_mime_type": args.response_mime_type,
        "response_logprobs": args.response_logprobs,
        "logprobs": args.logprobs if args.response_logprobs else None,
        "thinking_level": args.thinking_level or None,
        "thinking_budget": args.thinking_budget if args.thinking_budget >= 0 else None,
        "include_thoughts": args.include_thoughts,
        "use_response_schema": use_schema,
    }
    return config, snapshot


def write_rows(path: Path, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    """写 CSV。"""
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def run_conference(
    name: str,
    input_path: Path,
    out_dir: Path,
    api_keys: List[str],
    model: str,
    concurrency_per_key: int,
    max_retries: int,
    base_prompt: str,
    generation_config: types.GenerateContentConfig,
    config_snapshot: Dict[str, Any],
    print_every: int,
) -> None:
    """执行单个会议的重筛。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "scored_raw_incremental.csv"
    sorted_path = out_dir / "scored_all_0_100.csv"
    p1_path = out_dir / "priority1_80_100.csv"
    p2_path = out_dir / "priority2_60_79.csv"
    p3_path = out_dir / "priority3_40_59_review.csv"
    p4_path = out_dir / "priority4_lt40.csv"
    summary_json = out_dir / "summary.json"
    summary_txt = out_dir / "summary.txt"

    with input_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        input_rows = list(reader)
        input_fields = reader.fieldnames or []

    processed = load_processed_keys(raw_path)
    pending = [r for r in input_rows if make_resume_key(r) not in processed]

    out_fields = input_fields + [
        "_resume_key",
        "score_100",
        "priority_bucket",
        "matched_dimensions",
        "reason",
        "parse_ok",
    ]

    if not raw_path.exists():
        write_rows(raw_path, out_fields, [])

    print(f"\n=== {name} ===")
    print(f"input={input_path}")
    print(f"total={len(input_rows)} pending={len(pending)}")

    progress = {"done": 0, "total": len(pending)}
    lock = Lock()

    if pending:
        workers = max(1, len(api_keys) * concurrency_per_key)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [
                ex.submit(
                    score_one,
                    row,
                    idx,
                    api_keys,
                    model,
                    max_retries,
                    base_prompt,
                    generation_config,
                )
                for idx, row in enumerate(pending)
            ]

            with raw_path.open("a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=out_fields)
                for fut in as_completed(futures):
                    result = fut.result()
                    writer.writerow(result)
                    with lock:
                        progress["done"] += 1
                        done = progress["done"]
                        total = progress["total"]
                        if done % print_every == 0 or done == total:
                            print(
                                f"[{done}/{total}] score={result['score_100']} "
                                f"bucket={result['priority_bucket']} "
                                f"title={result.get('title','')[:56]}"
                            )

    # 聚合并排序
    with raw_path.open("r", encoding="utf-8", newline="") as f:
        all_rows = list(csv.DictReader(f))

    all_rows.sort(key=lambda r: int(r.get("score_100", "0") or 0), reverse=True)
    write_rows(sorted_path, out_fields, all_rows)

    p1 = [r for r in all_rows if r["priority_bucket"] == "Priority1_80_100"]
    p2 = [r for r in all_rows if r["priority_bucket"] == "Priority2_60_79"]
    p3 = [r for r in all_rows if r["priority_bucket"] == "Priority3_40_59"]
    p4 = [r for r in all_rows if r["priority_bucket"] == "Priority4_lt40"]

    write_rows(p1_path, out_fields, p1)
    write_rows(p2_path, out_fields, p2)
    write_rows(p3_path, out_fields, p3)
    write_rows(p4_path, out_fields, p4)

    parse_fail = sum(1 for r in all_rows if r.get("parse_ok") != "1")
    avg_score = (
        round(sum(int(r["score_100"]) for r in all_rows) / len(all_rows), 2)
        if all_rows
        else 0
    )
    bucket_counts = Counter(r["priority_bucket"] for r in all_rows)

    summary = {
        "conference": name,
        "input_path": str(input_path),
        "model": model,
        "generation_config": config_snapshot,
        "total_rows": len(all_rows),
        "avg_score_100": avg_score,
        "parse_fail_count": parse_fail,
        "priority_distribution": dict(bucket_counts),
        "output_files": {
            "raw": str(raw_path),
            "all_sorted": str(sorted_path),
            "p1_80_100": str(p1_path),
            "p2_60_79": str(p2_path),
            "p3_40_59_review": str(p3_path),
            "p4_lt40": str(p4_path),
        },
    }

    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with summary_txt.open("w", encoding="utf-8") as f:
        for k, v in summary.items():
            f.write(f"{k}: {v}\n")

    print(
        f"done {name}: total={summary['total_rows']} "
        f"avg={summary['avg_score_100']} parse_fail={parse_fail} "
        f"dist={summary['priority_distribution']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="新提示词批量重筛（0-100）")
    parser.add_argument(
        "--prompt-file",
        required=True,
        help="新提示词文件路径",
    )
    parser.add_argument(
        "--output-base",
        default=os.path.join("output", "new_prompt_rerun"),
        help="输出根目录",
    )
    parser.add_argument(
        "--conferences",
        default="ICLR_2026,ICML,NeurIPS,ICLR",
        help="逗号分隔的会议列表",
    )
    parser.add_argument(
        "--api-keys",
        default=os.getenv("API_KEYS", ""),
        help="逗号分隔 API keys，或通过环境变量 API_KEYS 提供",
    )
    parser.add_argument("--model", default=os.getenv("MODEL_NAME", "gemini-3-flash-preview"))
    parser.add_argument("--concurrency-per-key", type=int, default=6)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--top-k", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20260301)
    parser.add_argument("--candidate-count", type=int, default=1)
    parser.add_argument("--max-output-tokens", type=int, default=1536)
    parser.add_argument("--presence-penalty", type=float, default=0.0)
    parser.add_argument("--frequency-penalty", type=float, default=0.0)
    parser.add_argument("--response-mime-type", default="application/json")
    parser.add_argument("--disable-response-schema", action="store_true")
    parser.add_argument("--response-logprobs", action="store_true")
    parser.add_argument("--logprobs", type=int, default=5)
    parser.add_argument(
        "--thinking-level",
        choices=["LOW", "MEDIUM", "HIGH"],
        default="HIGH",
    )
    parser.add_argument("--thinking-budget", type=int, default=-1)
    parser.add_argument("--include-thoughts", action="store_true")
    parser.add_argument("--print-every", type=int, default=25)
    args = parser.parse_args()

    api_keys = [k.strip() for k in args.api_keys.split(",") if k.strip()]
    if not api_keys:
        raise SystemExit("未提供 API keys，请使用 --api-keys 或设置 API_KEYS")

    prompt_path = Path(args.prompt_file)
    if not prompt_path.exists():
        raise SystemExit(f"提示词文件不存在: {prompt_path}")
    base_prompt = prompt_path.read_text(encoding="utf-8")
    generation_config, config_snapshot = build_generation_config(args)

    output_base = Path(args.output_base)
    output_base.mkdir(parents=True, exist_ok=True)

    selected = [c.strip() for c in args.conferences.split(",") if c.strip()]
    run_plan = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "prompt_file": str(prompt_path),
        "output_base": str(output_base),
        "conference_order": selected,
        "generation_config": config_snapshot,
        "inputs": {c: DEFAULT_INPUTS.get(c, "") for c in selected},
    }
    (output_base / "run_plan.json").write_text(
        json.dumps(run_plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    for conf in selected:
        if conf not in DEFAULT_INPUTS:
            print(f"skip unknown conference: {conf}")
            continue

        input_path = Path(DEFAULT_INPUTS[conf])
        if not input_path.exists():
            print(f"skip missing input: {input_path}")
            continue

        run_conference(
            name=conf,
            input_path=input_path,
            out_dir=output_base / conf,
            api_keys=api_keys,
            model=args.model,
            concurrency_per_key=args.concurrency_per_key,
            max_retries=args.max_retries,
            base_prompt=base_prompt,
            generation_config=generation_config,
            config_snapshot=config_snapshot,
            print_every=max(1, args.print_every),
        )


if __name__ == "__main__":
    main()
