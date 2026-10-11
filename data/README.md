# Data

## Table of contents
- [Third-party datasets](#third-party-datasets)
- [Generated data](#generated-data)

## Third-party datasets
Downloaded into `data/raw/` (git-ignored, not redistributed).

| Dataset | Source | Licence | Size | Use |
|---|---|---|---|---|
| Bitext retail e-commerce chatbot dataset | [Hugging Face: bitext/Bitext-retail-ecommerce-llm-chatbot-training-dataset](https://huggingface.co/datasets/bitext/Bitext-retail-ecommerce-llm-chatbot-training-dataset) | CDLA-Sharing 1.0 | 44,884 rows, 13 categories, 46 intents | Intent taxonomy; seed for generated tickets; triage accuracy sample |
| Customer Support on Twitter (optional) | Kaggle | To be checked before use | ~50-tweet sample | Calibrating realistic anger |

To fetch Bitext:
```bash
mkdir -p data/raw/bitext
curl -L -o data/raw/bitext/bitext-retail-ecommerce.csv "https://huggingface.co/datasets/bitext/Bitext-retail-ecommerce-llm-chatbot-training-dataset/resolve/main/bitext-retail-ecommerce-llm-chatbot-training-dataset.csv"
```

Columns: `instruction` (customer text), `intent`, `category`, `tags` (linguistic variation markers), `response`.

## Generated data
Planned per [D14](../docs/adr/014-evaluation-and-data.md): Indian mock order data, 14 policy documents with rules blocks, noisy tickets generated from Bitext intents, and the golden and red-team sets.
