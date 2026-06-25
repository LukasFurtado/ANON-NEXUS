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
  review_items?: Array<{
    id: string;
    category: string;
    label: string;
    status: string;
    recommendation: string;
    severity: string;
    metadata?: Record<string, unknown>;
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
    ollama_json_rejection_reasons?: string[];
    ollama_failure_reason?: string | null;
    ollama_preserved_items?: number;
    post_validation_warnings?: string[];
    post_validation_score?: number | null;
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
    confidence_score?: number;
    confidence_level?: string;
    confidence_reasons?: string[];
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
    confidence_score?: number;
    confidence_level?: string;
    confidence_reasons?: string[];
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
  status: "pendente" | "processando" | "concluÃ­do" | "erro" | "cancelado";
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

type ManualCorrectionPayload = {
  original_value: string;
  entity_type: string;
  anonymous_id?: string;
};

type SystemMetrics = {
  cpu: {
    available: boolean;
    percent: number | null;
  };
  memory: {
    available: boolean;
    percent: number | null;
    used_gb: number | null;
    total_gb: number | null;
  };
  gpu: {
    available: boolean;
    label: string;
    percent: number | null;
    memory_used_gb: number | null;
    memory_total_gb: number | null;
    source?: string;
  };
};

const API_URL = "http://127.0.0.1:8000";
const REQUESTS_STORAGE_KEY = "nexus-anon.requests.v1";
const REQUESTS_RECOVERY_KEY = "nexus-anon.requests.recovery.v1";
const FALLBACK_MODELS = ["qwen3:32b"];
const MAX_FILES = 3;
const VALID_DOCUMENT_KINDS = new Set(["rif", "extrato_bancario", "relatorio_investigativo"]);
const LOCAL_AI_PROCESSING_MESSAGES = [
  "Preparando o documento para leitura local e identificacao segura do formato.",
  "Extraindo o texto preservando a ordem original das informacoes sempre que possivel.",
  "Conferindo padroes de CPF, CNPJ, nomes, contas, PIX, telefones e demais identificadores.",
  "Aplicando regras especificas do perfil documental selecionado pelo operador.",
  "Avaliando entidades sensiveis sem enviar dados para a internet.",
  "Cruzando regras deterministicas, perfil documental e resposta da IA local.",
  "Preservando a consistencia dos marcadores entre entidades repetidas.",
  "Protegendo datas, valores, colunas e estrutura documental contra alteracoes indevidas.",
  "Comparando identificadores pessoais e empresariais com regras de preservacao.",
  "Verificando se ha termos institucionais que nao devem ser anonimizados.",
  "Construindo tabela de controle interno para rastreabilidade da anonimizacao.",
  "Conferindo se a substituicao foi aplicada sem reescrever o conteudo tecnico.",
  "Avaliando possiveis avisos para revisao humana obrigatoria.",
  "Calculando hashes SHA-256 para controle de integridade dos produtos gerados.",
  "Gerando produtos exportaveis conforme o perfil e o formato do arquivo.",
  "Documentos extensos podem exigir mais tempo conforme memoria, processador e GPU disponiveis.",
  "O sistema prioriza substituicao controlada, sem resumir, interpretar ou reescrever o conteudo.",
  "A etapa atual pode variar conforme o tamanho do arquivo e a resposta do modelo local.",
  "Ao final, revise manualmente o produto antes de qualquer uso institucional externo.",
  "Finalizando registros de auditoria, avisos e rastreabilidade da solicitacao."
];

const NEXUS_QUICK_PROMPTS = [
  "Qual e a finalidade do ANON?",
  "O que devo revisar ao final?",
  "Como conferir um RIF?",
  "Como conferir extrato bancario?",
  "O que fazer se algo nao foi anonimizado?",
  "O que significa produto interno e externo?"
];

const ENTITY_MARKER_PREFIXES: Record<string, string> = {
  PERSON: "PESSOA",
  CPF: "CPF",
  CNPJ: "CNPJ",
  ORGANIZATION: "EMPRESA",
  BANK_ACCOUNT: "CONTA",
  PIX: "PIX",
  ADDRESS: "ENDERECO",
  PHONE: "TELEFONE",
  EMAIL: "EMAIL",
  OTHER_IDENTIFIER: "IDENTIFICADOR"
};

function fileKey(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

export function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [model, setModel] = useState("qwen3:32b");
  const [documentKind, setDocumentKind] = useState("");
  const [requestName, setRequestName] = useState("");
  const [fileHashes, setFileHashes] = useState<Record<string, string>>({});
  const [syncPackage, setSyncPackage] = useState<File | null>(null);
  const [localModels, setLocalModels] = useState<string[]>(FALLBACK_MODELS);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsStatus, setModelsStatus] = useState("Modelos locais ainda nÃ£o detectados nesta sessÃ£o.");
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
  const syncPackageInputRef = useRef<HTMLInputElement | null>(null);
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
    if (loading) return "Processando solicitaÃ§Ã£o localmente";
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
      title: requestName.trim() || `SolicitaÃ§Ã£o ${requests.length + 1}`,
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
        setProcessingStep("Preparando arquivo para anÃ¡lise local.");
        updateFile(groupId, fileId, { status: "processando" });

        const form = new FormData();
        form.append("file", file);
        form.append("document_kind", documentKind);
        form.append("model", model);
        form.append("use_ollama", String(useOllama));
        form.append("request_title", initialGroup.title);
        if (syncPackage) {
          form.append("sync_package", syncPackage);
        }

        try {
          setProcessingStep("Executando IA local obrigatÃ³ria, extraÃ§Ã£o textual e regras de apoio.");
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
          setProcessingStep("Registrando produto no HistÃ³rico de anonimizaÃ§Ã£o.");
          updateFile(groupId, fileId, { status: "concluÃ­do", result });
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
        setError("Processamento cancelado pelo usuÃ¡rio.");
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
      setSyncPackage(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      if (syncPackageInputRef.current) {
        syncPackageInputRef.current.value = "";
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
      title: requestName.trim() || `SolicitaÃ§Ã£o ${requests.length + 1}`,
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
      setProcessingStep("Preparando lote e dicionÃ¡rio Ãºnico de substituiÃ§Ãµes.");
      initialGroup.files.forEach((file) => updateFile(groupId, file.id, { status: "processando" }));

      const form = new FormData();
      files.forEach((file) => form.append("files", file));
      form.append("document_kind", documentKind);
      form.append("model", model);
      form.append("use_ollama", String(useOllama));
      form.append("request_title", initialGroup.title);
      if (syncPackage) {
        form.append("sync_package", syncPackage);
      }

      setProcessingStep("Executando IA local obrigatÃ³ria com consistÃªncia entre arquivos e regras de apoio.");
      const response = await fetch(`${API_URL}/api/anonymize-batch`, {
        method: "POST",
        body: form,
        signal: controller.signal
      });
      setProcessingStep("Conferindo hashes, exportaÃ§Ãµes e log de auditoria do conjunto.");
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
                  status: payload.results[index] ? "concluÃ­do" : "erro",
                  result: payload.results[index],
                  error: payload.results[index] ? undefined : "Resultado nÃ£o retornado pelo processamento em lote."
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
      setSyncPackage(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      if (syncPackageInputRef.current) {
        syncPackageInputRef.current.value = "";
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
      setError(`Limite de ${MAX_FILES} arquivos por solicitaÃ§Ã£o. Remova algum arquivo antes de anexar outro.`);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      return;
    }

    if (newFiles.length === 0 && selectedFiles.length > 0) {
      setError("Este arquivo jÃ¡ foi anexado nesta solicitaÃ§Ã£o.");
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
      `Excluir a solicitaÃ§Ã£o "${group?.title || "selecionada"}" Esta aÃ§Ã£o nÃ£o pode ser revertida.`
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
      window.alert("Log de processamento ainda nÃ£o disponÃ­vel para esta solicitaÃ§Ã£o.");
      return;
    }
    const response = await fetch(`${API_URL}/api/exports/groups/${group.backendGroupId}/log`);
    if (!response.ok) {
      window.alert("NÃ£o foi possÃ­vel baixar o log do conjunto.");
      return;
    }
    const blob = await response.blob();
    const buffer = await blob.arrayBuffer();
    const actualHash = await sha256Buffer(buffer);
    if (actualHash !== group.logSha256.toUpperCase()) {
      window.alert("O hash do log nÃ£o corresponde ao registro informado. Download bloqueado.");
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

  async function applyManualCorrection(groupId: string, fileId: string, corrections: ManualCorrectionPayload[]) {
    const group = requests.find((item) => item.id === groupId);
    const file = group?.files.find((item) => item.id === fileId);
    if (!file?.result) return undefined;
    const response = await fetch(`${API_URL}/api/jobs/${file.result.job_id}/manual-reanalysis`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        corrections,
        note: "Correcao manual dirigida pelo operador."
      })
    });
    if (!response.ok) {
      window.alert(await readErrorMessage(response));
      return undefined;
    }
    const result = (await response.json()) as Result;
    updateFile(groupId, fileId, { result, status: "concluÃ­do" });
    return result;
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
          : "Ollama nÃ£o respondeu. Lista padrÃ£o mantida."
      );
    } catch (err) {
      setLocalModels(FALLBACK_MODELS);
      setModelsStatus(err instanceof Error ? err.message : "NÃ£o foi possÃ­vel detectar modelos locais.");
    } finally {
      setModelsLoading(false);
    }
  }

  function handleDrop(event: React.DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    void setFilesFromList(event.dataTransfer.files);
  }

  function handleSyncPackageChange(fileList: FileList | null) {
    const file = fileList?.[0] || null;
    if (!file) {
      setSyncPackage(null);
      return;
    }
    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith(".json") && !lowerName.endsWith(".txt")) {
      setError("O pacote de sincronizacao deve ser um arquivo JSON do ANON ou log TXT de reanalise dirigida.");
      if (syncPackageInputRef.current) {
        syncPackageInputRef.current.value = "";
      }
      return;
    }
    setSyncPackage(file);
    setError(null);
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
          <img src="/logo_pcpe_header.png" alt="PolÃ­cia Civil de Pernambuco" />
        </div>

        <div className="brand">
          <ShieldCheck size={28} />
          <div>
            <strong>ANON</strong>
            <span>Anonimizador institucional offline de arquivos</span>
          </div>
        </div>

        <nav className="sideNav" aria-label="NavegaÃ§Ã£o principal">
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
            SolicitaÃ§Ãµes
          </button>
        </nav>

        <label
          className="dropzone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
        >
          <UploadCloud size={34} />
          <strong>{files.length > 0 ? `${files.length} arquivo(s) selecionado(s)` : "Arraste os documentos"}</strong>
          <span>Ã‰ possÃ­vel inserir atÃ© 3 arquivos. Recomenda-se mesma extensÃ£o e mesmo trabalho investigativo.</span>
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
                  <span>Pronto para anonimizaÃ§Ã£o</span>
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
            NÃºmero IP / Nome solicitaÃ§Ã£o
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
            Perfil documental estratÃ©gico
            <select value={documentKind} onChange={(event) => setDocumentKind(event.target.value)}>
              <option value="" disabled>Selecione o perfil documental</option>
              <option value="rif">RIF / COAF</option>
              <option value="extrato_bancario">Extrato bancÃ¡rio</option>
              <option value="relatorio_investigativo">RelatÃ³rio investigativo</option>
            </select>
            <small className="modelStatus">Altera prompt local, regras regex e critÃ©rios de validaÃ§Ã£o.</small>
          </label>

          <div className="syncPackageBox">
            <div>
              <span className="panelLabel">SincronizaÃ§Ã£o de anonimizaÃ§Ã£o</span>
              <strong>{syncPackage ? syncPackage.name : "Nenhum pacote vinculado"}</strong>
              <small>Use pacote de uma anonimizaÃ§Ã£o anterior para manter os mesmos marcadores em nova demanda.</small>
            </div>
            <input
              ref={syncPackageInputRef}
              type="file"
              accept=".json,.txt"
              onChange={(event) => handleSyncPackageChange(event.target.files)}
              disabled={loading}
            />
            {syncPackage ? (
              <button
                type="button"
                onClick={() => {
                  setSyncPackage(null);
                  if (syncPackageInputRef.current) syncPackageInputRef.current.value = "";
                }}
                disabled={loading}
              >
                <XCircle size={14} />
                Remover
              </button>
            ) : null}
          </div>

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
          <span>Processamento 100% local. Nenhum documento Ã© enviado para a internet.</span>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <span className="eyebrow">
              {activeView === "solicitacoes" ? "Consulta de solicitaÃ§Ãµes" : "Fluxo operacional"}
            </span>
            <h1>
              {activeView === "solicitacoes" ? "HistÃ³rico de anonimizaÃ§Ã£o" : "AnonimizaÃ§Ã£o Forense de Documentos"}
            </h1>
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
            onManualCorrection={(groupId, fileId, corrections) => applyManualCorrection(groupId, fileId, corrections)}
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
        summaryLabel="Resumo operacional - Ãšltima solicitaÃ§Ã£o"
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
        Os hashes abaixo sÃ£o calculados localmente antes da anonimizaÃ§Ã£o. Eles servem para controle interno, conferÃªncia de integridade e rastreabilidade da solicitaÃ§Ã£o.
      </p>
      {files.length > 0 ? (
        <div className="integrityFiles">
          {files.map((file) => (
            <AuditHash
              key={fileKey(file)}
              label={`SHA-256 original Â· ${file.name}`}
              value={fileHashes[fileKey(file)] || "Calculando hash..."}
            />
          ))}
        </div>
      ) : (
        <div className="integrityEmpty">Nenhum arquivo anexado para cÃ¡lculo de hash.</div>
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
  onDownloadErrorLog,
  onManualCorrection
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
  onManualCorrection: (groupId: string, fileId: string, corrections: ManualCorrectionPayload[]) => Promise<Result | undefined>;
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
        <h2>Nenhuma solicitaÃ§Ã£o registrada</h2>
        <p>Envie um ou mais arquivos para criar um grupo de anonimizaÃ§Ã£o consultÃ¡vel.</p>
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
                {group.files.length} arquivo(s) Â· {formatDate(group.createdAt)}
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
                aria-label="Renomear solicitaÃ§Ã£o"
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
            <ManualReanalysisPanel
              selectedGroup={selectedGroup}
              selectedFile={selectedFile}
              onManualCorrection={onManualCorrection}
            />

            <ExportBar result={result} fileName={selectedFile?.name} />
          </div>
        </div>
      </section>
      {qualityModal ? <QualityModal data={qualityModal} onClose={() => setQualityModal(null)} /> : null}
    </section>
  );
}

function ManualReanalysisPanel({
  selectedGroup,
  selectedFile,
  onManualCorrection
}: {
  selectedGroup?: RequestGroup;
  selectedFile?: ProcessedFile;
  onManualCorrection: (groupId: string, fileId: string, corrections: ManualCorrectionPayload[]) => Promise<Result | undefined>;
}) {
  const [value, setValue] = useState("");
  const [entityType, setEntityType] = useState("PERSON");
  const [anonymousId, setAnonymousId] = useState("");
  const [corrections, setCorrections] = useState<ManualCorrectionPayload[]>([]);
  const [reprocessing, setReprocessing] = useState(false);
  const [lastResult, setLastResult] = useState<Result | null>(null);
  const builtAnonymousId = buildManualAnonymousId(entityType, anonymousId);
  const canAdd = Boolean(value.trim() && anonymousId.trim());
  const canReprocess = Boolean(selectedGroup && selectedFile?.result && corrections.length > 0 && !reprocessing);

  useEffect(() => {
    setCorrections([]);
    setLastResult(null);
    setValue("");
    setAnonymousId("");
  }, [selectedFile?.id]);

  function addCorrection(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canAdd) return;
    const nextCorrection = {
      original_value: value.trim(),
      entity_type: entityType,
      anonymous_id: builtAnonymousId
    };
    setCorrections((items) => {
      const exists = items.some((item) => item.original_value.toLowerCase() === nextCorrection.original_value.toLowerCase());
      return exists ? items : [...items, nextCorrection];
    });
    setValue("");
    setAnonymousId("");
  }

  async function runReanalysis() {
    if (!canReprocess || !selectedGroup || !selectedFile) return;
    setReprocessing(true);
    setLastResult(null);
    try {
      const result = await onManualCorrection(selectedGroup.id, selectedFile.id, corrections);
      if (result) {
        setLastResult(result);
        setCorrections([]);
      }
    } finally {
      setReprocessing(false);
    }
  }

  const latestResult = lastResult || selectedFile?.result;
  const downloadFormat = latestResult?.audit.export_sha256.pdf ? "pdf" : Object.keys(latestResult?.audit.export_sha256 || {}).find(isExternalProductFormat);
  const hasReanalysisLog = Boolean(lastResult?.audit.export_sha256.reanalise_log);

  return (
    <section className="manualReanalysisPanel">
      {reprocessing ? <ReanalysisLoadingDialog total={corrections.length} /> : null}
      <header>
        <div>
          <span className="panelLabel">Reanalise dirigida</span>
          <strong>Correcao controlada pelo operador</strong>
        </div>
      </header>
      <p>
        Use quando identificar nome, documento ou outro dado sensivel que permaneceu no produto. O ANON regenera uma nova versao com hash proprio, sem alterar o registro original.
      </p>
      <div className="manualReanalysisNotice">
        <AlertCircle size={16} />
        <span>Informe o texto EXATAMENTE como consta no documento. Diferencas de espaco, acento, pontuacao ou abreviacao podem impedir a substituicao.</span>
      </div>
      <form onSubmit={addCorrection}>
        <label>
          Valor sensivel encontrado
          <input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="Ex.: AYLA DE ARAUJO BESERRA"
          />
        </label>
        <label>
          Tipo
          <select value={entityType} onChange={(event) => setEntityType(event.target.value)}>
            <option value="PERSON">Pessoa</option>
            <option value="CPF">CPF</option>
            <option value="CNPJ">CNPJ</option>
            <option value="ORGANIZATION">Empresa</option>
            <option value="BANK_ACCOUNT">Conta bancaria</option>
            <option value="PIX">PIX</option>
            <option value="ADDRESS">Endereco</option>
            <option value="PHONE">Telefone</option>
            <option value="EMAIL">E-mail</option>
            <option value="OTHER_IDENTIFIER">Outro identificador</option>
          </select>
        </label>
        <label>
          Numero, letra ou termo do marcador
          <input
            value={anonymousId}
            onChange={(event) => setAnonymousId(event.target.value)}
            placeholder="Ex.: 123, A, ALVO_01"
          />
          <small className="manualMarkerPreview">
            Substituicao: {builtAnonymousId || `[${ENTITY_MARKER_PREFIXES[entityType] || "DADO"}_...]`}
          </small>
        </label>
        <button type="submit" disabled={!canAdd}>
          <CheckCircle2 size={16} />
          Adicionar termo
        </button>
      </form>

      {corrections.length ? (
        <div className="manualCorrectionQueue">
          <strong>{corrections.length} termo(s) preparado(s) para reanalise</strong>
          <div>
            {corrections.map((item, index) => (
              <span key={`${item.original_value}-${index}`}>
                <b>{item.original_value}</b>
                <small>{item.entity_type}{item.anonymous_id ? ` -> ${item.anonymous_id}` : ""}</small>
                <button
                  type="button"
                  onClick={() => setCorrections((items) => items.filter((_, itemIndex) => itemIndex !== index))}
                  aria-label="Remover termo da reanalise"
                >
                  <XCircle size={13} />
                </button>
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <div className="manualReanalysisActions">
        <button type="button" disabled={!canReprocess} onClick={() => void runReanalysis()}>
          <RefreshCw size={16} />
          {reprocessing ? "Providenciando..." : "Reprocessar tudo"}
        </button>
        {lastResult && downloadFormat ? (
          <button
            type="button"
            className="manualDownloadButton"
            onClick={() => void downloadResultProduct(lastResult, downloadFormat, selectedFile?.name)}
          >
            <Download size={16} />
            Baixar novo {formatExportLabel(downloadFormat)}
          </button>
        ) : null}
        {lastResult && hasReanalysisLog ? (
          <button
            type="button"
            className="manualLogDownloadButton"
            onClick={() => void downloadResultProduct(lastResult, "reanalise_log", selectedFile?.name)}
          >
            <Download size={16} />
            Baixar log da reanalise
          </button>
        ) : null}
      </div>
    </section>
  );
}

function ReanalysisLoadingDialog({ total }: { total: number }) {
  return (
    <div className="reanalysisLoadingBackdrop" role="dialog" aria-modal="true">
      <section className="reanalysisLoadingBox">
        <RefreshCw size={22} />
        <div>
          <span className="panelLabel">Reanalise dirigida</span>
          <h3>Providenciando novo produto</h3>
          <p>O ANON esta aplicando {total} termo(s) informado(s), regenerando os arquivos e calculando novos hashes.</p>
        </div>
        <TypingDots label="Reprocessamento em andamento" />
      </section>
    </div>
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
            <span className="panelLabel">ClassificaÃ§Ã£o automÃ¡tica</span>
            <h3>{qualityLabel(data.status)}</h3>
          </div>
          <button type="button" onClick={onClose} aria-label="Fechar classificaÃ§Ã£o">
            <XCircle size={18} />
          </button>
        </header>
        <p>
          Este selo resume a conferÃªncia automÃ¡tica do ANON. Ele nÃ£o substitui a revisÃ£o humana obrigatÃ³ria,
          mas indica se o produto exige atenÃ§Ã£o adicional antes de qualquer uso institucional.
        </p>
        <div className="qualityScore">
          <span>PontuaÃ§Ã£o</span>
          <strong>{typeof data.score === "number" ? `${data.score}/100` : "NÃ£o informada"}</strong>
        </div>
        <ul>
          {(data.reasons.length ? data.reasons : ["Nenhum motivo especÃ­fico informado."]).map((reason) => (
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
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [aiMessageIndex, setAiMessageIndex] = useState(0);

  useEffect(() => {
    let mounted = true;
    const loadMetrics = async () => {
      try {
        const response = await fetch(`${API_URL}/api/system-metrics`);
        if (!response.ok) return;
        const payload = (await response.json()) as SystemMetrics;
        if (mounted) setMetrics(payload);
      } catch {
        if (mounted) setMetrics((current) => current);
      }
    };

    void loadMetrics();
    const timer = window.setInterval(() => {
      void loadMetrics();
    }, 2200);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setAiMessageIndex((index) => (index + 1) % LOCAL_AI_PROCESSING_MESSAGES.length);
    }, 4300);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="processingOverlay" role="dialog" aria-modal="true">
      <section className="processingWindow">
        <header>
          <div>
            <span className="panelLabel">Processamento local</span>
            <h2>Processando solicitaÃ§Ã£o, aguarde.</h2>
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
            <span>IdentificaÃ§Ã£o do formato</span>
            <span>ExtraÃ§Ã£o textual</span>
            <span>Reconhecimento por regex</span>
            <span>IA local obrigatÃ³ria: {model}</span>
            <span>ValidaÃ§Ã£o e exportaÃ§Ã£o</span>
          </div>

          <div className="progressTrack">
            <div />
          </div>

          <div className="processingStepText">
            <RefreshCw size={15} />
            <div>
              <span key={aiMessageIndex} className="processingRotatingMessage">
                {LOCAL_AI_PROCESSING_MESSAGES[aiMessageIndex]}
              </span>
            </div>
          </div>

          <ResourceUsagePanel metrics={metrics} />

          <div className="processingNotice">
            Arquivos extensos podem exigir mais tempo de processamento. VocÃª pode aguardar com tranquilidade enquanto a anÃ¡lise local Ã© concluÃ­da.
          </div>

          <div className="processingWarning">
            Este procedimento pode demandar elevado poder computacional, especialmente em documentos extensos ou com mÃºltiplos arquivos. Recomenda-se a execuÃ§Ã£o em equipamento com recursos adequados de memÃ³ria, processador e capacidade de inferÃªncia local.
          </div>
        </div>

        <footer>
          <p>Nenhum dado sai deste computador. O processamento usa apenas serviÃ§os locais.</p>
          <button className="cancelButton" onClick={onCancel}>
            <XCircle size={18} />
            Cancelar
          </button>
        </footer>
      </section>
    </div>
  );
}

function ResourceUsagePanel({ metrics }: { metrics: SystemMetrics | null }) {
  const cpuPercent = metrics?.cpu.available ? metrics.cpu.percent : null;
  const memoryPercent = metrics?.memory.available ? metrics.memory.percent : null;
  const gpuPercent = metrics?.gpu.available ? metrics.gpu.percent : null;
  const memoryDetails =
    metrics?.memory.available && metrics.memory.used_gb !== null && metrics.memory.total_gb !== null
      ? `${metrics.memory.used_gb.toLocaleString("pt-BR")} GB de ${metrics.memory.total_gb.toLocaleString("pt-BR")} GB`
      : "Aguardando leitura local";
  const gpuDetails = gpuDetailText(metrics);

  return (
    <section className="resourceUsagePanel" aria-label="Uso local de recursos">
      <div className="resourceUsageHeader">
        <span>Monitor local de recursos</span>
        <strong>{metrics ? "tempo real" : "conectando"}</strong>
      </div>
      <div className="resourceUsageGrid">
        <ResourceMeter label="Processador" value={cpuPercent} detail="Uso atual da CPU" />
        <ResourceMeter label="GPU" value={gpuPercent} detail={gpuDetails} unavailable={metrics ? !metrics.gpu.available : false} />
        <ResourceMeter label="MemÃ³ria" value={memoryPercent} detail={memoryDetails} />
      </div>
    </section>
  );
}

function gpuDetailText(metrics: SystemMetrics | null) {
  if (!metrics) return "Aguardando leitura local";
  if (!metrics.gpu.available) return "GPU nao detectada ou sem permissao de leitura local";
  if (metrics.gpu.memory_used_gb !== null && metrics.gpu.memory_total_gb !== null) {
    return `${metrics.gpu.label} - ${metrics.gpu.memory_used_gb.toLocaleString("pt-BR")} GB de ${metrics.gpu.memory_total_gb.toLocaleString("pt-BR")} GB`;
  }
  if (metrics.gpu.memory_total_gb !== null) {
    return `${metrics.gpu.label} - memoria dedicada informada: ${metrics.gpu.memory_total_gb.toLocaleString("pt-BR")} GB`;
  }
  return `${metrics.gpu.label} - GPU detectada; memoria dedicada sem leitura disponivel`;
}

function ResourceMeter({
  label,
  value,
  detail,
  unavailable = false
}: {
  label: string;
  value: number | null | undefined;
  detail: string;
  unavailable?: boolean;
}) {
  const safeValue = typeof value === "number" ? Math.max(0, Math.min(100, value)) : 0;
  const displayedValue = typeof value === "number" ? `${value.toLocaleString("pt-BR")}%` : unavailable ? "IndisponÃ­vel" : "Lendo";

  return (
    <div className="resourceMeter">
      <div className="resourceMeterTop">
        <span>{label}</span>
        <strong>{displayedValue}</strong>
      </div>
      <div className="resourceMeterTrack">
        <div style={{ width: `${safeValue}%` }} />
      </div>
      <small>{detail}</small>
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
          text: "IA NEXUS ativa. Aguarde a conclusÃ£o da solicitaÃ§Ã£o e realize revisÃ£o humana antes de qualquer uso externo.",
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

  function askNexusQuick(prompt: string) {
    const answer = nexusLocalAnswer(prompt, {
      loading,
      processingStep,
      elapsedSeconds,
      fileName,
      selectedResult,
      selectedFile,
      selectedGroup
    }) || "A orientacao principal e revisar manualmente o produto final, confirmar se apenas identificadores sensiveis foram substituidos e preservar valores, datas, estrutura e finalidade institucional.";
    setMessages((items) => [
      ...items.slice(-6),
      { role: "user", text: prompt },
      { role: "nexus", text: answer, tone: "info" }
    ]);
  }

  async function askNexus(text: string) {
    return;
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
    }) ?? "";
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
        body: JSON.stringify({
          question: trimmed,
          profile: selectedResult?.safe_summary?.profile || selectedGroup?.documentKind || "",
          document_id: selectedResult?.audit.safe_summary_id || selectedResult?.audit.source_sha256 || ""
        })
      });
      const payload = await response.json();
      setMessages((items) => [...items.slice(-7), { role: "nexus", text: payload.answer || "OrientaÃ§Ã£o institucional indisponÃ­vel neste momento.", tone: "info" }]);
    } catch {
      const canceledByOperator = timeoutController.signal.aborted && nexusAnswerCanceledByOperatorRef.current;
      setMessages((items) => [
        ...items.slice(-7),
        {
          role: "nexus",
          text: canceledByOperator
            ? "Envio da ?ltima mensagem cancelado pelo operador."
            : "Este canal Ã© restrito a orientaÃ§Ãµes institucionais de uso, revisÃ£o e finalidade da anonimizaÃ§Ã£o.",
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
              <span className="panelLabel">ObservaÃ§Ã£o operacional</span>
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
            <strong>{loading ? "Acompanhando solicitaÃ§Ã£o" : "OrientaÃ§Ã£o institucional"}</strong>
            <span>{loading ? `Tempo decorrido: ${formatElapsed(elapsedSeconds)}` : "Canal restrito a finalidade, sigilo e revisÃ£o humana."}</span>
          </div>

          <div className="nexusAssistantMessages" ref={nexusMessagesRef}>
            {messages.length === 0 ? (
              <p>Estou pronta para orientar sobre finalidade da anonimizaÃ§Ã£o, sigilo, preservaÃ§Ã£o documental e revisÃ£o humana.</p>
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

          <div className="nexusQuickPrompts" aria-label="Perguntas rapidas da IA NEXUS">
            {NEXUS_QUICK_PROMPTS.map((prompt) => (
              <button key={prompt} type="button" onClick={() => askNexusQuick(prompt)}>
                {prompt}
              </button>
            ))}
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
              placeholder="Fale com a IA NEXUS, em breve..."
              disabled
            />
            <button type="submit" disabled>
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
    return "A solicitaÃ§Ã£o foi recebida. Aguarde a conclusÃ£o e mantenha a revisÃ£o humana como etapa obrigatÃ³ria.";
  }
  if (normalized.includes("ia local")) {
    return "A anonimizaÃ§Ã£o estÃ¡ em andamento. O tempo pode variar conforme o tamanho do material e a capacidade do computador.";
  }
  if (normalized.includes("hash") || normalized.includes("export")) {
    return "A solicitaÃ§Ã£o estÃ¡ sendo finalizada para disponibilizaÃ§Ã£o do produto de revisÃ£o.";
  }
  if (normalized.includes("hist")) {
    return "O resultado serÃ¡ disponibilizado no histÃ³rico da solicitaÃ§Ã£o para conferÃªncia institucional.";
  }
  return "A solicitaÃ§Ã£o permanece em andamento. Aguarde a conclusÃ£o antes de revisar o produto final.";
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
    return "Este canal Ã© restrito a orientaÃ§Ãµes institucionais de uso, revisÃ£o e finalidade da anonimizaÃ§Ã£o. QuestÃµes tÃ©cnicas devem ser tratadas pelos instrumentos formais de auditoria e suporte.";
  }
  if (normalized.includes("rif") || normalized.includes("coaf") || normalized.includes("financeir")) {
    return "Em RIF e dados financeiros, o objetivo Ã© substituir identificadores sensÃ­veis mantendo valores, datas, movimentaÃ§Ãµes, estrutura e coerÃªncia analÃ­tica.";
  }
  if (normalized.includes("extrato") || normalized.includes("banc")) {
    return "Em extratos bancÃ¡rios, revise se a sequÃªncia dos lanÃ§amentos, datas, valores e saldos permaneceu preservada, com substituiÃ§Ã£o apenas de identificadores sensÃ­veis.";
  }
  if (normalized.includes("nao foi anonimizado") || normalized.includes("nÃ£o foi anonimizado") || normalized.includes("algo nao") || normalized.includes("algo nÃ£o")) {
    return "Se um dado sensivel permanecer visivel, use a reanalise dirigida no historico do arquivo: informe o valor encontrado, escolha o tipo da entidade e gere novo produto com hash proprio.";
  }
  if (normalized.includes("interno") || normalized.includes("externo")) {
    return "Produto externo e o arquivo anonimizado destinado a revisao humana e eventual compartilhamento. Produto interno contem auditoria, avisos, controle e rastreabilidade, devendo permanecer restrito.";
  }
  if (normalized.includes("revis") || normalized.includes("confer") || normalized.includes("compartilh")) {
    return "Antes de compartilhar, confira manualmente se nomes, documentos, contas, endereÃ§os, contatos e demais identificadores foram substituÃ­dos sem alteraÃ§Ã£o indevida do conteÃºdo preservado.";
  }
  if (normalized.includes("sigilo") || normalized.includes("seguran") || normalized.includes("uso")) {
    return "O uso deve permanecer institucional, local e controlado, observando sigilo, finalidade, necessidade, rastreabilidade e revisÃ£o humana qualificada.";
  }
  if (normalized.includes("objetivo") || normalized.includes("serve") || normalized.includes("finalidade") || normalized.includes("anon")) {
    return "A finalidade do ANON Ã© apoiar a anonimizaÃ§Ã£o documental, substituindo identificadores sensÃ­veis por marcadores consistentes e preservando o conteÃºdo tÃ©cnico, jurÃ­dico e financeiro.";
  }
  return null;
}

function UsageRulesDialogV3({ onAccept, onClose }: { onAccept: () => void; onClose: () => void }) {
  return (
    <div className="processingOverlay" role="dialog" aria-modal="true" aria-labelledby="usage-rules-title">
      <section className="usageRulesWindow">
        <header>
          <div>
            <span className="panelLabel">CiÃªncia obrigatÃ³ria</span>
            <h2 id="usage-rules-title">âš  Regras institucionais de uso e Avisos âš </h2>
          </div>
          <ShieldCheck size={26} />
        </header>

        <div className="usageRulesBody">
          <div className="usageRulesIntro">
            <p>
              O NEXUS ANON Ã© uma ferramenta local de apoio Ã  anonimizaÃ§Ã£o documental para uso institucional, interno
              e controlado. A ciÃªncia abaixo reforÃ§a deveres de sigilo, proteÃ§Ã£o de dados, rastreabilidade, revisÃ£o
              humana e uso responsÃ¡vel de sistemas de inteligÃªncia artificial.
            </p>
            <img src="/logo_pcpe_header.png" alt="PolÃ­cia Civil de Pernambuco" />
          </div>

          <ol>
            <li>Utilizar o sistema somente para finalidade institucional legÃ­tima, necessÃ¡ria, proporcional e vinculada Ã  atividade funcional autorizada.</li>
            <li>Manter o tratamento de documentos em ambiente local, controlado e compatÃ­vel com o grau de sigilo, sem envio de dados sensÃ­veis a serviÃ§os externos nÃ£o homologados.</li>
            <li>Preservar hashes, histÃ³rico, registros de processamento e demais elementos necessÃ¡rios Ã  rastreabilidade, auditoria e cadeia de custÃ³dia.</li>
            <li>Reconhecer que a IA possui natureza auxiliar, preliminar e nÃ£o decisÃ³ria, nÃ£o substituindo anÃ¡lise jurÃ­dica, tÃ©cnica ou funcional humana.</li>
            <li>Revisar o produto anonimizado antes de compartilhar, juntar, imprimir, remeter ou utilizar oficialmente, conferindo se nÃ£o houve exposiÃ§Ã£o residual ou alteraÃ§Ã£o indevida de conteÃºdo preservado.</li>
            <li className="criticalRule">O programa ainda estÃ¡ em fase de testes e pode apresentar erros de identificaÃ§Ã£o, omissÃ£o ou classificaÃ§Ã£o. A revisÃ£o humana qualificada Ã© imprescindÃ­vel.</li>
            <li>Quando a IA ou as regras automÃ¡ticas nÃ£o anonimizarem determinado dado sensÃ­vel, a anonimizaÃ§Ã£o manual deve ser realizada antes de qualquer uso externo ou oficial do produto.</li>
          </ol>

          <div className="usageRulesWarning">
            O processamento local reduz riscos de exposiÃ§Ã£o, mas nÃ£o elimina a responsabilidade funcional do operador
            pela conferÃªncia, ValidaÃ§Ã£o e seguranÃ§a do documento final.
          </div>
        </div>

        <footer>
          <button className="secondaryButton" type="button" onClick={onClose}>
            Voltar
          </button>
          <button className="primary acceptRulesButton" type="button" onClick={onAccept}>
            <ShieldCheck size={17} />
            Declaro ciÃªncia e concordo
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
        `SolicitaÃ§Ã£o: ${requestTitle || "NÃ£o informada"}`,
        `Arquivo: ${fileName || result.original_filename}`,
        `Status: ${status || "concluÃ­do"}`,
        `Modelo: ${result.model}`,
        `Tempo: ${formatSeconds(result.audit.processing_time_seconds)}`,
        `OCR: ${result.audit.ocr_used ? "Utilizado" : "NÃ£o utilizado"}`,
        `Estrutura: ${result.audit.structure_preserved ? "Preservada" : "NÃ£o preservada"}`,
        `ValidaÃ§Ã£o: ${result.audit.validation_status}`,
        `Hash SHA-256 original: ${result.audit.source_sha256}`,
        `Entidades identificadas: ${result.stats.entities_found}`,
        `SubstituiÃ§Ãµes aplicadas: ${result.stats.replacements_applied}`,
        ...Object.entries(result.audit.export_sha256).map(([format, hash]) => `Hash SHA-256 ${format.toUpperCase()}: ${hash}`),
        `Avisos de ValidaÃ§Ã£o: ${result.stats.validation_warnings.length}`
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
          {requestCreatedAt ? <p className="summaryDate">Solicita??o registrada em {formatDate(requestCreatedAt)}</p> : null}
          <h2>{requestTitle || fileName || "Produto ainda nÃ£o disponÃ­vel"}</h2>
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
        <>
          <AuditSeal result={result} />
          <PipelineStatePanel result={result} />
        </>
      ) : (
        <p className="summaryPlaceholder">
          O resultado serÃ¡ apresentado por indicadores, estatÃ­sticas e arquivos exportÃ¡veis. O conteÃºdo integral nÃ£o Ã© exibido na tela para preservar a navegaÃ§Ã£o em documentos extensos.
        </p>
      )}
      {result?.stats.validation_warnings.length ? (
        <ValidationWarningsPanel warnings={result.stats.validation_warnings} />
      ) : null}
    </article>
  );
}

function PipelineStatePanel({ result }: { result: Result }) {
  const stages = result.pipeline_state?.stages || [];
  if (!stages.length) return null;

  return (
    <section className="pipelineStatePanel">
      <header>
        <span className="panelLabel">Estado do processamento</span>
        <strong>{pipelineStatusLabel(result.pipeline_state?.overall_status || "ok")}</strong>
      </header>
      <div className="pipelineStages">
        {stages.map((stage) => (
          <div key={stage.name} className={`pipelineStage ${stage.status}`}>
            <span>{formatStageName(stage.name)}</span>
            <strong>{stageStatusLabel(stage.status)}</strong>
            {typeof stage.duration_ms === "number" ? <small>{stage.duration_ms} ms</small> : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function ValidationWarningsPanel({ warnings }: { warnings: string[] }) {
  const groupedWarnings = groupValidationWarnings(warnings);

  return (
    <details className="summaryWarnings">
      <summary>
        <div>
          <strong>Avisos de ValidaÃ§Ã£o automÃ¡tica</strong>
          <span>
            {warnings.length} ocorrÃªncia(s) reunida(s) em {groupedWarnings.length} tipo(s). Clique para consultar a
            explicaÃ§Ã£o e revisar os pontos indicados.
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
      {count > 1 ? <em>Repetido {count} vez(es) nesta solicitaÃ§Ã£o.</em> : null}
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
  const currentResult = result;

  const quickQuestions = ["Qual Ã© a finalidade?", "O que devo revisar?", "Se surgir erro, o que fazer?", "Como conferir RIF ou extrato?"];

  async function askDiagnostic(text: string) {
    return;
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
        body: JSON.stringify({
          question: trimmed,
          profile: currentResult.safe_summary?.profile || selectedGroup?.documentKind || "",
          document_id: currentResult.audit.safe_summary_id || currentResult.audit.source_sha256
        })
      });
      const payload = await response.json();
      setMessages((items) => [...items, { role: "anon", text: payload.answer || "OrientaÃ§Ã£o institucional indisponÃ­vel neste momento.", source: payload.source }]);
    } catch {
      setMessages((items) => [...items, { role: "anon", text: "Este canal permanece restrito a orientaÃ§Ãµes institucionais de uso, sigilo e revisÃ£o." }]);
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
            <span className="panelLabel">OrientaÃ§Ã£o institucional</span>
            <h3>IA NEXUS</h3>
            <p>Canal individual desta solicitaÃ§Ã£o, vinculado Ã  IA local, em fase de testes (Acionar a IA ocasionarÃ¡ lentidÃ£o no sistema).</p>
          </div>
        </div>
        <div className="diagnosticStatusBadge">
          <span />
          IA local
        </div>
      </header>
      <div className="diagnosticQuick">
        {quickQuestions.map((item) => (
          <button key={item} type="button" onClick={() => void askDiagnostic(item)} disabled>
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
              <span>Estou conectada Ã  IA local para orientar esta solicitaÃ§Ã£o sobre o ANON, o produto anonimizado e a revisÃ£o humana obrigatÃ³ria.</span>
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
        <input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Fale com a IA NEXUS, em breve..." disabled />
        <button type="submit" disabled>
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
        <AuditItem label="VersÃ£o ANON" value={result.audit.anon_version || "NÃ£o informada"} />
        <AuditItem label="Tempo" value={formatSeconds(result.audit.processing_time_seconds)} />
        <AuditItem label="OCR" value={result.audit.ocr_used ? "Utilizado" : "NÃ£o utilizado"} />
        <AuditItem label="Estrutura" value={result.audit.structure_preserved ? "Preservada" : "NÃ£o preservada"} />
        <AuditItem label="ValidaÃ§Ã£o" value={result.audit.validation_status} />
      </div>
      <AuditStrengthPanel result={result} />
      <section className="hashSection">
        <header>
          <span className="panelLabel">Hashes SHA-256</span>
          <strong>Integridade do arquivo original e dos produtos exportÃ¡veis</strong>
        </header>
        <AuditHash label="Hash SHA-256 original" value={result.audit.source_sha256} />
        {exportEntries.map(([format, hash]) => (
          <AuditHash key={format} label={`Hash SHA-256 ${format.toUpperCase()}`} value={hash} />
        ))}
      </section>
      <div className="auditCounters">
        <Metric label="SubstituiÃ§Ãµes" value={result.stats.replacements_applied} />
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

function AuditStrengthPanel({ result }: { result: Result }) {
  const jsonRejected = result.stats.ollama_json_rejected_chunks ?? 0;
  const correctionAttempts = result.stats.ollama_correction_attempts ?? 0;
  const correctionSuccesses = result.stats.ollama_correction_successes ?? 0;
  const warnings = result.stats.validation_warnings.length;
  const quality = result.stats.quality_status ? qualityLabel(result.stats.quality_status) : "RevisÃ£o";
  const qualityScore = result.stats.quality_score ? ` Â· ${result.stats.quality_score}/100` : "";
  const confidenceScore = result.stats.confidence_score ?? result.safe_summary?.confidence_score;
  const confidenceLevel = result.stats.confidence_level ?? result.safe_summary?.confidence_level ?? "NÃ£o informada";
  const reviewItems = result.review_items ?? [];

  return (
    <section className="auditStrengthPanel">
      <header>
        <div>
          <span className="panelLabel">Painel de auditoria reforÃ§ada</span>
          <strong>Controle institucional do processamento</strong>
        </div>
        <span className={`auditRiskBadge ${warnings || jsonRejected ? "review" : "good"}`}>
          {warnings || jsonRejected ? "RevisÃ£o exigida" : "Sem ressalva automÃ¡tica"}
        </span>
      </header>
      <div className="auditStrengthGrid">
        <AuditItem label="Qualidade" value={`${quality}${qualityScore}`} />
        <AuditItem label="Avisos" value={`${warnings}`} />
        <AuditItem label="JSON recusado" value={`${jsonRejected}`} />
        <AuditItem label="CorreÃ§Ãµes JSON" value={`${correctionSuccesses}/${correctionAttempts}`} />
        <AuditItem label="Eventos NCE" value={`${result.stats.communication_summary?.events ?? 0}`} />
        <AuditItem label="Confiabilidade" value={confidenceScore == null ? confidenceLevel : `${confidenceLevel} Â· ${confidenceScore}/100`} />
        <AuditItem label="Produto" value={result.audit.export_sha256.auditoria ? "Manifesto interno gerado" : "Sem manifesto"} />
      </div>
      {reviewItems.length ? (
        <details className="auditReasons">
          <summary>Modo de revisÃ£o humana: {reviewItems.length} item(ns) pendente(s)</summary>
          <ul>
            {reviewItems.slice(0, 8).map((item) => (
              <li key={item.id}>
                <strong>{item.category}:</strong> {item.label} - {item.recommendation}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {result.stats.confidence_reasons?.length ? (
        <details className="auditReasons">
          <summary>Fatores da pontuaÃ§Ã£o de confiabilidade</summary>
          <ul>
            {result.stats.confidence_reasons.slice(0, 6).map((reason, index) => (
              <li key={`${reason}-${index}`}>{reason}</li>
            ))}
          </ul>
        </details>
      ) : null}
      {result.stats.ollama_json_rejection_reasons?.length ? (
        <details className="auditReasons">
          <summary>Motivos de recusa JSON registrados</summary>
          <ul>
            {result.stats.ollama_json_rejection_reasons.slice(0, 5).map((reason, index) => (
              <li key={`${reason}-${index}`}>{reason}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
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
  const externalFormats = formats.filter(isExternalProductFormat).map(formatExportLabel);
  const internalFormats = formats.filter(isInternalProductFormat).map(formatExportLabel);

  return (
    <div className="downloadFormatsInfo">
      <span>Arquivos disponÃ­veis para download</span>
      <strong>{externalFormats.length ? externalFormats.join(" â€¢ ") : "Aguardando geraÃ§Ã£o"}</strong>
      <small>Produto externo para revisÃ£o humana e eventual compartilhamento institucional.</small>
      {internalFormats.length ? <em>Internos restritos: {internalFormats.join(" â€¢ ")}</em> : null}
    </div>
  );
}

async function downloadResultProduct(result: Result, format: string, fileName?: string) {
  const expectedHash = result.audit.export_sha256[format]?.toUpperCase();
  if (!expectedHash) {
    window.alert("Hash do produto nÃ£o localizado. A exportaÃ§Ã£o foi bloqueada para preservar a integridade.");
    return;
  }

  const response = await fetch(`${API_URL}/api/exports/${result.job_id}/${format}`);
  if (!response.ok) {
    window.alert("NÃ£o foi possÃ­vel gerar o arquivo solicitado.");
    return;
  }

  const blob = await response.blob();
  const buffer = await blob.arrayBuffer();
  const actualHash = await sha256Buffer(buffer);
  if (actualHash !== expectedHash) {
    window.alert("O hash do arquivo gerado nÃ£o corresponde ao hash informado. Download bloqueado.");
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

async function downloadSyncPackage(result: Result, fileName?: string) {
  const response = await fetch(`${API_URL}/api/jobs/${result.job_id}/sync-package`);
  if (!response.ok) {
    window.alert("NÃ£o foi possÃ­vel gerar o pacote de sincronizaÃ§Ã£o.");
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `sincronizacao_${sanitizeFileBase((fileName || result.original_filename).replace(/\.[^.]+$/, ""))}_.json`;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function ExportBar({ result, fileName }: { result?: Result; fileName?: string }) {
  const availableFormats = result ? Object.keys(result.audit.export_sha256) : ["pdf", "docx", "txt"];
  const externalFormats = availableFormats.filter(isExternalProductFormat);
  const internalFormats = availableFormats.filter(isInternalProductFormat);

  async function downloadExport(format: string) {
    if (!result) return;
    await downloadResultProduct(result, format, fileName);
  }

  return (
    <footer className="exports splitExports">
      <div className="exportsIntro">
        <FileText size={18} />
        <span>
          <strong>Produtos gerados para download</strong>
          <small>{fileName ? `Itens derivados de ${fileName}` : "Selecione um arquivo processado para baixar o produto final."}</small>
        </span>
      </div>
      <ExportGroup
        title="Produto externo"
        description="Arquivo anonimizado para revisÃ£o humana e eventual uso fora do controle interno."
        formats={externalFormats}
        result={result}
        onDownload={downloadExport}
      />
      <ExportGroup
        title="Interno restrito"
        description="Auditoria, avisos, tabela de controle e rastreabilidade. NÃ£o compartilhar como produto final."
        formats={internalFormats}
        result={result}
        onDownload={downloadExport}
      />
      <section className="exportGroup syncExportGroup">
        <header>
          <strong>SincronizaÃ§Ã£o</strong>
          <small>Pacote interno para reaplicar os mesmos marcadores em outra demanda.</small>
        </header>
        <div className="exportButtons">
          <button type="button" disabled={!result} onClick={() => result && void downloadSyncPackage(result, fileName)}>
            <Download size={16} />
            <span>
              <strong>SYNC</strong>
              <small>Pacote de sincronizaÃ§Ã£o</small>
            </span>
          </button>
        </div>
      </section>
    </footer>
  );
}

function ExportGroup({
  title,
  description,
  formats,
  result,
  onDownload
}: {
  title: string;
  description: string;
  formats: string[];
  result?: Result;
  onDownload: (format: string) => Promise<void>;
}) {
  return (
    <section className="exportGroup">
      <header>
        <strong>{title}</strong>
        <small>{description}</small>
      </header>
      <div className="exportButtons">
        {formats.length ? (
          formats.map((format) => (
            <button
              key={format}
              type="button"
              disabled={!result}
              onClick={() => void onDownload(format)}
              title={result ? formatExportTitle(format) : undefined}
            >
              <Download size={16} />
              <span>
                <strong>{formatExportLabel(format)}</strong>
                <small>{isInternalProductFormat(format) ? "Uso interno" : "Produto anonimizado"}</small>
              </span>
            </button>
          ))
        ) : (
          <div className="exportEmpty">NÃ£o gerado para este arquivo.</div>
        )}
      </div>
    </section>
  );
}

function InstitutionalFooter() {
  return (
    <footer className="institutionalFooter">
      <span>
        Â© 2026 NEXUS ANON Â· Uso institucional e interno Â· Criador e Desenvolvedor:{" "}
        <a href="https://github.com/LukasFurtado" target="_blank" rel="noreferrer">Lukas Furtado</a>
        {" "}- PolÃ­cia Civil do Estado de Pernambuco.
      </span>
      <strong>
        <a href="https://github.com/LukasFurtado/NEXUS-ANON" target="_blank" rel="noreferrer">VersÃ£o 1.8.39</a>
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
    return "ServiÃ§o local do ANON nÃ£o respondeu. Reinicie o mÃ³dulo local e tente processar novamente.";
  }
  return err instanceof Error ? err.message : "Erro inesperado.";
}

function explainValidationWarning(warning: string) {
  const normalized = warning.toLowerCase();

  if (normalized.includes("termos protegidos do perfil")) {
    return "O sistema percebeu que algum termo que deveria permanecer igual pode ter mudado. Confira principalmente cabeÃ§alhos, colunas, histÃ³ricos, totais e rÃ³tulos do documento.";
  }
  if (normalized.includes("ia local nao utilizada") || normalized.includes("ia local nÃ£o utilizada")) {
    return "O Ollama ou o modelo selecionado nÃ£o participou dessa execuÃ§Ã£o. O documento foi processado pelas regras automÃ¡ticas locais; verifique se o Ollama estÃ¡ aberto e se o modelo escolhido estÃ¡ instalado.";
  }
  if (normalized.includes("valores possivelmente alterados")) {
    return "O sistema encontrou diferenÃ§a em valores monetÃ¡rios. Confira se quantias, centavos e formataÃ§Ã£o financeira foram preservados exatamente como no original.";
  }
  if (normalized.includes("datas possivelmente alteradas")) {
    return "O sistema encontrou diferenÃ§a em datas. Confira se datas de movimentaÃ§Ã£o, emissÃ£o, abertura, encerramento ou registro continuam corretas.";
  }
  if (normalized.includes("termo juridico") || normalized.includes("termo jurÃ­dico")) {
    return "Uma possÃ­vel anonimizaÃ§Ã£o foi descartada porque atingiria texto jurÃ­dico ou expressÃ£o legal. Isso evita alterar fundamento, lei, artigo ou jurisprudÃªncia.";
  }
  if (normalized.includes("termo generico") || normalized.includes("termo genÃ©rico")) {
    return "Uma possÃ­vel anonimizaÃ§Ã£o foi descartada porque parecia ser apenas um nome de campo ou tipo de documento, e nÃ£o uma informaÃ§Ã£o pessoal.";
  }
  if (normalized.includes("termo protegido do perfil")) {
    return "Uma possÃ­vel anonimizaÃ§Ã£o foi descartada para nÃ£o apagar estrutura do documento. Em extratos, isso normalmente envolve histÃ³ricos bancÃ¡rios, nomes de colunas, tÃ­tulos ou descriÃ§Ãµes de operaÃ§Ã£o.";
  }

  return "Aviso automÃ¡tico de conferÃªncia. Revise o ponto indicado para confirmar se sÃ³ os dados sensÃ­veis foram substituÃ­dos e se o restante do documento foi preservado.";
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
  if (format === "avisos") return `avisos_${cleanBase}_.pdf`;
  if (format === "controle") return `controle_${cleanBase}_.pdf`;
  if (format === "auditoria") return `auditoria_${cleanBase}_.json`;
  if (format === "reanalise_log") return `log_reanalise_${cleanBase}_.txt`;
  return `${format.toUpperCase()}__${cleanBase}_.${format}`;
}

function formatExportLabel(format: string) {
  if (format === "controle") return "CONTROLE";
  if (format === "auditoria") return "AUDITORIA";
  if (format === "reanalise_log") return "LOG";
  return format === "avisos" ? "AVISOS" : format.toUpperCase();
}

function formatExportTitle(format: string) {
  if (format === "controle") return "Tabela de controle interno gerada em arquivo separado e restrito.";
  if (format === "auditoria") return "Manifesto interno de auditoria e rastreabilidade gerado.";
  if (format === "reanalise_log") return "Log da reanalise dirigida gerado.";
  return format === "avisos" ? "Arquivo de avisos e validaÃ§Ã£o gerado." : `Arquivo ${format.toUpperCase()} anonimizado gerado.`;
}

function isExternalProductFormat(format: string) {
  return ["txt", "docx", "pdf", "csv"].includes(format);
}

function isInternalProductFormat(format: string) {
  return ["avisos", "controle", "auditoria", "reanalise_log"].includes(format);
}

function qualityLabel(status: string) {
  if (status === "BOM") return "Bom";
  if (status === "ATENCAO_CRITICA") return "AtenÃ§Ã£o crÃ­tica";
  return "Revisar";
}

function qualityCssClass(status: string) {
  if (status === "BOM") return "good";
  if (status === "ATENCAO_CRITICA") return "critical";
  return "review";
}

function pipelineStatusLabel(status: string) {
  if (status === "fail") return "Falha registrada";
  if (status === "warn") return "ConcluÃ­do com avisos";
  if (status === "running") return "Em andamento";
  return "ConcluÃ­do";
}

function stageStatusLabel(status: string) {
  if (status === "fail") return "Falha";
  if (status === "warn") return "Aviso";
  if (status === "running") return "Em andamento";
  return "ConcluÃ­da";
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
  if (value === "qwen3:32b") return "Qwen3 32B";
  return value;
}

function buildManualAnonymousId(entityType: string, suffix: string) {
  const raw = suffix.trim();
  if (!raw) return "";
  if (/^\[[A-Z0-9_]+_[A-Z0-9_-]+\]$/i.test(raw)) return raw.toUpperCase();
  const prefix = ENTITY_MARKER_PREFIXES[entityType] || "DADO";
  const cleanSuffix = raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/^\[|\]$/g, "")
    .replace(/[^A-Za-z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .toUpperCase();
  return cleanSuffix ? `[${prefix}_${cleanSuffix}]` : "";
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

