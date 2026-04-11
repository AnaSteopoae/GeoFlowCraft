"""
GeoFlowCraft SR Service — DualBranchSARNet Architecture
========================================================
Copiat din: /mnt/ssd/psteopoae/sarnet_dual_branch.py (HPC)

Arhitectura:
    - Branch S2:   Conv → N × RCAB → features_s2  [4ch → 64ch]
    - Branch S1:   Conv → N × RCAB → features_s1  [2ch → 64ch]
    - Fusion:      Channel Attention Cross-Modal   [128ch → 64ch]
    - Shared Body: M × RCAB cu Long Skip Connection
    - Upsample:    2× PixelShuffle × 2
    - Tail:        Conv → 4ch output
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


# ──────────────────────────────────────────────
# Blocuri de baza
# ──────────────────────────────────────────────

class ChannelAttention(nn.Module):
    def __init__(self, num_features: int, reduction: int = 16):
        super().__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Conv2d(num_features, num_features // reduction, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(num_features // reduction, num_features, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        return x * self.fc(self.avg_pool(x))


class RCAB(nn.Module):
    def __init__(self, num_features: int = 64, reduction: int = 16):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(num_features, num_features, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(num_features, num_features, 3, padding=1),
            ChannelAttention(num_features, reduction)
        )

    def forward(self, x):
        return self.block(x) + x


class UpsampleBlock(nn.Module):
    def __init__(self, num_features: int = 64, scale: int = 2):
        super().__init__()
        self.conv = nn.Conv2d(num_features, num_features * scale ** 2, 3, padding=1)
        self.ps   = nn.PixelShuffle(scale)
        self.relu = nn.ReLU(inplace=True)
        self.avg  = nn.AvgPool2d(2, stride=1, padding=0)

    def forward(self, x):
        out = self.relu(self.ps(self.conv(x)))
        out = F.pad(out, (0, 1, 0, 1), mode='replicate')
        return self.avg(out)


# ──────────────────────────────────────────────
# Modul de Fuziune Cross-Modal cu Atentie
# ──────────────────────────────────────────────

class CrossModalFusion(nn.Module):
    def __init__(self, num_features: int = 64, reduction: int = 16):
        super().__init__()
        self.s1_to_attn = nn.Sequential(
            nn.Conv2d(num_features, num_features // reduction, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(num_features // reduction, num_features, 1),
            nn.Sigmoid()
        )
        self.fusion_conv = nn.Sequential(
            nn.Conv2d(num_features * 2, num_features, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(num_features, num_features, 3, padding=1),
        )
        self.gate = nn.Parameter(torch.ones(1) * 0.5)

    def forward(self, feat_s2: torch.Tensor, feat_s1: torch.Tensor) -> torch.Tensor:
        attn   = self.s1_to_attn(feat_s1)
        s2_mod = feat_s2 * attn
        fused  = self.fusion_conv(torch.cat([s2_mod, feat_s1], dim=1))
        gate   = torch.sigmoid(self.gate)
        return gate * fused + (1 - gate) * feat_s2


# ──────────────────────────────────────────────
# Dual-Branch SARNet
# ──────────────────────────────────────────────

class DualBranchSARNet(nn.Module):
    def __init__(
        self,
        num_features:    int = 64,
        num_rcab_branch: int = 4,
        num_rcab_shared: int = 8,
        reduction:       int = 16,
        scale:           int = 4,
    ):
        super().__init__()

        # Branch S2 (4 canale input)
        self.s2_head = nn.Sequential(
            nn.Conv2d(4, num_features, 3, padding=1),
            nn.ReLU(inplace=True)
        )
        self.s2_body = nn.Sequential(*[
            RCAB(num_features, reduction) for _ in range(num_rcab_branch)
        ])

        # Branch S1 (2 canale input)
        self.s1_head = nn.Sequential(
            nn.Conv2d(2, num_features, 3, padding=1),
            nn.ReLU(inplace=True)
        )
        self.s1_body = nn.Sequential(*[
            RCAB(num_features, reduction) for _ in range(num_rcab_branch)
        ])

        # Fuziune Cross-Modal
        self.fusion = CrossModalFusion(num_features, reduction)

        # Corp comun dupa fuziune
        self.shared_body = nn.Sequential(*[
            RCAB(num_features, reduction) for _ in range(num_rcab_shared)
        ])
        self.shared_conv = nn.Conv2d(num_features, num_features, 3, padding=1)
        self.shared_bn   = nn.BatchNorm2d(num_features)

        # Upsampling
        num_up = scale // 2
        self.upsample = nn.Sequential(*[
            UpsampleBlock(num_features, 2) for _ in range(num_up)
        ])

        # Tail
        self.tail = nn.Conv2d(num_features, 4, 3, padding=1)
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, s2: torch.Tensor, s1: torch.Tensor) -> torch.Tensor:
        feat_s2 = self.s2_head(s2)
        feat_s2 = self.s2_body(feat_s2)

        feat_s1 = self.s1_head(s1)
        feat_s1 = self.s1_body(feat_s1)

        fused = self.fusion(feat_s2, feat_s1)

        body = self.shared_body(fused)
        body = self.shared_conv(body)
        body = self.shared_bn(body)
        body = body + fused

        up  = self.upsample(body)
        out = self.tail(up)
        return out