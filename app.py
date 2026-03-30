import requests
import streamlit as st
from deep_translator import GoogleTranslator
from unidecode import unidecode

st.title("Catálogo de Livros - Open Library (PT-BR)")
query_pt = st.text_input("Digite o título ou autor do livro:", "")

def translate_query(query: str) -> str:
    """
    Traduz a query para inglês antes de interagir com a API
    """
    return GoogleTranslator(source="pt", target="en").translate(query)


if query_pt:
    # Traduz a query para inglês antes de enviar
    query_en = translate_query(query_pt)

    url = f"https://openlibrary.org/search.json?q={query_en}"
    response = requests.get(url)
    data = response.json()

    if data["docs"]:
        # pega os 10 primeiros resultados

        for doc in data["docs"][:10]:
            cover_id = doc.get("cover_i")
            found = False

            # só continua se tiver capa válida
            if isinstance(cover_id, int) and cover_id > 0:
                cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                title = doc.get("title", "Sem título")
                translated_title = GoogleTranslator(source="auto", target="pt").translate(title)
                author = ", ".join(doc.get("author_name", []))

                query_norm = unidecode(query_pt.lower())
                title_norm = unidecode(translated_title.lower())
                author_norm = unidecode(author.lower())

                query_words = query_norm.split()

                title_match = all(word in title_norm for word in query_words)
                author_match = all(word in author_norm for word in query_words)

                if title_match or author_match:
                    found = True
                    year = doc.get("first_publish_year", "Ano desconhecido")

                    st.subheader(f"**Título:** {translated_title}")
                    st.write(f"**Autor(es):** {author}")
                    st.write(f"**Ano de publicação:** {year}")
                    st.image(cover_url, caption=title)

                    olid = doc.get("key")
                    if olid:
                        work_url = f"https://openlibrary.org{olid}.json"
                        work_resp = requests.get(work_url).json()
                        description = work_resp.get("description")
                        if isinstance(description, dict):
                            description = description.get("value")

                        if description:
                            traducao = GoogleTranslator(source="auto", target="pt").translate(description)
                            st.write(traducao)
                        else:
                            st.write("Sinopse não disponível.")
        if not found:
            st.write("Nenhum livro encontrado com esse critério.")
    else:
        st.write("Nenhum livro encontrado.")