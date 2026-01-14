import os
import google.generativeai as genai
import feedparser
import duckdb
import edge_tts
import nest_asyncio
import asyncio
import telebot
import re
import requests
from datetime import datetime
from pydub import AudioSegment

# --- CONFIGURAÇÕES GERAIS ---

# Pego as chaves de segurança que configurei no ambiente
CHAVE_GEMINI = os.environ.get("CHAVE_GEMINI")
TOKEN_TELEGRAM = os.environ.get("TOKEN_TELEGRAM")

# Defini o ID fixo aqui para garantir que a mensagem chegue no meu chat
CHAT_ID_FIXO = "5953297022"

# Configuro os personagens que vão apresentar o podcast
PERSONAGEM_A = "Ana"
VOZ_A = "pt-BR-ThalitaMultilingualNeural"
PERSONAGEM_B = "Carlos"
VOZ_B = "pt-BR-AntonioNeural"

# Defino onde vou salvar o banco de dados local
CAMINHO_DB = 'memoria_noticias.duckdb'

# Escolhi este link do GitHub para a música porque é mais estável e não bloqueia robôs
URL_MUSICA = "https://github.com/rafaelreis-hotmart/Audio-Sample-files/raw/master/sample.mp3"

# Verifico se as chaves existem antes de começar, para não dar erro lá na frente
if not CHAVE_GEMINI or not TOKEN_TELEGRAM:
    print("Erro: Não encontrei as chaves de acesso. Preciso configurar os Secrets.")
else:
    genai.configure(api_key=CHAVE_GEMINI)
    modelo = genai.GenerativeModel('models/gemini-2.5-flash')
    bot = telebot.TeleBot(TOKEN_TELEGRAM)
    nest_asyncio.apply()

# --- FUNÇÕES DE APOIO ---

def limpar_texto_audio(texto):
    # Removo caracteres especiais que podem atrapalhar a fala da IA
    texto = re.sub(r'\(.*?\)', '', texto)
    texto = texto.replace('*', '').replace('#', '')
    return texto.strip()

def baixar_musica_fundo():
    caminho_musica = "musica_fundo.mp3"
    
    # Se eu já baixei a música antes, uso a que está salva para economizar tempo
    if os.path.exists(caminho_musica):
        return caminho_musica

    print("Estou baixando a música de fundo...")
    try:
        # Aqui eu uso um cabeçalho falso para fingir que sou um navegador Chrome
        # Isso evita que o servidor bloqueie meu download achando que sou um robô
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        r = requests.get(URL_MUSICA, headers=headers, timeout=10)
        
        if r.status_code == 200:
            with open(caminho_musica, 'wb') as f:
                f.write(r.content)
            return caminho_musica
        else:
            print(f"Tive um problema ao baixar a música. Código de erro: {r.status_code}")
            return None
            
    except Exception as e:
        print(f"Ocorreu uma exceção durante o download da música: {e}")
        return None

def mixar_audio(caminho_fala):
    # Tento baixar a música primeiro
    caminho_musica = baixar_musica_fundo()
    
    # Se o download falhou, decidi retornar apenas a voz para não perder o podcast inteiro
    if not caminho_musica: 
        print("Aviso: Vou enviar o áudio sem música pois não consegui baixar o arquivo de fundo.")
        return caminho_fala
    
    print("Iniciando a mixagem da voz com a música...")
    try:
        fala = AudioSegment.from_mp3(caminho_fala)
        bg_music = AudioSegment.from_mp3(caminho_musica)
        
        # Abaixo o volume da música em 25dB para ela ficar bem de fundo
        bg_music = bg_music - 25
        
        # Repito a música em loop para cobrir toda a duração da fala
        while len(bg_music) < len(fala) + 5000:
            bg_music += bg_music
            
        # Corto a música para ter o tamanho exato da fala mais uma margem de segurança
        bg_music = bg_music[:len(fala) + 2000]
        # Aplico fade in e fade out para suavizar o início e o fim
        bg_music = bg_music.fade_in(2000).fade_out(2000)
        
        # Junto as duas faixas
        podcast_final = bg_music.overlay(fala, position=1000)
        
        nome_final = "PODCAST_FINAL.mp3"
        podcast_final.export(nome_final, format="mp3")
        return nome_final
    except Exception as e:
        print(f"Falha na biblioteca de áudio (Pydub): {e}")
        return caminho_fala 

