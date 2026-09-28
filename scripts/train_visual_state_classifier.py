from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
import pyarrow.parquet as pq
import torch
from PIL import Image, ImageEnhance
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small
from torchvision.transforms import Normalize

STATE_NAMES = ("attack", "freeze", "shield")
IMAGE_SIZE = 96


def _stable_bucket(value: str, buckets: int) -> int:
    digest = hashlib.sha256(value.encode()).digest()
    return int.from_bytes(digest[:8], "big") % buckets


def _labels(path: Path) -> np.ndarray:
    stem = f"_{path.stem}_"
    return np.asarray(
        [float(f"_{name}_" in stem) for name in STATE_NAMES], dtype=np.float32
    )


def _load_backgrounds(path: Path | None, limit: int = 96) -> list[np.ndarray]:
    if path is None:
        return []
    table = pq.read_table(path, columns=["image"])
    indices = np.linspace(0, len(table) - 1, min(limit, len(table)), dtype=np.int64)
    backgrounds: list[np.ndarray] = []
    for index in indices.tolist():
        payload = table["image"][index].as_py()["bytes"]
        frame = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            continue
        backgrounds.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return backgrounds


class StateCropDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(
        self,
        paths: list[Path],
        backgrounds: list[np.ndarray],
        *,
        training: bool,
        seed: int,
    ) -> None:
        self.paths = paths
        self.backgrounds = backgrounds
        self.training = training
        self.seed = seed
        weights = MobileNet_V3_Small_Weights.DEFAULT
        preset = weights.transforms()
        self.normalize = Normalize(mean=preset.mean, std=preset.std)

    def __len__(self) -> int:
        return len(self.paths)

    def _background(self, rng: random.Random) -> Image.Image:
        if not self.backgrounds:
            color = tuple(rng.randint(35, 190) for _ in range(3))
            return Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), color)
        source = self.backgrounds[rng.randrange(len(self.backgrounds))]
        height, width = source.shape[:2]
        crop_size = max(24, min(height, width, rng.randint(64, 180)))
        left = rng.randint(0, max(0, width - crop_size))
        top = rng.randint(0, max(0, height - crop_size))
        crop = source[top : top + crop_size, left : left + crop_size]
        return Image.fromarray(crop).resize(
            (IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR
        )

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        path = self.paths[index]
        rng = random.Random(self.seed * 1_000_003 + index)
        sprite = Image.open(path).convert("RGBA")
        scale = rng.uniform(0.48, 0.92) if self.training else 0.72
        target = max(10, int(IMAGE_SIZE * scale))
        ratio = min(target / sprite.width, target / sprite.height)
        sprite = sprite.resize(
            (
                max(1, round(sprite.width * ratio)),
                max(1, round(sprite.height * ratio)),
            ),
            Image.Resampling.BILINEAR,
        )
        background = self._background(rng).convert("RGBA")
        jitter = 9 if self.training else 0
        left = (IMAGE_SIZE - sprite.width) // 2 + rng.randint(-jitter, jitter)
        top = (IMAGE_SIZE - sprite.height) // 2 + rng.randint(-jitter, jitter)
        background.alpha_composite(sprite, (left, top))
        image = background.convert("RGB")
        if self.training:
            image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.82, 1.18))
            image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.82, 1.18))
        array = np.asarray(image, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(array).permute(2, 0, 1)
        return self.normalize(tensor), torch.from_numpy(_labels(path))


@dataclass(frozen=True)
class StateMetrics:
    threshold: float
    precision: float
    recall: float
    f1: float
    positives: int


def _metrics(logits: torch.Tensor, labels: torch.Tensor) -> dict[str, StateMetrics]:
    probabilities = logits.sigmoid().numpy()
    truth = labels.numpy().astype(bool)
    result: dict[str, StateMetrics] = {}
    for column, name in enumerate(STATE_NAMES):
        best: StateMetrics | None = None
        for threshold in np.linspace(0.05, 0.95, 91):
            predicted = probabilities[:, column] >= threshold
            tp = int(np.count_nonzero(predicted & truth[:, column]))
            fp = int(np.count_nonzero(predicted & ~truth[:, column]))
            fn = int(np.count_nonzero(~predicted & truth[:, column]))
            precision = tp / max(1, tp + fp)
            recall = tp / max(1, tp + fn)
            f1 = 2 * precision * recall / max(1e-12, precision + recall)
            candidate = StateMetrics(
                threshold=float(threshold),
                precision=precision,
                recall=recall,
                f1=f1,
                positives=int(truth[:, column].sum()),
            )
            if best is None or candidate.f1 > best.f1:
                best = candidate
        assert best is not None
        result[name] = best
    return result


@torch.inference_mode()
def _evaluate(
    model: nn.Module, loader: DataLoader, device: torch.device
) -> tuple[float, dict[str, StateMetrics]]:
    model.eval()
    losses: list[float] = []
    logits: list[torch.Tensor] = []
    labels: list[torch.Tensor] = []
    criterion = nn.BCEWithLogitsLoss()
    for images, target in loader:
        output = model(images.to(device)).cpu()
        losses.append(float(criterion(output, target)))
        logits.append(output)
        labels.append(target)
    return float(np.mean(losses)), _metrics(torch.cat(logits), torch.cat(labels))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--segments", type=Path, required=True)
    parser.add_argument("--background-parquet", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--device", default="mps")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    paths = sorted(args.segments.rglob("*.png"))
    if not paths:
        raise ValueError("no segment PNGs found")
    train_paths: list[Path] = []
    validation_paths: list[Path] = []
    for path in paths:
        identity = path.parent.name
        # Whole identities are held out. Royal Recruit is the only shielded
        # identity in this small source, so shield validation is explicitly an
        # image holdout and is never reported as cross-identity evidence.
        is_validation = _stable_bucket(identity, 5) == 0
        if identity == "royal-recruit":
            is_validation = _stable_bucket(path.name, 5) == 0
        (validation_paths if is_validation else train_paths).append(path)

    backgrounds = _load_backgrounds(args.background_parquet)
    train_dataset = StateCropDataset(
        train_paths, backgrounds, training=True, seed=args.seed
    )
    validation_dataset = StateCropDataset(
        validation_paths, backgrounds, training=False, seed=args.seed + 1
    )
    sample_weights = np.asarray(
        [1.0 + float((_labels(path) * np.asarray([8, 16, 10])).sum()) for path in train_paths]
    )
    generator = torch.Generator().manual_seed(args.seed)
    sampler = WeightedRandomSampler(
        torch.from_numpy(sample_weights),
        num_samples=len(train_paths),
        replacement=True,
        generator=generator,
    )
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        sampler=sampler,
        num_workers=0,
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )

    device = torch.device(args.device)
    model = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(STATE_NAMES))
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-4)
    criterion = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([4.0, 10.0, 6.0], device=device)
    )
    history: list[dict[str, object]] = []
    best_score = -1.0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = args.output_dir / "visual_state_mobilenet_v3_small.pt"
    for epoch in range(1, args.epochs + 1):
        model.train()
        train_losses: list[float] = []
        for images, target in train_loader:
            optimizer.zero_grad(set_to_none=True)
            output = model(images.to(device))
            loss = criterion(output, target.to(device))
            loss.backward()
            optimizer.step()
            train_losses.append(float(loss.detach().cpu()))
        validation_loss, metrics = _evaluate(model, validation_loader, device)
        score = float(np.mean([value.f1 for value in metrics.values()]))
        row = {
            "epoch": epoch,
            "train_loss": float(np.mean(train_losses)),
            "validation_loss": validation_loss,
            "metrics": {name: asdict(value) for name, value in metrics.items()},
        }
        history.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
        if score > best_score:
            best_score = score
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "state_names": STATE_NAMES,
                    "image_size": IMAGE_SIZE,
                    "metrics": row,
                    "seed": args.seed,
                },
                checkpoint_path,
            )

    report = {
        "schema": "visual-state-classifier-experiment-v1",
        "checkpoint": str(checkpoint_path.resolve()),
        "model": "mobilenet_v3_small",
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "train_images": len(train_paths),
        "validation_images": len(validation_paths),
        "validation_contract": {
            "attack": "held-out troop identities",
            "freeze": "held-out troop identities",
            "shield": "held-out Royal Recruit images only; no identity generalization claim",
        },
        "backgrounds": len(backgrounds),
        "history": history,
    }
    report_path = args.output_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"report": str(report_path.resolve()), "best_score": best_score}))


if __name__ == "__main__":
    main()
