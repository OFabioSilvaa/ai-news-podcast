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

# --- 1. CONFIGURAÇÕES ---
# Pega as senhas dos Segredos do GitHub
CHAVE_GEMINI = os.environ.get("CHAVE_GEMINI")
TOKEN_TELEGRAM = os.environ.get("TOKEN_TELEGRAM")

# 🚨 IMPORTANTE: COLOQUE SEU NÚMERO AQUI ENTRE ASPAS (Ex: "123456789")
CHAT_ID_FIXO = "5953297022" 

# Personagens
PERSONAGEM_A = "Ana"
VOZ_A = "pt-BR-ThalitaMultilingualNeural"
PERSONAGEM_B = "Carlos"
VOZ_B = "pt-BR-AntonioNeural"

CAMINHO_DB = 'memoria_noticias.duckdb'
URL_MUSICA = "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/no_curator/Kevin_MacLeod/Jazz_Sampler/Kevin_MacLeod_-_AcidJazz.mp3"

# Inicialização segura
if not CHAVE_GEMINI:
    print("❌ ERRO GRAVE: CHAVE_GEMINI não encontrada nas variáveis de ambiente.")
if not TOKEN_TELEGRAM:
    print("❌ ERRO GRAVE: TOKEN_TELEGRAM não encontrado nas variáveis de ambiente.")
else:
    genai.configure(api_key=CHAVE_GEMINI)
    modelo = genai.GenerativeModel('models/gemini-2.5-flash')
    bot = telebot.TeleBot(TOKEN_TELEGRAM)
    nest_asyncio.apply()

# --- 2. FUNÇÕES AUXILIARES ---

def limpar_texto_audio(texto):
    texto = re.sub(r'\(.*?\)', '', texto)
    texto = texto.replace('*', '').replace('#', '')
    return texto.strip()

def baixar_musica_fundo():
    caminho_musica = "musica_fundo.mp3"
    if not os.path.exists(caminho_musica):
        print("🎵 Baixando Jazz de fundo...")
        try:
            r = requests.get(URL_MUSICA)
            with open(caminho_musica, 'wb') as f:
                f.write(r.content)
        except Exception as e:
            print(f"⚠️ Erro ao baixar música: {e}")
            return None
    return caminho_musica

def mixar_audio(caminho_fala):
    caminho_musica = baixar_musica_fundo()
    if not caminho_musica: return caminho_fala
    
    print("🎛️ Mixando voz e música...")
    try:
        fala = AudioSegment.from_mp3(caminho_fala)
        bg_music = AudioSegment.from_mp3(caminho_musica)
        
        # Volume da música (-22dB)
        bg_music = bg_music - 22 
        
        # Loop da música se for curta
        while len(bg_music) < len(fala) + 5000:
            bg_music += bg_music
            
        # Corta tamanho exato
        bg_music = bg_music[:len(fala) + 2000]
        bg_music = bg_music.fade_in(2000).fade_out(2000)
        
        # Junta
        podcast_final = bg_music.overlay(fala, position=1000)
        nome_final = "PODCAST_FINAL.mp3"
        podcast_final.export(nome_final, format="mp3")
        return nome_final
    except Exception as e:
        print(f"⚠️ Erro na mixagem: {e}")
        return caminho_fala 

def coletar_noticias():
    print("🔎 Lendo RSS...")
    con = duckdb.connect(CAMINHO_DB)
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
            for entry in feed.entries[:2]: 
                link = entry.link
                if not con.execute("SELECT link FROM lidas WHERE link = ?", [link]).fetchone():
                    novas.append({'titulo': entry.title, 'link': link})
                    # ATENÇÃO: Em produção real, descomente a linha abaixo para salvar no banco
                    # con.execute("INSERT INTO lidas VALUES (?)", [link])
        except Exception as e:
            print(f"⚠️ Erro RSS {url}: {e}")
            
    con.close()
    return novas

