import json
import time
import re
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

# --- IMPORTAÇÕES ---
from atproto import (
    FirehoseSubscribeReposClient,
    parse_subscribe_repos_message,
    CAR,
    models
)
# (Import da libipld não é mais necessário aqui se usarmos o 'record' direto)
# --------------------

# --- Configuração ---
# O filtro agora é APENAS 'bope'
ALL_KEYWORDS = ['bope']

# Criar um padrão RegEx para "Whole Word Matching"
# \b(bope)\b vai pegar "BOPE" ou "bope", mas não "bopest"
KEYWORD_PATTERN = re.compile(r'\b(' + '|'.join(re.escape(k) for k in ALL_KEYWORDS) + r')\b', re.IGNORECASE)
# -----------------------------------------------------------

KAFKA_TOPIC = 'posts_bluesky'
KAFKA_SERVER = 'localhost:9092'
# --- Fim da Configuração ---

def create_kafka_producer(retries=10):
    for i in range(retries):
        try:
            print(f"Tentando conectar ao Kafka em {KAFKA_SERVER} (Tentativa {i+1}/{retries})...")
            producer = KafkaProducer(
                bootstrap_servers=[KAFKA_SERVER],
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
            )
            print("SUCESSO: Conectado ao Kafka.")
            return producer
        except NoBrokersAvailable:
            print("Falha ao conectar. Broker indisponível. Tentando novamente em 5 segundos...")
            time.sleep(5)
    
    print(f"ERRO FATAL: Não foi possível conectar ao Kafka após {retries} tentativas.")
    return None

def on_message_handler(message):
    global producer
    
    commit = parse_subscribe_repos_message(message)
    
    if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
        return

    try:
        car = CAR.from_bytes(commit.blocks)
    except Exception:
        return

    for op in commit.ops:
        if op.action == 'create' and op.path.startswith('app.bsky.feed.post'):
            
            try:
                record = car.blocks.get(op.cid)
                if not record:
                    continue
                
                # --- NOVO FILTRO DE IDIOMA ---
                post_langs = record.get('langs', []) 
                
                # Se 'pt' (Português) NÃO ESTIVER na lista, pulamos o post.
                if 'pt' not in post_langs:
                    continue 
                # --- FIM DO FILTRO DE IDIOMA ---

                post_text = record.get('text', '') 
                
                # Aplicamos nosso filtro de 'bope'
                if KEYWORD_PATTERN.search(post_text):
                    
                    print(f"\n== POST FILTRADO ENCONTRADO (v10 - BOPE) ==")
                    print(f"Usuário: {commit.repo}")
                    print(f"Texto: {record.get('text')}")
                    
                    # --- JSON SIMPLIFICADO ---
                    # Removemos as categorias
                    post_data = {
                        'timestamp_iso': record.get('createdAt'),
                        'user_did': commit.repo,
                        'text': record.get('text')
                    }
                    
                    producer.send(KAFKA_TOPIC, post_data)
                    producer.flush()
                    print(f"-> Enviado para o Kafka (tópico: {KAFKA_TOPIC})")
                    
            except Exception as e:
                print(f"ERRO ao processar um record: {e}")


# --- Ponto de Partida do Script ---
if __name__ == "__main__":
    print("Iniciando o Coletor do Bluesky (v10 - Apenas BOPE)...")
    
    producer = create_kafka_producer()
    
    if producer:
        print("Conectando ao Firehose do Bluesky...")
        client = FirehoseSubscribeReposClient()
        
        try:
            client.start(on_message_handler)
        except KeyboardInterrupt:
            print("\nEncerrando o coletor...")
            client.stop()
            producer.close()
        except Exception as e:
            print(f"ERRO FATAL no Firehose: {e}")
            producer.close()