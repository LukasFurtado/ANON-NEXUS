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
  stats: {
    entities_found: number;
    replacements_applied: number;
    preserved_dates: number;
    preserved_values: number;
    validation_warnings: string[];
  };
  audit: {
    source_sha256: string;
    export_sha256: Record<string, string>;
    processing_time_seconds: number;
    ocr_used: boolean;
    structure_preserved: boolean;
    validation_status: string;
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
  title: string;
  createdAt: string;
  model: string;
  documentKind: string;
  files: ProcessedFile[];
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
const FALLBACK_MODELS = ["NEXUS-anon:latest", "qwen3:32b", "gemma4:31b"];
const MAX_FILES = 3;

function fileKey(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

export function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [model, setModel] = useState("NEXUS-anon:latest");
  const [documentKind, setDocumentKind] = useState("rif");
  const [requestName, setRequestName] = useState("");
  const [fileHashes, setFileHashes] = useState<Record<string, string>>({});
  const [localModels, setLocalModels] = useState<string[]>(FALLBACK_MODELS);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsStatus, setModelsStatus] = useState("Modelos locais ainda não detectados nesta sessão.");
  const [useOllama, setUseOllama] = useState(false);
  const [rulesModalOpen, setRulesModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
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
    if (!loading) return;
    setElapsedSeconds(0);
    const timer = window.setInterval(() => {
      setElapsedSeconds((value) => value + 1);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    localStorage.setItem(REQUESTS_STORAGE_KEY, JSON.stringify(requests));
  }, [requests]);

  useEffect(() => {
    void detectLocalModels();
  }, []);

  const progressLabel = useMemo(() => {
    if (loading) return "Processando solicitação localmente";
    if (selectedResult) return "Produto disponível para consulta";
    return "Aguardando documentos";
  }, [loading, selectedResult]);

  async function anonymize() {
    if (files.length === 0 || !requestName.trim()) return;

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
          setProcessingStep("Executando extração textual e regras de pré-anonimização.");
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
          setProcessingStep("Registrando produto no histórico de anonimização.");
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
        setError(err instanceof Error ? err.message : "Erro inesperado.");
      }
    } finally {
      abortControllerRef.current = null;
      setLoading(false);
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
        <UsageRulesDialog
          onAccept={() => {
            setUseOllama(true);
            setRulesModalOpen(false);
          }}
          onClose={() => setRulesModalOpen(false)}
        />
      )}

      <aside className="sidebar">
        <div className="pcpeHeader">
          <img src="/logo_pcpe_header.png" alt="Polícia Civil de Pernambuco" />
        </div>

        <div className="brand">
          <ShieldCheck size={28} />
          <div>
            <strong>NEXUS ANON</strong>
            <span>Anonimização institucional offline</span>
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
              <option value="rif">RIF / COAF</option>
              <option value="inquerito">Inquérito policial</option>
              <option value="relatorio">Relatório</option>
              <option value="oficio">Ofício</option>
              <option value="administrativo">Administrativo</option>
              <option value="auto">Automático</option>
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

        <button className="primary" disabled={files.length === 0 || !requestName.trim() || !useOllama || loading} onClick={anonymize}>
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
          <div className={`status ${loading ? "active" : ""}`}>{progressLabel}</div>
        </header>

        {error && (
          <div className="alert">
            <AlertCircle size={18} />
            {error}
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
              setSelectedGroupId(groupId);
              const group = requests.find((item) => item.id === groupId);
              setSelectedFileId(group?.files[0]?.id ?? null);
            }}
            onSelectFile={setSelectedFileId}
            onRenameGroup={renameGroup}
            onDeleteGroup={deleteGroup}
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
  onDeleteGroup
}: {
  requests: RequestGroup[];
  selectedGroup?: RequestGroup;
  selectedFile?: ProcessedFile;
  onSelectGroup: (groupId: string) => void;
  onSelectFile: (fileId: string) => void;
  onRenameGroup: (groupId: string, title: string) => void;
  onDeleteGroup: (groupId: string) => void;
}) {
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
            <span>{selectedGroup?.model}</span>
            <span>{selectedGroup?.files.length ?? 0} arquivo(s)</span>
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
                </div>
              </button>
            ))}
          </div>

          <div className="productPanel">
            {selectedFile?.error && (
              <div className="alert compact">
                <AlertCircle size={17} />
                {selectedFile.error}
              </div>
            )}

            <WorkSummary
              result={result}
              fileName={selectedFile?.name}
              status={selectedFile?.status}
              requestTitle={selectedGroup?.title}
              requestCreatedAt={selectedGroup?.createdAt}
            />

            <ExportBar result={result} fileName={selectedFile?.name} />
          </div>
        </div>
      </section>
    </section>
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
            <span>IA local: {model}</span>
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

