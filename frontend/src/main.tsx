import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles/app.css";

const rootElement = document.getElementById("root");
const REQUESTS_STORAGE_KEY = "nexus-anon.requests.v1";
const REQUESTS_RECOVERY_KEY = "nexus-anon.requests.recovery.v1";

function renderBootError(message: string) {
  if (!rootElement) return;
  rootElement.innerHTML = `
    <main class="bootRecovery">
      <section>
        <strong>ANON</strong>
        <h1>Não foi possível carregar a interface.</h1>
        <p>O Chrome pode estar usando arquivos temporários incompatíveis com a versão atual. O histórico de solicitações será preservado antes de qualquer reparo.</p>
        <pre>${escapeHtml(message)}</pre>
        <div class="bootRecoveryActions">
          <button type="button" id="nexus-reload-only">Recarregar sem apagar histórico</button>
          <button type="button" id="nexus-safe-repair">Baixar backup e reparar carregamento</button>
        </div>
      </section>
    </main>
  `;

  document.getElementById("nexus-reload-only")?.addEventListener("click", () => {
    window.location.href = `${window.location.pathname}?reload=${Date.now()}`;
  });

  document.getElementById("nexus-safe-repair")?.addEventListener("click", () => {
    preserveRequestHistoryBeforeRepair();
    window.location.href = `${window.location.pathname}?repair=${Date.now()}`;
  });
}

function preserveRequestHistoryBeforeRepair() {
  const storedHistory = localStorage.getItem(REQUESTS_STORAGE_KEY);
  if (!storedHistory) return;

  sessionStorage.setItem(REQUESTS_RECOVERY_KEY, storedHistory);
  downloadTextFile(
    `anon-historico-backup-${new Date().toISOString().replace(/[:.]/g, "-")}.json`,
    JSON.stringify(
      {
        generated_at: new Date().toISOString(),
        source: REQUESTS_STORAGE_KEY,
        note: "Backup automático criado antes do reparo de carregamento da interface.",
        requests: safeJsonParse(storedHistory) ?? storedHistory
      },
      null,
      2
    )
  );
  localStorage.removeItem(REQUESTS_STORAGE_KEY);
}

function downloadTextFile(filename: string, text: string) {
  const blob = new Blob([text], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function safeJsonParse(value: string) {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

window.addEventListener("error", (event) => {
  renderBootError(event.message || "Erro inesperado no carregamento.");
});

window.addEventListener("unhandledrejection", (event) => {
  const reason = event.reason instanceof Error ? event.reason.message : String(event.reason || "Erro inesperado.");
  renderBootError(reason);
});

if (!rootElement) {
  throw new Error("Elemento raiz da interface não encontrado.");
}

try {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
} catch (error) {
  renderBootError(error instanceof Error ? error.message : "Erro inesperado no carregamento.");
}
