import base64
import numpy as np
from backend.app.schemas.common import EncodedArray


def encode_array(arr: np.ndarray) -> EncodedArray:
    """Encode a numpy array as base64 little-endian bytes.

    - Real arrays become float32.
    - Complex arrays become complex64 stored as interleaved [re0, im0, re1, im1, ...] float32.
    """
    a = np.ascontiguousarray(arr)
    if np.iscomplexobj(a):
        a = a.astype(np.complex64, copy=False)
        flat = a.view(np.float32).tobytes()
        return EncodedArray(
            shape=list(arr.shape),
            dtype="complex64",
            data=base64.b64encode(flat).decode("ascii"),
        )
    a = a.astype(np.float32, copy=False)
    return EncodedArray(
        shape=list(arr.shape),
        dtype="float32",
        data=base64.b64encode(a.tobytes()).decode("ascii"),
    )
