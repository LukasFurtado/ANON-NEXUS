# Modelo Ollama NEXUS ANON

O arquivo `backend/resources/ollama/AnonRIF2.modelfile` define o modelo local especializado:

```text
FROM qwen3:32b
```

O modelo criado pelo script se chama:

```text
NEXUS-anon:latest
```

## Finalidade correta

O modelo nao gera documentos anonimizados.
Ele atua apenas como detector contextual de entidades sensiveis.

A resposta esperada e sempre JSON valido, no formato:

```json
[
  {"type": "PERSON", "text": "Joao da Silva", "start": 10, "end": 23}
]
```

As substituicoes, os identificadores anonimos, a preservacao estrutural, os hashes, a validacao e as exportacoes sao responsabilidade do backend.

## Criar ou recriar o modelo local

Com o Ollama instalado e `qwen3:32b` ja baixado:

```powershell
.\scripts\create-anonrif2-model.ps1
```

## Arquitetura preservada

```text
Parser -> CSV estruturado/Regex -> IA local apenas quando necessario -> Validacao -> Substituicao pelo backend -> Exportacao
```

## Pensamento desligado

O backend envia `/no_think` e `think: false` ao Ollama.
O Modelfile tambem proibe pensamento visivel, tags `<think>`, explicacoes e qualquer texto fora do JSON.
