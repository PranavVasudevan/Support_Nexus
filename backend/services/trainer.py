"""
DistilBERT Fine-tuning Trainer
Triggered nightly or manually via /api/admin/retrain.
Trains on the feedback_logs table: all corrected + approved agent decisions.

Heavy ML imports (torch / transformers / mlflow) are done lazily inside the
functions so that simply importing this module (which the admin route does)
never requires the ML stack in a Gemini-only local run.
"""
from datetime import datetime
from loguru import logger

from core.config import settings


def _build_dataset_class():
    import torch
    from torch.utils.data import Dataset

    class TicketDataset(Dataset):
        def __init__(self, texts, labels, tokenizer, max_length=256):
            self.encodings = tokenizer(
                texts,
                truncation=True,
                padding=True,
                max_length=max_length,
                return_tensors="pt",
            )
            self.labels = torch.tensor(labels, dtype=torch.long)

        def __len__(self):
            return len(self.labels)

        def __getitem__(self, idx):
            return {
                "input_ids":      self.encodings["input_ids"][idx],
                "attention_mask": self.encodings["attention_mask"][idx],
                "labels":         self.labels[idx],
            }

    return TicketDataset


def _compute_metrics(eval_pred):
    import numpy as np
    from sklearn.metrics import f1_score

    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    f1 = f1_score(labels, preds, average="weighted", zero_division=0)
    acc = float((preds == labels).mean())
    return {"f1": f1, "accuracy": acc}


async def retrain_model(classifier):
    """Main retraining entry point called by the scheduler or admin API."""
    logger.info("Starting retraining pipeline...")

    import pandas as pd
    import torch
    from sklearn.model_selection import train_test_split
    from transformers import (
        DistilBertTokenizerFast,
        DistilBertForSequenceClassification,
        TrainingArguments,
        Trainer,
    )

    from db.postgres import get_session
    from sqlalchemy import text

    async with get_session() as db:
        result = await db.execute(text(
            "SELECT t.title, t.description, f.final_category "
            "FROM feedback_logs f "
            "JOIN tickets t ON t.id = f.ticket_id "
            "WHERE f.final_category IS NOT NULL"
        ))
        rows = result.fetchall()

    if len(rows) < settings.retrain_min_samples:
        logger.warning(f"Only {len(rows)} samples, skipping retrain")
        return

    logger.info(f"Retraining on {len(rows)} feedback samples")
    df = pd.DataFrame(rows, columns=["title", "description", "category"])
    df["text"] = df["title"].fillna("") + " [SEP] " + df["description"].fillna("")
    df = df[df["category"].isin(settings.categories)].copy()
    df["label"] = df["category"].map(settings.label2id)
    df = df.dropna(subset=["label"])

    texts = df["text"].tolist()
    labels = df["label"].astype(int).tolist()

    train_texts, val_texts, train_labels, val_labels = train_test_split(
        texts, labels, test_size=0.15, random_state=42, stratify=labels
    )

    TicketDataset = _build_dataset_class()
    tokenizer = DistilBertTokenizerFast.from_pretrained(settings.base_model)
    train_dataset = TicketDataset(train_texts, train_labels, tokenizer)
    val_dataset   = TicketDataset(val_texts, val_labels, tokenizer)

    model = DistilBertForSequenceClassification.from_pretrained(
        settings.base_model,
        num_labels=settings.num_labels,
        id2label=settings.id2label,
        label2id=settings.label2id,
    )

    output_dir = f"./models/distilbert_retrain_{datetime.now().strftime('%Y%m%d_%H%M')}"

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=4,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        warmup_steps=50,
        weight_decay=0.01,
        learning_rate=2e-5,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=20,
        fp16=torch.cuda.is_available(),
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=_compute_metrics,
        processing_class=tokenizer,
    )

    mlflow_run = _maybe_start_mlflow()
    try:
        train_result = trainer.train()
        eval_result = trainer.evaluate()
        if mlflow_run is not None:
            import mlflow
            mlflow.log_param("train_samples", len(train_texts))
            mlflow.log_param("val_samples", len(val_texts))
            mlflow.log_metrics({
                "train_loss": train_result.training_loss,
                "val_f1": eval_result.get("eval_f1", 0),
                "val_accuracy": eval_result.get("eval_accuracy", 0),
            })

        trainer.save_model(settings.model_path)
        tokenizer.save_pretrained(settings.model_path)
        logger.info(f"Model saved to {settings.model_path}")
        logger.info(f"Val F1: {eval_result.get('eval_f1', 0):.4f}")

        # Record metrics for the Model Performance dashboard.
        try:
            from db.postgres import record_model_metric
            await record_model_metric(
                f1=float(eval_result.get("eval_f1", 0)),
                accuracy=float(eval_result.get("eval_accuracy", 0)),
                total_samples=len(train_texts) + len(val_texts),
            )
        except Exception as e:
            logger.warning(f"Could not record model metric: {e}")
    finally:
        if mlflow_run is not None:
            import mlflow
            mlflow.end_run()

    # Hot-reload classifier with the freshly trained weights.
    await classifier.load()
    logger.info("Classifier hot-reloaded with new model")


def _maybe_start_mlflow():
    if not settings.mlflow_uri:
        logger.info("MLflow disabled (no MLFLOW_URI) — skipping experiment tracking")
        return None
    try:
        import mlflow
        mlflow.set_tracking_uri(settings.mlflow_uri)
        mlflow.set_experiment("ticket-classifier")
        return mlflow.start_run(run_name=f"retrain_{datetime.now().strftime('%Y%m%d')}")
    except Exception as e:
        logger.warning(f"MLflow unavailable ({e}) — continuing without tracking")
        return None
