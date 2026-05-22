import type { EncodedArray } from "@/types/common";

/** Decode a base64 string into a Uint8Array. Fast browser-native path. */
function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export interface DecodedRealArray {
  shape: number[];
  data: Float32Array;
  kind: "real";
}

export interface DecodedComplexArray {
  shape: number[];
  /** Interleaved [re0, im0, re1, im1, ...] */
  data: Float32Array;
  kind: "complex";
}

export type DecodedArray = DecodedRealArray | DecodedComplexArray;

export function decodeArray(enc: EncodedArray): DecodedArray {
  const bytes = base64ToBytes(enc.data);
  // Float32 is 4 bytes
  const f32 = new Float32Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 4);
  if (enc.dtype === "complex64") {
    return { shape: enc.shape, data: f32, kind: "complex" };
  }
  return { shape: enc.shape, data: f32, kind: "real" };
}

/** Reshape a 1D Float32Array into nested 2D arrays for Plotly. */
export function reshape2D(flat: Float32Array, rows: number, cols: number): number[][] {
  if (flat.length !== rows * cols) {
    throw new Error(`reshape2D: ${flat.length} != ${rows}*${cols}`);
  }
  const out: number[][] = new Array(rows);
  for (let i = 0; i < rows; i++) {
    const row = new Array<number>(cols);
    const base = i * cols;
    for (let j = 0; j < cols; j++) row[j] = flat[base + j];
    out[i] = row;
  }
  return out;
}

/** Slice a (Nz, Nx, Ny) flat float32 buffer at z index. Returns Nx x Ny 2D array. */
export function slice2DFrom3D(
  flat: Float32Array,
  shape: number[],
  zIndex: number
): number[][] {
  const [Nz, Nx, Ny] = shape;
  if (zIndex < 0 || zIndex >= Nz) throw new Error("z index out of range");
  const planeSize = Nx * Ny;
  const view = flat.subarray(zIndex * planeSize, (zIndex + 1) * planeSize);
  return reshape2D(view, Nx, Ny);
}
