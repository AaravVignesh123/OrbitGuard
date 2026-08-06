"""1-D CNN over CDM sequences — the learned challenger to the tree baseline.

Each event is a ``(F, L)`` multi-channel signal (F per-CDM features across L
timesteps). A small 1-D convolutional net reads the whole trajectory — how the
risk, miss distance and covariance evolve as TCA approaches — and regresses the
final risk. Evaluated on the **identical** 5-fold split and metrics as
``model.train_baseline`` so the comparison is honest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.model_selection import StratifiedKFold

from .model import _metrics
from .sequences import SeqDataset, standardize

_TORCH_ERR = ("PyTorch is required for the CNN. Install it with:\n"
              "    pip install torch")


@dataclass
class CNNResult:
    metrics: dict
    oof_pred: np.ndarray
    history: list = field(default_factory=list)


def _build_net(n_feat, hidden=64, p=0.2):
    import torch.nn as nn

    class CDMConvNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.body = nn.Sequential(
                nn.Conv1d(n_feat, hidden, 3, padding=1), nn.BatchNorm1d(hidden), nn.ReLU(),
                nn.Conv1d(hidden, hidden, 3, padding=1), nn.BatchNorm1d(hidden), nn.ReLU(),
                nn.Conv1d(hidden, hidden, 3, padding=1), nn.BatchNorm1d(hidden), nn.ReLU(),
            )
            self.head = nn.Sequential(
                nn.Linear(hidden * 2, 64), nn.ReLU(), nn.Dropout(p), nn.Linear(64, 1))

        def forward(self, x, mask):           # x: (B, F, L)  mask: (B, L)
            import torch
            h = self.body(x)                  # (B, hidden, L)
            m = mask.unsqueeze(1).float()     # (B, 1, L)
            avg = (h * m).sum(-1) / m.sum(-1).clamp(min=1.0)
            mx = h.masked_fill(m == 0, float("-inf")).max(-1).values
            mx = torch.nan_to_num(mx, neginf=0.0)
            return self.head(torch.cat([avg, mx], dim=1)).squeeze(1)

    return CDMConvNet()


def _train_fold(Xtr, mtr, ytr, wtr, Xva, mva, *, epochs, lr, device):
    import torch
    from torch.utils.data import DataLoader, TensorDataset

    net = _build_net(Xtr.shape[1]).to(device)
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-4)
    ds = TensorDataset(torch.from_numpy(Xtr), torch.from_numpy(mtr),
                       torch.from_numpy(ytr), torch.from_numpy(wtr))
    dl = DataLoader(ds, batch_size=256, shuffle=True, drop_last=True)

    net.train()
    for _ in range(epochs):
        for xb, mb, yb, wb in dl:
            xb, mb, yb, wb = xb.to(device), mb.to(device), yb.to(device), wb.to(device)
            opt.zero_grad()
            pred = net(xb, mb)
            loss = (wb * (pred - yb) ** 2).mean()      # weighted MSE
            loss.backward()
            opt.step()

    net.eval()
    with torch.no_grad():
        pv = net(torch.from_numpy(Xva).to(device), torch.from_numpy(mva).to(device))
    return pv.cpu().numpy()


def train_cnn(seq: SeqDataset, *, n_splits: int = 5, seed: int = 42,
              risk_floor: float = -10.0, epochs: int = 40, lr: float = 1e-3,
              pos_weight: float = 8.0) -> "CNNResult":
    try:
        import torch
    except ImportError as e:                 # pragma: no cover
        raise ImportError(_TORCH_ERR) from e

    torch.manual_seed(seed)
    np.random.seed(seed)
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    X = np.transpose(seq.X, (0, 2, 1)).astype(np.float32)   # (N, F, L)
    mask = seq.mask
    y_risk, y_high = seq.y_risk, seq.y_high
    y_train = np.clip(y_risk, risk_floor, None).astype(np.float32)
    weights = np.where(y_high, pos_weight, 1.0).astype(np.float32)

    oof = np.full(len(X), np.nan, dtype=np.float64)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for fold, (tr, va) in enumerate(skf.split(X, y_high), 1):
        # standardize per feature using train timesteps only (no leakage)
        Xall = standardize(np.transpose(X[tr], (0, 2, 1)),          # (n,L,F) for stats
                           np.transpose(X, (0, 2, 1)), mask[tr])
        Xall = np.transpose(Xall, (0, 2, 1)).astype(np.float32)     # back to (N,F,L)
        pv = _train_fold(Xall[tr], mask[tr], y_train[tr], weights[tr],
                         Xall[va], mask[va], epochs=epochs, lr=lr, device=device)
        oof[va] = pv

    metrics = _metrics(y_high, y_risk, oof)
    metrics["risk_floor"] = risk_floor
    metrics["model"] = "cnn1d"
    return CNNResult(metrics=metrics, oof_pred=oof)
