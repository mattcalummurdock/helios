"""ResNet-18 + CBAM for MSTAR SAR classification."""

from __future__ import annotations

import torch
from torch import nn
from torchvision.models import ResNet18_Weights, resnet18

from ml.models.cbam import CBAM


class MStarCNN(nn.Module):
    def __init__(self, num_classes: int = 8) -> None:
        super().__init__()
        backbone = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
        backbone.conv1 = nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.stem = nn.Sequential(backbone.conv1, backbone.bn1, backbone.relu, backbone.maxpool)
        self.layer1 = backbone.layer1
        self.layer2 = backbone.layer2
        self.layer3 = backbone.layer3
        self.cbam = CBAM(256)
        self.layer4 = backbone.layer4
        self.pool = backbone.avgpool
        self.fc = nn.Linear(backbone.fc.in_features, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.cbam(x)
        x = self.layer4(x)
        x = self.pool(x)
        x = torch.flatten(x, 1)
        return self.fc(x)


def load_mstar_model(checkpoint_path: str | None = None, num_classes: int = 8) -> MStarCNN:
    model = MStarCNN(num_classes=num_classes)
    if checkpoint_path:
        state = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        if isinstance(state, dict) and "model_state_dict" in state:
            model.load_state_dict(state["model_state_dict"])
        elif isinstance(state, dict) and "state_dict" in state:
            model.load_state_dict(state["state_dict"])
        else:
            model.load_state_dict(state)
    model.eval()
    return model
