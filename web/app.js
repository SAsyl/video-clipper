// Wires the download form, preview player, trim controls and cut action together.

import { getJson, pollJob, postJson, uploadFile } from "./api.js";
import { TimecodeField } from "./stepper.js";
import { clamp, formatBytes, formatTimecode } from "./timecode.js";

const MIN_CLIP_MS = 1;
const SEEK_EPSILON_MS = 2;

const dom = {
  downloadForm: query("#download-form"),
  url: query("#url"),
  quality: query("#quality"),
  downloadBtn: query("#download-btn"),
  downloadProgress: query("#download-progress"),
  downloadError: query("#download-error"),
  dropzone: query("#dropzone"),
  fileInput: query("#file-input"),
  previewWarning: query("#preview-warning"),
  editor: query("#card-editor"),
  sourceTitle: query("#source-title"),
  sourceMeta: query("#source-meta"),
  preview: query("#preview"),
  playBtn: query("#play-btn"),
  frameBack: query("#frame-back"),
  frameFwd: query("#frame-fwd"),
  playhead: query("#playhead"),
  loopBtn: query("#loop-btn"),
  timeline: query("#timeline"),
  timelineTrack: query(".timeline-track"),
  timelineSelection: query("#timeline-selection"),
  timelinePlayhead: query("#timeline-playhead"),
  handleStart: query("#handle-start"),
  handleEnd: query("#handle-end"),
  durationReadout: query("#duration-readout"),
  cutBtn: query("#cut-btn"),
  cutProgress: query("#cut-progress"),
  cutError: query("#cut-error"),
  result: query("#card-result"),
  clipMeta: query("#clip-meta"),
  clipPreview: query("#clip-preview"),
  clipDownload: query("#clip-download"),
};

const state = {
  /** @type {import("./api.js").SourceInfo|null} */
  source: null,
  startMs: 0,
  endMs: 0,
  loop: false,
  busy: false,
};

const fields = {
  start: new TimecodeField(query('.timecode[data-edge="start"]'), (ms) => setEdge("start", ms)),
  end: new TimecodeField(query('.timecode[data-edge="end"]'), (ms) => setEdge("end", ms)),
};

/* ---------- source download ---------- */

dom.downloadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.busy) return;
  state.busy = true;
  hide(dom.downloadError);
  setBusy(dom.downloadBtn, true, "Downloading...");
  show(dom.downloadProgress);
  updateProgress(dom.downloadProgress, 0, "Queued");

  try {
    const queued = await postJson("/api/download", {
      url: dom.url.value.trim(),
      max_height: Number(dom.quality.value),
    });
    const finished = await pollJob(queued.id, (job) =>
      updateProgress(dom.downloadProgress, job.progress, job.message),
    );
    if (!finished.source) throw new Error("Server returned no source information");
    loadSource(finished.source);
  } catch (error) {
    fail(dom.downloadError, error);
  } finally {
    state.busy = false;
    setBusy(dom.downloadBtn, false, "Download");
  }
});

/* ---------- local file import ---------- */

dom.fileInput.addEventListener("change", () => {
  const [file] = dom.fileInput.files ?? [];
  if (file) void importFile(file);
  // Clear the value so re-picking the same file fires change again.
  dom.fileInput.value = "";
});

let dragDepth = 0;

window.addEventListener("dragenter", (event) => {
  if (!carriesFiles(event)) return;
  dragDepth += 1;
  dom.dropzone.classList.add("is-armed");
});

window.addEventListener("dragover", (event) => {
  if (carriesFiles(event)) event.preventDefault();
});

window.addEventListener("dragleave", () => {
  dragDepth = Math.max(0, dragDepth - 1);
  if (dragDepth === 0) clearDragState();
});

window.addEventListener("drop", (event) => {
  if (!carriesFiles(event)) return;
  event.preventDefault();
  dragDepth = 0;
  clearDragState();
  const [file] = event.dataTransfer?.files ?? [];
  if (file) void importFile(file);
});

dom.dropzone.addEventListener("dragover", (event) => {
  if (!carriesFiles(event)) return;
  event.preventDefault();
  dom.dropzone.classList.add("is-over");
});

dom.dropzone.addEventListener("dragleave", () => dom.dropzone.classList.remove("is-over"));

/**
 * Upload a local file and open it in the editor.
 * @param {File} file
 */
async function importFile(file) {
  if (state.busy) return;
  state.busy = true;
  hide(dom.downloadError);
  setBusy(dom.downloadBtn, true, "Importing...");
  show(dom.downloadProgress);
  updateProgress(dom.downloadProgress, 0, `Reading ${file.name}`);

  try {
    const job = await uploadFile("/api/upload", file, (fraction) =>
      updateProgress(dom.downloadProgress, fraction, `Importing ${file.name}`),
    );
    updateProgress(dom.downloadProgress, 1, "Ready");
    if (!job.source) throw new Error("Server returned no source information");
    loadSource(job.source);
  } catch (error) {
    fail(dom.downloadError, error);
    hide(dom.downloadProgress);
  } finally {
    state.busy = false;
    setBusy(dom.downloadBtn, false, "Download");
  }
}

