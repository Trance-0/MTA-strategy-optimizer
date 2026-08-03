import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { dirname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const documentationRoot = resolve(scriptDirectory, "..");
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
          response.statusCode = 200;
          response.setHeader("Content-Type", "application/pdf");
          response.setHeader("Content-Length", fileStatus.size);
          response.setHeader("Content-Disposition", "inline");
          createReadStream(sourcePath).pipe(response);
        } catch {
          next();
        }
      });
    },
  };
}
