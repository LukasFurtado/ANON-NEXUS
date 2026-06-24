# Modelo Ollama AnonRIF2

O arquivo `backend/resources/ollama/AnonRIF2.modelfile` foi incorporado ao projeto. Ele inicia com:

```text
FROM qwen3:32b
```

Isso significa que o modelo especializado deve ser criado localmente a partir do `qwen3:32b`.

## Criar o modelo local

Com o Ollama instalado e o `qwen3:32b` já baixado:

```powershell
.\scripts\create-anonrif2-model.ps1
```

O comando cria o modelo:

```text
NEXUS-anon:latest
```

## Como o NEXUS ANON usa isso

A interface agora oferece a opção **NEXUS-anon - Qwen3 32B**. Internamente, o nome enviado ao Ollama é `NEXUS-anon:latest`.

O pipeline do NEXUS ANON continua preservando a arquitetura de segurança:

```text
Parser -> Regex -> Reconhecimento local -> Validação -> Exportação
```

O documento não é tratado como conversa. O modelo local atua como apoio de reconhecimento/anonimização dentro do fluxo documental.

## Qwen3 sem pensamento visivel

O backend envia a diretiva `/no_think` em todas as chamadas ao Ollama e tambem informa `think: false` no payload local.

O Modelfile tambem registra que o modelo especializado nao deve emitir pensamento, tags `<think>`, justificativas internas ou explicacoes. Para aplicar essa regra ao modelo `NEXUS-anon:latest` ja criado, recrie-o localmente:

```powershell
.\scripts\create-anonrif2-model.ps1
```
