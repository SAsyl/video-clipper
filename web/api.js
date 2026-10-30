// Thin fetch wrapper plus job polling.

const POLL_INTERVAL_MS = 400;

/**
 * @typedef {{id:string,kind:string,state:string,progress:number,message:string,
 *   source:SourceInfo|null,clip:ClipInfo|null,error:string|null}} JobStatus
 * @typedef {{id:string,title:string,duration_ms:number,width:number,height:number,
 *   fps:number,size_bytes:number,media_url:string}} SourceInfo
 * @typedef {{name:string,start_ms:number,end_ms:number,duration_ms:number,
 *   size_bytes:number,media_url:string,download_url:string}} ClipInfo
 */

/**
 * POST a JSON body and return the parsed response.
 * @param {string} path
 * @param {unknown} body
 * @returns {Promise<JobStatus>}
 */
export async function postJson(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJson(response);
}

/**
 * GET and return the parsed response.
 * @param {string} path
 * @returns {Promise<JobStatus>}
 */
export async function getJson(path) {
  return readJson(await fetch(path));
}

/**
 * Poll a job until it finishes, reporting intermediate states.
 * @param {string} jobId
 * @param {(job: JobStatus) => void} onUpdate
 * @returns {Promise<JobStatus>}
 */
export async function pollJob(jobId, onUpdate) {
  for (;;) {
    const job = await getJson(`/api/jobs/${jobId}`);
    onUpdate(job);
    if (job.state === "done") return job;
    if (job.state === "failed") throw new Error(job.error ?? "Job failed");
    await delay(POLL_INTERVAL_MS);
  }
}

/**
 * Parse a response, raising the server supplied error message on failure.
 * @param {Response} response
 * @returns {Promise<JobStatus>}
 */
async function readJson(response) {
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new Error(describeError(payload, response.status));
  return payload;
}

/**
 * Upload a file, reporting progress. XHR is used because fetch cannot
 * report upload progress for large bodies.
 * @param {string} path
 * @param {File} file
 * @param {(fraction: number) => void} onProgress
 * @returns {Promise<JobStatus>}
 */
export function uploadFile(path, file, onProgress) {
  return new Promise((resolve, reject) => {
    const body = new FormData();
    body.append("file", file, file.name);

    const request = new XMLHttpRequest();
    request.open("POST", path);
    request.responseType = "json";
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    });
    request.addEventListener("load", () => {
      if (request.status >= 200 && request.status < 300) resolve(request.response);
      else reject(new Error(describeError(request.response, request.status)));
    });
    request.addEventListener("error", () => reject(new Error("Upload failed, connection lost")));
    request.addEventListener("abort", () => reject(new Error("Upload cancelled")));
    request.send(body);
  });
}

/**
 * Turn an error payload into a readable message.
 * @param {any} payload
 * @param {number} status
 * @returns {string}
 */
function describeError(payload, status) {
  if (typeof payload?.error === "string") return payload.error;
  const detail = payload?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => item?.msg).filter(Boolean);
    if (messages.length) return messages.join("; ");
  }
  return `Request failed (${status})`;
}

/**
 * @param {number} ms
 * @returns {Promise<void>}
 */
function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
