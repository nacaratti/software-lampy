from pydantic import BaseModel, Field


class EncodedArray(BaseModel):
    """A numpy array serialized as base64.

    - dtype: 'float32' for real arrays, 'complex64' for complex
      (complex stored as interleaved real/imag float32 pairs)
    - data: base64 of the raw little-endian byte buffer
    """
    shape: list[int]
    dtype: str = Field(..., pattern="^(float32|complex64)$")
    data: str  # base64-encoded
