# Video Clipper

A local web app: paste a video link, preview it, set `mm:ss:ms` in/out points with
arrow steppers, and export the clip. Wraps `yt-dlp` and `ffmpeg`.

## Requirements

- `ffmpeg` and `ffprobe` on `PATH`
- [`uv`](https://docs.astral.sh/uv/) (provisions Python 3.12 itself)

## Run

```bash
./run.sh
```

Then open <http://127.0.0.1:8420>.

## Workflow

1. **Source** — either:
   - paste a link, pick a max height, press *Download*. The format selector prefers
     H.264/AAC so the browser can preview the file directly; or
   - **drag a video file anywhere onto the page** (or click the drop zone to browse) to
     import a file you already have, skipping the download entirely.
2. **Trim** — scrub the preview, then set the in/out points:
   - click **▲▼** next to any segment, or focus a segment and use <kbd>↑</kbd>/<kbd>↓</kbd>
   - hold <kbd>Shift</kbd> for ×10 and <kbd>Ctrl</kbd> for ×100 (so ±10 ms / ±100 ms)
   - hold an arrow down to repeat
   - segments carry and borrow: `00:05:000` − 1 ms becomes `00:04:999`
   - drag the timeline handles, or press <kbd>I</kbd>/<kbd>O</kbd> to capture the playhead
3. **Result** — preview the clip and save it.

### Keyboard

| Key | Action |
| --- | --- |
| <kbd>Space</kbd> | play / pause |
| <kbd>I</kbd> / <kbd>O</kbd> | set start / end from playhead |
| <kbd>,</kbd> / <kbd>.</kbd> | step one frame back / forward |
| <kbd>↑</kbd> / <kbd>↓</kbd> | nudge the focused timecode segment |

## Cut modes

| Mode | ffmpeg | Accuracy | Speed |
| --- | --- | --- | --- |
| **Precise** | `libx264` + `aac` re-encode | frame exact at the requested timecode | slower |
| **Fast** | `-c copy` | start snaps to the nearest preceding keyframe | near instant |

Durations land on frame and audio-sample boundaries, so a precise clip can differ from the
requested length by under one frame (e.g. 17850 ms requested → 17852 ms written). A fast clip
can differ by seconds, because stream copy cannot cut mid-GOP.

## Importing local files

Dropping a file copies it into `media/source/`, because browsers never expose a local file's
real path to a page. A 619 MB file imports in about two seconds over loopback; the upload is
streamed to disk in 1 MB chunks, so file size does not drive memory use.

Containers accepted: `.mp4 .webm .mkv .mov .m4v .avi .ts .flv .mpg .mpeg .wmv`. Anything else
is rejected with `415`, as is a file whose extension lies about its contents — ffprobe has to
read it first, and a rejected file is deleted rather than left behind.

The source id comes from the filename, reduced to `[A-Za-z0-9_-]`. A name that survives none
of that (for example, one written entirely in Cyrillic) becomes `upload`, `upload-2`, and so
on — the original name is still shown in the editor and used as the title. Imports never
overwrite an existing source; a repeated name gains a `-2` suffix.

If the preview stays blank, your browser cannot decode that codec (common for HEVC or some
MKVs). Trimming still works — set the range with the timecode fields.

## Layout

```
app/
  main.py        FastAPI routes
  models.py      request/response schemas and validation
  jobs.py        in-memory job registry, worker threads
  downloader.py  yt-dlp wrapper
  cutter.py      ffmpeg wrapper with progress parsing
  uploads.py     drag and drop import, filename sanitisation
  probe.py       ffprobe inspection
  sources.py     shared source description
  storage.py     path resolution and identifier validation
  streaming.py   HTTP Range responses so the preview can seek
  timecode.py    mm:ss:ms conversions
web/
  index.html  styles.css  app.js  stepper.js  timecode.js  api.js
media/        downloaded sources and generated clips (gitignored)
```

Downloads land in `media/source/`, clips in `media/clips/`. Clip filenames encode the
selection (`<id>-<start_ms>-<end_ms>-<mode>.mp4`), so re-cutting the same range overwrites
rather than piling up. Reopen a source already on disk with `#source=<id>` in the page URL.

## Tests

```bash
uv run --group dev pytest          # timecode math, validation, ffmpeg command construction
npm install && npm test            # stepper arrows, carry/borrow, clamping (jsdom)
```

## Notes

- yt-dlp warns `No supported JavaScript runtime could be found` on YouTube. It still works;
  installing `deno` removes the warning and exposes a few extra formats.
- yt-dlp requires Python 3.11+. `run.sh` pins 3.12 through `uv`, so a system Python 3.10
  does not matter.
