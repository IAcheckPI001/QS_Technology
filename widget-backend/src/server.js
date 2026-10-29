import http from 'node:http';
import { pathToFileURL } from 'node:url';

import { createAiClient } from './ai_client.js';
import { loadConfig } from './config.js';
import { createRouter } from './routes.js';

export function createWidgetServer(config, { fetchImpl, logger } = {}) {
    const handle = createRouter({ config, ai: createAiClient(config, fetchImpl), logger });
    // handle tự bắt mọi lỗi và luôn trả response.
    return http.createServer((req, res) => {
        void handle(req, res);
    });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    const config = loadConfig();
    createWidgetServer(config).listen(config.port, () => {
        console.info(`widget-backend listening on :${config.port} -> ${config.aiServiceUrl}`);
    });
}
