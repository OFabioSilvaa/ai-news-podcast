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

# --- CONFIGURAÇÕES ---
# Pega as senhas dos Segredos do GitHub
CHAVE_GEMINI = os.environ.get("CHAVE_GEMINI")
TOKEN_TELEGRAM = os.environ.get("TOKEN_TELEGRAM")

# Personagens
PERSONAGEM_A = "Ana"
VOZ_A = "pt-BR-ThalitaMultilingualNeural"
PERSONAGEM_B = "Carlos"
VOZ_B = "pt-BR-AntonioNeural"

# Caminhos
CAMINHO_DB = 'memoria_noticias.duckdb'
# Jazz Royalty Free
URL_MUSICA = "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/no_curator/Kevin_MacLeod/Jazz_Sampler/Kevin_MacLeod_-_AcidJazz.mp3"

# Inicialização
genai.configure(api_key=CHAVE_GEMINI)
modelo = genai.GenerativeModel('models/gemini-2.5-flash')
bot = telebot.TeleBot(TOKEN_TELEGRAM)
nest_asyncio.apply()

# --- FUNÇÕES ---

def limpar_texto_audio(texto):
    texto = re.sub(r'\(.*?\)', '', texto)
    texto = texto.replace('*', '').replace('#', '')
    return texto.strip()

def baixar_musica_fundo():
    caminho_musica = "musica_fundo.mp3"
    if not os.path.exists(caminho_musica):
        print("Baixando Jazz...")
        try:
            r = requests.get(URL_MUSICA)
            with open(caminho_musica, 'wb') as f:
                f.write(r.content)
        except Exception as e:
            print(f"Erro download música: {e}")
            return None
    return caminho_musica

def mixar_audio(caminho_fala):
    print("Mixando áudio...")
    caminho_musica = baixar_musica_fundo()
    if not caminho_musica: return caminho_fala
    
    try:
        fala = AudioSegment.from_mp3(caminho_fala)
        bg_music = AudioSegment.from_mp3(caminho_musica)
        
        bg_music = bg_music - 22 
        while len(bg_music) < len(fala) + 5000:
            bg_music += bg_music
        bg_music = bg_music[:len(fala) + 2000]
        bg_music = bg_music.fade_in(2000).fade_out(2000)
        
        podcast_final = bg_music.overlay(fala, position=1000)
        nome_final = "PODCAST_FINAL.mp3"
        podcast_final.export(nome_final, format="mp3")
        return nome_final
    except Exception as e:
        print(f"Erro mixagem: {e}")
        return caminho_fala 

def gerar_conteudo(noticias):
    print("Gerando roteiro...")
    txt_noticias = "\n".join([f"- {n['titulo']}" for n in noticias])
    prompt = f"""
    Atue como Roteirista Sênior. Diálogo curto entre {PERSONAGEM_A} (Sênior) e {PERSONAGEM_B} (Inovador).
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
        print(f"Erro IA: {e}")
        return None

async def criar_podcast(roteiro):
    print("Gerando vozes...")
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

# --- ORQUESTRADOR DE TESTE ---
async def main():
    # 1. COLOQUE SEU ID AQUI (Ex: "123456789")
    chat_id = "5953297022"

    if chat_id == "5953297022":
        print("ERRO: Você esqueceu de colocar o número do ID no código!")
        return

    # 2. Notícia Falsa para Testar Envio
    print("Modo Teste: Criando notícia simulada...")
    noticias = [{
        'titulo': 'Sucesso Total: O GitHub Actions está funcionando!', 
        'link': 'https://github.com'
    }]

    # 3. Gera Roteiro
    roteiro = gerar_conteudo(noticias)
    if not roteiro: return

    # 4. Gera Áudio
    audio_voz = await criar_podcast(roteiro)
    audio_final = mixar_audio(audio_voz) if audio_voz else None

    # 5. Envia
    if audio_final:
        print(f"Tentando enviar para ID: {chat_id}...")
        try:
            msg = f"✅ TESTE GITHUB - {datetime.now().strftime('%H:%M')}\n\nFunciona!"
            bot.send_message(chat_id, msg)
            
            with open(audio_final, 'rb') as aud:
                bot.send_audio(chat_id, aud, title="Teste Final", performer="Ana & Carlos")
            print("ENVIO COM SUCESSO!")
        except Exception as e:
            print(f"Erro no envio Telegram: {e}")

if __name__ == "__main__":
    asyncio.run(main())
