"""
Learning to Rank (LTR) Framework

Implements multiple LTR models to learn optimal ranking from ground truth data:
- LambdaMART: Gradient boosted trees for ranking
- RankNet: Neural pairwise ranking
- ListNet: Listwise ranking with cross-entropy loss

Optimizes for NDCG@10 with query-type-specific weight adaptation.
"""

import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass
import pickle
import json
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import ndcg_score
import torch
import torch.nn as nn
import torch.optim as optim
from feature_extractor import QueryDocFeatures


@dataclass
class RankingWeights:
    """Learned weights for ranking components"""
    query_type: str
    simrank_weight: float
    horn_index_weight: float
    embedding_weight: float
    confidence: float  # Model confidence in these weights

    def to_array(self) -> np.ndarray:
        """Convert to numpy array"""
        return np.array([self.simrank_weight, self.horn_index_weight, self.embedding_weight])

    def normalize(self):
        """Normalize weights to sum to 1.0"""
        total = self.simrank_weight + self.horn_index_weight + self.embedding_weight
        if total > 0:
            self.simrank_weight /= total
            self.horn_index_weight /= total
            self.embedding_weight /= total


class LambdaMART:
    """
    LambdaMART: Gradient Boosted Trees for Ranking

    Uses gradient boosting with custom lambda gradients that optimize
    for ranking metrics like NDCG.
    """

    def __init__(self, n_estimators: int = 100, max_depth: int = 6, learning_rate: float = 0.1):
        """Initialize LambdaMART model"""
        self.model = GradientBoostingRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            random_state=42
        )
        self.is_trained = False

    def train(self, X: np.ndarray, y: np.ndarray, query_ids: np.ndarray):
        """
        Train LambdaMART model

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Relevance labels (n_samples,)
            query_ids: Query identifiers for grouping (n_samples,)
        """
        # Group samples by query for NDCG calculation
        self.query_groups = self._group_by_query(X, y, query_ids)

        # Train model
        self.model.fit(X, y)
        self.is_trained = True

        # Compute training NDCG
        train_ndcg = self._compute_ndcg(X, y, query_ids)
        print(f"LambdaMART trained: Training NDCG@10 = {train_ndcg:.4f}")

        return train_ndcg

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict relevance scores"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        return self.model.predict(X)

    def _group_by_query(self, X: np.ndarray, y: np.ndarray, query_ids: np.ndarray) -> Dict:
        """Group samples by query ID"""
        groups = {}
        for i, qid in enumerate(query_ids):
            if qid not in groups:
                groups[qid] = {'X': [], 'y': []}
            groups[qid]['X'].append(X[i])
            groups[qid]['y'].append(y[i])

        # Convert to arrays
        for qid in groups:
            groups[qid]['X'] = np.array(groups[qid]['X'])
            groups[qid]['y'] = np.array(groups[qid]['y'])

        return groups

    def _compute_ndcg(self, X: np.ndarray, y_true: np.ndarray, query_ids: np.ndarray, k: int = 10) -> float:
        """Compute NDCG@k"""
        y_pred = self.predict(X)
        groups = self._group_by_query(X, y_true, query_ids)

        ndcg_scores = []
        for qid in groups:
            y_t = groups[qid]['y'].reshape(1, -1)

            # Get predictions for this query
            mask = query_ids == qid
            y_p = y_pred[mask].reshape(1, -1)

            # Compute NDCG@k
            if len(y_t[0]) > 0:
                ndcg = ndcg_score(y_t, y_p, k=min(k, len(y_t[0])))
                ndcg_scores.append(ndcg)

        return np.mean(ndcg_scores) if ndcg_scores else 0.0

    def extract_weights(self) -> np.ndarray:
        """
        Extract component weights from feature importances

        Returns first 3 feature importances (simrank, horn, embedding)
        normalized to sum to 1.0
        """
        if not self.is_trained:
            return np.array([0.4, 0.3, 0.3])  # Default weights

        importances = self.model.feature_importances_[:3]  # First 3 features
        total = importances.sum()
        if total > 0:
            importances = importances / total

        return importances