function UsageRulesDialog({ onAccept, onClose }: { onAccept: () => void; onClose: () => void }) {
  return (
    <div className="processingOverlay" role="dialog" aria-modal="true" aria-labelledby="usage-rules-title">
      <section className="usageRulesWindow">
        <header>
          <div>
            <span className="panelLabel">Ciência obrigatória</span>
            <h2 id="usage-rules-title">Regras institucionais de uso</h2>
          </div>
          <ShieldCheck size={26} />
        </header>

        <div className="usageRulesBody">
          <p>
            O NEXUS ANON é uma ferramenta de apoio à anonimização documental, destinada ao uso institucional,
            interno e local. A confirmação abaixo registra ciência operacional antes do processamento de dados
            sensíveis, em observância à Política Institucional de Governança e Uso Responsável de Sistemas de
            Inteligência Artificial Generativa - PIGIA, instituída pela Portaria Normativa DG/PCPE nº 29/2026.
          </p>

          <ol>
            <li>Utilizar o sistema somente para finalidade institucional legítima, necessária, proporcional e compatível com as atribuições funcionais.</li>
            <li>Reconhecer que a IA possui natureza auxiliar, instrumental, preliminar e não decisória, não substituindo o juízo funcional humano.</li>
            <li>Submeter todo produto anonimizado à revisão humana qualificada antes de compartilhar, juntar, imprimir, remeter ou utilizar oficialmente.</li>
            <li>Conferir correção factual, coerência, completude, adequação jurídica ou técnica, inexistência de alucinações e ausência de exposição residual.</li>
            <li>Observar sigilo funcional, investigativo, operacional e de inteligência, proteção de dados pessoais, LGPD e normas internas de segurança da informação.</li>
            <li>Aplicar minimização de dados: processar apenas documentos necessários ao trabalho autorizado e evitar dados excedentes ou fora do escopo.</li>
            <li>Preservar integridade, autenticidade, rastreabilidade, hashes, histórico, cadeia de custódia e registros de auditoria dos documentos tratados.</li>
            <li>Não utilizar o resultado como fundamento único ou autônomo de ato administrativo, técnico-científico, operacional, apuratório ou decisório.</li>
            <li>Não usar o sistema para suprir ausência de diligência, fonte, documento, evidência, exame, fundamentação própria ou análise funcional exigível.</li>
            <li>Usar apenas ambiente local, controlado e compatível com o grau de sensibilidade dos dados; ferramentas externas não homologadas não devem receber dados sigilosos, investigativos, funcionais, operacionais ou de inteligência.</li>
            <li>Comunicar e revisar imediatamente qualquer falha, vazamento, comportamento inesperado, exposição indevida, viés relevante ou incidente relacionado ao uso de IA.</li>
          </ol>

          <div className="usageRulesWarning">
            O processamento é local e offline, mas permanece sujeito às cautelas da PIGIA: supervisão humana efetiva,
            responsabilidade funcional, segurança da informação, controle institucional, verificabilidade e vedação à
            automação decisória.
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
        `Avisos de validação: ${result.stats.validation_warnings.length}`
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
        <div className="summaryWarnings">
          {result.stats.validation_warnings.map((warning) => (
            <span key={warning}>{warning}</span>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function AuditSeal({ result }: { result: Result }) {
  const exportEntries = Object.entries(result.audit.export_sha256);

  return (
    <section className="auditSeal">
      <div className="successStamp">DOCUMENTO PROCESSADO COM SUCESSO</div>
      <div className="auditGrid">
        <AuditItem label="Modelo" value={formatModelName(result.model)} />
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
        <Metric label="Entidades" value={result.stats.entities_found} />
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

function ExportBar({ result, fileName }: { result?: Result; fileName?: string }) {
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
          <strong>{fileName || "Nenhum produto selecionado"}</strong>
          <small>Produto final disponível para download auditado por SHA-256.</small>
        </span>
      </div>
      <div className="exportButtons">
        {["pdf", "docx", "txt"].map((format) => (
          <button
            key={format}
            type="button"
            disabled={!result}
            onClick={() => void downloadExport(format)}
            title={result ? `Verifica SHA-256 antes de baixar ${format.toUpperCase()}` : undefined}
          >
            <Download size={16} />
            {format.toUpperCase()}
          </button>
        ))}
      </div>
    </footer>
  );
}

function InstitutionalFooter() {
  return (
    <footer className="institutionalFooter">
      <span>© 2026 NEXUS ANON · Uso institucional e interno · Criador: Lukas Furtado - Polícia Civil do Estado de Pernambuco.</span>
      <strong>Versão 1.5.7</strong>
    </footer>
  );
}

function formatElapsed(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
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
  const cleanBase = fileName.replace(/\.[^.]+$/, "").replace(/[\\/:*?"<>|]+/g, "-").trim() || "anonimizado";
  return `${cleanBase}-anonimizado.${format}`;
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
    const stored = localStorage.getItem(REQUESTS_STORAGE_KEY);
    if (!stored) return [];
    const parsed = JSON.parse(stored) as RequestGroup[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
