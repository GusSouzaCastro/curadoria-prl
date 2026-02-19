#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import feedparser
import json
import csv
import os
import requests
from datetime import datetime
from pathlib import Path
import time
import re

# Configurações
PERFIL_FILE = "perfil.json"
ARTIGOS_VISTOS_FILE = "artigos_vistos.csv"
RESULTADOS_FILE = "recomendacoes.json"

# Carregar perfil do usuário
def carregar_perfil():
    try:
        with open(PERFIL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERRO: Arquivo {PERFIL_FILE} não encontrado!")
        return None

# Buscar feed RSS da PRL
def buscar_feed_prl():
    """Busca o feed RSS oficial da Physical Review Letters"""
    print("Buscando feed da PRL...")
    
    # URL CORRETA do feed RSS da PRL
    feed_url = "https://feeds.aps.org/rss/recent/prl.xml"
    
    try:
        # Fazer o parse do feed
        feed = feedparser.parse(feed_url)
        
        # Verificar se o feed tem entries (artigos)
        if not feed.entries:
            print(f"⚠️ Feed encontrado, mas não contém artigos. Verifique a URL: {feed_url}")
            return []
        
        print(f"✓ Feed encontrado! Processando {len(feed.entries)} artigos...")
        
        artigos = []
        for entry in feed.entries[:15]:  # Últimos 15 artigos
            # Extrair informações básicas
            titulo = entry.get('title', 'Sem título')
            link = entry.get('link', '')
            
            # Extrair resumo: pode estar em summary, description ou content
            resumo = entry.get('summary', '')
            if not resumo and hasattr(entry, 'content'):
                resumo = entry.content[0].value if entry.content else ''
            if not resumo:
                resumo = entry.get('description', 'Resumo não disponível')
            
            # Limpar tags HTML do resumo (se houver)
            resumo = re.sub(r'<[^>]+>', '', resumo)
            
            # Extrair autores
            if hasattr(entry, 'authors'):
                autores = [{'name': a.name} for a in entry.authors if hasattr(a, 'name')]
            else:
                autor_texto = entry.get('author', '')
                autores = [{'name': a.strip()} for a in autor_texto.split(',')] if autor_texto else []
            
            # Extrair data de publicação
            publicado = entry.get('published', entry.get('updated', 'Data desconhecida'))
            
            # Extrair DOI (se disponível)
            doi = None
            if hasattr(entry, 'prism_doi'):
                doi = entry.prism_doi
            elif hasattr(entry, 'dc_identifier'):
                doi = entry.dc_identifier.replace('doi:', '')
            else:
                # Tentar extrair do link
                match = re.search(r'10\.1103/[^"]+', link)
                doi = match.group(0) if match else None
            
            artigo = {
                'titulo': titulo,
                'resumo': resumo,
                'link': link,
                'publicado': publicado,
                'autores': autores,
                'doi': doi
            }
            artigos.append(artigo)
        
        print(f"✓ {len(artigos)} artigos processados com sucesso")
        return artigos
        
    except Exception as e:
        print(f"✗ Erro ao processar feed: {e}")
        return []

def extrair_doi(link):
    """Extrai DOI do link"""
    match = re.search(r'10\.1103/[^\s]+', link)
    return match.group(0) if match else None

# Verificar se artigo já foi visto
def artigo_ja_visto(titulo):
    """Verifica se o artigo já está no arquivo de vistos"""
    if not Path(ARTIGOS_VISTOS_FILE).exists():
        return False
    
    try:
        with open(ARTIGOS_VISTOS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            # Pular cabeçalho
            next(reader, None)
            for row in reader:
                if row and len(row) > 0 and row[0] == titulo:
                    return True
    except:
        pass
    return False

# Marcar artigo como visto
def marcar_como_visto(titulo, relevancia):
    """Adiciona artigo ao arquivo de vistos"""
    arquivo_existe = Path(ARTIGOS_VISTOS_FILE).exists()
    
    with open(ARTIGOS_VISTOS_FILE, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        if not arquivo_existe:
            writer.writerow(['titulo', 'data_visto', 'relevancia'])
        writer.writerow([titulo, datetime.now().isoformat(), relevancia])

# Analisar artigo com LLM
def analisar_artigo(artigo, perfil):
    """
    Versão principal que decide entre LLM real e fallback
    """
    # Se tiver token, usa LLM real
    if os.getenv("HUGGINGFACE_TOKEN"):
        return analisar_com_llm(artigo, perfil)
    else:
        # Fallback para a versão local
        return analisar_artigo_fallback(artigo, perfil)

# Gerar mensagem formatada
def formatar_mensagem(artigo, analise):
    """Formata a mensagem para exibição"""
    autores = artigo.get('autores', [])
    if autores:
        autores_str = ', '.join([a.get('name', '') for a in autores[:3]])
        if len(autores) > 3:
            autores_str += f" et al."
    else:
        autores_str = "Autores não listados"
    
    mensagem = f"""
╔══════════════════════════════════════════════════════════╗
║            NOVA RECOMENDAÇÃO - Physical Review Letters   ║
╚══════════════════════════════════════════════════════════╝

📌 TÍTULO:
{artigo['titulo']}

👥 AUTORES:
{autores_str}

📅 PUBLICADO:
{artigo['publicado']}

🎯 RELEVÂNCIA: {analise['relevancia']} (Pontuação: {analise['pontuacao']})

💡 JUSTIFICATIVA:
{analise['justificativa']}

🔑 CONCEITOS-CHAVE:
{', '.join(analise['conceitos_chave']) if analise['conceitos_chave'] else 'Não identificados'}

🔗 LINK:
{artigo['link']}

📋 DOI:
{artigo['doi'] if artigo['doi'] else 'Não disponível'}
"""
    return mensagem

# Salvar recomendações
def salvar_recomendacao(artigo, analise):
    """Salva recomendação em arquivo JSON"""
    recomendacoes = []
    if Path(RESULTADOS_FILE).exists():
        with open(RESULTADOS_FILE, 'r', encoding='utf-8') as f:
            try:
                recomendacoes = json.load(f)
            except:
                recomendacoes = []
    
    recomendacoes.append({
        'data_recomendacao': datetime.now().isoformat(),
        'artigo': artigo,
        'analise': analise
    })
    
    # Manter apenas últimas 50 recomendações
    if len(recomendacoes) > 50:
        recomendacoes = recomendacoes[-50:]
    
    with open(RESULTADOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(recomendacoes, f, ensure_ascii=False, indent=2)

# Função principal
def main():

    # Carregar variáveis de ambiente
    load_dotenv()
    
    print("=" * 60)
    print("CURADOR DE ARTIGOS - PHYSICAL REVIEW LETTERS")
    print("=" * 60)
    print(f"Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Carregar perfil
    perfil = carregar_perfil()
    if not perfil:
        print("ERRO: Perfil não encontrado. Execute o script novamente.")
        return
    
    print(f"Perfil carregado para: {perfil.get('nome', 'Usuário')}")
    print(f"Áreas de interesse: {', '.join(perfil['areas'][:3])}...")
    print(f"Palavras-chave: {', '.join(perfil['palavras_chave'][:5])}...")
    print()
    
    # Buscar artigos
    artigos = buscar_feed_prl()
    if not artigos:
        print("Nenhum artigo encontrado no feed.")
        return
    
    print(f"\nProcessando {len(artigos)} artigos...")
    print("-" * 60)
    
    recomendacoes = []
    
    for i, artigo in enumerate(artigos, 1):
        print(f"\n[{i}/{len(artigos)}] Analisando...")
        
        # Verificar se já foi visto
        if artigo_ja_visto(artigo['titulo']):
            print(f"  ↳ Artigo já processado anteriormente (pulado)")
            continue
        
        # Analisar artigo
        analise = analisar_artigo(artigo, perfil)
        print(f"  ↳ Relevância: {analise['relevancia']} ({analise['pontuacao']} pts)")
        
        # Marcar como visto
        marcar_como_visto(artigo['titulo'], analise['relevancia'])
        
        # Se relevante, salvar
        if analise['relevancia'] == "ALTA":
            print(f"  ↳ ⭐ RECOMENDADO!")
            recomendacoes.append((artigo, analise))
            salvar_recomendacao(artigo, analise)
            
            # Mostrar mensagem formatada
            print(formatar_mensagem(artigo, analise))
    
    # Resumo final
    print("=" * 60)
    print(f"RESUMO DA EXECUÇÃO")
    print("=" * 60)
    print(f"Total de artigos processados: {len(artigos)}")
    print(f"Artigos recomendados (ALTA): {len(recomendacoes)}")
    print(f"Artigos ignorados (já vistos): {len(artigos) - len([a for a in artigos if artigo_ja_visto(a['titulo'])])}")
    print(f"\nRecomendações salvas em: {RESULTADOS_FILE}")
    print(f"Histórico salvo em: {ARTIGOS_VISTOS_FILE}")
    print(f"Fim: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

import os
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# Carregar variáveis de ambiente
load_dotenv()

def analisar_com_llm(artigo, perfil):
    """
    Analisa um artigo usando a Hugging Face Inference API
    """
    print(f"  ↳ Enviando para LLM: {artigo['titulo'][:50]}...")
    
    # Obter token do ambiente
    hf_token = os.getenv("HUGGINGFACE_TOKEN")
    if not hf_token:
        print("  ↳ ⚠️ Token da Hugging Face não encontrado. Usando fallback local.")
        return analisar_artigo_fallback(artigo, perfil)
    
    try:
        # Inicializar cliente
        client = InferenceClient(token=hf_token)
        
        # Construir prompt
        prompt = self.construir_prompt_llm(artigo, perfil)
        
        # Chamar API
        response = client.chat_completion(
            model="mistralai/Mistral-7B-Instruct-v0.3",
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em curadoria de artigos científicos em física. Responda apenas com JSON válido."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        
        # Extrair resposta
        resultado = response['choices'][0]['message']['content']
        
        # Parse do JSON
        import json
        analise = json.loads(resultado)
        
        # Validar campos obrigatórios
        if not all(k in analise for k in ['relevancia', 'justificativa', 'pontuacao', 'conceitos_chave']):
            raise ValueError("Resposta do LLM não contém todos os campos obrigatórios")
        
        print(f"  ↳ ✓ Análise concluída: {analise['relevancia']} ({analise['pontuacao']}/10)")
        return analise
        
    except Exception as e:
        print(f"  ↳ ⚠️ Erro na API: {e}. Usando fallback local.")
        return analisar_artigo_fallback(artigo, perfil)

def construir_prompt_llm(artigo, perfil):
    """
    Constrói o prompt para o LLM
    """
    # Formatar áreas de interesse
    areas = ", ".join(perfil['areas'])
    keywords = ", ".join(perfil['palavras_chave'])
    
    # Formatar autores
    autores = artigo.get('autores', [])
    autores_str = ", ".join([a.get('name', '') for a in autores[:3]])
    if len(autores) > 3:
        autores_str += f" et al."
    
    prompt = f"""
Analise este artigo da Physical Review Letters e determine sua relevância para um pesquisador.

## Perfil do Pesquisador:
- Áreas de pesquisa: {areas}
- Palavras-chave de interesse: {keywords}
- {perfil.get('instrucoes_extras', '')}

## Artigo:
Título: {artigo['titulo']}
Autores: {autores_str}
Resumo: {artigo['resumo']}

## Instruções:
1. Avalie a relevância deste artigo para o pesquisador baseado no perfil acima
2. Atribua uma pontuação de 0 a 10 (0 = totalmente irrelevante, 10 = extremamente relevante)
3. Classifique a relevância como: "BAIXA" (0-3), "MEDIA" (4-6), "ALTA" (7-10)
4. Identifique os principais conceitos e palavras-chave do artigo
5. Escreva uma justificativa breve (2-3 frases) explicando sua avaliação

## Formato de Resposta (JSON obrigatório):
{{
    "relevancia": "ALTA/MEDIA/BAIXA",
    "pontuacao": 7,
    "justificativa": "Este artigo é relevante porque...",
    "conceitos_chave": ["conceito1", "conceito2", "conceito3"]
}}
"""
    return prompt

def analisar_artigo_fallback(artigo, perfil):
    """
    Versão fallback quando a API não está disponível
    (cópia da função anterior de simulação)
    """
    print(f"  ↳ Usando análise local (fallback)")
    
    titulo_resumo = (artigo['titulo'] + ' ' + artigo['resumo']).lower()
    
    # Contar palavras-chave
    matches = []
    for kw in perfil['palavras_chave']:
        if kw.lower() in titulo_resumo:
            matches.append(kw)
    
    # Contar áreas
    areas_encontradas = []
    for area in perfil['areas']:
        if area.lower() in titulo_resumo:
            areas_encontradas.append(area)
    
    # Calcular pontuação
    pontuacao = len(matches) * 3 + len(areas_encontradas) * 2
    
    if pontuacao >= 10:
        relevancia = "ALTA"
    elif pontuacao >= 5:
        relevancia = "MEDIA"
    else:
        relevancia = "BAIXA"
    
    return {
        'relevancia': relevancia,
        'pontuacao': pontuacao,
        'justificativa': f"Encontradas {len(matches)} palavras-chave e {len(areas_encontradas)} áreas de interesse.",
        'conceitos_chave': matches[:5]
    }

if __name__ == "__main__":
    main()
