from dataclasses import dataclass


@dataclass
class TrainingConfig:
    manifest_path: str = "dataset/manifest.csv"
    output_dir: str = "models"
    image_size: int = 224
    batch_size: int = 16
    epochs: int = 30
    learning_rate: float = 3e-4
    weight_decay: float = 1e-4
    dropout: float = 0.3
    patience: int = 5
    workers: int = 0
    seed: int = 42
    modality: str = "fusion_env"
    pretrained: bool = False
