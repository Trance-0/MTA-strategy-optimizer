/**
 * Provide byte-range serving for repository research PDFs during local
 * VitePress development without exposing files outside docs/research.
 */

import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { dirname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const documentationRoot = resolve(scriptDirectory, "..", "docs");
const researchRoot = resolve(documentationRoot, "research");
const researchPrefix = `${researchRoot}${sep}`;

export function researchPdfDevPlugin() {
  return {
    name: "marketing-roi-research-pdf-dev-server",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        let pathname;
        try {
          pathname = decodeURIComponent(
            new URL(request.url ?? "/", "http://documentation.local").pathname,
          );
        } catch {
          next();
          return;
        }
        if (!pathname.toLowerCase().endsWith(".pdf")) {
          next();
          return;
        }

        const sourcePath = resolve(documentationRoot, `.${pathname}`);
        if (!sourcePath.startsWith(researchPrefix)) {
          next();
          return;
        }
        try {
          const fileStatus = await stat(sourcePath);
          if (!fileStatus.isFile()) {
            next();
            return;
          }
          const method = request.method ?? "GET";
          const rangeMatch = request.headers.range?.match(/^bytes=(\d*)-(\d*)$/);
          let start = 0;
          let end = fileStatus.size - 1;
          if (rangeMatch) {
            start = rangeMatch[1] ? Number(rangeMatch[1]) : start;
            end = rangeMatch[2] ? Number(rangeMatch[2]) : end;
            if (start > end || end >= fileStatus.size) {
              response.statusCode = 416;
              response.setHeader("Content-Range", `bytes */${fileStatus.size}`);
              response.end();
              return;
            }
            response.statusCode = 206;
            response.setHeader("Content-Range", `bytes ${start}-${end}/${fileStatus.size}`);
          } else {
            response.statusCode = 200;
          }
          response.setHeader("Content-Type", "application/pdf");
          response.setHeader("Accept-Ranges", "bytes");
          response.setHeader("Content-Length", end - start + 1);
          response.setHeader("Content-Disposition", "inline");
          if (method === "HEAD") {
            response.end();
            return;
          }
          createReadStream(sourcePath, { start, end }).pipe(response);
        } catch {
          next();
        }
      });
    },
  };
}
