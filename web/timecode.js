// Shared mm:ss:ms timecode helpers.

export const MS_PER_SECOND = 1000;
export const MS_PER_MINUTE = 60000;

/**
 * Render milliseconds as mm:ss:ms.
 * @param {number} totalMs
 * @returns {string}
 */
export function formatTimecode(totalMs) {
  const safe = Math.max(0, Math.round(totalMs));
  const minutes = Math.floor(safe / MS_PER_MINUTE);
  const seconds = Math.floor((safe % MS_PER_MINUTE) / MS_PER_SECOND);
  const millis = safe % MS_PER_SECOND;
  return `${pad(minutes, 2)}:${pad(seconds, 2)}:${pad(millis, 3)}`;
}

/**
 * Left-pad a number with zeroes.
 * @param {number} value
 * @param {number} width
 * @returns {string}
 */
export function pad(value, width) {
  return String(value).padStart(width, "0");
}

/**
 * Clamp a value into an inclusive range.
 * @param {number} value
 * @param {number} min
 * @param {number} max
 * @returns {number}
 */
export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

/**
 * Human readable byte size.
 * @param {number} bytes
 * @returns {string}
 */
export function formatBytes(bytes) {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 && unit > 0 ? 1 : 0)} ${units[unit]}`;
}