/**
 * True when a drag event carries files rather than text or page elements.
 * @param {DragEvent} event
 * @returns {boolean}
 */
function carriesFiles(event) {
  return [...(event.dataTransfer?.types ?? [])].includes("Files");
}

/** Drop every drag highlight. */
function clearDragState() {
  dom.dropzone.classList.remove("is-armed", "is-over");
}

/**
 * Attach a downloaded source to the editor.
 * @param {import("./api.js").SourceInfo} source
 */
function loadSource(source) {
  state.source = source;
  dom.preview.src = source.media_url;
  dom.sourceTitle.textContent = source.title;
  dom.sourceTitle.title = source.title;
  dom.sourceMeta.textContent =
    `${source.width}x${source.height} - ${source.fps.toFixed(2)} fps - ` +
    `${formatTimecode(source.duration_ms)} - ${formatBytes(source.size_bytes)}`;

  fields.start.setRange(0, Math.max(source.duration_ms - MIN_CLIP_MS, 0));
  fields.end.setRange(MIN_CLIP_MS, source.duration_ms);
  state.startMs = 0;
  state.endMs = source.duration_ms;
  fields.start.set(state.startMs, false);
  fields.end.set(state.endMs, false);

  hide(dom.previewWarning);
  show(dom.editor);
  hide(dom.result);
  renderSelection();
  dom.editor.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- selection ---------- */

/**
 * Move one edge of the selection, keeping start strictly before end.
 * @param {"start"|"end"} edge
 * @param {number} valueMs
 */
function setEdge(edge, valueMs) {
  if (!state.source) return;
  if (edge === "start") {
    state.startMs = Math.min(valueMs, state.endMs - MIN_CLIP_MS);
    if (state.startMs !== valueMs) fields.start.set(state.startMs, false);
  } else {
    state.endMs = Math.max(valueMs, state.startMs + MIN_CLIP_MS);
    if (state.endMs !== valueMs) fields.end.set(state.endMs, false);
  }
  seekTo(edge === "start" ? state.startMs : state.endMs);
  renderSelection();
}

/** Repaint the timeline and the length readout. */
function renderSelection() {
  if (!state.source) return;
  const total = state.source.duration_ms || 1;
  const left = (state.startMs / total) * 100;
  const width = ((state.endMs - state.startMs) / total) * 100;
  dom.timelineSelection.style.left = `${left}%`;
  dom.timelineSelection.style.width = `${width}%`;
  dom.handleStart.style.left = `${left}%`;
  dom.handleEnd.style.left = `${left + width}%`;
  dom.durationReadout.textContent = formatTimecode(state.endMs - state.startMs);
}

/* ---------- player ---------- */

/**
 * Seek the preview, avoiding redundant jumps.
 * @param {number} ms
 */
function seekTo(ms) {
  const target = ms / 1000;
  if (Math.abs(dom.preview.currentTime - target) * 1000 > SEEK_EPSILON_MS) {
    dom.preview.currentTime = target;
  }
}

dom.playBtn.addEventListener("click", togglePlay);
dom.frameBack.addEventListener("click", () => stepFrames(-1));
dom.frameFwd.addEventListener("click", () => stepFrames(1));

dom.loopBtn.addEventListener("click", () => {
  state.loop = !state.loop;
  dom.loopBtn.classList.toggle("is-active", state.loop);
  if (state.loop) {
    seekTo(state.startMs);
    void dom.preview.play();
  }
});

dom.preview.addEventListener("play", () => (dom.playBtn.textContent = "⏸ Pause"));
dom.preview.addEventListener("pause", () => (dom.playBtn.textContent = "▶ Play"));
dom.preview.addEventListener("timeupdate", onTimeUpdate);
dom.preview.addEventListener("seeked", renderPlayhead);
dom.preview.addEventListener("error", () => show(dom.previewWarning));
dom.preview.addEventListener("loadeddata", () => hide(dom.previewWarning));

/** Keep the loop inside the selection and refresh the readouts. */
function onTimeUpdate() {
  if (state.loop && dom.preview.currentTime * 1000 >= state.endMs) {
    seekTo(state.startMs);
  }
  renderPlayhead();
}

/** Repaint the playhead marker and numeric readout. */
function renderPlayhead() {
  const ms = dom.preview.currentTime * 1000;
  dom.playhead.textContent = formatTimecode(ms);
  if (!state.source) return;
  const percent = clamp((ms / (state.source.duration_ms || 1)) * 100, 0, 100);
  dom.timelinePlayhead.style.left = `${percent}%`;
}

/** Toggle playback of the preview. */
function togglePlay() {
  if (dom.preview.paused) void dom.preview.play();
  else dom.preview.pause();
}

/**
 * Nudge the playhead by whole frames.
 * @param {number} frames
 */
function stepFrames(frames) {
  if (!state.source) return;
  const fps = state.source.fps || 25;
  dom.preview.pause();
  const next = dom.preview.currentTime * 1000 + (frames * 1000) / fps;
  dom.preview.currentTime = clamp(next, 0, state.source.duration_ms) / 1000;
}

/* ---------- timeline interaction ---------- */

for (const handle of [dom.handleStart, dom.handleEnd]) {
  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    const edge = /** @type {"start"|"end"} */ (handle.dataset.edge);
    const onMove = (move) => fields[edge].set(msFromClientX(move.clientX));
    const onUp = () => {
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup", onUp);
    };
    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onUp);
  });
}

