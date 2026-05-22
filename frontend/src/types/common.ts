export interface EncodedArray {
  shape: number[];
  dtype: "float32" | "complex64";
  data: string; // base64
}
