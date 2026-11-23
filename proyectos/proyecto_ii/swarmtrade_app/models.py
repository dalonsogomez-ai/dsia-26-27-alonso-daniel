"""-> Modelos sklearn: mismos factores al entrenar e inferir."""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted
from ._vendor.specialists import DEFAULT_ROSTER


def ridge_model(alpha: float = 10):
    return make_pipeline(StandardScaler(), Ridge(alpha=alpha))


class SwarmRegressor(RegressorMixin, BaseEstimator):
    """~> Cinco especialistas originales, cada uno con Ridge, y media fija."""
    def __init__(self, alpha: float = 10):
        self.alpha = alpha

    def fit(self, X, y):
        self.models_ = {}
        self.feature_names_in_ = np.array(X.columns, dtype=object)
        self.n_features_in_ = len(X.columns)
        for specialist in DEFAULT_ROSTER:
            columns = list(specialist.available(list(X.columns)))
            self.models_[specialist.name] = (columns, ridge_model(self.alpha).fit(X[columns], y))
        return self

    def specialist_predictions(self, X):
        check_is_fitted(self, 'models_')
        return {name: model.predict(X[columns]) for name, (columns, model) in self.models_.items()}

    def predict(self, X):
        return np.column_stack(list(self.specialist_predictions(X).values())).mean(axis=1)
