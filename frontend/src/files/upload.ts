/**
 * Browser upload of one file (A-06-T03 flow): start → send straight to the bucket with the
 * presigned POST form (XHR, so progress can be shown) → finalize. Checks name and size first
 * (the API checks them again, and the content after the upload).
 */
import {
  ACCEPTED_EXTENSIONS,
  extensionOf,
  filesApi,
  MAX_FILE_SIZE,
  type FileDocument,
} from "./api";

export type UploadState =
  | { kind: "refused"; reason: "size" | "type" }
  | { kind: "uploading"; percent: number }
  | { kind: "checking" }
  | { kind: "done"; document: FileDocument; duplicate: boolean }
  | { kind: "failed"; message: string };

export function precheck(file: File): UploadState | null {
  if (!ACCEPTED_EXTENSIONS.includes(extensionOf(file.name)))
    return { kind: "refused", reason: "type" };
  if (file.size > MAX_FILE_SIZE) return { kind: "refused", reason: "size" };
  return null;
}

/** POST the form + file to the bucket; resolves with the HTTP status (0 on network failure). */
export function sendToBucket(
  form: { url: string; fields: Record<string, string> },
  file: File,
  onProgress: (percent: number) => void,
): Promise<number> {
  return new Promise((resolve) => {
    const body = new FormData();
    for (const [key, value] of Object.entries(form.fields)) body.append(key, value);
    body.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", form.url);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => resolve(xhr.status);
    xhr.onerror = () => resolve(0);
    xhr.send(body);
  });
}

export async function uploadFile(
  org: string,
  file: File,
  onState: (state: UploadState) => void,
): Promise<UploadState> {
  const report = (state: UploadState) => {
    onState(state);
    return state;
  };
  const refused = precheck(file);
  if (refused) return report(refused);
  report({ kind: "uploading", percent: 0 });
  const started = await filesApi.startUpload(org, file.name, file.size);
  if (started.status !== 201 || !started.body.upload) {
    return report({ kind: "failed", message: started.body.detail ?? "" });
  }
  const sent = await sendToBucket(started.body.upload, file, (percent) =>
    onState({ kind: "uploading", percent }),
  );
  if (sent < 200 || sent >= 300) return report({ kind: "failed", message: "" });
  report({ kind: "checking" });
  const finalized = await filesApi.finalize(org, started.body.document.id);
  if (finalized.status !== 200)
    return report({ kind: "failed", message: finalized.body.detail ?? "" });
  const { duplicate, ...document } = finalized.body;
  return report({
    kind: "done",
    document: document as FileDocument,
    duplicate: Boolean(duplicate),
  });
}
