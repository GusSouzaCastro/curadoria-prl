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
    """Busca o feed RSS da Physical Review Letters"""
    print("Buscando feed da PRL...")
    
    # Tentar URLs comuns do feed da PRL
    urls_teste = [
        "https://journals.aps.org/prl/rss/current.xml",
        "https://journals.aps.org/prl/feed",
        "https://rss.journals.aps.org/prl/current.xml"
    ]
    
    feed_url = None
    for url in urls_teste:
        try:
            teste = feedparser.parse(url)
            if teste.entries:
                feed_url = url
                print(f"Feed encontrado em: {url}")
                break
        except:
            continue
    
    if not feed_url:
        print("Usando URL padrão - pode não funcionar")
        feed_url = "https://journals.aps.org/prd/recent"
    
    # Fazer o parse do feed
    feed = feedparser.parse(feed_url)
    
    artigos = []
    for entry in feed.entries[:15]:  # Últimos 15 artigos
        artigo = {
            'titulo': entry.get('title', 'Sem título'),
            'resumo': entry.get('summary', entry.get('description', 'Sem resumo')),
            'link': entry.get('link', ''),
            'publicado': entry.get('published', entry.get('updated', 'Data desconhecida')),
            'autores': entry.get('authors', [{'name': a} for a in entry.get('author', '').split(',')]) if entry.get('authors') else [],
            'doi': extrair_doi(entry.get('link', ''))
        }
        artigos.append(artigo)
    
    print(f"Encontrados {len(artigos)} artigos no feed")
    return artigos

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

# Analisar artigo com LLM (versão simulada por enquanto)
def analisar_artigo(artigo, perfil):
    """
    Por enquanto, vamos usar uma versão simplificada que simula a análise.
    Depois substituiremos pela chamada real à API.
    """
    print(f"Analisando: {artigo['titulo'][:50]}...")
    
    # SIMULAÇÃO: Contar quantas palavras-chave aparecem
    titulo_resumo = (artigo['titulo'] + ' ' + artigo['resumo']).lower()
    
    # Contar ocorrências de palavras-chave
    matches = []
    for kw in perfil['palavras_chave']:
        if kw.lower() in titulo_resumo:
            matches.append(kw)
    
    # Contar ocorrências de áreas
    areas_encontradas = []
    for area in perfil['areas']:
        if area.lower() in titulo_resumo:
            areas_encontradas.append(area)
    
    # Calcular relevância (simulado)
    pontuacao = len(matches) * 3 + len(areas_encontradas) * 2
    
    if pontuacao >= 10:
        relevancia = "ALTA"
    elif pontuacao >= 5:
        relevancia = "MEDIA"
    else:
        relevancia = "BAIXA"
    
    # Simular análise do LLM
    analise = {
        'relevancia': relevancia,
        'pontuacao': pontuacao,
        'justificativa': f"Encontradas {len(matches)} palavras-chave e {len(areas_encontradas)} áreas de interesse.",
        'conceitos_chave': matches[:5],
        'areas_relacionadas': areas_encontradas
    }
    
    # Pequena pausa para não sobrecarregar
    time.sleep(0.5)
    
    return analise

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

if __name__ == "__main__":
    main()