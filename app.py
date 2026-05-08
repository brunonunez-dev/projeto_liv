import requests
import streamlit as st
import time
import json
import os
import re
import threading
from deep_translator import GoogleTranslator
from unidecode import unidecode

# --- CONFIGURAÇÃO E CONSTANTES ---
CACHE_FILE = "books_database.json"
SEARCH_CACHE_FILE = "search_cache.json"
st.set_page_config(page_title="Catálogo Master", page_icon="📚", layout="centered")

if 'translate_lock' not in st.session_state:
    st.session_state.translate_lock = threading.Lock()

st.markdown("""
    <style>
    .stMarkdown { line-height: 1.7 !important; }
    .stButton button { width: 100%; border-radius: 8px; transition: 0.3s; }
    .stButton button:hover { border-color: #ff4b4b; color: #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

# --- GERENCIAMENTO DE CACHE ---

def get_global_cache():
    if 'global_book_cache' not in st.session_state:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    st.session_state.global_book_cache = json.load(f)
            except:
                st.session_state.global_book_cache = {}
        else:
            st.session_state.global_book_cache = {}
    return st.session_state.global_book_cache

def update_global_cache(key, data):
    cache = get_global_cache()
    cache[key] = data
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)
    except:
        pass

def get_search_cache():
    if os.path.exists(SEARCH_CACHE_FILE):
        try:
            with open(SEARCH_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def update_search_cache(query, results):
    cache = get_search_cache()
    cache[query] = {
        "results": results,
        "timestamp": time.time()
    }
    try:
        with open(SEARCH_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)
    except:
        pass

# --- FUNÇÕES DE REDE ---

def fetch_books_smart(query_en):
    query_key = unidecode(query_en.lower().strip())
    search_cache = get_search_cache()
    
    if query_key in search_cache:
        return search_cache[query_key]["results"]
    
    url = "https://openlibrary.org/search.json"
    payload = {
        'q': query_en, 
        'fields': 'key,title,author_name,cover_i,first_publish_year,description,first_sentence', 
        'limit': 20
    }
    headers = {'User-Agent': 'Mozilla/5.0 (StreamlitApp; CatalogoMasterPro/12.0)'}
    
    try:
        response = requests.get(url, params=payload, timeout=12, headers=headers)
        if response.status_code == 200:
            docs = response.json().get("docs", [])
            if docs:
                update_search_cache(query_key, docs)
            return docs
        return []
    except:
        return []

def fetch_work_details_safe(work_key):
    url = f"https://openlibrary.org{work_key}.json"
    headers = {'User-Agent': 'Mozilla/5.0 (ProjectBookV12)'}
    for i in range(3):
        try:
            res = requests.get(url, timeout=8, headers=headers)
            if res.status_code == 200:
                return res.json()
            elif res.status_code == 429:
                time.sleep(3 + i)
            else:
                break
        except:
            time.sleep(1)
    return None

@st.cache_data(show_spinner=False, ttl=86400)
def safe_translate(text, src='en', dest='pt'):
    if not text or len(text) < 3: return text
    with st.session_state.translate_lock:
        try:
            time.sleep(0.4) 
            translator = GoogleTranslator(source=src, target=dest)
            translated = translator.translate(text[:3000])
            fixed = re.sub(r'([.])([A-Z])', r'\1 \2', translated)
            return fixed.replace(". ", ".\n\n")
        except Exception:
            return text

# --- COMPONENTE DE LIVRO ---

@st.fragment
def exibir_livro(doc, idx, search_suffix):
    work_key = doc.get("key")
    cache = get_global_cache()
    book_data = cache.get(work_key, {})
    
    title_orig = doc.get("title", "Sem título")
    title_display = book_data.get("title_pt", title_orig)
    
    st.subheader(title_display)
    authors = ", ".join(doc.get("author_name", ["Desconhecido"]))
    st.caption(f"✍️ {authors} | 📅 {doc.get('first_publish_year', 'N/A')}")
    
    col1, col2 = st.columns([1, 2.5])
    
    with col1:
        cover_id = doc.get("cover_i")
        # --- IMPLEMENTAÇÃO DO FILTRO DE CAPA ZERO ---
        # Verificamos se cover_id existe E se é diferente de 0 (ou maior que 0)
        if cover_id and int(cover_id) > 0:
            st.image(f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg", use_container_width=True)
        else:
            st.info("Sem Capa")
            
    with col2:
        sinopse_pt = book_data.get("sinopse_pt")
        if sinopse_pt:
            st.markdown(sinopse_pt)
        else:
            if st.button("📖 Carregar Sinopse", key=f"btn_{idx}_{search_suffix}"):
                with st.spinner("Traduzindo..."):
                    details = fetch_work_details_safe(work_key)
                    raw_desc = ""
                    if details and details.get("description"):
                        raw_desc = details.get("description")
                        if isinstance(raw_desc, dict): raw_desc = raw_desc.get("value")
                    else:
                        raw_desc = doc.get("description") or doc.get("first_sentence") or "Sinopse detalhada não encontrada."
                    
                    new_title = f"🇧🇷 {safe_translate(title_orig)}"
                    new_sinopse = safe_translate(raw_desc)
                    
                    update_global_cache(work_key, {"title_pt": new_title, "sinopse_pt": new_sinopse})
                    st.rerun()
    st.markdown("---")

# --- INTERFACE PRINCIPAL ---

st.title("📚 Catálogo de Livros (PT-BR)")

with st.form(key='search_form'):
    query_pt = st.text_input("O que você quer ler hoje?", placeholder="Ex: Machado de Assis...")
    submit_button = st.form_submit_button(label='🔍 Pesquisar')

if (submit_button or 'current_query' in st.session_state) and query_pt:
    
    if st.session_state.get('current_query') != query_pt:
        st.session_state.current_query = query_pt
        st.session_state.display_limit = 2 

    query_en = safe_translate(query_pt, src='pt', dest='en')
    
    status_placeholder = st.empty()
    
    with status_placeholder.status("Buscando no acervo...", expanded=False) as s:
        results = fetch_books_smart(query_en)
        s.update(label="Resultados prontos!", state="complete")
    
    status_placeholder.empty()
    
    if results:
        # --- IMPLEMENTAÇÃO DO FILTRO DE RESULTADOS VÁLIDOS ---
        # Filtra apenas quem tem cover_i e cujo valor é maior que 0
        valid_results = [d for d in results if d.get("cover_i") and int(d.get("cover_i")) > 0]
        
        suffix = unidecode(query_pt.lower()).replace(" ", "_")
        
        if valid_results:
            for i, doc in enumerate(valid_results[:st.session_state.display_limit]):
                exibir_livro(doc, i, suffix)
                
            if len(valid_results) > st.session_state.display_limit:
                if st.button("➕ Carregar mais 2 livros"):
                    st.session_state.display_limit += 2
                    st.rerun()
        else:
            st.warning("Livros encontrados, mas nenhum possui capa disponível.")
    else:
        st.error("Nenhum livro encontrado.")