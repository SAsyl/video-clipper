// Stepper widget behaviour tests. Requires jsdom: npm install jsdom

import { JSDOM } from "jsdom";
import { readFileSync } from "node:fs";

const WEB = new URL("../web/", import.meta.url).pathname;
const dom = new JSDOM(readFileSync(`${WEB}index.html`, "utf8"), { url: "http://localhost/" });

// Expose the DOM globals the module expects.
for (const key of ["window", "document", "HTMLElement", "Event", "KeyboardEvent", "MouseEvent"]) {
  globalThis[key] = key === "window" ? dom.window : dom.window[key];
}

const { TimecodeField } = await import(`${WEB}stepper.js`);

const root = document.querySelector('.timecode[data-edge="start"]');
if (!root) throw new Error('selector .timecode[data-edge="start"] did not resolve');
console.log("selector .timecode[data-edge=start] resolves ->", root.tagName);

const seen = [];
const field = new TimecodeField(root, (ms) => seen.push(ms));
field.setRange(0, 510747); // duration of the test video

const read = () => [...root.querySelectorAll(".tc-input")].map((i) => i.value).join(":");
const arrows = (unit) => {
  const cell = [...root.querySelectorAll(".tc-seg")].find(
    (c) => c.querySelector(".tc-input").dataset.unit === unit,
  );
  const [up, down] = cell.querySelectorAll(".tc-arrow");
  return { up, down };
};
const click = (btn, mods = {}) =>
  btn.dispatchEvent(new dom.window.MouseEvent("pointerdown", { bubbles: true, cancelable: true, ...mods }));

const checks = [];
const check = (label, got, want) => {
  checks.push(got === want);
  console.log(`${got === want ? "PASS" : "FAIL"}  ${label}: ${got}${got === want ? "" : ` (want ${want})`}`);
};

check("initial render", read(), "00:00:000");

// Three segments with up/down arrows each.
check("segments built", root.querySelectorAll(".tc-seg").length, 3);
check("arrows built", root.querySelectorAll(".tc-arrow").length, 6);

// Millisecond arrows.
click(arrows("ms").up);
check("ms +1", read(), "00:00:001");
click(arrows("ms").up, { shiftKey: true });
check("ms +10 (shift)", read(), "00:00:011");
click(arrows("ms").up, { ctrlKey: true });
check("ms +100 (ctrl)", read(), "00:00:111");

// Clamp at the lower bound instead of going negative.
field.set(0, false);
click(arrows("ms").down);
check("clamped at zero", read(), "00:00:000");

// Borrow across the second boundary.
field.set(5000, false);
click(arrows("ms").down);
check("5.000s minus 1ms borrows", read(), "00:04:999");

// Carry across the second boundary.
field.set(4999, false);
click(arrows("ms").up);
check("4.999s plus 1ms carries", read(), "00:05:000");

// Carry across the minute boundary.
field.set(59999, false);
click(arrows("ms").up);
check("59.999s plus 1ms carries to minute", read(), "01:00:000");

// Second and minute arrows.
click(arrows("sec").up);
check("sec +1", read(), "01:01:000");
click(arrows("min").up);
check("min +1", read(), "02:01:000");
click(arrows("min").down);
check("min -1", read(), "01:01:000");

// Keyboard nudging on the focused segment.
const msInput = [...root.querySelectorAll(".tc-input")].find((i) => i.dataset.unit === "ms");
msInput.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true, cancelable: true }));
check("ArrowUp on ms field", read(), "01:01:001");
msInput.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true, cancelable: true, shiftKey: true }));
check("Shift+ArrowDown on ms field", read(), "01:00:991");

// Upper bound clamp.
field.set(999999999, false);
check("clamped to duration", read(), "08:30:747");

// Callback fired on every real change.
check("onChange fired", seen.length > 0, true);

console.log(`\n${checks.filter(Boolean).length}/${checks.length} checks passed`);
process.exit(checks.every(Boolean) ? 0 : 1);
