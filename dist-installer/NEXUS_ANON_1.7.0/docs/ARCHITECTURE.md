# Arquitetura

O NEXUS ANON foi desenhado como uma ferramenta documental, nao como chatbot. O backend recebe arquivos, extrai texto, identifica entidades sensiveis, aplica substituicoes consistentes e exporta o resultado.

## Camadas

```text
Interface Desktop
  React + TypeScript + Tauri

API Local
  FastAPI em 127.0.0.1

Pipeline
  parser -> ocr -> regex -> ollama -> validator -> exporter

Persistencia
  SQLite local

IA
  Ollama em 127.0.0.1:11434
```

## Garantias de privacidade

- A API escuta somente em localhost.
- O Ollama e chamado por `http://127.0.0.1:11434`.
- Nao ha chamadas externas no codigo da aplicacao.
- O documento integral nao precisa ser enviado ao LLM; a proxima etapa deve segmentar apenas trechos candidatos.

## Preservacao documental

A versao inicial exporta texto anonimizado. A fase seguinte deve implementar exportadores estruturais:

- PDF: aplicar redacoes/substituicoes por coordenadas usando PyMuPDF.
- DOCX: substituir runs mantendo estilos com python-docx.
- Tabelas: preservar delimitadores e celulas.
- Graficos: manter objetos e metadados, anonimizar apenas rotulos sensiveis.

## Validacao

O validador atual impede anonimização de datas, valores monetarios e termos juridicos marcados por engano. Em producao, esta camada deve comparar:

- contagem de datas antes/depois;
- soma e ocorrencias de valores financeiros;
- artigos de lei;
- percentuais;
- titulos e cabecalhos;
- tabelas e alinhamentos.
