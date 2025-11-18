import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, udf
# --- MUDANÇA: Não precisamos mais do MapType ou BooleanType ---
from pyspark.sql.types import StructType, StructField, StringType, TimestampType
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import warnings
warnings.filterwarnings('ignore')

# --- CONFIGURAÇÃO ---
KAFKA_TOPIC = "posts_bluesky"
KAFKA_SERVER = "kafka:29092"
SPARK_MASTER_URL = "spark://spark-master:7077"
BERT_MODEL = "lxyuan/distilbert-base-multilingual-cased-sentiments-student"

PATH_SAIDA_JSON = "/opt/spark/dados_saida/json"
PATH_CHECKPOINT = "/opt/spark/checkpoint/analise"
# --------------------

def get_spark_session():
    """
    Cria e configura a sessão Spark.
    """
    kafka_pkg_version = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1"

    try:
        spark = (
            SparkSession.builder
            .appName("AnaliseSentimentoBERT_Bluesky")
            .master(SPARK_MASTER_URL)
            .config("spark.jars.packages", kafka_pkg_version) 
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
print(f"Carregando modelo BERT: {BERT_MODEL}")
try:
    tokenizer = AutoTokenizer.from_pretrained(BERT_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(BERT_MODEL)
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"Modelo carregado com sucesso! Usando device: {device}")
except Exception as e:
    print(f"ERRO ao carregar modelo BERT: {e}")
    sys.exit(1)
# ------------------------------------

def perform_sentiment_analysis_bert(text):
    """
    Análise de sentimento base usando o modelo Transformer BERT.
    """
    if text is None or text.strip() == "":
        return "NEUTRO"
    
    try:
        text = text[:512] 
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model(**inputs)
        
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        sentiment_idx = torch.argmax(probs, dim=-1).item()
        
        labels_map = {0: "NEGATIVO", 1: "NEUTRO", 2: "POSITIVO"}
        sentiment = labels_map.get(sentiment_idx, "NEUTRO")
        
        return sentiment
        
    except Exception as e:
        print(f"ERRO na análise BERT: {e}")
        return "NEUTRO"

# --- REMOVEMOS A FUNÇÃO HÍBRIDA (pois ela dependia de 'categorias') ---

def process_stream(spark):
    """
    Função principal que lê do Kafka e processa os dados.
    """
    print(f"--- Lendo do tópico Kafka: {KAFKA_TOPIC} ---")
    
    try:
        # 1. Definir o esquema SIMPLIFICADO (sem 'categorias')
        schema = StructType([
            StructField("timestamp_iso", StringType(), True),
            StructField("user_did", StringType(), True),
            StructField("text", StringType(), True)
            # StructField("categorias", ...) FOI REMOVIDO
        ])

        # 2. Ler o stream do Kafka (sem mudanças)
        df_kafka = (
            spark.readStream
            .format("kafka")
            .option("kafka.bootstrap.servers", KAFKA_SERVER)
            .option("subscribe", KAFKA_TOPIC)
            .option("startingOffsets", "latest")
            .load()
        )

        # 3. Converter e Parsear JSON (sem mudanças)
        df_json = df_kafka.select(col("value").cast("string").alias("json_value"))
        df_posts = df_json.select(from_json(col("json_value"), schema).alias("data")).select("data.*")

        # 4. Registrar a UDF (agora só podemos usar a BERT pura)
        sentiment_udf = udf(perform_sentiment_analysis_bert, StringType())
        
        # 5. Aplicar a UDF (agora só passamos o 'text')
        df_sentimento = df_posts.withColumn(
            "sentimento", sentiment_udf(col("text"))
        )
        
        # 6. Salvar em JSON (removendo 'categorias' da seleção)
        query = (
            df_sentimento
            .select("timestamp_iso", "text", "sentimento") # Coluna 'categorias' removida
            .writeStream
            .outputMode("append")
            .format("json")
            .path(PATH_SAIDA_JSON)
            .option("checkpointLocation", PATH_CHECKPOINT)
            .trigger(processingTime='1 minute')
            .start()
        )
        
        print(f"--- Query de streaming iniciada! Salvando JSON em {PATH_SAIDA_JSON} ---")
        query.awaitTermination()

    except Exception as e:
        print(f"ERRO no stream do Spark: {e}")

# --- Ponto de Partida do Script ---
if __name__ == "__main__":
    spark = get_spark_session()
    if spark:
        process_stream(spark)