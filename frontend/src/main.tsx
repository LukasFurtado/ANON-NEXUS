import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles/app.css";

const rootElement = document.getElementById("root");

function renderBootError(message: string) {
  if (!rootElement) return;
  rootElement.innerHTML = `
    <main class="bootRecovery">
      <section>
        <strong>NEXUS ANON</strong>
        <h1>Não foi possível carregar a interface.</h1>
        <p>O Chrome pode estar usando dados locais antigos ou cache incompatível com a versão atual.</p>
        <pre>${message}</pre>
        <button type="button" id="nexus-clear-local-data">Limpar dados locais e recarregar</button>
      </section>
    </main>
  `;
  document.getElementById("nexus-clear-local-data")?.addEventListener("click", () => {
    localStorage.removeItem("nexus-anon.requests.v1");
    window.location.reload();
  });
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