def gerar_conteudo(noticias):
    print("🧠 Gerando roteiro com IA...")
    txt_noticias = "\n".join([f"- {n['titulo']}" for n in noticias])
    prompt = f"""
    Atue como Roteirista Sênior. Dialogo curto entre {PERSONAGEM_A} (Sênior) e {PERSONAGEM_B} (Inovador).
    Pauta: {txt_noticias}
    Diretrizes: Tom corporativo, direto, sem gírias.
    Formato:
    {PERSONAGEM_A}: [fala]
    {PERSONAGEM_B}: [fala]
    """
    try:
        resp = modelo.generate_content(prompt)
        return resp.text
    except Exception as e:
        print(f"❌ Erro Gemini: {e}")
        return None

async def criar_podcast(roteiro):
    print("🎙️ Sintetizando vozes...")
    linhas = roteiro.split('\n')
    arquivos = []
    for i, linha in enumerate(linhas):
        linha = linha.replace('*', '').strip()
        if not linha: continue
        
        voz, fala = None, ""
        if linha.startswith(f"{PERSONAGEM_A}:"):
            voz, fala = VOZ_A, linha.split(":", 1)[1]
        elif linha.startswith(f"{PERSONAGEM_B}:"):
            voz, fala = VOZ_B, linha.split(":", 1)[1]
        
        if voz:
            fala = limpar_texto_audio(fala)
            if fala:
                fname = f"temp_{i}.mp3"
                await edge_tts.Communicate(fala, voz, rate="+5%").save(fname)
                arquivos.append(fname)
    
    if arquivos:
        nome_bruto = "vozes_brutas.mp3"
        with open(nome_bruto, 'wb') as out:
            for f in arquivos:
                with open(f, 'rb') as inp: out.write(inp.read())
                os.remove(f)
        return nome_bruto
    return None

# --- 3. ORQUESTRADOR ---
async def main():
    print(f"🚀 Iniciando automação. ID Alvo: {CHAT_ID_FIXO}")
    
    # Validação Básica
    if CHAT_ID_FIXO == "SEU_NUMERO_AQUI":
        print("❌ PARE! Você esqueceu de colocar seu ID do Telegram na linha 19.")
        return

    # 1. COLETA (Modo Robusto: Se não achar no RSS, cria notícia de teste)
    noticias = coletar_noticias()
    
    if not noticias:
        print("😴 Sem notícias novas no RSS. Ativando MODO DE TESTE para não falhar.")
        noticias = [{
            'titulo': 'Automação GitHub Actions Funcionando!', 
            'link': 'https://github.com'
        }]

    # 2. GERAÇÃO
    roteiro = gerar_conteudo(noticias)
    if not roteiro: return

    # 3. ÁUDIO
    audio_voz = await criar_podcast(roteiro)
    audio_final = mixar_audio(audio_voz) if audio_voz else None

    # 4. ENVIO (Com tratamento de erro detalhado)
    if audio_final:
        print(f"📤 Tentando enviar para Telegram...")
        msg = f"✅ UPDATE TECH - {datetime.now().strftime('%d/%m')}\n\n"
        for n in noticias: msg += f"- {n['titulo']}\n{n['link']}\n\n"
        
        try:
            # Tenta mandar só o texto primeiro (pra testar conexão)
            bot.send_message(CHAT_ID_FIXO, msg)
            print("✅ Texto enviado!")
            
            # Tenta mandar o áudio
            with open(audio_final, 'rb') as aud:
                bot.send_audio(CHAT_ID_FIXO, aud, title="Tech Briefing", performer="Ana & Carlos")
            print("✅ Áudio enviado!")
            
        except Exception as e:
            print(f"❌ ERRO FATAL AO ENVIAR PRO TELEGRAM: {e}")
            print("Dica: Verifique se o TOKEN_TELEGRAM nos Segredos está correto.")

if __name__ == "__main__":
    asyncio.run(main())
