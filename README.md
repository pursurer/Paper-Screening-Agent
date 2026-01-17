# 🔬 Paper-Screening-Agent

**Screen 1000+ papers in minutes, not days.**

An AI agent that automatically reads paper abstracts, evaluates research relevance with a **1-10 scoring system**, and routes papers into accept/review/reject categories. Built for researchers who need to efficiently survey literature across any domain.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## ✨ Features

| Feature | Description |
|---------|-------------|
| **🎯 1-10 Scoring** | Semantic-anchored scoring ensures consistent, explainable evaluation |
| **📊 Tiered Routing** | Auto-accept (≥4), Human review (=3), Auto-reject (≤2) |
| **⚡ 200+ Concurrent** | Multi-API parallel processing with independent worker pools |
| **🔄 Breakpoint Resume** | Crash-safe — automatically resumes from last processed paper |
| **📝 Customizable Prompts** | Swap `config/prompts.json` to adapt to any research topic |
| **🛡️ High-Recall Design** | "Never miss important work" — uncertain papers go to review, not rejection |

## 🏗️ How It Works

```
┌────────────┐     ┌─────────────┐     ┌──────────┐     ┌─────────────┐
│ CSV Input  │────▶│  LLM Judge  │────▶│  Router  │────▶│   Output    │
│ (papers)   │     │ (1-10 score)│     │ (triage) │     │ (sorted CSV)│
└────────────┘     └─────────────┘     └──────────┘     └─────────────┘
                          │                  │
                   ┌──────┴──────┐    ┌──────┴──────────────────┐
                   │   Prompt    │    │  Score ≥ 4 → ACCEPTED   │
                   │   Config    │    │  Score = 3 → REVIEW     │
                   │   (JSON)    │    │  Score ≤ 2 → REJECTED   │
                   └─────────────┘    └─────────────────────────┘
```

## 🎯 Design Philosophy

### High-Recall Scoring
The agent prioritizes **not missing important papers**:
- **Score 4**: Marginally relevant → still included
- **Score 3**: Uncertain → human review (safety net)
- **Score 1-2**: Clearly irrelevant → auto-reject

### Semantic Anchoring
Each score has a **precise definition** to ensure LLM consistency:

| Score | Tier | Meaning |
|-------|------|---------|  
| 10 | Core | Title explicitly contains topic keyword as main contribution |
| 9 | Core | Proposes new architecture/method directly addressing topic |
| 7-8 | Strong | Core mechanism strongly related (implicit relevance) |
| 5-6 | General | Application-level relevance |
| 4 | Marginal | Weak but possible relevance — include for high recall |
| 3 | Boundary | Uncertain — route to human review |
| 1-2 | Irrelevant | Clearly unrelated |

## 📦 Installation

```bash
git clone https://github.com/pursurer/Paper-Screening-Agent.git
cd Paper-Screening-Agent

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Add your Gemini API key(s) to .env
```

## ⚙️ Configuration

### API Keys
```bash
# .env file
GEMINI_API_KEY=your_key_here

# Or pass multiple keys via CLI for higher throughput
--api-keys "key1,key2,key3,key4"
```

### Customizing for Your Topic

Edit `config/prompts.json` to adapt to **any research domain**:

```json
{
  "screening_topic": "Reinforcement Learning",
  "system_prompt": "You are an expert. Score papers on '{topic}' relevance (1-10)...",
  "scoring_tiers": {
    "10": {"name": "Core", "description": "Title contains RL/Policy/Reward"},
    "9": {"name": "Core", "description": "Proposes new RL algorithm"},
    ...
  }
}
```

## 🚀 Usage

```bash
# Basic: single API key
python -m src.multi_api_batch \
  --input papers.csv \
  --output output/results \
  --api-keys "YOUR_API_KEY"

# Turbo: 4 API keys × 50 concurrent = 200 parallel requests
python -m src.multi_api_batch \
  --input papers.csv \
  --output output/results \
  --api-keys "KEY1,KEY2,KEY3,KEY4" \
  --concurrency 50
```

### Input Format

| Field | Required | Description |
|-------|:--------:|-------------|
| id | ✅ | Unique identifier |
| title | ✅ | Paper title |
| abstract | ✅ | Paper abstract |
| keywords | | Optional |
| pdf | | PDF link |

### Output

| File | Content |
|------|---------|
| `ai_memory_papers_graded.csv` | Accepted papers (score ≥ 4), sorted by relevance |
| `human_review_boundary.csv` | Boundary cases (score = 3) for manual review |

## 📁 Project Structure

```
Paper-Screening-Agent/
├── src/
│   ├── llm_judge.py         # LLM scoring (loads from config)
│   ├── router.py            # Accept/Review/Reject routing
│   ├── paper_parser.py      # CSV parser
│   ├── output_generator.py  # Output writer
│   ├── multi_api_batch.py   # Multi-API parallel engine
│   └── statistics.py        # Logging & stats
├── config/
│   └── prompts.json         # ⭐ Customizable prompts
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

## 🧪 Testing

```bash
pytest tests/ -v
```

## 🌟 Example Use Case

This tool was used to screen **5,700+ papers** on AI Memory from 10 top conferences:

👉 [Curated-Agent-Memory-Papers](https://github.com/pursurer/Curated-Agent-Memory-Papers)

## 📄 License

MIT License

## 🤝 Contributing

Pull requests welcome! Feel free to open issues for bugs or feature requests.
