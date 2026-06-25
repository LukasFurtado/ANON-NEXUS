# NEXUS ANON

Aplicação desktop profissional, local e offline, para anonimização inteligente de documentos policiais, jurídicos e administrativos, com foco inicial em Relatórios de Inteligência Financeira (RIF/COAF).

## Princípios

- Nenhum documento é enviado para a internet.
- O processamento roda localmente em Python, FastAPI, SQLite e Ollama.
- Regex e validação protegem datas, valores, percentuais, fundamentação jurídica e análise técnica.
- A IA local é obrigatória para o reconhecimento de entidades e não atua como chatbot.
- Cada módulo tem responsabilidade única: parser, OCR, regex, IA, validação, exportação e histórico.

## Estrutura

```text
backend/
  app/
    api/          Rotas HTTP locais
    core/         Configuração
    models/       Contratos de dados
    pipeline/     Parser, OCR, regex, IA, validação e exportação
    services/     SQLite e Ollama
frontend/
  src/            Interface React + TypeScript
src-tauri/        Configuração desktop Tauri
docs/             Documentação técnica
```

## Fluxo

```text
Arquivo
-> Identificação do formato
-> Extração do texto
-> OCR quando necessário
-> Pré-processamento por regex
-> Reconhecimento por Ollama local
-> Validação automática
-> Exportação em TXT, DOCX e PDF
```

## Instalação assistida

Para uso por pessoas sem familiaridade com terminal, utilize os arquivos da raiz do projeto:

- `INSTALAR_NEXUS_ANON.bat`: prepara Python, dependências do backend, dependências da interface, modelo local do Ollama e cria atalho na Área de Trabalho.
- `ABRIR_NEXUS_ANON.bat`: liga os serviços locais e abre automaticamente `http://localhost:5173/` no navegador.
- `INSTALACAO_NEXUS_ANON.html`: guia visual de instalação e requisitos para operadores não técnicos.
- `GERAR_PACOTE_NEXUS_ANON.bat`: gera um pacote ZIP limpo para distribuição local.
- `install.py`: assistente Python alternativo para preparar backend e interface quando o `.bat` não for usado.
- `install_check.py`: verificador rápido de ambiente, dependências e modelos locais antes da execução.

O pacote não inclui o peso do modelo `qwen3:32b`, pois ele é grande e deve ser instalado ou baixado pelo Ollama na máquina de destino.

## Execução local

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

OCR é opcional no MVP. Depois que a aplicação estiver abrindo, instale OCR separadamente se precisar analisar imagens ou PDFs escaneados:

```powershell
pip install -r requirements-ocr.txt
```

Se o Pillow falhar em Python 3.14, use Python 3.11 ou 3.12. O backend principal não depende do Pillow para abrir.

### 2. Ollama

Instale e execute o Ollama localmente. Depois baixe pelo próprio ambiente local os modelos desejados:

```powershell
ollama pull qwen3:32b
ollama serve
```

O Ollama deve permanecer em execução durante o uso do ANON. Sem resposta local do Ollama, a anonimização é bloqueada para evitar processamento sem IA.

O modelo operacional padrão é `qwen3:32b`. O ANON não exige criação de `NEXUS-anon:latest`; a especialização institucional fica nos prompts, perfis JSON, regras determinísticas, validação e corretor de JSON.

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

## Diagnóstico rápido

Se o navegador abrir em `http://127.0.0.1:8000/` e não aparecer a interface, isso é esperado: a porta 8000 é somente a API. A tela principal roda em `http://localhost:5173/`.

Verifique se a API está ativa:

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

Se a interface não abrir, inicie o frontend em outra janela:

```powershell
.\scripts\start-frontend.ps1
```

Se aparecer erro dizendo que `python` ou `npm` não foi encontrado, instale Python 3.11+ e Node.js 20+ e abra um novo PowerShell.

## Estado do MVP

Esta versão entrega:

- Upload por arrastar e soltar.
- Escolha de modelo local.
- Perfil documental RIF/COAF e demais perfis iniciais.
- API local de anonimização.
- Detecção por regex para CPF, CNPJ, telefone, e-mail, CEP, placas, IP, MAC, contas, agências, PIX, processos, protocolos e documentos.
- Uso obrigatório do Ollama local para reconhecimento de entidades.
- Validador para preservar datas, valores e termos jurídicos.
- Exportação em TXT, DOCX e PDF.
- Histórico básico em SQLite com SHA-256.

## Versionamento

Versão atual: **1.8.39**.

Toda atualização funcional, visual ou documental deve incrementar a versão e registrar a mudança em `CHANGELOG.md`.

## Próximas fases

1. Preservação visual fiel de PDF/DOCX com mapeamento por coordenadas.
2. OCR avançado com Tesseract/EasyOCR e fila de processamento.
3. Relatório de auditoria detalhado por entidade anonimizada.
4. Processamento em lote.
5. Perfis especializados por documento.
6. Tela de revisão humana com aceite/rejeição de entidades.
7. Empacotamento com instalador e verificador de dependências locais.
