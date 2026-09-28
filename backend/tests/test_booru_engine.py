"""WD v3 category and threshold compatibility without downloading a model."""

import numpy as np

from companion.booru_engine import BooruEngine
from companion.config import Settings


class FakeSession:
    def run(self, outputs, inputs):
        assert outputs == ["scores"]
        assert list(inputs) == ["pixels"]
        return [np.array([[0.7, 0.34, 0.89, 0.95, 0.8, 0.5]], dtype=np.float32)]


def test_predictions_match_wd_general_character_and_best_rating_rules() -> None:
    engine = BooruEngine(Settings())
    engine._session = FakeSession()
    engine._repo = "SmilingWolf/wd-swinv2-tagger-v3"
    engine._names = ["sky", "below", "character_low", "character_high", "general", "explicit"]
    engine._categories = [0, 0, 4, 4, 9, 9]
    engine._input = "pixels"
    engine._output = "scores"
    engine._prepare = lambda data: np.zeros((2, 2, 3), dtype=np.float32)

    assert engine._predict(b"image", engine._repo, 0.35, 0.9) == [
        "character_high", "general", "sky"
    ]
