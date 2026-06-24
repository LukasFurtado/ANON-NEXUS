# NEXUS ANON

Aplicacao desktop profissional, local e offline, para anonimização inteligente de documentos policiais, juridicos e administrativos, com foco inicial em Relatorios de Inteligencia Financeira (RIF/COAF).

## Principios

- Nenhum documento e enviado para a internet.
- O processamento roda localmente em Python, FastAPI, SQLite e Ollama.
- Regex e validacao protegem datas, valores, percentuais, fundamentacao juridica e analise tecnica.
- A IA local atua como motor auxiliar de reconhecimento de entidades, nao como chatbot.
- Cada modulo tem responsabilidade unica: parser, OCR, regex, IA, validacao, exportacao e historico.

## Estrutura

```text
backend/
  app/
    api/          Rotas HTTP locais
    core/         Configuracao
    models/       Contratos de dados
    pipeline/     Parser, OCR, regex, IA, validacao e exportacao
    services/     SQLite e Ollama
frontend/
  src/            Interface React + TypeScript
src-tauri/        Configuracao desktop Tauri
docs/             Documentacao tecnica
```

## Fluxo

```text
Arquivo
-> Identificacao do formato
-> Extracao do texto
-> OCR quando necessario
-> Pre-processamento por regex
-> Reconhecimento por Ollama local
-> Validacao automatica
-> Exportacao em TXT, DOCX e PDF
```

## Execucao local

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

OCR e opcional no MVP. Depois que a aplicacao estiver abrindo, instale OCR separadamente se precisar analisar imagens ou PDFs escaneados:

```powershell
pip install -r requirements-ocr.txt
```

Se o Pillow falhar em Python 3.14, use Python 3.11 ou 3.12. O backend principal nao depende do Pillow para abrir.

### 2. Ollama

Instale e execute o Ollama localmente. Depois baixe pelo proprio ambiente local os modelos desejados:

```powershell
ollama pull qwen3:32b
ollama pull gemma4:31b
ollama serve
```

### 3. Frontend

```powershell
cd frontend
npm install
npm run dev
```

### 4. Desktop

Com Rust, Node e Tauri configurados:

```powershell
cd frontend
npm run tauri dev
```

## Diagnostico rapido

Se o navegador abrir em `http://127.0.0.1:8000/` e nao aparecer a interface, isso e esperado: a porta 8000 e somente a API. A tela principal roda em `http://localhost:5173`.

Verifique se a API esta ativa:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Resposta esperada:

```json
{"status":"ok","mode":"offline"}
```

Se falhar, inicie o backend:

```powershell
.\scripts\start-backend.ps1
```

Se a interface nao abrir, inicie o frontend em outra janela:

```powershell
.\scripts\start-frontend.ps1
```

Se aparecer erro dizendo que `python` ou `npm` nao foi encontrado, instale Python 3.11+ e Node.js 20+ e abra um novo PowerShell.

## Estado do MVP

Esta versao entrega:

- Upload por arrastar e soltar.
- Escolha de modelo local.
- Perfil documental RIF/COAF e demais perfis iniciais.
- API local de anonimização.
- Detecção por regex para CPF, CNPJ, telefone, e-mail, CEP, placas, IP, MAC, contas, agencias, PIX, processos, protocolos e documentos.
- Encaixe para Ollama local.
- Validador para preservar datas, valores e termos juridicos.
- Comparacao lado a lado entre texto original e anonimizado.
- Exportacao em TXT, DOCX e PDF.
- Historico basico em SQLite com SHA-256.

## Versionamento

Versao atual: **1.5.7**.

Toda atualizacao funcional, visual ou documental deve incrementar a versao e registrar a mudanca em `CHANGELOG.md`.

## Proximas fases

1. Preservacao visual fiel de PDF/DOCX com mapeamento por coordenadas.
2. OCR avancado com Tesseract/EasyOCR e fila de processamento.
3. Relatorio de auditoria detalhado por entidade anonimizada.
4. Processamento em lote.
5. Perfis especializados por documento.
6. Tela de revisao humana com aceite/rejeicao de entidades.
7. Empacotamento com instalador e verificador de dependencias locais.
