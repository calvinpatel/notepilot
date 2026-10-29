/** A claim's source span (§9.10), cut from the text that was sent. */
export interface Segments {
  readonly before: string;
  readonly marked: string;
  readonly after: string;
}

/**
 * The text's code points. Python indexes strings by code point, and `source_span` is a
 * Python index (L177); `String.prototype.slice` counts UTF-16 units, so every character
 * past the BMP before a span would shift it by one.
 */
export function codePoints(text: string): readonly string[] {
  return [...text];
}

/**
 * The span's three parts, or null when the span doesn't fit the text: a caller then marks
 * nothing rather than the wrong characters.
 */
export function segments(
  points: readonly string[],
  span: readonly [number, number],
): Segments | null {
  const [start, end] = span;
  if (!Number.isInteger(start) || !Number.isInteger(end)) {
    return null;
  }
  if (start < 0 || start > end || end > points.length) {
    return null;
  }
  return {
    before: points.slice(0, start).join(""),
    marked: points.slice(start, end).join(""),
    after: points.slice(end).join(""),
  };
}
