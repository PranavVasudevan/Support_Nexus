#!/usr/bin/env python3
"""
Initial training script.
Run this ONCE to fine-tune DistilBERT on your 200k dataset before starting the system.

Usage:
  python scripts/initial_train.py \
    --train-csv /path/to/ticket_train_140k.csv \
    --val-csv   /path/to/ticket_val_30k.csv \
    --epochs 3

Requirements: GPU strongly recommended. CPU will work but is slow.
"""
import sys
sys.path.insert(0, "./backend")

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger
from sklearn.metrics import classification_report

import torch
from transformers import (
    DistilBertTokenizerFast,
    DistilBertForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from torch.utils.data import Dataset

from core.config import settings


class TicketDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=256):
        logger.info(f"Tokenizing {len(texts)} samples...")
        self.encodings = tokenizer(
            texts, truncation=True, padding=True,
            max_length=max_length, return_tensors="pt",
        )
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self): return len(self.labels)
    def __getitem__(self, idx):
        return {
            "input_ids": self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
            "labels": self.labels[idx],
        }


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    from sklearn.metrics import f1_score
    return {
        "f1": f1_score(labels, preds, average="weighted", zero_division=0),
        "accuracy": float((preds == labels).mean()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-csv", required=True)
    parser.add_argument("--val-csv",   required=True)
    parser.add_argument("--output",     default=settings.model_path)
    parser.add_argument("--epochs",     type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=16)   # fits 4GB GPUs (RTX 3050)
    parser.add_argument("--max-length", type=int, default=128)  # short tickets → 128 is plenty
    parser.add_argument("--limit",      type=int, default=0,
                        help="Subsample this many TRAIN rows (0 = use all). Speeds up trial runs.")
    parser.add_argument("--base-model", default=settings.base_model,
                        help="HF id or local path of the base model "
                             "(e.g. ./models/base-distilbert after download_base_model.py).")
    args = parser.parse_args()
    base_model = args.base_model

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Device: {device}")

    logger.info(f"Loading train CSV: {args.train_csv}")
    train_df = pd.read_csv(args.train_csv)
    val_df   = pd.read_csv(args.val_csv)

    # Build text input: title + SEP + description
    for df in [train_df, val_df]:
        df["text"] = df["title"].fillna("") + " [SEP] " + df["description"].fillna("")

    # Filter to known categories only
    train_df = train_df[train_df["category"].isin(settings.categories)].copy()
    val_df   = val_df[val_df["category"].isin(settings.categories)].copy()

    train_df["label"] = train_df["category"].map(settings.label2id)
    val_df["label"]   = val_df["category"].map(settings.label2id)

    train_df = train_df.dropna(subset=["label"])
    val_df   = val_df.dropna(subset=["label"])

    if args.limit and args.limit < len(train_df):
        train_df = train_df.sample(n=args.limit, random_state=42).reset_index(drop=True)
        logger.info(f"Subsampled train set to {len(train_df)} rows (--limit)")

    logger.info(f"Train: {len(train_df)} | Val: {len(val_df)} | max_length={args.max_length}")
    logger.info(f"Category distribution:\n{train_df['category'].value_counts().to_string()}")

    tokenizer = DistilBertTokenizerFast.from_pretrained(base_model)
    train_dataset = TicketDataset(
        train_df["text"].tolist(), train_df["label"].astype(int).tolist(),
        tokenizer, max_length=args.max_length,
    )
    val_dataset = TicketDataset(
        val_df["text"].tolist(), val_df["label"].astype(int).tolist(),
        tokenizer, max_length=args.max_length,
    )

    model = DistilBertForSequenceClassification.from_pretrained(
        base_model,
        num_labels=settings.num_labels,
        id2label=settings.id2label,
        label2id=settings.label2id,
    )

    training_args = TrainingArguments(
        output_dir=f"{args.output}_checkpoints",
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        warmup_ratio=0.06,
        weight_decay=0.01,
        learning_rate=2e-5,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=200,
        fp16=(device == "cuda"),
        report_to="none",
        dataloader_num_workers=0,   # 0 = safest on Windows (avoids spawn issues)
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
        processing_class=tokenizer,
    )

    logger.info("Starting training...")
    trainer.train()

    logger.info(f"Saving model to {args.output}")
    Path(args.output).mkdir(parents=True, exist_ok=True)
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)

    # Final evaluation
    eval_results = trainer.evaluate()
    logger.info(f"Final val F1: {eval_results.get('eval_f1', 0):.4f}")
    logger.info(f"Final val accuracy: {eval_results.get('eval_accuracy', 0):.4f}")

    # Per-class report
    preds_output = trainer.predict(val_dataset)
    preds = np.argmax(preds_output.predictions, axis=-1)
    print("\n" + classification_report(
        val_dataset.labels.numpy(), preds,
        target_names=settings.categories, zero_division=0,
    ))


if __name__ == "__main__":
    main()
