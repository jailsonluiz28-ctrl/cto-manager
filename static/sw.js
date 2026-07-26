const CACHE_NAME = "cto-manager-v1";
const ARQUIVOS_ESSENCIAIS = [
  "/static/css/estilo.css",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ARQUIVOS_ESSENCIAIS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((nomes) =>
      Promise.all(nomes.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

// Estratégia: sempre tenta a internet primeiro (dados atualizados). Se não
// conseguir (sem sinal), mostra a última versão daquela página que foi
// vista enquanto estava online. Não é sincronização de dados offline —
// é só uma rede de segurança pra quando o sinal do técnico falha em campo.
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  event.respondWith(
    fetch(req)
      .then((resposta) => {
        const copia = resposta.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copia));
        return resposta;
      })
      .catch(() =>
        caches.match(req).then((emCache) => {
          if (emCache) return emCache;
          if (req.mode === "navigate") {
            return new Response(
              "<html><body style='font-family:sans-serif;text-align:center;padding:60px 20px;color:#334155;'>" +
              "<h3>Sem conexão no momento</h3><p>Assim que o sinal voltar, é só tentar de novo.</p></body></html>",
              { headers: { "Content-Type": "text/html; charset=utf-8" } }
            );
          }
        })
      )
  );
});
