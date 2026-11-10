"""Fraud / anomaly detection engine for CardDemo transactions.

Uses Isolation Forest (unsupervised) to flag anomalous transactions based on
amount, merchant, time-of-day, and category patterns. Designed to complement
the rule-based posting validation (CBTRN02C) with ML-based risk scoring.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from .models import Transaction


@dataclass
class RiskScore:
    tran_id: str
    card_num: str
    amount: float
    risk_score: float  # 0.0 (safe) to 1.0 (high risk)
    is_anomaly: bool
    features: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


@dataclass
class FraudReport:
    total: int
    anomalies: int
    anomaly_rate: float
    high_risk: list[RiskScore]
    medium_risk: list[RiskScore]
    risk_distribution: dict[str, int]


class FraudDetector:
    """Unsupervised anomaly detection on transaction data."""

    def __init__(self, contamination: float = 0.05, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self.model: IsolationForest | None = None
        self.scaler: StandardScaler | None = None
        self._feature_names = [
            "amount", "amount_log", "hour", "is_weekend",
            "merchant_freq", "category_freq", "amount_zscore",
        ]

    def _extract_features(self, transactions: list[Transaction]) -> np.ndarray:
        """Extract numeric features for ML model."""
        # Compute merchant and category frequencies
        merchant_counts: dict[str, int] = {}
        category_counts: dict[str, int] = {}
        for t in transactions:
            merchant_counts[t.merchant_name] = merchant_counts.get(t.merchant_name, 0) + 1
            key = f"{t.tran_type_cd}-{t.tran_cat_cd}"
            category_counts[key] = category_counts.get(key, 0) + 1

        amounts = [float(t.tran_amt) for t in transactions]
        mean_amt = np.mean(amounts) if amounts else 0
        std_amt = np.std(amounts) if amounts and np.std(amounts) > 0 else 1

        features = []
        for t in transactions:
            amt = float(t.tran_amt)
            # Parse hour from proc_ts or orig_ts
            ts = t.proc_ts or t.orig_ts
            hour = 12
            is_weekend = 0
            if len(ts) >= 13:
                try:
                    hour = int(ts[11:13])
                except ValueError:
                    hour = 12
            if len(ts) >= 10:
                try:
                    from datetime import datetime
                    dt = datetime.strptime(ts[:10], "%Y-%m-%d")
                    is_weekend = 1 if dt.weekday() >= 5 else 0
                except ValueError:
                    pass

            merchant_freq = merchant_counts.get(t.merchant_name, 1)
            cat_key = f"{t.tran_type_cd}-{t.tran_cat_cd}"
            category_freq = category_counts.get(cat_key, 1)
            amount_zscore = (amt - mean_amt) / std_amt if std_amt > 0 else 0

            features.append([
                amt,
                np.log1p(abs(amt)),
                hour,
                is_weekend,
                merchant_freq,
                category_freq,
                amount_zscore,
            ])

        return np.array(features, dtype=float)

    def fit(self, transactions: list[Transaction]) -> FraudDetector:
        """Train the anomaly detection model."""
        if len(transactions) < 10:
            raise ValueError("Need at least 10 transactions for fraud detection")

        X = self._extract_features(transactions)
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100,
        )
        self.model.fit(X_scaled)
        return self

    def predict(self, transactions: list[Transaction]) -> list[RiskScore]:
        """Score transactions for fraud risk."""
        if self.model is None or self.scaler is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        X = self._extract_features(transactions)
        X_scaled = self.scaler.transform(X)

        # decision_function: negative = anomaly, positive = normal
        scores = self.model.decision_function(X_scaled)
        predictions = self.model.predict(X_scaled)  # -1 = anomaly, 1 = normal

        # Normalize scores to 0-1 risk (higher = more risky)
        # Use percentile-based normalization for better spread
        risk_scores = []
        # Convert decision_function to risk: invert and scale using min-max
        min_score = float(np.min(scores))
        max_score = float(np.max(scores))
        score_range = max_score - min_score if max_score != min_score else 1.0

        for i, t in enumerate(transactions):
            raw_score = float(scores[i])
            # Normalize to [0, 1], then invert (lower score = higher risk)
            normalized = (raw_score - min_score) / score_range
            risk = 1.0 - normalized
            risk = max(0.0, min(1.0, risk))
            is_anomaly = bool(predictions[i] == -1)

            # Build reasons
            reasons = []
            amt = float(t.tran_amt)
            if amt > 5000:
                reasons.append("High amount (>$5000)")
            if amt < -1000:
                reasons.append("Large negative amount")
            ts = t.proc_ts or t.orig_ts
            hour = 12
            if len(ts) >= 13:
                try:
                    hour = int(ts[11:13])
                except ValueError:
                    pass
            if hour < 6 or hour > 22:
                reasons.append(f"Unusual hour ({hour}:00)")
            if is_anomaly and not reasons:
                reasons.append("Statistical anomaly detected")

            risk_scores.append(RiskScore(
                tran_id=t.tran_id,
                card_num=t.card_num,
                amount=amt,
                risk_score=round(risk, 4),
                is_anomaly=is_anomaly,
                features={
                    "amount": amt,
                    "hour": hour,
                    "amount_zscore": float(X[i][6]),
                },
                reasons=reasons,
            ))

        return risk_scores

    def analyze(self, transactions: list[Transaction]) -> FraudReport:
        """Full fraud analysis with categorization."""
        self.fit(transactions)
        scores = self.predict(transactions)

        high_risk = [s for s in scores if s.risk_score >= 0.7]
        medium_risk = [s for s in scores if 0.4 <= s.risk_score < 0.7]
        anomalies = sum(1 for s in scores if s.is_anomaly)

        # Risk distribution
        dist = {"low (0-0.3)": 0, "medium (0.3-0.7)": 0, "high (0.7-1.0)": 0}
        for s in scores:
            if s.risk_score < 0.3:
                dist["low (0-0.3)"] += 1
            elif s.risk_score < 0.7:
                dist["medium (0.3-0.7)"] += 1
            else:
                dist["high (0.7-1.0)"] += 1

        high_risk.sort(key=lambda s: s.risk_score, reverse=True)
        medium_risk.sort(key=lambda s: s.risk_score, reverse=True)

        return FraudReport(
            total=len(transactions),
            anomalies=anomalies,
            anomaly_rate=round(anomalies / len(transactions), 4) if transactions else 0,
            high_risk=high_risk[:20],
            medium_risk=medium_risk[:20],
            risk_distribution=dist,
        )

    def to_json(self, report: FraudReport) -> dict:
        return {
            "total_transactions": report.total,
            "anomalies_detected": report.anomalies,
            "anomaly_rate": report.anomaly_rate,
            "risk_distribution": report.risk_distribution,
            "high_risk_count": len(report.high_risk),
            "medium_risk_count": len(report.medium_risk),
            "high_risk": [
                {"tran_id": s.tran_id, "card": s.card_num, "amount": s.amount,
                 "risk_score": s.risk_score, "reasons": s.reasons}
                for s in report.high_risk
            ],
            "medium_risk": [
                {"tran_id": s.tran_id, "card": s.card_num, "amount": s.amount,
                 "risk_score": s.risk_score, "reasons": s.reasons}
                for s in report.medium_risk
            ],
        }
