const DEFAULT_MAX_BYTES = 256 * 1024;

/**
 * @param {{ ok: boolean; result?: unknown; error?: unknown; blocked?: boolean; decision?: unknown }} value
 * @param {{ maxBytes?: number }} options
 */
export function serializeToolResult(value, options = {}) {
  const json = JSON.stringify(value, null, 2);
  const originalBytes = Buffer.byteLength(json, "utf8");
  const maxBytes = positiveInteger(options.maxBytes, DEFAULT_MAX_BYTES);

  if (originalBytes <= maxBytes) {
    return {
      content: json,
      bytes: originalBytes,
      originalBytes,
      omittedBytes: 0,
      truncated: false
    };
  }

  const marker = `\n...[tool result truncated: ${originalBytes} original bytes]`;
  const markerBytes = Buffer.byteLength(marker, "utf8");
  if (markerBytes >= maxBytes) {
    const content = truncateUtf8(marker.trimStart(), maxBytes);
    return {
      content,
      bytes: Buffer.byteLength(content, "utf8"),
      originalBytes,
      omittedBytes: originalBytes,
      truncated: true
    };
  }
  const preview = truncateUtf8(json, Math.max(0, maxBytes - markerBytes));
  const content = `${preview}${marker}`;
  const bytes = Buffer.byteLength(content, "utf8");

  return {
    content,
    bytes,
    originalBytes,
    omittedBytes: Math.max(0, originalBytes - Buffer.byteLength(preview, "utf8")),
    truncated: true
  };
}

function positiveInteger(value, fallback) {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : fallback;
}

function truncateUtf8(value, maxBytes) {
  if (maxBytes <= 0) {
    return "";
  }
  const buffer = Buffer.from(String(value ?? ""), "utf8");
  if (buffer.length <= maxBytes) {
    return buffer.toString("utf8");
  }
  let end = maxBytes;
  let text = buffer.subarray(0, end).toString("utf8");
  while (text.endsWith("\uFFFD") && end > 0) {
    end -= 1;
    text = buffer.subarray(0, end).toString("utf8");
  }
  return text;
}
