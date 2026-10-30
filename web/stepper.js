// mm:ss:ms field with per-segment arrow steppers, keyboard and wheel nudging.

import { MS_PER_MINUTE, MS_PER_SECOND, clamp, pad } from "./timecode.js";

const SEGMENTS = [
  { unit: "min", label: "min", step: MS_PER_MINUTE, digits: 2 },
  { unit: "sec", label: "sec", step: MS_PER_SECOND, digits: 2 },
  { unit: "ms", label: "ms", step: 1, digits: 3 },
];

const SHIFT_MULTIPLIER = 10;
const CTRL_MULTIPLIER = 100;
const REPEAT_DELAY_MS = 380;
const REPEAT_INTERVAL_MS = 55;

/** A three segment timecode input bound to a millisecond value. */
export class TimecodeField {
  /**
   * @param {HTMLElement} root container that receives the generated markup
   * @param {(valueMs: number) => void} onChange called whenever the value changes
   */
  constructor(root, onChange) {
    this.root = root;
    this.onChange = onChange;
    this.valueMs = 0;
    this.minMs = 0;
    this.maxMs = 0;
    /** @type {Map<string, HTMLInputElement>} */
    this.inputs = new Map();
    this.#build();
  }

  /**
   * Set the allowed range, re-clamping the current value.
   * @param {number} minMs
   * @param {number} maxMs
   */
  setRange(minMs, maxMs) {
    this.minMs = minMs;
    this.maxMs = Math.max(minMs, maxMs);
    this.set(this.valueMs, false);
  }

  /**
   * Update the value, optionally notifying listeners.
   * @param {number} valueMs
   * @param {boolean} notify
   */
  set(valueMs, notify = true) {
    const next = clamp(Math.round(valueMs), this.minMs, this.maxMs);
    const changed = next !== this.valueMs;
    this.valueMs = next;
    this.#render();
    if (notify && changed) this.onChange(next);
  }

  /**
   * Add a signed delta to the value.
   * @param {number} deltaMs
   */
  nudge(deltaMs) {
    this.set(this.valueMs + deltaMs);
  }

  #build() {
    SEGMENTS.forEach((segment, index) => {
      if (index > 0) this.root.appendChild(colon());
      this.root.appendChild(this.#buildSegment(segment));
    });
    this.#render();
  }

  /**
   * @param {{unit:string,label:string,step:number,digits:number}} segment
   * @returns {HTMLElement}
   */
  #buildSegment(segment) {
    const cell = document.createElement("div");
    cell.className = "tc-seg";

    const input = document.createElement("input");
    input.className = "tc-input";
    input.type = "text";
    input.inputMode = "numeric";
    input.maxLength = segment.digits;
    input.setAttribute("aria-label", segment.label);
    input.dataset.unit = segment.unit;

    const unitLabel = document.createElement("span");
    unitLabel.className = "tc-unit";
    unitLabel.textContent = segment.label;

    cell.append(
      this.#buildArrow(segment, 1),
      input,
      this.#buildArrow(segment, -1),
      unitLabel,
    );

    input.addEventListener("keydown", (event) => this.#onKeyDown(event, segment));
    input.addEventListener("wheel", (event) => this.#onWheel(event, segment), { passive: false });
    input.addEventListener("input", () => this.#onType());
    input.addEventListener("blur", () => this.#render());
    input.addEventListener("focus", () => input.select());

    this.inputs.set(segment.unit, input);
    return cell;
  }

  /**
   * @param {{step:number,label:string}} segment
   * @param {1|-1} direction
   * @returns {HTMLButtonElement}
   */
  #buildArrow(segment, direction) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tc-arrow";
    button.tabIndex = -1;
    button.textContent = direction > 0 ? "▲" : "▼";
    button.setAttribute(
      "aria-label",
      `${direction > 0 ? "Increase" : "Decrease"} ${segment.label}`,
    );
    attachRepeat(button, (event) => {
      this.nudge(direction * segment.step * multiplierFor(event));
    });
    return button;
  }

  /**
   * @param {KeyboardEvent} event
   * @param {{step:number}} segment
   */
  #onKeyDown(event, segment) {
    const direction = event.key === "ArrowUp" ? 1 : event.key === "ArrowDown" ? -1 : 0;
    if (direction === 0) return;
    event.preventDefault();
    this.nudge(direction * segment.step * multiplierFor(event));
  }

  /**
   * @param {WheelEvent} event
   * @param {{step:number}} segment
   */
  #onWheel(event, segment) {
    if (document.activeElement !== event.currentTarget) return;
    event.preventDefault();
    const direction = event.deltaY < 0 ? 1 : -1;
    this.nudge(direction * segment.step * multiplierFor(event));
  }

  /** Recompute the value from the three raw fields while typing. */
  #onType() {
    const minutes = readInt(this.inputs.get("min"));
    const seconds = readInt(this.inputs.get("sec"));
    const millis = readInt(this.inputs.get("ms"));
    this.set(minutes * MS_PER_MINUTE + seconds * MS_PER_SECOND + millis);
  }

  /** Paint the current value back into the segment inputs. */
  #render() {
    const minutes = Math.floor(this.valueMs / MS_PER_MINUTE);
    const seconds = Math.floor((this.valueMs % MS_PER_MINUTE) / MS_PER_SECOND);
    const millis = this.valueMs % MS_PER_SECOND;
    const values = { min: pad(minutes, 2), sec: pad(seconds, 2), ms: pad(millis, 3) };
    for (const [unit, input] of this.inputs) {
      if (document.activeElement !== input || input.value !== values[unit]) {
        input.value = values[unit];
      }
    }
  }
}

/**
 * Resolve the modifier driven step multiplier.
 * @param {KeyboardEvent|MouseEvent|WheelEvent} event
 * @returns {number}
 */
function multiplierFor(event) {
  if (event.ctrlKey || event.metaKey) return CTRL_MULTIPLIER;
  if (event.shiftKey) return SHIFT_MULTIPLIER;
  return 1;
}

/**
 * Fire ``action`` once on press, then repeatedly while the button is held.
 * @param {HTMLElement} button
 * @param {(event: PointerEvent) => void} action
 */
function attachRepeat(button, action) {
  /** @type {number|undefined} */
  let delayTimer;
  /** @type {number|undefined} */
  let repeatTimer;

  const stop = () => {
    window.clearTimeout(delayTimer);
    window.clearInterval(repeatTimer);
  };

  button.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    action(event);
    delayTimer = window.setTimeout(() => {
      repeatTimer = window.setInterval(() => action(event), REPEAT_INTERVAL_MS);
    }, REPEAT_DELAY_MS);
  });

  for (const name of ["pointerup", "pointerleave", "pointercancel", "blur"]) {
    button.addEventListener(name, stop);
  }
}

/**
 * Read an input as a non-negative integer.
 * @param {HTMLInputElement|undefined} input
 * @returns {number}
 */
function readInt(input) {
  const parsed = Number.parseInt(input?.value ?? "", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

/** @returns {HTMLElement} */
function colon() {
  const span = document.createElement("span");
  span.className = "tc-colon";
  span.textContent = ":";
  return span;
}
