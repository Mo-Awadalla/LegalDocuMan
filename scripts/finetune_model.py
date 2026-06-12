"""Fine-tune the small LM on pseudo-labelled contract data.

Consumes the JSONL produced by `scripts/generate_pseudo_labels.py` and
fine-tunes `google/flan-t5-small` (or a local base) for 3-5 epochs with
HuggingFace `seq2seq` training.  Saves the result to
`models/small_lm/` so the runtime pipeline picks it up automatically.

Usage:

    python scripts/generate_pseudo_labels.py \\
        --input ./uploads \\
        --output ./models/pseudo_labels.jsonl

    python scripts/finetune_model.py \\
        --data ./models/pseudo_labels.jsonl \\
        --output ./models/small_lm \\
        --epochs 3

The fine-tune script keeps dependencies minimal — only `transformers`
and `torch` are required (already in requirements.txt).  For larger
runs, install `accelerate` and pass `--use-accelerate`.
"""
import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Ensure the repo root is on the path so we can import the package even
# when this script is run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Stable answer format.  The runtime parser in ml_model.py accepts JSON
# and key/value forms, but JSON is the form the model is trained to
# emit.  Keep the labels and order in sync with _VALID_DOC_TYPES.
_ANSWER_TEMPLATE = '{{"doc_type": "{doc_type}", "vendor": "{vendor}"}}'

# Instruction used at training and inference time.  Kept in sync with
# legaldocuman.ml_model._INSTRUCTION.
_INSTRUCTION = (
    "Extract the document type and vendor name from the contract text. "
    "Reply as JSON with keys doc_type and vendor. doc_type is one of "
    "MSA, SOW, NDA, PO, AMD, LICENSE, CONTRACT. "
    "Text: "
)


@dataclass
class Example:
    prompt: str
    target: str


def load_jsonl(path: str) -> List[Dict]:
    examples: List[Dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            examples.append(json.loads(line))
    return examples


def to_seq2seq(records: List[Dict], max_input_chars: int = 2000) -> List[Example]:
    out: List[Example] = []
    for r in records:
        text = (r.get("text") or "").strip()
        doc_type = (r.get("doc_type") or "").upper().strip() or "CONTRACT"
        vendor = (r.get("vendor") or "").strip()
        if not text:
            continue
        # Truncate so the prompt fits inside FLAN-T5's 512-token window
        # with margin for the answer.
        if len(text) > max_input_chars:
            text = text[:max_input_chars]
        prompt = _INSTRUCTION + text
        target = _ANSWER_TEMPLATE.format(doc_type=doc_type, vendor=_escape(vendor))
        out.append(Example(prompt=prompt, target=target))
    return out


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def split_train_eval(
    examples: List[Example], eval_ratio: float = 0.1
) -> Tuple[List[Example], List[Example]]:
    if not examples:
        return [], []
    if len(examples) < 10:
        # Too few to split sensibly; everything is training data.
        return examples, []
    cutoff = max(1, int(len(examples) * (1 - eval_ratio)))
    return examples[:cutoff], examples[cutoff:]


def fine_tune(
    data_path: str,
    output_dir: str,
    base_model: str = "google/flan-t5-small",
    epochs: int = 3,
    batch_size: int = 4,
    learning_rate: float = 3e-4,
    max_input_length: int = 512,
    max_target_length: int = 64,
    use_accelerate: bool = False,
) -> str:
    try:
        from transformers import (
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
            DataCollatorForSeq2Seq,
            Seq2SeqTrainer,
            Seq2SeqTrainingArguments,
        )
    except ImportError as exc:
        raise RuntimeError(
            "transformers and torch are required for fine-tuning — see requirements.txt"
        ) from exc

    records = load_jsonl(data_path)
    examples = to_seq2seq(records)
    if not examples:
        raise RuntimeError(f"No training records found in {data_path}")
    train_examples, eval_examples = split_train_eval(examples)

    logging.info(f"Loaded {len(examples)} examples ({len(train_examples)} train, {len(eval_examples)} eval)")

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForSeq2SeqLM.from_pretrained(base_model)

    def tokenize(batch):
        model_inputs = tokenizer(
            batch["prompt"],
            max_length=max_input_length,
            truncation=True,
            padding="max_length",
        )
        labels = tokenizer(
            text_target=batch["target"],
            max_length=max_target_length,
            truncation=True,
            padding="max_length",
        )
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    train_dicts = [{"prompt": e.prompt, "target": e.target} for e in train_examples]
    eval_dicts = [{"prompt": e.prompt, "target": e.target} for e in eval_examples]

    from datasets import Dataset
    train_ds = Dataset.from_list(train_dicts).map(tokenize, batched=True, remove_columns=["prompt", "target"])
    eval_ds = None
    if eval_dicts:
        eval_ds = Dataset.from_list(eval_dicts).map(tokenize, batched=True, remove_columns=["prompt", "target"])

    args_kwargs: Dict = {
        "output_dir": output_dir,
        "num_train_epochs": epochs,
        "per_device_train_batch_size": batch_size,
        "per_device_eval_batch_size": batch_size,
        "learning_rate": learning_rate,
        "save_strategy": "epoch",
        "logging_steps": 10,
        "report_to": "none",
        "predict_with_generate": True,
    }
    if use_accelerate:
        try:
            from transformers import TrainingArguments  # noqa: F401
        except ImportError:
            pass
    if eval_ds is not None:
        args_kwargs["eval_strategy"] = "epoch"

    training_args = Seq2SeqTrainingArguments(**args_kwargs)

    data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=data_collator,
        tokenizer=tokenizer,
    )

    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    logging.info(f"Fine-tuned model saved to {output_dir}")
    return output_dir


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="JSONL training data path")
    parser.add_argument("--output", required=True, help="Output model directory")
    parser.add_argument("--base-model", default="google/flan-t5-small", help="Base model to fine-tune from")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--use-accelerate", action="store_true")
    args = parser.parse_args(argv)

    out = fine_tune(
        data_path=args.data,
        output_dir=args.output,
        base_model=args.base_model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        use_accelerate=args.use_accelerate,
    )
    print(out)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
