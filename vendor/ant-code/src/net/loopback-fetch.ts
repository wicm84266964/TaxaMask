import http from "node:http";
import { Readable } from "node:stream";

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

export function loopbackProxyUrl(env: NodeJS.ProcessEnv = process.env) {
  return String(env.TAXAMASK_WSL_LOOPBACK_PROXY ?? "").trim();
}

export function isLoopbackGatewayUrl(value: string) {
  try {
    return LOOPBACK_HOSTS.has(new URL(value).hostname.toLowerCase());
  } catch {
    return false;
  }
}

export function gatewayConnectError(url: string, env: NodeJS.ProcessEnv = process.env) {
  if (!isLoopbackGatewayUrl(url) || !env.WSL_DISTRO_NAME) {
    return "无法连接模型来源";
  }
  if (loopbackProxyUrl(env)) {
    return "无法连接模型来源。内嵌智能体在 WSL 中运行，Windows 本机回环转发没有连上这个网关。";
  }
  return "无法连接模型来源。内嵌智能体在 WSL 中运行，127.0.0.1 指向 Linux，到不了 Windows 上的本地网关。请重启 TaxaMask 后再试。";
}

export async function fetchGateway(url: string | URL, init: RequestInit = {}, env: NodeJS.ProcessEnv = process.env) {
  const href = typeof url === "string" ? url : url.href;
  const proxyUrl = isLoopbackGatewayUrl(href) ? loopbackProxyUrl(env) : "";
  if (!proxyUrl) {
    return fetch(url, init);
  }
  return fetchThroughLoopbackProxy(href, init, proxyUrl);
}

function fetchThroughLoopbackProxy(target: string, init: RequestInit, proxyUrl: string) {
  const proxy = new URL(proxyUrl);
  const headers = new Headers(init.headers ?? {});
  if (!headers.has("host")) {
    headers.set("host", new URL(target).host);
  }
  const body = init.body == null ? null : Buffer.from(typeof init.body === "string" ? init.body : init.body as Uint8Array);
  if (body && !headers.has("content-length")) {
    headers.set("content-length", String(body.length));
  }
  return new Promise<Response>((resolve, reject) => {
    const request = http.request({
      protocol: proxy.protocol,
      hostname: proxy.hostname,
      port: proxy.port,
      method: init.method || "GET",
      path: target,
      headers: Object.fromEntries(headers.entries()),
      signal: init.signal ?? undefined
    });
    request.once("error", reject);
    request.once("response", (incoming) => {
      const responseHeaders = new Headers();
      for (const [key, value] of Object.entries(incoming.headers)) {
        if (value == null) continue;
        responseHeaders.set(key, Array.isArray(value) ? value.join(", ") : value);
      }
      const stream = Readable.toWeb(incoming) as ReadableStream<Uint8Array>;
      resolve(new Response(stream, {
        status: incoming.statusCode ?? 502,
        statusText: incoming.statusMessage,
        headers: responseHeaders
      }));
    });
    request.end(body ?? undefined);
  });
}