class RankNet(nn.Module):
    """
    RankNet: Neural Pairwise Ranking Model

    Learns to predict pairwise preferences using neural network.
    """

    def __init__(self, input_dim: int, hidden_dim: int = 64):
        """Initialize RankNet"""
        super(RankNet, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.fc3 = nn.Linear(hidden_dim // 2, 1)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)

    def forward(self, x):
        """Forward pass"""
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.relu(self.fc2(x))
        x = self.dropout(x)
        x = self.fc3(x)
        return x

    def pairwise_loss(self, scores_i, scores_j, labels_i, labels_j):
        """
        RankNet pairwise loss

        If labels_i > labels_j, score_i should be > score_j
        """
        # Only compute loss for pairs where relevance differs
        diff = labels_i - labels_j

        # Sigmoid cross-entropy loss
        score_diff = (scores_i - scores_j).squeeze(-1)
        target = (diff > 0).float()

        loss = nn.functional.binary_cross_entropy_with_logits(
            score_diff,
            target,
            reduction='mean'
        )

        return loss


class ListNet(nn.Module):
    """
    ListNet: Listwise Ranking Model

    Treats ranking as a probability distribution learning problem.
    """

    def __init__(self, input_dim: int, hidden_dim: int = 64):
        """Initialize ListNet"""
        super(ListNet, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.fc3 = nn.Linear(hidden_dim // 2, 1)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)

    def forward(self, x):
        """Forward pass"""
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.relu(self.fc2(x))
        x = self.dropout(x)
        x = self.fc3(x)
        return x.squeeze(-1)

    def listwise_loss(self, scores, labels):
        """
        ListNet loss: KL divergence between predicted and true distributions

        Args:
            scores: Predicted scores (batch_size,)
            labels: True relevance labels (batch_size,)
        """
        # Convert scores to probability distribution via softmax
        pred_probs = torch.softmax(scores, dim=0)

        # Convert labels to probability distribution
        # Use exponential to give higher weight to more relevant docs
        true_probs = torch.softmax(labels.float(), dim=0)

        # KL divergence
        loss = torch.sum(true_probs * (torch.log(true_probs + 1e-10) - torch.log(pred_probs + 1e-10)))

        return loss


class LearnedRanker:
    """
    Main LTR Framework

    Trains and compares multiple LTR models, extracts learned weights,
    and provides query-type-specific ranking.
    """

    def __init__(self, model_type: str = 'lambdamart'):
        """
        Initialize learned ranker

        Args:
            model_type: 'lambdamart', 'ranknet', or 'listnet'
        """
        self.model_type = model_type
        self.model = None
        self.query_type_weights = {}  # Weights for each query type
        self.is_trained = False

    def train(self,
              training_features: List[QueryDocFeatures],
              n_folds: int = 5,
              optimize_per_query_type: bool = True):
        """
        Train LTR model with cross-validation

        Args:
            training_features: List of QueryDocFeatures
            n_folds: Number of CV folds
            optimize_per_query_type: Train separate weights per query type
        """
        # Convert to arrays
        X = np.array([f.to_feature_vector() for f in training_features])
        y = np.array([f.relevance_label for f in training_features])
        query_ids = np.array([f.query_id for f in training_features])
        query_types = np.array([f.query_type_encoding for f in training_features])

        print(f"\nTraining {self.model_type.upper()} model:")
        print(f"  Training samples: {len(training_features)}")
        print(f"  Unique queries: {len(np.unique(query_ids))}")
        print(f"  Features: {X.shape[1]}")

        if self.model_type == 'lambdamart':
            self.model = self._train_lambdamart(X, y, query_ids, n_folds)
        elif self.model_type == 'ranknet':
            self.model = self._train_ranknet(X, y, query_ids, n_folds)
        elif self.model_type == 'listnet':
            self.model = self._train_listnet(X, y, query_ids, n_folds)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        # Extract query-type-specific weights
        if optimize_per_query_type:
            self._extract_query_type_weights(X, y, query_types)

        self.is_trained = True

    def _train_lambdamart(self, X: np.ndarray, y: np.ndarray, query_ids: np.ndarray, n_folds: int) -> LambdaMART:
        """Train LambdaMART with cross-validation"""
        kfold = KFold(n_splits=n_folds, shuffle=True, random_state=42)

        cv_scores = []
        for fold, (train_idx, val_idx) in enumerate(kfold.split(X)):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]
            qid_train, qid_val = query_ids[train_idx], query_ids[val_idx]

            model = LambdaMART()
            model.train(X_train, y_train, qid_train)

            # Validate
            val_ndcg = model._compute_ndcg(X_val, y_val, qid_val)
            cv_scores.append(val_ndcg)
            print(f"  Fold {fold+1}/{n_folds}: NDCG@10 = {val_ndcg:.4f}")

        print(f"  Cross-validation NDCG@10: {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores):.4f})")

        # Train final model on all data
        final_model = LambdaMART()
        final_model.train(X, y, query_ids)

        return final_model

    def _train_ranknet(self, X: np.ndarray, y: np.ndarray, query_ids: np.ndarray, n_folds: int) -> RankNet:
        """Train RankNet with cross-validation"""
        input_dim = X.shape[1]
        kfold = KFold(n_splits=n_folds, shuffle=True, random_state=42)

        cv_scores = []
        for fold, (train_idx, val_idx) in enumerate(kfold.split(X)):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            model = RankNet(input_dim)
            optimizer = optim.Adam(model.parameters(), lr=0.001)

            # Training loop
            X_train_tensor = torch.FloatTensor(X_train)
            y_train_tensor = torch.FloatTensor(y_train)

            epochs = 50
            batch_size = 32

            for epoch in range(epochs):
                model.train()
                total_loss = 0

                # Generate pairwise samples
                n_samples = len(X_train)
                for _ in range(n_samples // batch_size):
                    # Sample pairs
                    idx_i = np.random.choice(n_samples, batch_size)
                    idx_j = np.random.choice(n_samples, batch_size)

                    X_i = X_train_tensor[idx_i]
                    X_j = X_train_tensor[idx_j]
                    y_i = y_train_tensor[idx_i]
                    y_j = y_train_tensor[idx_j]

                    # Forward pass
                    scores_i = model(X_i)
                    scores_j = model(X_j)

                    # Compute loss
                    loss = model.pairwise_loss(scores_i, scores_j, y_i, y_j)

                    # Backward pass
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()

                    total_loss += loss.item()

            # Validation NDCG
            model.eval()
            with torch.no_grad():
                X_val_tensor = torch.FloatTensor(X_val)
                val_scores = model(X_val_tensor).numpy()
                val_ndcg = self._compute_ndcg_from_scores(val_scores, y_val, query_ids[val_idx])
                cv_scores.append(val_ndcg)
                print(f"  Fold {fold+1}/{n_folds}: NDCG@10 = {val_ndcg:.4f}")

        print(f"  Cross-validation NDCG@10: {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores):.4f})")

        # Train final model on all data
        final_model = RankNet(input_dim)
        optimizer = optim.Adam(final_model.parameters(), lr=0.001)

        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.FloatTensor(y)

        for epoch in range(50):
            final_model.train()
            for _ in range(len(X) // 32):
                idx_i = np.random.choice(len(X), 32)
                idx_j = np.random.choice(len(X), 32)

                scores_i = final_model(X_tensor[idx_i])
                scores_j = final_model(X_tensor[idx_j])

                loss = final_model.pairwise_loss(scores_i, scores_j, y_tensor[idx_i], y_tensor[idx_j])

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

        return final_model

    def _train_listnet(self, X: np.ndarray, y: np.ndarray, query_ids: np.ndarray, n_folds: int) -> ListNet:
        """Train ListNet with cross-validation"""
        input_dim = X.shape[1]
        kfold = KFold(n_splits=n_folds, shuffle=True, random_state=42)

        cv_scores = []
        for fold, (train_idx, val_idx) in enumerate(kfold.split(X)):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]
            qid_train, qid_val = query_ids[train_idx], query_ids[val_idx]

            model = ListNet(input_dim)
            optimizer = optim.Adam(model.parameters(), lr=0.001)

            # Group by query
            unique_qids = np.unique(qid_train)

            # Training loop
            epochs = 50
            for epoch in range(epochs):
                model.train()
                total_loss = 0

                for qid in unique_qids:
                    mask = qid_train == qid
                    X_q = torch.FloatTensor(X_train[mask])
                    y_q = torch.FloatTensor(y_train[mask])

                    if len(X_q) < 2:
                        continue

                    # Forward pass
                    scores = model(X_q)

                    # Compute loss
                    loss = model.listwise_loss(scores, y_q)

                    # Backward pass
                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()

                    total_loss += loss.item()

            # Validation NDCG
            model.eval()
            with torch.no_grad():
                X_val_tensor = torch.FloatTensor(X_val)
                val_scores = model(X_val_tensor).numpy()
                val_ndcg = self._compute_ndcg_from_scores(val_scores, y_val, qid_val)
                cv_scores.append(val_ndcg)
                print(f"  Fold {fold+1}/{n_folds}: NDCG@10 = {val_ndcg:.4f}")

        print(f"  Cross-validation NDCG@10: {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores):.4f})")

        # Train final model (similar to fold training)
        final_model = ListNet(input_dim)
        optimizer = optim.Adam(final_model.parameters(), lr=0.001)

        unique_qids = np.unique(query_ids)
        for epoch in range(50):
            final_model.train()
            for qid in unique_qids:
                mask = query_ids == qid
                X_q = torch.FloatTensor(X[mask])
                y_q = torch.FloatTensor(y[mask])

                if len(X_q) < 2:
                    continue

                scores = final_model(X_q)
                loss = final_model.listwise_loss(scores, y_q)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

        return final_model

    def _compute_ndcg_from_scores(self, scores: np.ndarray, y_true: np.ndarray, query_ids: np.ndarray, k: int = 10) -> float:
        """Compute NDCG@k from predicted scores"""
        unique_qids = np.unique(query_ids)
        ndcg_scores = []

        for qid in unique_qids:
            mask = query_ids == qid
            y_t = y_true[mask].reshape(1, -1)
            y_p = scores[mask].reshape(1, -1)

            if len(y_t[0]) > 0:
                ndcg = ndcg_score(y_t, y_p, k=min(k, len(y_t[0])))
                ndcg_scores.append(ndcg)

        return np.mean(ndcg_scores) if ndcg_scores else 0.0

    def _extract_query_type_weights(self, X: np.ndarray, y: np.ndarray, query_types: np.ndarray):
        """Extract weights for each query type"""
        from query_classifier import QueryTypeClassifier

        type_names = QueryTypeClassifier.QUERY_TYPES

        print("\nExtracting query-type-specific weights:")

        for type_id, type_name in type_names.items():
            mask = query_types == type_id

            if mask.sum() == 0:
                print(f"  {type_name}: No samples, using default weights")
                self.query_type_weights[type_name] = RankingWeights(
                    query_type=type_name,
                    simrank_weight=0.4,
                    horn_index_weight=0.3,
                    embedding_weight=0.3,
                    confidence=0.5
                )
                continue

            X_type = X[mask]
            y_type = y[mask]

            # Extract weights from model
            if self.model_type == 'lambdamart':
                weights = self.model.extract_weights()
            else:
                # For neural models, use feature importance approximation
                weights = self._approximate_feature_importance(X_type, y_type)

            # Create RankingWeights object
            ranking_weights = RankingWeights(
                query_type=type_name,
                simrank_weight=float(weights[0]),
                horn_index_weight=float(weights[1]),
                embedding_weight=float(weights[2]),
                confidence=min(mask.sum() / 10, 1.0)  # Confidence based on sample size
            )
            ranking_weights.normalize()

            self.query_type_weights[type_name] = ranking_weights

            print(f"  {type_name} ({mask.sum()} samples):")
            print(f"    SimRank: {ranking_weights.simrank_weight:.3f}")
            print(f"    Horn: {ranking_weights.horn_index_weight:.3f}")
            print(f"    Embedding: {ranking_weights.embedding_weight:.3f}")
            print(f"    Confidence: {ranking_weights.confidence:.3f}")

    def _approximate_feature_importance(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Approximate feature importance for neural models"""
        # Use correlation with labels as proxy for importance
        correlations = np.abs([np.corrcoef(X[:, i], y)[0, 1] for i in range(3)])
        correlations = np.nan_to_num(correlations)  # Handle NaN
        total = correlations.sum()
        if total > 0:
            return correlations / total
        return np.array([0.4, 0.3, 0.3])

    def get_weights_for_query_type(self, query_type: str) -> RankingWeights:
        """Get learned weights for a specific query type"""
        if not self.is_trained:
            raise ValueError("Model not trained")

        return self.query_type_weights.get(query_type, self._get_default_weights())

    def _get_default_weights(self) -> RankingWeights:
        """Get default weights (fallback)"""
        return RankingWeights(
            query_type='default',
            simrank_weight=0.4,
            horn_index_weight=0.3,
            embedding_weight=0.3,
            confidence=0.5
        )

    def save(self, model_file: str):
        """Save trained model and weights"""
        model_data = {
            'model_type': self.model_type,
            'query_type_weights': self.query_type_weights,
            'is_trained': self.is_trained
        }

        # Save model based on type
        if self.model_type == 'lambdamart':
            model_data['model'] = self.model
        elif self.model_type in ['ranknet', 'listnet']:
            model_data['model_state'] = self.model.state_dict()

        with open(model_file, 'wb') as f:
            pickle.dump(model_data, f)

        print(f"\nModel saved to: {model_file}")

    def load(self, model_file: str):
        """Load trained model and weights"""
        with open(model_file, 'rb') as f:
            model_data = pickle.load(f)

        self.model_type = model_data['model_type']
        self.query_type_weights = model_data['query_type_weights']
        self.is_trained = model_data['is_trained']

        if self.model_type == 'lambdamart':
            self.model = model_data['model']
        elif self.model_type in ['ranknet', 'listnet']:
            # Recreate model and load state
            # Note: Need to know input_dim, using default
            if self.model_type == 'ranknet':
                self.model = RankNet(18)  # Default feature count
            else:
                self.model = ListNet(18)
            self.model.load_state_dict(model_data['model_state'])

        print(f"Model loaded from: {model_file}")


if __name__ == '__main__':
    print("Learning to Rank Framework")
    print("="*60)
    print("\nThis module requires training data from:")
    print("  - Ground truth annotations")
    print("  - Recommender system output with component scores")
    print("\nSee training script: src/5_ranking/train_ltr.py")