def coletar_noticias():
    print("Verificando as fontes RSS...")
    con = duckdb.connect(CAMINHO_DB)
    # Crio a tabela se ela não existir para guardar o histórico
    con.execute("CREATE TABLE IF NOT EXISTS lidas (link TEXT)")
    
    fontes = [
        "https://openai.com/news/rss.xml",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "http://googleaiblog.blogspot.com/atom.xml"
    ]
    
    novas = []
    for url in fontes:
        try:
            feed = feedparser.parse(url)
            # Pego apenas as 2 primeiras notícias para não ficar muito longo
            for entry in feed.entries[:2]: 
                link = entry.link
                # Verifico no banco se já li essa notícia antes
                if not con.execute("SELECT link FROM lidas WHERE link = ?", [link]).fetchone():
                    novas.append({'titulo': entry.title, 'link': link})
                    # Em produção, eu descomentaria a linha abaixo para salvar no banco
                    # con.execute("INSERT INTO lidas VALUES (?)", [link])
        except Exception as e:
            print(f"Erro ao ler o feed {url}: {e}")
            
    con.close()
    return novas

def gerar_conteudo(noticias):
    print("Solicitando ao Gemini a criação do roteiro...")
    txt_noticias = "\n".join([f"- {n['titulo']}" for n in noticias])
    
    # Estruturei o prompt para garantir que a IA siga o formato de diálogo
    prompt = f"""
    Atue como Roteirista de Podcast Tech. 
    Crie um diálogo curto, profissional e direto entre {PERSONAGEM_A} e {PERSONAGEM_B}.
    Notícias de hoje:
    {txt_noticias}
    
    Regras:
    - {PERSONAGEM_A} introduz o tópico.
    - {PERSONAGEM_B} complementa com dados técnicos.
    - Use linguagem natural.
    - Limite total de 150 palavras.
    
    Formato obrigatório:
    {PERSONAGEM_A}: [fala]
    {PERSONAGEM_B}: [fala]
    """
    try:
        resp = modelo.generate_content(prompt)
        return resp.text
    except Exception as e:
        print(f"Erro na API do Gemini: {e}")
        return None

async def criar_podcast(roteiro):
    print("Transformando o texto em áudio neural...")
    linhas = roteiro.split('\n')
    arquivos = []
    
    for i, linha in enumerate(linhas):
        linha = linha.replace('*', '').strip()
        if not linha: continue
        
        voz, fala = None, ""
        # Identifico quem está falando para atribuir a voz correta
        if linha.startswith(f"{PERSONAGEM_A}:"):
            voz, fala = VOZ_A, linha.split(":", 1)[1]
        elif linha.startswith(f"{PERSONAGEM_B}:"):
            voz, fala = VOZ_B, linha.split(":", 1)[1]
        
        if voz:
            fala = limpar_texto_audio(fala)
            if fala:
                fname = f"temp_{i}.mp3"
                # Uso o Edge TTS para gerar o áudio
                await edge_tts.Communicate(fala, voz, rate="+0%").save(fname)
                arquivos.append(fname)
    
    # Se gerei arquivos de áudio, junto todos em um só
    if arquivos:
        nome_bruto = "vozes_brutas.mp3"
        with open(nome_bruto, 'wb') as out:
            for f in arquivos:
                with open(f, 'rb') as inp: out.write(inp.read())
                os.remove(f) # Limpo os arquivos temporários
        return nome_bruto
    return None

# --- FLUXO PRINCIPAL ---

async def main():
    print(f"Iniciando a execução do pipeline. ID de destino: {CHAT_ID_FIXO}")
    
    # 1. Coleta de Dados
    noticias = coletar_noticias()
    
    # Se não tiver notícias reais, crio uma falsa apenas para testar se o áudio está funcionando
    if not noticias:
        print("Nenhuma notícia nova encontrada. Vou usar uma notícia de teste para validar o áudio.")
        noticias = [{'titulo': 'Teste de Sistema com Trilha Sonora', 'link': 'https://github.com'}]

    # 2. Geração do Roteiro
    roteiro = gerar_conteudo(noticias)
    if not roteiro: return

    # 3. Processamento de Áudio
    audio_voz = await criar_podcast(roteiro)
    if audio_voz:
        # Aqui é onde aplico a trilha de fundo
        audio_final = mixar_audio(audio_voz) 
    else:
        print("Não foi possível gerar o áudio das vozes.")
        return

    # 4. Entrega via Telegram
    if audio_final:
        tamanho = os.path.getsize(audio_final)
        print(f"Preparando para enviar arquivo de {tamanho} bytes...")
        try:
            caption = f"Update Tecnológico\n\n" + "\n".join([f"- {n['titulo']}" for n in noticias])
            
            with open(audio_final, 'rb') as aud:
                bot.send_audio(
                    CHAT_ID_FIXO, 
                    aud, 
                    title="Daily AI News", 
                    performer="Ana & Carlos", 
                    caption=caption
                )
            print("Processo finalizado com sucesso. O áudio foi enviado.")
        except Exception as e:
            print(f"Falha ao enviar mensagem para o Telegram: {e}")

if __name__ == "__main__":
    asyncio.run(main())
