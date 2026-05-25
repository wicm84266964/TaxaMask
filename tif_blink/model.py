from __future__ import annotations

import torch
import torch.nn as nn


class DoubleConv(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class TifBlinkUNet2D(nn.Module):
    """Small 2D U-Net suitable for early TIF-Blink 2.5D experiments."""

    def __init__(self, in_channels: int, num_classes: int, base_channels: int = 32):
        super().__init__()
        c = int(base_channels)
        self.enc1 = DoubleConv(in_channels, c)
        self.pool1 = nn.MaxPool2d(2)
        self.enc2 = DoubleConv(c, c * 2)
        self.pool2 = nn.MaxPool2d(2)
        self.bottleneck = DoubleConv(c * 2, c * 4)
        self.up2 = nn.ConvTranspose2d(c * 4, c * 2, kernel_size=2, stride=2)
        self.dec2 = DoubleConv(c * 4, c * 2)
        self.up1 = nn.ConvTranspose2d(c * 2, c, kernel_size=2, stride=2)
        self.dec1 = DoubleConv(c * 2, c)
        self.out = nn.Conv2d(c, num_classes, kernel_size=1)

    def _pad_to(self, x: torch.Tensor, ref: torch.Tensor) -> torch.Tensor:
        diff_y = ref.shape[-2] - x.shape[-2]
        diff_x = ref.shape[-1] - x.shape[-1]
        if diff_y == 0 and diff_x == 0:
            return x
        return nn.functional.pad(
            x,
            [diff_x // 2, diff_x - diff_x // 2, diff_y // 2, diff_y - diff_y // 2],
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool1(e1))
        b = self.bottleneck(self.pool2(e2))
        d2 = self._pad_to(self.up2(b), e2)
        d2 = self.dec2(torch.cat([d2, e2], dim=1))
        d1 = self._pad_to(self.up1(d2), e1)
        d1 = self.dec1(torch.cat([d1, e1], dim=1))
        return self.out(d1)

