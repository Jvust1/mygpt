"""Already-installed NumPy scalars; no wake SDK/model download or inference."""
import numpy as np

from mygpt_brain.wakeword import OpenWakeWordGate


def test_actual_numpy_wake_scalars_preserve_valid_confidence_and_reject_bool_arrays():
    class Model:
        def __init__(self, row):
            self.row = row

        def predict(self, _frame):
            return self.row

    for value in (np.float16(0.5), np.float32(0.5), np.float64(0.5), np.int64(1)):
        result = OpenWakeWordGate(Model({"wake": value}), threshold=0.5).process(b"pcm")
        assert result.triggered and result.score == float(value)
    invalid = {"bool": np.bool_(True), "array": np.array([1.0]), "inf": np.float32(np.inf),
               "nan": np.float64(np.nan), "high": np.float64(2.0),
               "precise-high": np.nextafter(np.longdouble(1), np.longdouble(2))}
    result = OpenWakeWordGate(Model(invalid)).process(b"pcm")
    assert not result.triggered and result.score == 0.0
    result = OpenWakeWordGate(Model({**invalid, "valid": np.float32(0.75)})).process(b"pcm")
    assert result.triggered and result.label == "valid" and result.score == 0.75
