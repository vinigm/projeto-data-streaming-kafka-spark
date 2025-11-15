import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, udf
from pyspark.sql.types import StructType, StructField, StringType, TimestampType, BooleanType, MapType
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import warnings
warnings.filterwarnings('ignore')

# --- CONFIGURAÇÃO ---
KAFKA_TOPIC = "posts_bluesky"
KAFKA_SERVER = "kafka:29092"
SPARK_MASTER_URL = "spark://spark-master:7077"

# Modelo BERT para análise de sentimento em português brasileiro
# Opções de modelos (escolha um):
# 1. "neuralmind/bert-base-portuguese-cased" - Modelo geral PT-BR
# 2. "lxyuan/distilbert-base-multilingual-cased-sentiments-student" - Mais rápido, multilíngue
# 3. "cardiffnlp/twitter-xlm-roberta-base-sentiment" - Treinado em tweets
BERT_MODEL = "lxyuan/distilbert-base-multilingual-cased-sentiments-student"
# --------------------

def get_spark_session():
    """
    Cria e configura a sessão Spark com recursos aumentados para ML.
    """
    kafka_pkg_version = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1"

    try:
        spark = (
            SparkSession.builder
            .appName("AnaliseSentimentoBERT_Bluesky")
            .master(SPARK_MASTER_URL)
            .config("spark.jars.packages", kafka_pkg_version)
            # Aumentar memória para lidar com modelo BERT
            .config("spark.executor.memory", "4g")
            .config("spark.driver.memory", "4g")
            .getOrCreate()
        )
        spark.sparkContext.setLogLevel("WARN")
        print("--- Sessão Spark criada com sucesso! ---")
        return spark
    except Exception as e:
        print(f"ERRO ao criar a sessão Spark: {e}")
        sys.exit(1)


# --- CARREGAMENTO DO MODELO BERT ---
# Carregar modelo e tokenizer uma única vez (não dentro da UDF)
print(f"Carregando modelo BERT: {BERT_MODEL}")
try:
    tokenizer = AutoTokenizer.from_pretrained(BERT_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(BERT_MODEL)
    model.eval()  # Modo de inferência (não treinamento)
    
    # Verificar se GPU está disponível
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"Modelo carregado com sucesso! Usando device: {device}")
except Exception as e:
    print(f"ERRO ao carregar modelo BERT: {e}")
    print("Certifique-se de ter instalado: pip install transformers torch")
    sys.exit(1)


def perform_sentiment_analysis_bert(text):
    """
    Análise de sentimento usando modelo Transformer BERT.
    Retorna: POSITIVO, NEUTRO ou NEGATIVO
    """
    if text is None or text.strip() == "":
        return "NEUTRO"
    
    try:
        # Limitar tamanho do texto (BERT tem limite de 512 tokens)
        text = text[:512]
        
        # Tokenizar o texto
        inputs = tokenizer(
            text, 
            return_tensors="pt", 
            truncation=True, 
            max_length=512,
            padding=True
        )
        
        # Mover para GPU se disponível
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Inferência (sem calcular gradientes)
        with torch.no_grad():
            outputs = model(**inputs)
        
        # Converter logits em probabilidades
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        sentiment_idx = torch.argmax(probs, dim=-1).item()
        confidence = probs[0][sentiment_idx].item()
        
        # Mapeamento de índices para labels
        # O modelo "lxyuan/distilbert-base-multilingual-cased-sentiments-student" usa:
        # 0: negativo, 1: neutro, 2: positivo
        labels_map = {0: "NEGATIVO", 1: "NEUTRO", 2: "POSITIVO"}
        sentiment = labels_map.get(sentiment_idx, "NEUTRO")
        
        print(f"[BERT] Sentimento: {sentiment} (confiança: {confidence:.2%})")
        return sentiment
        
    except Exception as e:
        print(f"ERRO na análise de sentimento: {e}")
        return "NEUTRO"


def perform_sentiment_analysis_hybrid(text, categorias):
    """
    Análise híbrida: Regras de domínio + BERT.
    Para casos específicos que você conhece o contexto, aplicamos regras.
    Para o resto, delegamos ao BERT.
    """
    if text is None:
        return "NEUTRO"
    
    text_lower = text.lower()
    
    # REGRA 1: Menção de vítimas civis sempre é muito negativo
    if any(term in text_lower for term in ["criança morta", "crianca morta", "bala perdida", "vítima inocente", "vitima inocente"]):
        return "MUITO_NEGATIVO"
    
    # REGRA 2: Ironia/sarcasmo com emojis (heurística simples)
    if "👏" in text and any(term in text_lower for term in ["parabéns", "parabens", "ótimo", "otimo"]):
        return "NEGATIVO"  # Provavelmente ironia
    
    # REGRA 3: Contextos claramente positivos
    if any(term in text_lower for term in ["preso", "apreendeu", "prisão bem-sucedida", "salvou"]):
        return "POSITIVO"
    
    # Senão, usar o modelo BERT
    return perform_sentiment_analysis_bert(text)

def process_stream(spark):
    """
    Função principal que lê do Kafka e processa os dados com BERT.
    """
    print(f"--- Lendo do tópico Kafka: {KAFKA_TOPIC} ---")
    
    try:
        # Esquema atualizado com categorias
        schema = StructType([
            StructField("timestamp_iso", StringType(), True),
            StructField("user_did", StringType(), True),
            StructField("text", StringType(), True),
            StructField("categorias", MapType(StringType(), BooleanType()), True)
        ])

        # Ler o stream do Kafka
        df_kafka = (
            spark.readStream
            .format("kafka")
            .option("kafka.bootstrap.servers", KAFKA_SERVER)
            .option("subscribe", KAFKA_TOPIC)
            .option("startingOffsets", "latest")
            .load()
        )

        # Converter dados binários para JSON
        df_json = df_kafka.select(
            col("value").cast("string").alias("json_value")
        )

        # Parsear JSON
        df_posts = df_json.select(
            from_json(col("json_value"), schema).alias("data")
        ).select("data.*")

        # Aplicar análise de sentimento com BERT
        # IMPORTANTE: usar perform_sentiment_analysis_bert para apenas BERT
        # ou perform_sentiment_analysis_hybrid para regras + BERT
        sentiment_udf = udf(perform_sentiment_analysis_bert, StringType())
        
        df_sentimento = df_posts.withColumn(
            "sentimento", sentiment_udf(col("text"))
        )
        
        # Exibir resultados no console
        query = (
            df_sentimento
            .select("timestamp_iso", "user_did", "text", "categorias", "sentimento")
            .writeStream
            .outputMode("append")
            .format("console")
            .option("truncate", "false")
            .start()
        )
        
        print("--- Query de streaming com BERT iniciada! Aguardando dados... ---")
        print("ATENÇÃO: A primeira análise pode demorar enquanto o modelo é carregado.")
        query.awaitTermination()

    except Exception as e:
        print(f"ERRO no stream do Spark: {e}")
        print("Verifique se o tópico do Kafka existe e se os dados estão no formato correto.")

# --- Ponto de Partida do Script ---
if __name__ == "__main__":
    spark = get_spark_session()
    if spark:
        process_stream(spark)