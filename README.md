# Paper-Screening-Agent

[![Tests](https://github.com/pursurer/Paper-Screening-Agent/actions/workflows/tests.yml/badge.svg)](https://github.com/pursurer/Paper-Screening-Agent/actions)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An LLM agent that reads paper abstracts, scores how relevant each paper is to one research topic
(1–10), and routes it to accept, human review or reject. It runs on the Gemini API and can spread
the work over several API keys.

It graded 10,000+ papers from the 2025 editions of 10 AI conferences for agent memory: 5,720 were
accepted and 4,421 went to human review. The accepted list is
[Curated-Agent-Memory-Papers](https://github.com/pursurer/Curated-Agent-Memory-Papers); the input
came from [top-ai-conference-papers](https://github.com/pursurer/top-ai-conference-papers).

## How it works

1. Read a CSV of papers (`id`, `title`, `abstract`; `keywords`, `pdf` optional).
2. Ask the LLM for a score and a short reason. The prompt comes from `config/prompts.json`.
3. Route by score. The rule favours recall: a weak but possible match is kept, and an uncertain
   one goes to a person instead of being dropped.

| Score | Tier | Meaning | Route |
| --- | --- | --- | --- |
| 10 | Core | The topic is the paper's main contribution, named in the title | Accept |
| 9 | Core | New method that directly addresses the topic | Accept |
| 7–8 | Strong | Core mechanism closely related | Accept |
| 5–6 | General | Uses the topic in an application | Accept |
| 4 | Marginal | Weak but possible relevance | Accept |
| 3 | Boundary | Uncertain | Human review |
| 1–2 | Irrelevant | Clearly unrelated | Reject |

Results are written as each paper finishes, so a stopped run picks up where it left off: papers
already in the output files are skipped.

## Install

```bash
git clone https://github.com/pursurer/Paper-Screening-Agent.git
cd Paper-Screening-Agent
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python -m src.multi_api_batch \
  --input papers.csv \
  --output output/results \
  --api-keys "KEY1,KEY2"
```

Each key gets its own worker pool. `--concurrency` sets requests per key (default 50) and
`--model` sets the Gemini model (default `gemini-2.5-flash`).

Two files come out:

| File | Content |
| --- | --- |
| `ai_memory_papers_graded.csv` | Accepted papers (score ≥ 4) with score, tier and reason |
| `human_review_boundary.csv` | Boundary papers (score 3) for manual review |

Rejected papers are counted but not written. The file names keep the agent-memory topic they
were first used for.

## Screen a different topic

Edit `config/prompts.json`. The code reads four entries: `screening_topic`, `system_prompt`,
`user_prompt_template` and `keywords_section_template`. The score definitions live inside
`system_prompt` (in Chinese, written for agent memory), so rewrite them for the new topic.
`scoring_tiers` and `routing_rules` only document the scale; the routing thresholds are in
`src/router.py`.

## Other entry points

| Script | Use |
| --- | --- |
| `src/main.py` | One key, one request at a time; reads `GEMINI_API_KEY` from `.env` |
| `src/async_main.py` | One key, concurrent; `batch_process` runs it once per conference |
| `src/batch_process.py` | Nine conferences (all but NeurIPS) from `PAPERS_DATA_ROOT`, default `../top-ai-conference-papers` |
| `src/new_prompt_screen_batch.py` | Experimental 0–100 rescoring with a prompt file you supply |

## Tests

```bash
pytest tests/
```

## License

MIT, see [LICENSE](LICENSE).
