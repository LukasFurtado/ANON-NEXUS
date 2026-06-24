import {
  AlertCircle,
  Archive,
  Clock,
  Copy,
  Download,
  Edit3,
  FileText,
  Files,
  FolderOpen,
  CheckCircle2,
  ListChecks,
  Lock,
  MessageCircle,
  Play,
  RefreshCw,
  Trash2,
  ShieldCheck,
  UploadCloud,
  XCircle
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

type Result = {
  job_id: string;
  original_filename: string;
  model: string;
  original_text: string;
  anonymized_text: string;
  export_paths: Record<string, string>;
  control_table: Array<{
    original_value: string;
    entity_type: string;
    anonymous_id: string;
    occurrences: number;
  }>;
  stats: {
    entities_found: number;
    replacements_applied: number;
    preserved_dates: number;
    preserved_values: number;
    validation_warnings: string[];
    ollama_chunks_processed?: number;
    ollama_json_rejected_chunks?: number;
    ollama_correction_attempts?: number;
    ollama_correction_successes?: number;
    communication_events?: Array<{
      timestamp?: string;
      cell?: string;
      stage?: string;
      level?: string;
      message?: string;
      data?: Record<string, unknown>;
    }>;
    communication_summary?: {
      events?: number;
      levels?: Record<string, number>;
      cells?: Record<string, number>;
      last_stage?: string;
    };
    quality_status?: string;
    quality_score?: number;
    quality_reasons?: string[];
  };
  audit: {
    source_sha256: string;
    export_sha256: Record<string, string>;
    processing_time_seconds: number;
    ocr_used: boolean;
    structure_preserved: boolean;
    validation_status: string;
    anon_version?: string;
    safe_summary_id?: string;
    pipeline_state_id?: string;
  };
  safe_summary?: {
    document_id?: string;
    profile?: string;
    total_entities_detected?: number;
    entities_by_type?: Record<string, number>;
    warnings_raised?: string[];
    pipeline_stages_ok?: string[];
    quality_status?: string;
    quality_score?: number;
    quality_reasons?: string[];
  };
  pipeline_state?: {
    pipeline_id?: string;
    overall_status?: string;
    total_duration_ms?: number;
    stages?: Array<{
      name: string;
      status: string;
      duration_ms?: number;
      note?: string;
    }>;
  };
};

type ProcessedFile = {
  id: string;
  name: string;
  status: "pendente" | "processando" | "concluído" | "erro" | "cancelado";
  result?: Result;
  error?: string;
};

type RequestGroup = {
  id: string;
  backendGroupId?: string;
  title: string;
  createdAt: string;
  model: string;
  documentKind: string;
  logSha256?: string;
  files: ProcessedFile[];
};

type BatchResult = {
  group_id: string;
  request_title?: string;
  results: Result[];
  log_sha256?: string;
};

type ViewMode = "processamento" | "solicitacoes";

type ModelsResponse = {
  recommended: string[];
  installed: string[];
  models: string[];
  ollama_online: boolean;
  note: string;
};

const API_URL = "http://127.0.0.1:8000";
const REQUESTS_STORAGE_KEY = "nexus-anon.requests.v1";
const REQUESTS_RECOVERY_KEY = "nexus-anon.requests.recovery.v1";
const FALLBACK_MODELS = ["qwen3:32b", "NEXUS-anon:latest", "gemma4:31b"];
const MAX_FILES = 3;
const VALID_DOCUMENT_KINDS = new Set(["rif", "extrato_bancario", "relatorio_investigativo"]);

function fileKey(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

export function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [model, setModel] = useState("qwen3:32b");
  const [documentKind, setDocumentKind] = useState("");
  const [requestName, setRequestName] = useState("");
  const [fileHashes, setFileHashes] = useState<Record<string, string>>({});
  const [localModels, setLocalModels] = useState<string[]>(FALLBACK_MODELS);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsStatus, setModelsStatus] = useState("Modelos locais ainda não detectados nesta sessão.");
  const [useOllama, setUseOllama] = useState(false);
  const [rulesModalOpen, setRulesModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [processingStartedAt, setProcessingStartedAt] = useState<number | null>(null);
  const [currentFileName, setCurrentFileName] = useState("");
  const [currentFileIndex, setCurrentFileIndex] = useState(0);
  const [processingStep, setProcessingStep] = useState("Preparando processamento local.");
  const [error, setError] = useState<string | null>(null);
  const [requests, setRequests] = useState<RequestGroup[]>(() => loadStoredRequests());
  const [activeView, setActiveView] = useState<ViewMode>("processamento");
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const selectedGroup = requests.find((group) => group.id === selectedGroupId) ?? requests[0];
  const selectedProcessedFile =
    selectedGroup?.files.find((item) => item.id === selectedFileId) ??
    selectedGroup?.files.find((item) => item.result) ??
    selectedGroup?.files[0];
  const selectedResult = selectedProcessedFile?.result;

  useEffect(() => {
    if (!loading || !processingStartedAt) return;
    const updateElapsed = () => {
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - processingStartedAt) / 1000)));
    };
    updateElapsed();
    const timer = window.setInterval(() => {
      updateElapsed();
    }, 1000);
    return () => window.clearInterval(timer);
  }, [loading, processingStartedAt]);

  useEffect(() => {
    localStorage.setItem(REQUESTS_STORAGE_KEY, JSON.stringify(requests));
  }, [requests]);

  useEffect(() => {
    if (loading) return;
    setRequests((groups) => recoverInterruptedProcessing(groups));
  }, [loading]);

  useEffect(() => {
    void detectLocalModels();
  }, []);

  const progressLabel = useMemo(() => {
    if (loading) return "Processando solicitação localmente";
    return "Aguardando documentos";
  }, [loading]);

  async function anonymize() {
    if (files.length === 0 || !requestName.trim() || !documentKind) {
      setError("Selecione o perfil documental antes de anonimizar.");
      return;
    }

    const controller = new AbortController();
    const groupId = crypto.randomUUID();
    const initialGroup: RequestGroup = {
      id: groupId,
      title: requestName.trim() || `Solicitação ${requests.length + 1}`,
      createdAt: new Date().toISOString(),
      model,
      documentKind,
      files: files.map((file) => ({
        id: crypto.randomUUID(),
        name: file.name,
        status: "pendente"
      }))
    };

    abortControllerRef.current = controller;
    setRequests((items) => [initialGroup, ...items]);
    setSelectedGroupId(groupId);
    setSelectedFileId(initialGroup.files[0]?.id ?? null);
    setActiveView("solicitacoes");
    setProcessingStartedAt(Date.now());
    setElapsedSeconds(0);
    setLoading(true);
    setError(null);
    setRequestName("");

    try {
      for (let index = 0; index < files.length; index += 1) {
        if (controller.signal.aborted) break;

        const file = files[index];
        const fileId = initialGroup.files[index].id;
        setCurrentFileName(file.name);
        setCurrentFileIndex(index + 1);
        setProcessingStep("Preparando arquivo para análise local.");
        updateFile(groupId, fileId, { status: "processando" });

        const form = new FormData();
        form.append("file", file);
        form.append("document_kind", documentKind);
        form.append("model", model);
        form.append("use_ollama", String(useOllama));
        form.append("request_title", initialGroup.title);

        try {
          setProcessingStep("Executando IA local obrigatória, extração textual e regras de apoio.");
          const response = await fetch(`${API_URL}/api/anonymize`, {
            method: "POST",
            body: form,
            signal: controller.signal
          });
          setProcessingStep("Conferindo resposta do pipeline local e metadados de auditoria.");
          if (!response.ok) {
            const payload = await response.json();
            throw new Error(payload.detail || "Falha ao anonimizar.");
          }
          const result = (await response.json()) as Result;
          setProcessingStep("Registrando produto no Histórico de anonimização.");
          updateFile(groupId, fileId, { status: "concluído", result });
          setSelectedFileId(fileId);
        } catch (err) {
          if (err instanceof DOMException && err.name === "AbortError") {
            updateFile(groupId, fileId, { status: "cancelado" });
            throw err;
          }
          updateFile(groupId, fileId, {
            status: "erro",
            error: err instanceof Error ? err.message : "Erro inesperado."
          });
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setError("Processamento cancelado pelo usuário.");
      } else {
        setError(formatRequestError(err));
      }
    } finally {
      abortControllerRef.current = null;
      setLoading(false);
      setProcessingStartedAt(null);
      setCurrentFileName("");
      setCurrentFileIndex(0);
      setProcessingStep("Preparando processamento local.");
      setFiles([]);
      setFileHashes({});
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function anonymizeBatch() {
    if (files.length === 0 || !requestName.trim() || !documentKind) {
      setError("Selecione o perfil documental antes de anonimizar.");
      return;
    }

    const controller = new AbortController();
    const groupId = crypto.randomUUID();
    const initialGroup: RequestGroup = {
      id: groupId,
      title: requestName.trim() || `Solicitação ${requests.length + 1}`,
      createdAt: new Date().toISOString(),
      model,
      documentKind,
      files: files.map((file) => ({
        id: crypto.randomUUID(),
        name: file.name,
        status: "pendente"
      }))
    };

    abortControllerRef.current = controller;
    setRequests((items) => [initialGroup, ...items]);
    setSelectedGroupId(groupId);
    setSelectedFileId(initialGroup.files[0]?.id ?? null);
    setActiveView("solicitacoes");
    setProcessingStartedAt(Date.now());
    setElapsedSeconds(0);
    setLoading(true);
    setError(null);
    setRequestName("");

    try {
      setCurrentFileName(files.map((file) => file.name).join(", "));
      setCurrentFileIndex(1);
      setProcessingStep("Preparando lote e dicion?rio ?nico de substitui??es.");
      initialGroup.files.forEach((file) => updateFile(groupId, file.id, { status: "processando" }));

      const form = new FormData();
      files.forEach((file) => form.append("files", file));
      form.append("document_kind", documentKind);
      form.append("model", model);
      form.append("use_ollama", String(useOllama));
      form.append("request_title", initialGroup.title);

      setProcessingStep("Executando IA local obrigatória com consistência entre arquivos e regras de apoio.");
      const response = await fetch(`${API_URL}/api/anonymize-batch`, {
        method: "POST",
        body: form,
        signal: controller.signal
      });
      setProcessingStep("Conferindo hashes, exporta??es e log de auditoria do conjunto.");
      if (!response.ok) {
        throw new Error(await readErrorMessage(response));
      }

      const payload = (await response.json()) as BatchResult;
      setRequests((groups) =>
        groups.map((group) =>
          group.id !== groupId
            ? group
            : {
                ...group,
                backendGroupId: payload.group_id,
                logSha256: payload.log_sha256,
                files: group.files.map((item, index) => ({
                  ...item,
                  status: payload.results[index] ? "concluído" : "erro",
                  result: payload.results[index],
                  error: payload.results[index] ? undefined : "Resultado não retornado pelo processamento em lote."
                }))
              }
        )
      );
      setSelectedFileId(initialGroup.files[0]?.id ?? null);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        initialGroup.files.forEach((file) => updateFile(groupId, file.id, { status: "cancelado" }));
        setError("Processamento cancelado pelo usuario.");
      } else {
        initialGroup.files.forEach((file) =>
          updateFile(groupId, file.id, {
            status: "erro",
            error: err instanceof Error ? err.message : "Erro inesperado."
          })
        );
        setError(formatRequestError(err));
      }
    } finally {
      abortControllerRef.current = null;
      setLoading(false);
      setProcessingStartedAt(null);
      setCurrentFileName("");
      setCurrentFileIndex(0);
      setProcessingStep("Preparando processamento local.");
      setFiles([]);
      setFileHashes({});
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  function updateFile(groupId: string, fileId: string, patch: Partial<ProcessedFile>) {
    setRequests((groups) =>
      groups.map((group) =>
        group.id !== groupId
          ? group
          : {
              ...group,
              files: group.files.map((item) => (item.id === fileId ? { ...item, ...patch } : item))
            }
      )
    );
  }

  function cancelProcessing() {
    abortControllerRef.current?.abort();
  }

  async function setFilesFromList(fileList: FileList | null) {
    if (!fileList) return;
    const selectedFiles = Array.from(fileList);
    const currentKeys = new Set(files.map(fileKey));
    const newFiles = selectedFiles.filter((file) => !currentKeys.has(fileKey(file)));
    const nextFiles = [...files, ...newFiles];

    if (nextFiles.length > MAX_FILES) {
      setError(`Limite de ${MAX_FILES} arquivos por solicitação. Remova algum arquivo antes de anexar outro.`);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    if (newFiles.length === 0 && selectedFiles.length > 0) {
      setError("Este arquivo já foi anexado nesta solicitação.");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    setError(null);
    setFiles(nextFiles);
    const hashes: Record<string, string> = {};
    await Promise.all(
      newFiles.map(async (file) => {
        hashes[fileKey(file)] = await sha256File(file);
      })
    );
    setFileHashes((current) => ({ ...current, ...hashes }));
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function removeQueuedFile(indexToRemove: number) {
    if (loading) return;
    setFiles((items) => {
      const next = items.filter((_, index) => index !== indexToRemove);
      setFileHashes((hashes) => {
        const allowed = new Set(next.map(fileKey));
        return Object.fromEntries(Object.entries(hashes).filter(([key]) => allowed.has(key)));
      });
      return next;
    });
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function renameGroup(groupId: string, title: string) {
    setRequests((groups) =>
      groups.map((group) => (group.id === groupId ? { ...group, title: title.trim() || group.title } : group))
    );
  }

  function deleteGroup(groupId: string) {
    const group = requests.find((item) => item.id === groupId);
    const confirmed = window.confirm(
      `Excluir a solicitação "${group?.title || "selecionada"}"? Esta ação não pode ser revertida.`
    );
    if (!confirmed) return;

    setRequests((groups) => {
      const next = groups.filter((item) => item.id !== groupId);
      const fallback = next[0];
      setSelectedGroupId(fallback?.id ?? null);
      setSelectedFileId(fallback?.files[0]?.id ?? null);
      return next;
    });
  }

  async function downloadGroupLog(group: RequestGroup) {
    if (!group.backendGroupId || !group.logSha256) {
      window.alert("Log de processamento ainda não disponível para esta solicitação.");
      return;
    }
    const response = await fetch(`${API_URL}/api/exports/groups/${group.backendGroupId}/log`);
    if (!response.ok) {
      window.alert("N?o foi poss?vel baixar o log do conjunto.");
      return;
    }
    const blob = await response.blob();
    const buffer = await blob.arrayBuffer();
    const actualHash = await sha256Buffer(buffer);
    if (actualHash !== group.logSha256.toUpperCase()) {
      window.alert("O hash do log não corresponde ao registro informado. Download bloqueado.");
      return;
    }
    const url = URL.createObjectURL(new Blob([buffer], { type: blob.type || "application/pdf" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${sanitizeFileBase(group.title)}-log-processamento.pdf`;
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  async function downloadErrorLog() {
    const response = await fetch(`${API_URL}/api/logs/errors`);
    if (!response.ok) {
      window.alert("NÃ£o foi possÃ­vel baixar o log de erros local.");
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "ANON_log_erros.txt";
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  async function detectLocalModels() {
    setModelsLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/models`);
      if (!response.ok) throw new Error("Falha ao consultar modelos locais.");
      const payload = (await response.json()) as ModelsResponse;
      const detected = payload.models.length > 0 ? payload.models : FALLBACK_MODELS;
      setLocalModels(detected);
      if (!detected.includes(model)) {
        setModel(detected[0]);
      }
      setModelsStatus(
        payload.ollama_online
          ? `${payload.installed.length} modelo(s) local(is) detectado(s) no Ollama.`
          : "Ollama não respondeu. Lista padrão mantida."
      );
    } catch (err) {
      setLocalModels(FALLBACK_MODELS);
      setModelsStatus(err instanceof Error ? err.message : "Não foi possível detectar modelos locais.");
    } finally {
      setModelsLoading(false);
    }
  }

  function handleDrop(event: React.DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    void setFilesFromList(event.dataTransfer.files);
  }

  return (
    <main className="shell">
      {loading && (
        <ProcessingDialog
          fileName={currentFileName || "Documento"}
          elapsedSeconds={elapsedSeconds}
          model={model}
          currentFileIndex={currentFileIndex}
          totalFiles={files.length}
          processingStep={processingStep}
          onCancel={cancelProcessing}
        />
      )}

      {rulesModalOpen && (
        <UsageRulesDialogV3
          onAccept={() => {
            setUseOllama(true);
            setRulesModalOpen(false);
          }}
          onClose={() => setRulesModalOpen(false)}
        />
      )}

      <FloatingNexusAssistant
        loading={loading}
        processingStep={processingStep}
        elapsedSeconds={elapsedSeconds}
        fileName={currentFileName || selectedProcessedFile?.name || "Documento"}
        currentFileIndex={currentFileIndex}
        totalFiles={files.length || selectedGroup?.files.length || 1}
        selectedResult={selectedResult}
        selectedFile={selectedProcessedFile}
        selectedGroup={selectedGroup}
      />

      <aside className="sidebar">
        <div className="pcpeHeader">
          <img src="/logo_pcpe_header.png" alt="Polícia Civil de Pernambuco" />
        </div>

        <div className="brand">
          <ShieldCheck size={28} />
          <div>
            <strong>ANON</strong>
            <span>Anonimização institucional de Arquivos offline</span>
          </div>
        </div>

        <nav className="sideNav" aria-label="Navegação principal">
          <button
            className={activeView === "processamento" ? "active" : ""}
            onClick={() => setActiveView("processamento")}
          >
            <UploadCloud size={17} />
            Processamento
          </button>
          <button
            className={activeView === "solicitacoes" ? "active" : ""}
            onClick={() => setActiveView("solicitacoes")}
          >
            <ListChecks size={17} />
            Solicitações
          </button>
        </nav>

        <label
          className="dropzone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
        >
          <UploadCloud size={34} />
          <strong>{files.length > 0 ? `${files.length} arquivo(s) selecionado(s)` : "Arraste os documentos"}</strong>
          <span>É possível inserir até 3 arquivos. Recomenda-se mesma extensão e mesmo trabalho investigativo.</span>
          <small>PDF, DOCX, DOC, TXT, RTF ou CSV</small>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.txt,.rtf,.csv"
            onChange={(event) => void setFilesFromList(event.target.files)}
          />
        </label>

        {files.length > 0 && (
          <div className="queuedFiles" aria-label="Arquivos anexados aguardando processamento">
            <div className="queuedHeader">
              <CheckCircle2 size={16} />
              <strong>Arquivos anexados</strong>
            </div>
            {files.map((item, index) => (
              <div className="queuedFile" key={`${item.name}-${item.size}`}>
                <CheckCircle2 size={18} />
                <div>
                  <strong>{item.name}</strong>
                  <span>Pronto para anonimização</span>
                  {fileHashes[fileKey(item)] && <code>{shortHash(fileHashes[fileKey(item)])}</code>}
                </div>
                <button
                  type="button"
                  className="removeQueuedFile"
                  aria-label={`Remover ${item.name}`}
                  disabled={loading}
                  onClick={() => removeQueuedFile(index)}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
          </div>
        )}

        <section className="controls">
          <label>
            Número IP / Nome solicitação
            <input
              className="requestNameInput"
              value={requestName}
              onChange={(event) => setRequestName(event.target.value)}
              placeholder="Ex.: IP 123/2026 - RIF COAF"
              disabled={loading}
              required
            />
          </label>

          <label>
            Modelo local
            <div className="modelDetector">
              <select value={model} onChange={(event) => setModel(event.target.value)}>
                {localModels.map((item) => (
                  <option key={item} value={item}>
                    {formatModelName(item)}
                  </option>
                ))}
              </select>
              <button type="button" onClick={detectLocalModels} disabled={modelsLoading}>
                <RefreshCw size={15} />
                Detectar
              </button>
            </div>
            <small className="modelStatus">{modelsStatus}</small>
          </label>

          <label>
            Perfil documental estratégico
            <select value={documentKind} onChange={(event) => setDocumentKind(event.target.value)}>
              <option value="" disabled>Selecione o perfil documental</option>
              <option value="rif">RIF / COAF</option>
              <option value="extrato_bancario">Extrato bancário</option>
              <option value="relatorio_investigativo">Relatório investigativo</option>
            </select>
            <small className="modelStatus">Altera prompt local, regras regex e critérios de validação.</small>
          </label>

          <label className="toggle">
            <input
              type="checkbox"
              checked={useOllama}
              onChange={(event) => {
                if (event.target.checked) {
                  setRulesModalOpen(true);
                  return;
                }
                setUseOllama(false);
              }}
            />
            Eu estou ciente das regras de uso e concordo.
          </label>
        </section>

        <button className="primary" disabled={files.length === 0 || !requestName.trim() || !documentKind || !useOllama || loading} onClick={anonymizeBatch}>
          <Play size={18} />
          Anonimizar
        </button>

        <div className="offline">
          <Lock size={18} />
          <span>Processamento 100% local. Nenhum documento é enviado para a internet.</span>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">{activeView === "solicitacoes" ? "Consulta de solicitações" : "Fluxo operacional"}</span>
            <h1>{activeView === "solicitacoes" ? "Histórico de anonimização" : "Anonimização Forense de Documentos"}</h1>
          </div>
          {loading ? <div className="status active">{progressLabel}</div> : null}
        </header>

        {error && activeView === "processamento" && (
          <div className="alert">
            <AlertCircle size={18} />
            <span>{error}</span>
            <button type="button" onClick={() => void downloadErrorLog()}>
              <Download size={14} />
              Baixar log de erros
            </button>
          </div>
        )}

        {activeView === "processamento" ? (
          <ProcessingPage
            selectedResult={selectedResult}
            selectedFile={selectedProcessedFile}
            requestTitle={selectedGroup?.title || requestName}
            requestCreatedAt={selectedGroup?.createdAt}
            files={files}
            fileHashes={fileHashes}
            model={model}
          />
        ) : (
          <RequestsPage
            requests={requests}
            selectedGroup={selectedGroup}
            selectedFile={selectedProcessedFile}
            onSelectGroup={(groupId) => {
              setError(null);
              setSelectedGroupId(groupId);
              const group = requests.find((item) => item.id === groupId);
              setSelectedFileId(group?.files[0]?.id ?? null);
            }}
            onSelectFile={(fileId) => {
              setError(null);
              setSelectedFileId(fileId);
            }}
            onRenameGroup={renameGroup}
            onDeleteGroup={deleteGroup}
            onDownloadLog={(group) => void downloadGroupLog(group)}
            onDownloadErrorLog={() => void downloadErrorLog()}
          />
        )}

        <InstitutionalFooter />
      </section>
    </main>
  );
}

function ProcessingPage({
  selectedResult,
  selectedFile,
  requestTitle,
  requestCreatedAt,
  files,
  fileHashes,
  model
}: {
  selectedResult?: Result;
  selectedFile?: ProcessedFile;
  requestTitle?: string;
  requestCreatedAt?: string;
  files: File[];
  fileHashes: Record<string, string>;
  model: string;
}) {
  return (
    <>
      <ProcessingIntegrityPanel files={files} fileHashes={fileHashes} model={model} />
      <WorkSummary
        result={selectedResult}
        fileName={selectedFile?.name}
        status={selectedFile?.status}
        requestTitle={requestTitle}
        requestCreatedAt={requestCreatedAt}
        summaryLabel="Resumo operacional - Última solicitação"
      />
      <ExportBar result={selectedResult} fileName={selectedFile?.name} />
    </>
  );
}

function ProcessingIntegrityPanel({
  files,
  fileHashes,
  model
}: {
  files: File[];
  fileHashes: Record<string, string>;
  model: string;
}) {
  return (
    <section className="processingIntegrity">
      <header>
        <div>
          <span className="panelLabel">Controle de sigilo e integridade</span>
          <h2>Processamento local preparado</h2>
        </div>
        <div className="summaryPills">
          <span>{formatModelName(model)}</span>
          <span>{files.length} arquivo(s)</span>
        </div>
      </header>
      <p>
        Os hashes abaixo são calculados localmente antes da anonimização. Eles servem para controle interno, conferência de integridade e rastreabilidade da solicitação.
      </p>
      {files.length > 0 ? (
        <div className="integrityFiles">
          {files.map((file) => (
            <AuditHash
              key={fileKey(file)}
              label={`SHA-256 original · ${file.name}`}
              value={fileHashes[fileKey(file)] || "Calculando hash..."}
            />
          ))}
        </div>
      ) : (
        <div className="integrityEmpty">Nenhum arquivo anexado para cálculo de hash.</div>
      )}
    </section>
  );
}

function RequestsPage({
  requests,
  selectedGroup,
  selectedFile,
  onSelectGroup,
  onSelectFile,
  onRenameGroup,
  onDeleteGroup,
  onDownloadLog,
  onDownloadErrorLog
}: {
  requests: RequestGroup[];
  selectedGroup?: RequestGroup;
  selectedFile?: ProcessedFile;
  onSelectGroup: (groupId: string) => void;
  onSelectFile: (fileId: string) => void;
  onRenameGroup: (groupId: string, title: string) => void;
  onDeleteGroup: (groupId: string) => void;
  onDownloadLog: (group: RequestGroup) => void;
  onDownloadErrorLog: () => void;
}) {
  const [qualityModal, setQualityModal] = useState<{
    status: string;
    score?: number;
    reasons: string[];
  } | null>(null);

  if (requests.length === 0) {
    return (
      <section className="emptyState">
        <Archive size={34} />
        <h2>Nenhuma solicitação registrada</h2>
        <p>Envie um ou mais arquivos para criar um grupo de anonimização consultável.</p>
      </section>
    );
  }

  const result = selectedFile?.result;

  return (
    <section className="requestsLayout">
      <aside className="requestGroups">
        {requests.map((group) => (
          <button
            key={group.id}
            className={group.id === selectedGroup?.id ? "selected" : ""}
            onClick={() => onSelectGroup(group.id)}
          >
            <FolderOpen size={17} />
            <div>
              <strong>{group.title}</strong>
              <span>
                {group.files.length} arquivo(s) · {formatDate(group.createdAt)}
              </span>
            </div>
          </button>
        ))}
      </aside>

      <section className="requestDetail">
        <div className="requestSummary">
          <div>
            <span className="panelLabel">Grupo selecionado</span>
            <div className="renameGroup">
              <Edit3 size={17} />
              <input
                value={selectedGroup?.title ?? ""}
                onChange={(event) => selectedGroup && onRenameGroup(selectedGroup.id, event.target.value)}
                aria-label="Renomear solicitação"
              />
            </div>
          </div>
          <div className="summaryPills">
            <button
              type="button"
              className="logDownloadButton"
              disabled={!selectedGroup?.backendGroupId || !selectedGroup?.logSha256}
              onClick={() => selectedGroup && onDownloadLog(selectedGroup)}
              title={selectedGroup?.logSha256 ? "Log de auditoria do conjunto processado gerado." : undefined}
            >
              <Download size={14} />
              <span>
                <strong>Log PDF</strong>
                <small>Auditoria do conjunto</small>
              </span>
            </button>
            <button
              type="button"
              className="deleteRequestButton"
              disabled={!selectedGroup}
              onClick={() => selectedGroup && onDeleteGroup(selectedGroup.id)}
            >
              <Trash2 size={14} />
              Excluir
            </button>
          </div>
        </div>

        <div className="fileProducts">
          <div className="fileList">
            {selectedGroup?.files.map((item) => (
              <button
                key={item.id}
                className={item.id === selectedFile?.id ? "selected" : ""}
                onClick={() => onSelectFile(item.id)}
              >
                <Files size={16} />
                <div>
                  <strong>{item.name}</strong>
                  <span className={`fileStatus ${item.status}`}>{item.status}</span>
                  {item.result?.stats.quality_status ? (
                    <button
                      type="button"
                      className={`qualityBadge ${qualityCssClass(item.result.stats.quality_status)}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        setQualityModal({
                          status: item.result?.stats.quality_status || "REVISAR",
                          score: item.result?.stats.quality_score,
                          reasons: item.result?.stats.quality_reasons || []
                        });
                      }}
                    >
                      {qualityLabel(item.result.stats.quality_status)}
                    </button>
                  ) : null}
                </div>
              </button>
            ))}
          </div>

          <div className="productPanel">
            {selectedFile?.error && (
              <div className="alert compact">
                <AlertCircle size={17} />
                <span>{selectedFile.error}</span>
                <button type="button" onClick={onDownloadErrorLog}>
                  <Download size={14} />
                  Baixar log de erros
                </button>
              </div>
            )}

            <WorkSummary
              result={result}
              fileName={selectedFile?.name}
              status={selectedFile?.status}
              requestTitle={selectedGroup?.title}
              requestCreatedAt={selectedGroup?.createdAt}
            />
            <DiagnosticChatPanel result={result} selectedGroup={selectedGroup} selectedFile={selectedFile} />

            <ExportBar result={result} fileName={selectedFile?.name} />
          </div>
        </div>
      </section>
      {qualityModal ? <QualityModal data={qualityModal} onClose={() => setQualityModal(null)} /> : null}
    </section>
  );
}

function QualityModal({
  data,
  onClose
}: {
  data: { status: string; score?: number; reasons: string[] };
  onClose: () => void;
}) {
  return (
    <div className="qualityModalBackdrop" role="dialog" aria-modal="true">
      <section className="qualityModal">
        <header>
          <div>
            <span className="panelLabel">Classificação automática</span>
            <h3>{qualityLabel(data.status)}</h3>
          </div>
          <button type="button" onClick={onClose} aria-label="Fechar classificação">
            <XCircle size={18} />
          </button>
        </header>
        <p>
          Este selo resume a conferência automática do ANON. Ele não substitui a revisão humana obrigatória,
          mas indica se o produto exige atenção adicional antes de qualquer uso institucional.
        </p>
        <div className="qualityScore">
          <span>Pontuação</span>
          <strong>{typeof data.score === "number" ? `${data.score}/100` : "Não informada"}</strong>
        </div>
        <ul>
          {(data.reasons.length ? data.reasons : ["Nenhum motivo específico informado."]).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function ProcessingDialog({
  fileName,
  elapsedSeconds,
  model,
  currentFileIndex,
  totalFiles,
  processingStep,
  onCancel
}: {
  fileName: string;
  elapsedSeconds: number;
  model: string;
  currentFileIndex: number;
  totalFiles: number;
  processingStep: string;
  onCancel: () => void;
}) {
  return (
    <div className="processingOverlay" role="dialog" aria-modal="true">
      <section className="processingWindow">
        <header>
          <div>
            <span className="panelLabel">Processamento local</span>
            <h2>Processando solicitação, aguarde.</h2>
          </div>
          <div className="processingTimer">
            <Clock size={18} />
            {formatElapsed(elapsedSeconds)}
          </div>
        </header>

        <div className="processingBody">
          <div className="processingFile">
            <FileText size={20} />
            <div>
              <span>
                Arquivo {currentFileIndex || 1} de {totalFiles || 1}
              </span>
              <strong>{fileName}</strong>
            </div>
          </div>

          <div className="processingSteps">
            <span>Identificação do formato</span>
            <span>Extração textual</span>
            <span>Reconhecimento por regex</span>
            <span>IA local obrigatória: {model}</span>
            <span>Validação e exportação</span>
          </div>

          <div className="progressTrack">
            <div />
          </div>

          <div className="processingStepText">
            <RefreshCw size={15} />
            {processingStep}
          </div>

          <div className="processingNotice">
            Arquivos extensos podem exigir mais tempo de processamento. Você pode aguardar com tranquilidade enquanto a análise local é concluída.
          </div>

          <div className="processingWarning">
            Este procedimento pode demandar elevado poder computacional, especialmente em documentos extensos ou com múltiplos arquivos. Recomenda-se a execução em equipamento com recursos adequados de memória, processador e capacidade de inferência local.
          </div>
        </div>

        <footer>
          <p>Nenhum dado sai deste computador. O processamento usa apenas serviços locais.</p>
          <button className="cancelButton" onClick={onCancel}>
            <XCircle size={18} />
            Cancelar
          </button>
        </footer>
      </section>
    </div>
  );
}

type NexusAssistantMessage = {
  role: "nexus" | "user";
  text: string;
  tone?: "info" | "warning" | "success";
};

function FloatingNexusAssistant({
  loading,
  processingStep,
  elapsedSeconds,
  fileName,
  currentFileIndex,
  totalFiles,
  selectedResult,
  selectedFile,
  selectedGroup
}: {
  loading: boolean;
  processingStep: string;
  elapsedSeconds: number;
  fileName: string;
  currentFileIndex: number;
  totalFiles: number;
  selectedResult?: Result;
  selectedFile?: ProcessedFile;
  selectedGroup?: RequestGroup;
}) {
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<NexusAssistantMessage[]>([]);
  const [answering, setAnswering] = useState(false);
  const [fontScale, setFontScale] = useState(1.1);
  const wasLoadingRef = useRef(false);
  const lastStepRef = useRef("");
  const nexusMessagesRef = useRef<HTMLDivElement | null>(null);
  const nexusAnswerAbortRef = useRef<AbortController | null>(null);
  const nexusAnswerCanceledByOperatorRef = useRef(false);

  useEffect(() => {
    if (!open) return;
    const scrollToBottom = () => {
      if (nexusMessagesRef.current) {
        nexusMessagesRef.current.scrollTop = nexusMessagesRef.current.scrollHeight;
      }
    };
    scrollToBottom();
    const frame = window.requestAnimationFrame(scrollToBottom);
    return () => window.cancelAnimationFrame(frame);
  }, [open, messages, answering, fontScale]);

  useEffect(() => {
    if (loading && !wasLoadingRef.current) {
      setOpen(true);
      setMessages([
        {
          role: "nexus",
          text: "IA NEXUS ativa. Aguarde a conclusão da solicitação e realize revisão humana antes de qualquer uso externo.",
          tone: "info"
        }
      ]);
    }
    if (!loading && wasLoadingRef.current) {
      setOpen(false);
      setQuestion("");
      setMessages([]);
    }
    wasLoadingRef.current = loading;
  }, [loading]);

  useEffect(() => {
    if (!loading || !processingStep || lastStepRef.current === processingStep) return;
    lastStepRef.current = processingStep;
    pushNexusMessage(processingStepToNexusText(processingStep, fileName, currentFileIndex, totalFiles), "info");
  }, [processingStep, loading, fileName, currentFileIndex, totalFiles]);

  function pushNexusMessage(text: string, tone: NexusAssistantMessage["tone"] = "info") {
    setMessages((items) => {
      const last = items[items.length - 1];
      if (last?.role === "nexus" && last.text === text) return items;
      return [...items.slice(-7), { role: "nexus", text, tone }];
    });
  }

  function cancelNexusAnswer() {
    nexusAnswerCanceledByOperatorRef.current = true;
    nexusAnswerAbortRef.current?.abort();
  }

  async function askNexus(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    setMessages((items) => [...items.slice(-7), { role: "user", text: trimmed }]);
    setQuestion("");
    setAnswering(true);

    const localAnswer = nexusLocalAnswer(trimmed, {
      loading,
      processingStep,
      elapsedSeconds,
      fileName,
      selectedResult,
      selectedFile,
      selectedGroup
    });
    if (localAnswer) {
      setMessages((items) => [...items.slice(-7), { role: "nexus", text: localAnswer, tone: "info" }]);
      setAnswering(false);
      return;
    }

    const timeoutController = new AbortController();
    nexusAnswerCanceledByOperatorRef.current = false;
    nexusAnswerAbortRef.current = timeoutController;
    const timeoutId = window.setTimeout(() => timeoutController.abort(), 25000);
    try {
      const response = await fetch(`${API_URL}/api/diagnostics/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: timeoutController.signal,
        body: JSON.stringify({ question: trimmed })
      });
      const payload = await response.json();
      setMessages((items) => [...items.slice(-7), { role: "nexus", text: payload.answer || "Orientação institucional indisponível neste momento.", tone: "info" }]);
    } catch {
      const canceledByOperator = timeoutController.signal.aborted && nexusAnswerCanceledByOperatorRef.current;
      setMessages((items) => [
        ...items.slice(-7),
        {
          role: "nexus",
          text: canceledByOperator
            ? "Envio da última mensagem cancelado pelo operador."
            : "Este canal é restrito a orientações institucionais de uso, revisão e finalidade da anonimização.",
          tone: "warning"
        }
      ]);
    } finally {
      window.clearTimeout(timeoutId);
      if (nexusAnswerAbortRef.current === timeoutController) {
        nexusAnswerAbortRef.current = null;
        nexusAnswerCanceledByOperatorRef.current = false;
      }
      setAnswering(false);
    }
  }

  if (!loading) return null;

  return (
    <aside className={`nexusFloatingAssistant ${open ? "open" : "collapsed"}`} aria-live="polite">
      <button type="button" className="nexusAssistantToggle" onClick={() => setOpen((value) => !value)}>
        <MessageCircle size={18} />
        <span>IA NEXUS</span>
      </button>

      {open && (
        <div className="nexusAssistantPanel" style={{ "--nexus-font-scale": fontScale } as React.CSSProperties}>
          <header>
            <div>
              <span className="panelLabel">Observação operacional</span>
              <h3>IA NEXUS</h3>
            </div>
            <div className="nexusAssistantHeaderTools" aria-label="Controles da IA NEXUS">
              <button type="button" onClick={() => setFontScale((value) => Math.max(0.95, Number((value - 0.1).toFixed(2))))}>
                A-
              </button>
              <button type="button" onClick={() => setFontScale(1.1)}>
                A
              </button>
              <button type="button" onClick={() => setFontScale((value) => Math.min(1.5, Number((value + 0.1).toFixed(2))))}>
                A+
              </button>
              <ShieldCheck size={20} />
            </div>
          </header>

          <div className="nexusAssistantStatus">
            <strong>{loading ? "Acompanhando solicitação" : "Orientação institucional"}</strong>
            <span>{loading ? `Tempo decorrido: ${formatElapsed(elapsedSeconds)}` : "Canal restrito a finalidade, sigilo e revisão humana."}</span>
          </div>

          <div className="nexusAssistantMessages" ref={nexusMessagesRef}>
            {messages.length === 0 ? (
              <p>Estou pronta para orientar sobre finalidade da anonimização, sigilo, preservação documental e revisão humana.</p>
            ) : (
              messages.map((message, index) => (
                <div key={`${message.role}-${index}`} className={`nexusMessage ${message.role} ${message.tone || "info"}`}>
                  {message.role === "user" ? <img className="anonymousInlineAvatar" src="/anonymous-avatar.png" alt="Anonymous" /> : null}
                  <strong>{message.role === "user" ? "Anonymous" : "IA NEXUS"}</strong>
                  <span>{message.text}</span>
                </div>
              ))
            )}
          </div>

          <form
            className="nexusAssistantForm"
            onSubmit={(event) => {
              event.preventDefault();
              void askNexus(question);
            }}
          >
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Fale com a IA NEXUS."
            />
            <button type="submit" disabled={answering || !question.trim()}>
              {answering ? <TypingDots label="Processando resposta" /> : "Enviar"}
            </button>
            {answering && (
              <button type="button" className="nexusCancelSend" onClick={cancelNexusAnswer}>
                Cancelar
              </button>
            )}
          </form>
        </div>
      )}
    </aside>
  );
}

function processingStepToNexusText(step: string, _fileName: string, _currentFileIndex: number, _totalFiles: number) {
  const normalized = step.toLowerCase();
  if (normalized.includes("preparando")) {
    return "A solicitação foi recebida. Aguarde a conclusão e mantenha a revisão humana como etapa obrigatória.";
  }
  if (normalized.includes("ia local")) {
    return "A anonimização está em andamento. O tempo pode variar conforme o tamanho do material e a capacidade do computador.";
  }
  if (normalized.includes("hash") || normalized.includes("export")) {
    return "A solicitação está sendo finalizada para disponibilização do produto de revisão.";
  }
  if (normalized.includes("hist")) {
    return "O resultado será disponibilizado no histórico da solicitação para conferência institucional.";
  }
  return "A solicitação permanece em andamento. Aguarde a conclusão antes de revisar o produto final.";
}

function nexusLocalAnswer(
  question: string,
  _context: {
    loading: boolean;
    processingStep: string;
    elapsedSeconds: number;
    fileName: string;
    selectedResult?: Result;
    selectedFile?: ProcessedFile;
    selectedGroup?: RequestGroup;
  }
) {
  const normalized = question.toLowerCase();
  if (normalized.includes("erro") || normalized.includes("problema") || normalized.includes("json") || normalized.includes("log") || normalized.includes("intern")) {
    return "Este canal é restrito a orientações institucionais de uso, revisão e finalidade da anonimização. Questões técnicas devem ser tratadas pelos instrumentos formais de auditoria e suporte.";
  }
  if (normalized.includes("rif") || normalized.includes("coaf") || normalized.includes("financeir")) {
    return "Em RIF e dados financeiros, o objetivo é substituir identificadores sensíveis mantendo valores, datas, movimentações, estrutura e coerência analítica.";
  }
  if (normalized.includes("extrato") || normalized.includes("banc")) {
    return "Em extratos bancários, revise se a sequência dos lançamentos, datas, valores e saldos permaneceu preservada, com substituição apenas de identificadores sensíveis.";
  }
  if (normalized.includes("revis") || normalized.includes("confer") || normalized.includes("compartilh")) {
    return "Antes de compartilhar, confira manualmente se nomes, documentos, contas, endereços, contatos e demais identificadores foram substituídos sem alteração indevida do conteúdo preservado.";
  }
  if (normalized.includes("sigilo") || normalized.includes("seguran") || normalized.includes("uso")) {
    return "O uso deve permanecer institucional, local e controlado, observando sigilo, finalidade, necessidade, rastreabilidade e revisão humana qualificada.";
  }
  if (normalized.includes("objetivo") || normalized.includes("serve") || normalized.includes("finalidade") || normalized.includes("anon")) {
    return "A finalidade do ANON é apoiar a anonimização documental, substituindo identificadores sensíveis por marcadores consistentes e preservando o conteúdo técnico, jurídico e financeiro.";
  }
  return null;
}

function UsageRulesDialogV3({ onAccept, onClose }: { onAccept: () => void; onClose: () => void }) {
  return (
    <div className="processingOverlay" role="dialog" aria-modal="true" aria-labelledby="usage-rules-title">
      <section className="usageRulesWindow">
        <header>
          <div>
            <span className="panelLabel">Ciência obrigatória</span>
            <h2 id="usage-rules-title">⚠ Regras institucionais de uso e Avisos ⚠</h2>
          </div>
          <ShieldCheck size={26} />
        </header>

        <div className="usageRulesBody">
          <div className="usageRulesIntro">
            <p>
              O NEXUS ANON é uma ferramenta local de apoio à anonimização documental para uso institucional, interno
              e controlado. A ciência abaixo reforça deveres de sigilo, proteção de dados, rastreabilidade, revisão
              humana e uso responsável de sistemas de inteligência artificial.
            </p>
            <img src="/logo_pcpe_header.png" alt="Polícia Civil de Pernambuco" />
          </div>

          <ol>
            <li>Utilizar o sistema somente para finalidade institucional legítima, necessária, proporcional e vinculada à atividade funcional autorizada.</li>
            <li>Manter o tratamento de documentos em ambiente local, controlado e compatível com o grau de sigilo, sem envio de dados sensíveis a serviços externos não homologados.</li>
            <li>Preservar hashes, histórico, registros de processamento e demais elementos necessários à rastreabilidade, auditoria e cadeia de custódia.</li>
            <li>Reconhecer que a IA possui natureza auxiliar, preliminar e não decisória, não substituindo análise jurídica, técnica ou funcional humana.</li>
            <li>Revisar o produto anonimizado antes de compartilhar, juntar, imprimir, remeter ou utilizar oficialmente, conferindo se não houve exposição residual ou alteração indevida de conteúdo preservado.</li>
            <li className="criticalRule">O programa ainda está em fase de testes e pode apresentar erros de identificação, omissão ou classificação. A revisão humana qualificada é imprescindível.</li>
            <li>Quando a IA ou as regras automáticas não anonimizarem determinado dado sensível, a anonimização manual deve ser realizada antes de qualquer uso externo ou oficial do produto.</li>
          </ol>

          <div className="usageRulesWarning">
            O processamento local reduz riscos de exposição, mas não elimina a responsabilidade funcional do operador
            pela conferência, Validação e segurança do documento final.
          </div>
        </div>

        <footer>
          <button className="secondaryButton" type="button" onClick={onClose}>
            Voltar
          </button>
          <button className="primary acceptRulesButton" type="button" onClick={onAccept}>
            <ShieldCheck size={17} />
            Declaro ciência e concordo
          </button>
        </footer>
      </section>
    </div>
  );
}
function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function WorkSummary({
  result,
  fileName,
  status,
  requestTitle,
  requestCreatedAt,
  summaryLabel = "Resumo operacional"
}: {
  result?: Result;
  fileName?: string;
  status?: string;
  requestTitle?: string;
  requestCreatedAt?: string;
  summaryLabel?: string;
}) {
  const summary = result
    ? [
        `Solicitação: ${requestTitle || "Não informada"}`,
        `Arquivo: ${fileName || result.original_filename}`,
        `Status: ${status || "concluído"}`,
        `Modelo: ${result.model}`,
        `Tempo: ${formatSeconds(result.audit.processing_time_seconds)}`,
        `OCR: ${result.audit.ocr_used ? "Utilizado" : "Não utilizado"}`,
        `Estrutura: ${result.audit.structure_preserved ? "Preservada" : "Não preservada"}`,
        `Validação: ${result.audit.validation_status}`,
        `Hash SHA-256 original: ${result.audit.source_sha256}`,
        `Entidades identificadas: ${result.stats.entities_found}`,
        `Substituições aplicadas: ${result.stats.replacements_applied}`,
        ...Object.entries(result.audit.export_sha256).map(([format, hash]) => `Hash SHA-256 ${format.toUpperCase()}: ${hash}`),
        `Avisos de Validação: ${result.stats.validation_warnings.length}`
      ].join("\n")
    : "";

  async function copySummary() {
    if (!summary) return;
    await navigator.clipboard.writeText(summary);
  }

  return (
    <article className="workSummary">
      <header>
        <div>
          <span className="panelLabel">{summaryLabel}</span>
          {requestCreatedAt ? <p className="summaryDate">Solicitação registrada em {formatDate(requestCreatedAt)}</p> : null}
          <h2>{requestTitle || fileName || "Produto ainda não disponível"}</h2>
          {fileName && requestTitle ? <p className="summarySubtitle">Arquivo em consulta: {fileName}</p> : null}
        </div>
        <div className="paneActions">
          <button type="button" disabled={!result} onClick={copySummary}>
            <Copy size={14} />
            Copiar resumo
          </button>
        </div>
      </header>
      {result ? (
        <AuditSeal result={result} />
      ) : (
        <p className="summaryPlaceholder">
          O resultado será apresentado por indicadores, estatísticas e arquivos exportáveis. O conteúdo integral não é exibido na tela para preservar a navegação em documentos extensos.
        </p>
      )}
      {result?.stats.validation_warnings.length ? (
        <ValidationWarningsPanel warnings={result.stats.validation_warnings} />
      ) : null}
    </article>
  );
}

function ValidationWarningsPanel({ warnings }: { warnings: string[] }) {
  const groupedWarnings = groupValidationWarnings(warnings);

  return (
    <details className="summaryWarnings">
      <summary>
        <div>
          <strong>Avisos de Validação automática</strong>
          <span>
            {warnings.length} ocorrência(s) reunida(s) em {groupedWarnings.length} tipo(s). Clique para consultar a
            explicação e revisar os pontos indicados.
          </span>
        </div>
      </summary>

      <div className="validationWarningList">
        {groupedWarnings.map(({ warning, count }) => (
          <ValidationWarningCard key={warning} warning={warning} count={count} />
        ))}
      </div>
    </details>
  );
}

function ValidationWarningCard({ warning, count }: { warning: string; count: number }) {
  return (
    <article className="validationWarningCard">
      <strong>{warning}</strong>
      {count > 1 ? <em>Repetido {count} vez(es) nesta solicitação.</em> : null}
      <span>{explainValidationWarning(warning)}</span>
    </article>
  );
}

function DiagnosticChatPanel({
  result,
  selectedGroup,
  selectedFile
}: {
  result?: Result;
  selectedGroup?: RequestGroup;
  selectedFile?: ProcessedFile;
}) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Array<{ role: "user" | "anon"; text: string; source?: string }>>([]);
  const [loadingAnswer, setLoadingAnswer] = useState(false);
  const diagnosticMessagesRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const element = diagnosticMessagesRef.current;
    if (!element) return;
    element.scrollTop = element.scrollHeight;
  }, [messages, loadingAnswer]);

  if (!result) return null;

  const quickQuestions = ["Qual é a finalidade?", "O que devo revisar?", "Se surgir erro, o que fazer?", "Como conferir RIF ou extrato?"];

  async function askDiagnostic(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    setMessages((items) => [...items, { role: "user", text: trimmed }]);
    setQuestion("");
    setLoadingAnswer(true);
    const timeoutController = new AbortController();
    const timeoutId = window.setTimeout(() => timeoutController.abort(), 25000);
    try {
      const response = await fetch(API_URL + "/api/diagnostics/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: timeoutController.signal,
        body: JSON.stringify({ question: trimmed })
      });
      const payload = await response.json();
      setMessages((items) => [...items, { role: "anon", text: payload.answer || "Orientação institucional indisponível neste momento.", source: payload.source }]);
    } catch {
      setMessages((items) => [...items, { role: "anon", text: "Este canal permanece restrito a orientações institucionais de uso, sigilo e revisão." }]);
    } finally {
      window.clearTimeout(timeoutId);
      setLoadingAnswer(false);
    }
  }

  return (
    <section className="diagnosticChat">
      <header>
        <div className="diagnosticIdentity">
          <div className="diagnosticAvatar">
            <ShieldCheck size={22} />
          </div>
          <div>
            <span className="panelLabel">Orientação institucional</span>
            <h3>IA NEXUS</h3>
            <p>Canal individual desta solicitação, vinculado à IA local, para finalidade, sigilo, preservação documental e revisão humana.</p>
          </div>
        </div>
        <div className="diagnosticStatusBadge">
          <span />
          IA local
        </div>
      </header>
      <div className="diagnosticQuick">
        {quickQuestions.map((item) => (
          <button key={item} type="button" onClick={() => void askDiagnostic(item)} disabled={loadingAnswer}>
            {item}
          </button>
        ))}
      </div>
      <div className="diagnosticMessages" ref={diagnosticMessagesRef}>
        {messages.length === 0 ? (
          <div className="chatAnon emptyChat">
            <div className="messageAvatar">
              <MessageCircle size={16} />
            </div>
            <div>
              <strong>IA NEXUS</strong>
              <span>Estou conectada à IA local para orientar esta solicitação sobre o ANON, o produto anonimizado e a revisão humana obrigatória.</span>
            </div>
          </div>
        ) : (
          messages.map((message, index) => (
            <div key={index} className={message.role === "user" ? "chatUser" : "chatAnon"}>
              <div className="messageAvatar">
                {message.role === "user" ? <img className="anonymousAvatarImage" src="/anonymous-avatar.png" alt="Anonymous" /> : <MessageCircle size={16} />}
              </div>
              <div>
                <strong>{message.role === "user" ? "Anonymous" : "IA NEXUS"}</strong>
                <span>{message.text}</span>
              </div>
            </div>
          ))
        )}
        {loadingAnswer ? (
          <div className="chatAnon thinking">
            <div className="messageAvatar">
              <MessageCircle size={16} />
            </div>
            <div>
              <strong>IA NEXUS</strong>
              <span><TypingDots label="IA NEXUS respondendo" /></span>
            </div>
          </div>
        ) : null}
      </div>
      <form
        className="diagnosticForm"
        onSubmit={(event) => {
          event.preventDefault();
          void askDiagnostic(question);
        }}
      >
        <input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Fale com a IA NEXUS." />
        <button type="submit" disabled={loadingAnswer || !question.trim()}>
          {loadingAnswer ? <TypingDots label="Analisando resposta" /> : "Enviar"}
        </button>
      </form>
    </section>
  );
}

function TypingDots({ label }: { label: string }) {
  return (
    <span className="typingDots" aria-label={label} role="status">
      <span />
      <span />
      <span />
    </span>
  );
}
function AuditSeal({ result }: { result: Result }) {
  const exportEntries = Object.entries(result.audit.export_sha256);

  return (
    <section className="auditSeal">
      <div className="successStamp">DOCUMENTO PROCESSADO COM SUCESSO</div>
      <div className="auditGrid">
        <AuditItem label="Modelo" value={formatModelName(result.model)} />
        <AuditItem label="Versão ANON" value={result.audit.anon_version || "Não informada"} />
        <AuditItem label="Tempo" value={formatSeconds(result.audit.processing_time_seconds)} />
        <AuditItem label="OCR" value={result.audit.ocr_used ? "Utilizado" : "Não utilizado"} />
        <AuditItem label="Estrutura" value={result.audit.structure_preserved ? "Preservada" : "Não preservada"} />
        <AuditItem label="Validação" value={result.audit.validation_status} />
      </div>
      <section className="hashSection">
        <header>
          <span className="panelLabel">Hashes SHA-256</span>
          <strong>Integridade do arquivo original e dos produtos exportáveis</strong>
        </header>
        <AuditHash label="Hash SHA-256 original" value={result.audit.source_sha256} />
        {exportEntries.map(([format, hash]) => (
          <AuditHash key={format} label={`Hash SHA-256 ${format.toUpperCase()}`} value={hash} />
        ))}
      </section>
      <div className="auditCounters">
        <Metric label="Substituições" value={result.stats.replacements_applied} />
        <DownloadFormatsInfo formats={exportEntries.map(([format]) => format)} />
      </div>
    </section>
  );
}

function AuditItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="auditItem">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AuditHash({ label, value }: { label: string; value: string }) {
  const ready = !value.startsWith("Calculando");

  async function copyHash() {
    if (!ready) return;
    await navigator.clipboard.writeText(value);
  }

  return (
    <div className="auditHash">
      <div>
        <span>{label}</span>
        <strong>{shortHash(value)}</strong>
      </div>
      <button type="button" onClick={copyHash} disabled={!ready}>
        <Copy size={13} />
        Copiar
      </button>
    </div>
  );
}

function DownloadFormatsInfo({ formats }: { formats: string[] }) {
  const normalizedFormats = formats.map(formatExportLabel);

  return (
    <div className="downloadFormatsInfo">
      <span>Arquivos disponíveis para download</span>
      <strong>{normalizedFormats.length ? normalizedFormats.join(" · ") : "Aguardando geração"}</strong>
      <small>Os produtos são baixados com conferência prévia de SHA-256. Analise individualmente os novos arquivos gerados. Identifique qual é o melhor que sintetiza os seus dados.</small>
    </div>
  );
}

function ExportBar({ result, fileName }: { result?: Result; fileName?: string }) {
  const availableFormats = result ? Object.keys(result.audit.export_sha256) : ["pdf", "docx", "txt"];

  async function downloadExport(format: string) {
    if (!result) return;
    const expectedHash = result.audit.export_sha256[format]?.toUpperCase();
    if (!expectedHash) {
      window.alert("Hash do produto não localizado. A exportação foi bloqueada para preservar a integridade.");
      return;
    }

    const response = await fetch(`${API_URL}/api/exports/${result.job_id}/${format}`);
    if (!response.ok) {
      window.alert("Não foi possível gerar o arquivo solicitado.");
      return;
    }

    const blob = await response.blob();
    const buffer = await blob.arrayBuffer();
    const actualHash = await sha256Buffer(buffer);
    if (actualHash !== expectedHash) {
      window.alert("O hash do arquivo gerado não corresponde ao hash informado. Download bloqueado.");
      return;
    }

    const url = URL.createObjectURL(new Blob([buffer], { type: blob.type || "application/octet-stream" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = buildDownloadName(fileName || result.original_filename, format);
    anchor.rel = "noopener";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <footer className="exports">
      <div>
        <FileText size={18} />
        <span>
          <strong>Produtos gerados para download</strong>
          <small>{fileName ? `Arquivos anonimizados de ${fileName}` : "Selecione um arquivo processado para baixar o produto final."}</small>
        </span>
      </div>
      <div className="exportButtons">
        {availableFormats.map((format) => (
          <button
            key={format}
            type="button"
            disabled={!result}
            onClick={() => void downloadExport(format)}
            title={result ? formatExportTitle(format) : undefined}
          >
            <Download size={16} />
            <span>
              <strong>{formatExportLabel(format)}</strong>
              <small>{format === "avisos" ? "Documento complementar" : "Arquivo anonimizado"}</small>
            </span>
          </button>
        ))}
      </div>
    </footer>
  );
}

function InstitutionalFooter() {
  return (
    <footer className="institutionalFooter">
      <span>
        © 2026 NEXUS ANON · Uso institucional e interno · Criador e Desenvolvedor:{" "}
        <a href="https://github.com/LukasFurtado" target="_blank" rel="noreferrer">Lukas Furtado</a>
        {" "}- Polícia Civil do Estado de Pernambuco.
      </span>
      <strong>
        <a href="https://github.com/LukasFurtado/NEXUS-ANON" target="_blank" rel="noreferrer">Versão 1.8.34</a>
      </strong>
    </footer>
  );
}
function formatElapsed(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function formatRequestError(err: unknown) {
  if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
    return "Serviço local do ANON não respondeu. Reinicie o módulo local e tente processar novamente.";
  }
  return err instanceof Error ? err.message : "Erro inesperado.";
}

function explainValidationWarning(warning: string) {
  const normalized = warning.toLowerCase();

  if (normalized.includes("termos protegidos do perfil")) {
    return "O sistema percebeu que algum termo que deveria permanecer igual pode ter mudado. Confira principalmente cabeçalhos, colunas, históricos, totais e rótulos do documento.";
  }
  if (normalized.includes("ia local nao utilizada") || normalized.includes("ia local não utilizada")) {
    return "O Ollama ou o modelo selecionado não participou dessa execução. O documento foi processado pelas regras automáticas locais; verifique se o Ollama está aberto e se o modelo escolhido está instalado.";
  }
  if (normalized.includes("valores possivelmente alterados")) {
    return "O sistema encontrou diferença em valores monetários. Confira se quantias, centavos e formatação financeira foram preservados exatamente como no original.";
  }
  if (normalized.includes("datas possivelmente alteradas")) {
    return "O sistema encontrou diferença em datas. Confira se datas de movimentação, emissão, abertura, encerramento ou registro continuam corretas.";
  }
  if (normalized.includes("termo juridico") || normalized.includes("termo jurídico")) {
    return "Uma possível anonimização foi descartada porque atingiria texto jurídico ou expressão legal. Isso evita alterar fundamento, lei, artigo ou jurisprudência.";
  }
  if (normalized.includes("termo generico") || normalized.includes("termo genérico")) {
    return "Uma possível anonimização foi descartada porque parecia ser apenas um nome de campo ou tipo de documento, e não uma informação pessoal.";
  }
  if (normalized.includes("termo protegido do perfil")) {
    return "Uma possível anonimização foi descartada para não apagar estrutura do documento. Em extratos, isso normalmente envolve históricos bancários, nomes de colunas, títulos ou descrições de operação.";
  }

  return "Aviso automático de conferência. Revise o ponto indicado para confirmar se só os dados sensíveis foram substituídos e se o restante do documento foi preservado.";
}

function groupValidationWarnings(warnings: string[]) {
  const grouped = new Map<string, number>();
  warnings.forEach((warning) => grouped.set(warning, (grouped.get(warning) ?? 0) + 1));
  return Array.from(grouped.entries()).map(([warning, count]) => ({ warning, count }));
}

async function readErrorMessage(response: Response) {
  const copy = response.clone();
  try {
    const payload = await response.json();
    return payload.detail || "Falha ao anonimizar.";
  } catch {
    const text = await copy.text();
    return text || "Falha ao anonimizar.";
  }
}

function formatSeconds(value: number) {
  return `${value.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} s`;
}

function shortHash(value: string) {
  if (value.startsWith("Calculando")) return value;
  if (value.length <= 16) return value;
  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

async function sha256File(file: File) {
  const buffer = await file.arrayBuffer();
  return sha256Buffer(buffer);
}

async function sha256Buffer(buffer: ArrayBuffer) {
  const digest = await crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")
    .toUpperCase();
}

function buildDownloadName(fileName: string, format: string) {
  const cleanBase = sanitizeFileBase(fileName.replace(/\.[^.]+$/, "")) || "anonimizado";
  if (format === "avisos") return `${cleanBase}-avisos.pdf`;
  return `${cleanBase}-anonimizado.${format}`;
}

function formatExportLabel(format: string) {
  return format === "avisos" ? "AVISOS" : format.toUpperCase();
}

function formatExportTitle(format: string) {
  return format === "avisos" ? "Arquivo de avisos e validacao gerado." : `Arquivo ${format.toUpperCase()} anonimizado gerado.`;
}

function formatStageName(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function sanitizeFileBase(value: string) {
  return value.replace(/[\\/:*?"<>|]+/g, "-").trim() || "nexus-anon";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function formatModelName(value: string) {
  if (value === "NEXUS-anon:latest") return "NEXUS-anon - Qwen3 32B";
  return value;
}

function loadStoredRequests(): RequestGroup[] {
  try {
    const stored = localStorage.getItem(REQUESTS_STORAGE_KEY) ?? sessionStorage.getItem(REQUESTS_RECOVERY_KEY);
    if (!stored) return [];
    const parsed = JSON.parse(stored) as RequestGroup[];
    if (!Array.isArray(parsed)) {
      quarantineStoredRequests(stored);
      return [];
    }

    const validRequests = recoverInterruptedProcessing(parsed.filter(isValidRequestGroup));
    if (!localStorage.getItem(REQUESTS_STORAGE_KEY) && validRequests.length) {
      localStorage.setItem(REQUESTS_STORAGE_KEY, JSON.stringify(validRequests));
    }
    return validRequests;
  } catch {
    const stored = localStorage.getItem(REQUESTS_STORAGE_KEY);
    if (stored) quarantineStoredRequests(stored);
    return [];
  }
}

function quarantineStoredRequests(rawValue: string) {
  const backupKey = `${REQUESTS_STORAGE_KEY}.quarantine.${Date.now()}`;
  sessionStorage.setItem(REQUESTS_RECOVERY_KEY, rawValue);
  localStorage.setItem(backupKey, rawValue);
  localStorage.removeItem(REQUESTS_STORAGE_KEY);
}

function recoverInterruptedProcessing(groups: RequestGroup[]) {
  let changed = false;
  const nextGroups = groups.map((group) => {
    let groupChanged = false;
    const files = group.files.map((file) => {
      if (file.status !== "processando") return file;
      changed = true;
      groupChanged = true;
      return {
        ...file,
        status: "erro" as const,
        error:
          file.error ||
          "O processamento foi interrompido antes de retornar resultado ao ANON. Reprocesse o arquivo; se persistir, baixe o log de erros para auditoria."
      };
    });
    return groupChanged ? { ...group, files } : group;
  });
  return changed ? nextGroups : groups;
}

function isValidRequestGroup(value: unknown): value is RequestGroup {
  if (!value || typeof value !== "object") return false;
  const group = value as Partial<RequestGroup>;
  return (
    typeof group.id === "string" &&
    typeof group.title === "string" &&
    typeof group.createdAt === "string" &&
    typeof group.model === "string" &&
    typeof group.documentKind === "string" &&
    VALID_DOCUMENT_KINDS.has(group.documentKind) &&
    Array.isArray(group.files) &&
    group.files.every(isValidProcessedFile)
  );
}

function isValidProcessedFile(value: unknown): value is ProcessedFile {
  if (!value || typeof value !== "object") return false;
  const file = value as Partial<ProcessedFile>;
  return typeof file.id === "string" && typeof file.name === "string" && typeof file.status === "string";
}
