# 🌐 Projeto: Análise de Sentimento em Tempo Real - Bluesky + Kafka + Spark

## 📋 Descrição

Sistema de **streaming de dados em tempo real** para coletar, processar e analisar posts do Bluesky sobre operações policiais no Rio de Janeiro, utilizando **Apache Kafka**, **Apache Spark** e **Transformers BERT** para análise de sentimento.

Desenvolvido como parte de pesquisa de mestrado sobre segurança pública e percepção social.

---

## 🏗️ Arquitetura

```
┌──────────────────┐
│ Bluesky Firehose │ (Fonte de dados)
└────────┬─────────┘
         │ Posts em tempo real
         ↓
┌──────────────────────────────────┐
│  coletor_bluesky.py              │
│  - Filtra por 67 keywords        │
│  - Categoriza posts              │
│  - Envia para Kafka              │
└────────┬─────────────────────────┘
         │ JSON enriquecido
         ↓
┌──────────────────────────────────┐
│  Apache Kafka (Docker)           │
│  - Tópico: posts_bluesky         │
│  - Message broker                │
└────────┬─────────────────────────┘
         │ Stream de dados
         ↓
┌──────────────────────────────────┐
│  Apache Spark (Docker)           │
│  + processador_spark.py          │
│  - Análise BERT Transformer      │
│  - Classificação de sentimento   │
└──────────────────────────────────┘
```

---

## 🚀 Tecnologias

- **Python 3.13+**
- **Apache Kafka** (Confluent Platform 7.6.1)
- **Apache Spark** 3.5.1
- **Transformers** (Hugging Face) + **PyTorch**
- **Docker** & **Docker Compose**
- **atproto** (AT Protocol SDK)

---

## 📦 Componentes

### 1. Coletor (`coletor_bluesky.py`)
- Conecta ao Bluesky Firehose (stream global)
- Filtra posts usando **67 keywords** em 6 categorias:
  - Operação (operação, blitz, cerco, etc.)
  - Polícia (PM, BOPE, CORE, etc.)
  - Violência (tiroteio, confronto, bala perdida, etc.)
  - Atores (traficante, facção, milícia, etc.)
  - Locais (favela, Rocinha, Alemão, etc.)
  - Reação (medo, pânico, correria, etc.)
- Enriquece com metadados categorizados
- Envia para Kafka

### 2. Kafka (Container Docker)
- Message broker para desacoplamento
- Tópico: `posts_bluesky`
- Permite múltiplos consumidores

### 3. Processador Spark (`processador_spark.py`)
- Consome stream do Kafka
- Aplica análise de sentimento com **BERT Transformer**
- Modelo: `distilbert-multilingual-cased-sentiments-student`
- Classifica: POSITIVO, NEUTRO ou NEGATIVO
- Exibe resultados em tempo real

---

## 🔧 Setup

### 1. Clonar o repositório
```bash
git clone https://github.com/vinigm/projeto-data-streaming-kafka-spark.git
cd projeto-data-streaming-kafka-spark
```

### 2. Iniciar serviços Docker
```bash
docker-compose up -d
```

Serviços disponíveis:
- **Kafka**: `localhost:9092`
- **Zookeeper**: `localhost:2181`
- **Spark Master UI**: `http://localhost:8080`
- **Spark Master**: `spark://localhost:7077`

### 3. Instalar dependências Python (local)
```bash
pip install atproto kafka-python
```

### 4. Instalar PyTorch e Transformers (no container Spark)
```bash
docker exec -it spark-master pip install torch transformers
```

### 5. Executar o Coletor
```bash
python coletor_bluesky.py
```

### 6. Executar o Processador Spark
```bash
docker exec -it spark-master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
  /opt/spark/apps/processador_spark.py
```

---

## 📊 Exemplo de Saída

### Coletor:
```
== POST FILTRADO ENCONTRADO ==
Usuário: did:plc:xyz123...
Texto: Operação do BOPE na Rocinha causa pânico entre moradores
Categorias: ['operacao', 'policia', 'violencia', 'locais', 'reacao']
-> Enviado para o Kafka (tópico: posts_bluesky)
```

### Processador:
```
[BERT] Sentimento: NEGATIVO (confiança: 89.23%)

+-------------------+------------------+----------------------------------------+-----------+
|timestamp_iso      |user_did          |text                                    |sentimento |
+-------------------+------------------+----------------------------------------+-----------+
|2025-11-15T14:30:00|did:plc:xyz123... |Operação do BOPE na Rocinha causa...    |NEGATIVO   |
+-------------------+------------------+----------------------------------------+-----------+
```

---

## 📈 Melhorias Futuras

- [ ] Salvar resultados em banco de dados (PostgreSQL/MongoDB)
- [ ] Dashboard em tempo real (Grafana/Kibana)
- [ ] Análise temporal (agregação por janelas de tempo)
- [ ] Geolocalização automática de eventos
- [ ] Topic Modeling (LDA, BERTopic)
- [ ] Alertas para eventos críticos
- [ ] API REST para consultas

---

## 🎓 Uso Acadêmico

Este projeto é parte de uma pesquisa de mestrado sobre:
- Percepção social de operações policiais
- Análise de sentimento em redes sociais
- Processamento de streams em tempo real
- Aplicação de NLP em português brasileiro

---

## 📄 Licença

MIT License

---

## 👤 Autor

**Vinicius** - Mestrando em [Área de Pesquisa]

GitHub: [@vinigm](https://github.com/vinigm)

---

## 🙏 Agradecimentos

- AT Protocol / Bluesky pela API aberta
- Hugging Face pelos modelos pré-treinados
- Apache Software Foundation (Kafka, Spark)
