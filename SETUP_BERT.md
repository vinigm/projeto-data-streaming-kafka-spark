# 🚀 Guia de Setup - Análise de Sentimento com BERT

## 📦 O que foi implementado

### PONTO 1: Keywords Expandidas ✅
- **67 palavras-chave** organizadas em 6 categorias semânticas
- Cada post agora é classificado nas categorias: operação, polícia, violência, atores, locais, reação
- Metadados enriquecidos enviados ao Kafka

### PONTO 2: Modelo Transformer BERT ✅
- Modelo: `lxyuan/distilbert-base-multilingual-cased-sentiments-student`
- Análise de sentimento estado da arte
- Suporta português brasileiro nativamente

---

## 🔧 Instalação das Dependências

### 1. Instalar bibliotecas no ambiente Python local (Coletor)
```powershell
pip install atproto kafka-python
```

### 2. Instalar PyTorch e Transformers no container Spark
```powershell
# Entrar no container Spark Master
docker exec -it spark-master bash

# Dentro do container:
pip install torch transformers

# Sair do container
exit
```

**Nota:** Se você tiver GPU disponível, pode instalar a versão CUDA do PyTorch para acelerar:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

---

## 🎯 Modelos BERT Disponíveis

Você pode trocar o modelo editando a linha no `processador_spark.py`:

```python
BERT_MODEL = "lxyuan/distilbert-base-multilingual-cased-sentiments-student"
```

### Opções de modelos:

| Modelo | Idioma | Velocidade | Acurácia | Tamanho |
|--------|--------|------------|----------|---------|
| `lxyuan/distilbert-base-multilingual-cased-sentiments-student` | Multilíngue | ⚡⚡⚡ Rápido | ⭐⭐⭐ Bom | 256 MB |
| `neuralmind/bert-base-portuguese-cased` | PT-BR | ⚡⚡ Médio | ⭐⭐⭐⭐ Excelente | 421 MB |
| `cardiffnlp/twitter-xlm-roberta-base-sentiment` | Multilíngue (Twitter) | ⚡⚡ Médio | ⭐⭐⭐⭐ Excelente | 1.1 GB |

**Recomendação para Mestrado:** Use o `neuralmind/bert-base-portuguese-cased` para melhor acurácia em PT-BR.

---

## 🚦 Como Executar

### 1. Iniciar os serviços Docker
```powershell
docker-compose up -d
```

### 2. Iniciar o Coletor (Terminal 2)
```powershell
python coletor_bluesky.py
```

Agora você verá saídas como:
```
== POST FILTRADO ENCONTRADO ==
Usuário: did:plc:abc123...
Texto: Operação do BOPE na Rocinha causou pânico
Categorias: ['operacao', 'policia', 'violencia', 'locais', 'reacao']
-> Enviado para o Kafka
```

### 3. Iniciar o Processador Spark (Terminal 3)
```powershell
docker exec -it spark-master /opt/spark/bin/spark-submit `
  --master spark://spark-master:7077 `
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 `
  /opt/spark/apps/processador_spark.py
```

**ATENÇÃO:** Na primeira execução, o modelo BERT será baixado (~256MB). Isso pode levar alguns minutos.

---

## 📊 Saída Esperada

O processador Spark mostrará:
```
Carregando modelo BERT: lxyuan/distilbert-base-multilingual-cased-sentiments-student
Modelo carregado com sucesso! Usando device: cpu
--- Lendo do tópico Kafka: posts_bluesky ---

[BERT] Sentimento: NEGATIVO (confiança: 87.34%)

+-------------------+------------------+----------------------------------------+-------------------+-----------+
|timestamp_iso      |user_did          |text                                    |categorias         |sentimento |
+-------------------+------------------+----------------------------------------+-------------------+-----------+
|2025-11-15T10:30:00|did:plc:abc123... |Operação do BOPE causou pânico...       |{operacao=true,... |NEGATIVO   |
+-------------------+------------------+----------------------------------------+-------------------+-----------+
```

---

## 🎓 Configurações Avançadas para Mestrado

### 1. Usar GPU (Se disponível)
Edite o `processador_spark.py` e o modelo automaticamente detectará CUDA:
```python
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
```

### 2. Ativar Análise Híbrida (Regras + BERT)
Troque no `processador_spark.py` linha ~160:
```python
# De:
sentiment_udf = udf(perform_sentiment_analysis_bert, StringType())

# Para:
sentiment_udf = udf(perform_sentiment_analysis_hybrid, StringType())
```

Isso ativa regras específicas para casos conhecidos + BERT para o resto.

### 3. Ajustar Categorias Mínimas
Para reduzir ruído, você pode filtrar posts que não tenham pelo menos 2 categorias.

Adicione no `coletor_bluesky.py` antes de enviar ao Kafka:
```python
# Contar quantas categorias estão presentes
num_categorias = sum(categorias.values())

# Só enviar se tiver pelo menos 2 categorias
if num_categorias >= 2:
    producer.send(KAFKA_TOPIC, post_data)
```

---

## 🐛 Troubleshooting

### Erro: "No module named 'torch'"
```powershell
docker exec -it spark-master pip install torch transformers
```

### Erro: "CUDA out of memory"
O modelo é muito grande para sua GPU. Use CPU:
```python
device = torch.device("cpu")
```

### Análise muito lenta
- Use o modelo `lxyuan/distilbert...` (mais rápido)
- Ou adicione mais workers Spark
- Ou use GPU

### Modelo demora para carregar na primeira vez
Normal! O Hugging Face baixa ~256MB. Espere 2-5 minutos.

---

## 📈 Próximos Passos para Seu Mestrado

1. **Validação Manual:** Anote manualmente 200-300 posts para calcular acurácia
2. **Métricas:** Implemente cálculo de Precision, Recall, F1-Score
3. **Visualização:** Conecte a um dashboard (Grafana, Kibana)
4. **Armazenamento:** Salve resultados em banco de dados (PostgreSQL, MongoDB)
5. **Análise Temporal:** Adicione agregações por janelas de tempo
6. **Geolocalização:** Extraia e mapeie os locais mencionados
7. **Topic Modeling:** Use LDA ou BERTopic para descobrir tópicos emergentes

---

## 📚 Referências

- [Hugging Face Models](https://huggingface.co/models?pipeline_tag=text-classification&language=pt)
- [Transformers Documentation](https://huggingface.co/docs/transformers/index)
- [PySpark Structured Streaming](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html)

---

**Boa sorte com seu mestrado! 🎓**
