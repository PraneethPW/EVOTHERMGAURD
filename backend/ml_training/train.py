"""Train and validate the multimodal anomaly classifier on labelled field data."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.optim import AdamW
from torch.utils.data import DataLoader

from app.ml.model import GradCAM, MultimodalAnomalyNet, RISK_CLASSES
from ml_training.config import TrainingConfig
from ml_training.dataset import MultimodalDataset, class_weights, manifest_summary
from ml_training.evaluate import evaluate, localization_metrics


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _forward(model, batch, device):
    return model(
        batch["rgb"].to(device),
        batch["thermal"].to(device),
        batch["environment"].to(device),
    )


def train_epoch(model, loader, criterion, optimizer, device) -> float:
    model.train()
    total_loss = 0.0
    for batch in loader:
        optimizer.zero_grad(set_to_none=True)
        logits = _forward(model, batch, device)
        loss = criterion(logits, batch["label"].to(device))
        loss.backward()
        optimizer.step()
        total_loss += float(loss.item()) * len(batch["label"])
    return total_loss / len(loader.dataset)


@torch.no_grad()
def classify(model, loader, criterion, device) -> tuple[float, dict]:
    model.eval()
    labels, predictions, probabilities = [], [], []
    total_loss = 0.0
    for batch in loader:
        logits = _forward(model, batch, device)
        loss = criterion(logits, batch["label"].to(device))
        probs = logits.softmax(dim=1)
        labels.extend(batch["label"].cpu().tolist())
        predictions.extend(probs.argmax(dim=1).cpu().tolist())
        probabilities.extend(probs.cpu().tolist())
        total_loss += float(loss.item()) * len(batch["label"])
    return total_loss / len(loader.dataset), evaluate(labels, predictions, probabilities)


def evaluate_localization(model, loader, device) -> dict:
    predicted_masks, target_masks = [], []
    model.eval()
    gradcam = GradCAM(model, branch="thermal")
    try:
        for batch in loader:
            mask_flags = batch["has_mask"]
            for index, has_mask in enumerate(mask_flags):
                if not bool(has_mask):
                    continue
                result = gradcam(
                    batch["rgb"][index : index + 1].to(device),
                    batch["thermal"][index : index + 1].to(device),
                    batch["environment"][index : index + 1].to(device),
                )
                predicted_masks.append(result.heatmap)
                target_masks.append(batch["mask"][index, 0].numpy())
    finally:
        gradcam.close()
    if not predicted_masks:
        return {
            "samples": 0,
            "mean_iou": None,
            "mean_dice": None,
            "reason": "The test split contains no localization masks.",
        }
    return localization_metrics(predicted_masks, target_masks)


def run_training(config: TrainingConfig) -> dict:
    seed_everything(config.seed)
    if config.modality not in {"rgb", "thermal", "fusion", "fusion_env"}:
        raise ValueError("modality must be rgb, thermal, fusion, or fusion_env")
    summary = manifest_summary(config.manifest_path)
    if not summary["ready"]:
        raise ValueError(summary["reason"])

    train_set = MultimodalDataset(
        config.manifest_path, "train", config.image_size, augment=True
    )
    validation_set = MultimodalDataset(
        config.manifest_path, "validation", config.image_size
    )
    test_set = MultimodalDataset(config.manifest_path, "test", config.image_size)
    loader_args = {
        "batch_size": config.batch_size,
        "num_workers": config.workers,
        "pin_memory": torch.cuda.is_available(),
    }
    train_loader = DataLoader(train_set, shuffle=True, **loader_args)
    validation_loader = DataLoader(validation_set, shuffle=False, **loader_args)
    test_loader = DataLoader(test_set, shuffle=False, **loader_args)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MultimodalAnomalyNet(
        dropout=config.dropout,
        modality=config.modality,
        pretrained=config.pretrained,
    ).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights(train_set).to(device))
    optimizer = AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / f"multimodal-{config.modality}-best.pt"
    best_f1, stale_epochs, history = -1.0, 0, []
    for epoch in range(1, config.epochs + 1):
        training_loss = train_epoch(model, train_loader, criterion, optimizer, device)
        validation_loss, validation_metrics = classify(
            model, validation_loader, criterion, device
        )
        history.append(
            {
                "epoch": epoch,
                "training_loss": round(training_loss, 6),
                "validation_loss": round(validation_loss, 6),
                "validation_f1_macro": validation_metrics["f1_macro"],
            }
        )
        if validation_metrics["f1_macro"] > best_f1:
            best_f1 = validation_metrics["f1_macro"]
            stale_epochs = 0
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "classes": list(RISK_CLASSES),
                    "modality": config.modality,
                    "image_size": config.image_size,
                    "dropout": config.dropout,
                    "validated": False,
                },
                checkpoint_path,
            )
        else:
            stale_epochs += 1
            if stale_epochs >= config.patience:
                break

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["state_dict"])
    test_loss, test_metrics = classify(model, test_loader, criterion, device)
    test_metrics["localization"] = evaluate_localization(model, test_loader, device)
    manifest_hash = hashlib.sha256(Path(config.manifest_path).read_bytes()).hexdigest()
    experiment = {
        "id": f"{config.modality}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "research_claim": "held-out evaluation",
        "modality": config.modality,
        "architecture": "dual-resnet18-plus-environment-mlp",
        "dataset": {**summary, "manifest_sha256": manifest_hash},
        "config": asdict(config),
        "epochs_completed": len(history),
        "history": history,
        "test_loss": round(test_loss, 6),
        "metrics": test_metrics,
        "checkpoint": str(checkpoint_path),
    }
    experiment_path = output_dir / f"experiment-{experiment['id']}.json"
    experiment_path.write_text(json.dumps(experiment, indent=2), encoding="utf-8")
    checkpoint["validated"] = True
    checkpoint["metrics"] = test_metrics
    checkpoint["experiment_id"] = experiment["id"]
    torch.save(checkpoint, checkpoint_path)
    return experiment


def parse_args() -> TrainingConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="dataset/manifest.csv")
    parser.add_argument("--output-dir", default="models")
    parser.add_argument(
        "--modality", choices=("rgb", "thermal", "fusion", "fusion_env"), default="fusion_env"
    )
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pretrained", action="store_true")
    args = parser.parse_args()
    return TrainingConfig(
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        modality=args.modality,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        dropout=args.dropout,
        patience=args.patience,
        workers=args.workers,
        seed=args.seed,
        pretrained=args.pretrained,
    )


def main() -> None:
    result = run_training(parse_args())
    print(json.dumps({"experiment": result["id"], "metrics": result["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
