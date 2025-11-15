import json
import time
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

# --- IMPORTAÇÕES ---
from atproto import (
    FirehoseSubscribeReposClient,
    parse_subscribe_repos_message,
    CAR,
    models
)
# (Não precisamos mais do libipld ou cbor!)
# --------------------

# --- Configuração ---
# Keywords organizadas por categorias semânticas para análise mais robusta
KEYWORDS_OPERACAO = [
    'operação', 'operacao', 'operacão', 'megaoperação', 'mega operação',
    'blitz', 'ação policial', 'acao policial', 'incursão', 'incursao',
    'invasão', 'invasao', 'cerco', 'batida'
]

KEYWORDS_POLICIA = [
    'polícia', 'policia', 'pm', 'pmerj', 'policial', 'policiais',
    'bope', 'core', 'choque', 'militar', 'militares', 'batalhão', 'batalhao',
    'caveirão', 'caveirao', 'blindado', 'viatura', 'prf', 'pcerj'
]

KEYWORDS_VIOLENCIA = [
    'tiroteio', 'tiro', 'tiros', 'bala perdida', 'bala',
    'confronto', 'guerra', 'fogo cruzado', 'troca de tiros',
    'baleado', 'ferido', 'morto', 'vítima', 'vitima', 'morte',
    'disparos', 'trocação', 'trocacao', 'fuzil', 'armamento'
]

KEYWORDS_ATORES = [
    'traficante', 'traficantes', 'bandido', 'bandidos', 'criminoso', 'criminosos',
    'facção', 'faccao', 'milícia', 'milicia', 'miliciano',
    'cv', 'tcp', 'adp', 'comando vermelho', 'terceiro comando'
]

KEYWORDS_LOCAIS = [
    'favela', 'comunidade', 'morro', 'complexo',
    'alemão', 'alemao', 'rocinha', 'maré', 'mare',
    'jacarezinho', 'cidade de deus', 'penha', 'pavão', 'pavao',
    'vigário geral', 'vigario', 'acari', 'manguinhos'
]

KEYWORDS_REACAO = [
    'medo', 'pânico', 'panico', 'desespero', 'terror', 'susto',
    'correria', 'socorro', 'helicóptero', 'helicoptero', 'caveirão',
    'escola fechada', 'comércio fechado', 'comercio fechado',
    'trânsito interditado', 'transito', 'pista bloqueada'
]

# Combinar todas as keywords em uma lista única para filtragem
KEYWORDS = (
    KEYWORDS_OPERACAO + 
    KEYWORDS_POLICIA + 
    KEYWORDS_VIOLENCIA + 
    KEYWORDS_ATORES + 
    KEYWORDS_LOCAIS + 
    KEYWORDS_REACAO
)

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
                # --- A CORREÇÃO ESTÁ AQUI ---
                # A variável 'record' já é o dicionário que queremos!
                record = car.blocks.get(op.cid)
                if not record:
                    continue
                
                # A linha de decodificação (que causava o erro) FOI REMOVIDA.
                # --- FIM DA CORREÇÃO ---
                
                post_text = record.get('text', '').lower()
                
                if any(keyword in post_text for keyword in KEYWORDS):
                    
                    # Identificar categorias presentes no post
                    categorias = {
                        'operacao': any(k in post_text for k in KEYWORDS_OPERACAO),
                        'policia': any(k in post_text for k in KEYWORDS_POLICIA),
                        'violencia': any(k in post_text for k in KEYWORDS_VIOLENCIA),
                        'atores': any(k in post_text for k in KEYWORDS_ATORES),
                        'locais': any(k in post_text for k in KEYWORDS_LOCAIS),
                        'reacao': any(k in post_text for k in KEYWORDS_REACAO)
                    }
                    
                    print(f"\n== POST FILTRADO ENCONTRADO ==")
                    print(f"Usuário: {commit.repo}")
                    print(f"Texto: {record.get('text')}")
                    print(f"Categorias: {[k for k, v in categorias.items() if v]}")
                    
                    post_data = {
                        'timestamp_iso': record.get('createdAt'),
                        'user_did': commit.repo,
                        'text': record.get('text'),
                        'categorias': categorias
                    }
                    
                    producer.send(KAFKA_TOPIC, post_data)
                    producer.flush()
                    print(f"-> Enviado para o Kafka (tópico: {KAFKA_TOPIC})")
                    
            except Exception as e:
                print(f"ERRO ao processar um record: {e}")


# --- Ponto de Partida do Script ---
if __name__ == "__main__":
    print("Iniciando o Coletor do Bluesky (v6 - Final)...")
    
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