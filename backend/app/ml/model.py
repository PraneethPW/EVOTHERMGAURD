"""Trainable multimodal network and Grad-CAM utilities.

This module is imported lazily by the runtime so the lightweight heuristic
deployment can continue to run without PyTorch. Training environments install
the full requirements file and can activate this model with a real checkpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torchvision.models import ResNet18_Weights, resnet18


RISK_CLASSES = ("NORMAL", "WARNING", "HIGH_RISK", "CRITICAL")
ENVIRONMENT_FEATURES = 22
Modality = Literal["rgb", "thermal", "fusion", "fusion_env"]


def _backbone(input_channels: int, pretrained: bool) -> tuple[nn.Module, int]:
    weights = ResNet18_Weights.DEFAULT if pretrained else None
    network = resnet18(weights=weights)
    if input_channels == 1:
        original = network.conv1
        replacement = nn.Conv2d(
            1,
            original.out_channels,
            kernel_size=original.kernel_size,
            stride=original.stride,
            padding=original.padding,
            bias=False,
        )
        if pretrained:
            with torch.no_grad():
                replacement.weight.copy_(original.weight.mean(dim=1, keepdim=True))
        network.conv1 = replacement
    feature_dim = network.fc.in_features
    network.fc = nn.Identity()
    return network, feature_dim


class MultimodalAnomalyNet(nn.Module):
    """RGB CNN + thermal CNN + associated environmental context."""

    def __init__(
        self,
        environment_features: int = ENVIRONMENT_FEATURES,
        classes: int = len(RISK_CLASSES),
        dropout: float = 0.3,
        modality: Modality = "fusion_env",
        pretrained: bool = False,
    ) -> None:
        super().__init__()
        self.modality = modality
        self.rgb_branch, image_features = _backbone(3, pretrained)
        self.thermal_branch, _ = _backbone(1, pretrained)
        self.environment_branch = nn.Sequential(
            nn.Linear(environment_features, 64),
            nn.LayerNorm(64),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 64),
            nn.SiLU(),
        )

        fused_features = image_features
        if modality in ("fusion", "fusion_env"):
            fused_features += image_features
        if modality == "fusion_env":
            fused_features += 64
        self.classifier = nn.Sequential(
            nn.Linear(fused_features, 256),
            nn.LayerNorm(256),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(256, classes),
        )

    @property
    def rgb_gradcam_layer(self) -> nn.Module:
        return self.rgb_branch.layer4[-1]

    @property
    def thermal_gradcam_layer(self) -> nn.Module:
        return self.thermal_branch.layer4[-1]

    def forward(
        self, rgb: torch.Tensor, thermal: torch.Tensor, environment: torch.Tensor
    ) -> torch.Tensor:
        if self.modality == "rgb":
            fused = self.rgb_branch(rgb)
        elif self.modality == "thermal":
            fused = self.thermal_branch(thermal)
        else:
            fused = torch.cat(
                (self.rgb_branch(rgb), self.thermal_branch(thermal)), dim=1
            )
            if self.modality == "fusion_env":
                fused = torch.cat((fused, self.environment_branch(environment)), dim=1)
        return self.classifier(fused)


@dataclass
class GradCAMResult:
    heatmap: np.ndarray
    target_class: int


class GradCAM:
    """Gradient-weighted class activation map for a trained CNN branch."""

    def __init__(self, model: MultimodalAnomalyNet, branch: str = "thermal") -> None:
        self.model = model
        self.activations: torch.Tensor | None = None
        self.gradients: torch.Tensor | None = None
        layer = (
            model.thermal_gradcam_layer
            if branch == "thermal"
            else model.rgb_gradcam_layer
        )
        self._forward_handle = layer.register_forward_hook(self._capture_activations)

    def _capture_activations(self, _module, _inputs, output) -> None:
        self.activations = output
        if output.requires_grad:
            output.register_hook(self._capture_gradients)

    def _capture_gradients(self, gradient) -> None:
        self.gradients = gradient.detach()

    def __call__(
        self,
        rgb: torch.Tensor,
        thermal: torch.Tensor,
        environment: torch.Tensor,
        target_class: int | None = None,
    ) -> GradCAMResult:
        self.model.zero_grad(set_to_none=True)
        logits = self.model(rgb, thermal, environment)
        selected = int(logits.argmax(dim=1).item()) if target_class is None else target_class
        logits[:, selected].sum().backward()
        if self.activations is None or self.gradients is None:
            raise RuntimeError("Grad-CAM hooks did not capture a feature map")
        weights = self.gradients.mean(dim=(2, 3), keepdim=True)
        cam = F.relu((weights * self.activations).sum(dim=1, keepdim=True))
        cam = F.interpolate(cam, size=rgb.shape[-2:], mode="bilinear", align_corners=False)
        cam = cam[0, 0]
        cam -= cam.min()
        cam /= cam.max().clamp_min(1e-8)
        return GradCAMResult(cam.detach().cpu().numpy(), selected)

    def close(self) -> None:
        self._forward_handle.remove()
