export function attachmentFilename(
  contentDisposition: string | null,
  fallback: string,
): string {
  const match = contentDisposition?.match(/filename="([A-Za-z0-9._-]+)"/);
  return match?.[1] ?? fallback;
}

export async function responseErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const payload = await response.json() as { readonly message?: unknown };
    return typeof payload.message === "string" && payload.message !== ""
      ? payload.message
      : fallback;
  } catch {
    return fallback;
  }
}

export function downloadBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