dom.timelineTrack.addEventListener("pointerdown", (event) => {
  if (event.target !== dom.timelineTrack && event.target !== dom.timelineSelection) return;
  seekTo(msFromClientX(event.clientX));
});

/**
 * Convert a pointer x position into a source timestamp.
 * @param {number} clientX
 * @returns {number}
 */
function msFromClientX(clientX) {
  if (!state.source) return 0;
  const rect = dom.timelineTrack.getBoundingClientRect();
  const ratio = clamp((clientX - rect.left) / rect.width, 0, 1);
  return Math.round(ratio * state.source.duration_ms);
}

/* ---------- playhead capture buttons and shortcuts ---------- */

for (const button of document.querySelectorAll("[data-set-edge]")) {
  button.addEventListener("click", () => {
    const edge = /** @type {"start"|"end"} */ (button.dataset.setEdge);
    fields[edge].set(Math.round(dom.preview.currentTime * 1000));
  });
}

document.addEventListener("keydown", (event) => {
  if (isTyping(event.target) || !state.source) return;
  const actions = {
    " ": togglePlay,
    i: () => fields.start.set(Math.round(dom.preview.currentTime * 1000)),
    o: () => fields.end.set(Math.round(dom.preview.currentTime * 1000)),
    ",": () => stepFrames(-1),
    ".": () => stepFrames(1),
  };
  const action = actions[event.key.toLowerCase()];
  if (!action) return;
  event.preventDefault();
  action();
});

/* ---------- cut ---------- */

dom.cutBtn.addEventListener("click", async () => {
  if (!state.source) return;
  hide(dom.cutError);
  hide(dom.result);
  setBusy(dom.cutBtn, true, "Cutting...");
  show(dom.cutProgress);
  updateProgress(dom.cutProgress, 0, "Queued");

  try {
    const mode = query('input[name="mode"]:checked').value;
    const queued = await postJson("/api/cut", {
      source_id: state.source.id,
      start_ms: state.startMs,
      end_ms: state.endMs,
      mode,
    });
    const finished = await pollJob(queued.id, (job) =>
      updateProgress(dom.cutProgress, job.progress, job.message),
    );
    if (!finished.clip) throw new Error("Server returned no clip information");
    showClip(finished.clip);
  } catch (error) {
    fail(dom.cutError, error);
  } finally {
    setBusy(dom.cutBtn, false, "Cut clip");
  }
});

/**
 * Present a finished clip.
 * @param {import("./api.js").ClipInfo} clip
 */
function showClip(clip) {
  dom.clipPreview.src = clip.media_url;
  dom.clipDownload.href = clip.download_url;
  dom.clipDownload.setAttribute("download", clip.name);
  dom.clipMeta.textContent =
    `${formatTimecode(clip.duration_ms)} - ${formatBytes(clip.size_bytes)} - ${clip.name}`;
  show(dom.result);
  dom.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ---------- deep link ---------- */

void restoreFromHash();

/** Reopen a source already on disk when the page URL carries #source=<id>. */
async function restoreFromHash() {
  const match = /^#source=([A-Za-z0-9_-]+)$/.exec(window.location.hash);
  if (!match) return;
  try {
    const job = await getJson(`/api/sources/${match[1]}`);
    if (job.source) loadSource(job.source);
  } catch {
    // A stale link is not worth surfacing as an error.
  }
}

/* ---------- small DOM helpers ---------- */

/**
 * @param {string} selector
 * @returns {any}
 */
function query(selector) {
  const node = document.querySelector(selector);
  if (node === null) throw new Error(`Missing element for selector ${selector}`);
  return node;
}

/** @param {HTMLElement} node */
function show(node) {
  node.hidden = false;
}

/** @param {HTMLElement} node */
function hide(node) {
  node.hidden = true;
}

/**
 * @param {HTMLButtonElement} button
 * @param {boolean} busy
 * @param {string} label
 */
function setBusy(button, busy, label) {
  button.disabled = busy;
  button.textContent = label;
}

/**
 * @param {HTMLElement} container
 * @param {number} progress
 * @param {string} message
 */
function updateProgress(container, progress, message) {
  container.querySelector(".progress-fill").style.width = `${Math.round(progress * 100)}%`;
  container.querySelector(".progress-label").textContent = message;
}

/**
 * @param {HTMLElement} node
 * @param {unknown} error
 */
function fail(node, error) {
  node.textContent = error instanceof Error ? error.message : String(error);
  show(node);
}

/**
 * @param {EventTarget|null} target
 * @returns {boolean}
 */
function isTyping(target) {
  return target instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}
