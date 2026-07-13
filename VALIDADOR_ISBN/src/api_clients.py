import aiohttp
import asyncio
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import re

import warnings
try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

class MetadataFetcher:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._headers = {
            "User-Agent": "AutomatizacionISBN/2.0 (mailto:tu-correo@ejemplo.com)"
        }

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=self._headers)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1.5, min=2, max=20)
    )
    async def fetch_isbn_metadata(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Consulta asíncrona para obtener metadata de un libro a través del ISBN.
        Utiliza OpenLibrary como primario y Google Books como secundario.
        """
        session = await self.get_session()
        
        # 1. Intentar con OpenLibrary (Muy robusto, sin rate limits estrictos)
        openlibrary_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        
        async with session.get(openlibrary_url) as response:
            if response.status == 200:
                data = await response.json()
                key = f"ISBN:{isbn}"
                if key in data:
                    book_data = data[key]
                    title = book_data.get("title", "")
                    
                    authors_list = book_data.get("authors", [])
                    authors_str_list = [a.get("name", "") for a in authors_list[:15]]
                    authors = ", ".join(authors_str_list)
                    if len(authors_list) > 15:
                        authors += " [y otros...]"
                        
                    publishers_list = book_data.get("publishers", [])
                    publishers = ", ".join([p.get("name", "") for p in publishers_list])
                    
                    publish_date = book_data.get("publish_date", "")
                    
                    return {
                        "titulo": title,
                        "autores": authors,
                        "editorial": publishers,
                        "anio_publicacion": publish_date,
                        "fuente": "OpenLibrary"
                    }
            elif response.status == 429 or response.status >= 500:
                response.raise_for_status()

        # 2. Fallback: Intentar con Google Books API
        google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
        
        try:
            async with session.get(google_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if "items" in data and len(data["items"]) > 0:
                        vol_info = data["items"][0].get("volumeInfo", {})
                        
                        title = vol_info.get("title", "")
                        
                        authors_list = vol_info.get("authors", [])
                        authors = ", ".join(authors_list[:15])
                        if len(authors_list) > 15:
                            authors += " [y otros...]"
                            
                        publisher = vol_info.get("publisher", "")
                        published_date = vol_info.get("publishedDate", "")
                        if published_date and len(published_date) >= 4:
                            published_date = published_date[:4]
                            
                        return {
                            "titulo": title,
                            "autores": authors,
                            "editorial": publisher,
                            "anio_publicacion": published_date,
                            "fuente": "Google Books"
                        }
                elif response.status >= 500:
                    response.raise_for_status()
                # Si es 429 en Google, lo dejamos pasar para intentar UDLA
        except Exception:
            pass

        # 3. Fallback: Intentar con UDLA Publicaciones (Para libros de Ecuador/UDLA)
        udla_url = f"https://udlapublicaciones.com/buscar?q={isbn}"
        try:
            async with session.get(udla_url) as response:
                if response.status == 200:
                    html = await response.text()
                    if "No hay resultados" not in html:
                        # Extraer todos los h3
                        h3_matches = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.IGNORECASE)
                        for title in h3_matches:
                            title_clean = title.strip()
                            if title_clean.lower() not in ["filtrar por", "filtrar"]:
                                return {
                                    "titulo": title_clean,
                                    "autores": "Autor UDLA",
                                    "editorial": "UDLA Ediciones",
                                    "anio_publicacion": "Desconocido",
                                    "fuente": "UDLA Publicaciones"
                                }
        except Exception:
            pass # Si falla UDLA (timeout o caída), simplemente pasa a retornar None
                
        # 4. Fallback: Intentar con Búsqueda Universal en DuckDuckGo
        if DDGS is not None:
            try:
                def _search_ddg():
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", category=RuntimeWarning)
                        with DDGS() as ddgs:
                            # Buscamos literalmente "ISBN XXXXXXXXXXXXX"
                            return list(ddgs.text(f'"ISBN {isbn}"', max_results=3))
                        
                # Ejecutar búsqueda en un hilo separado para no bloquear el loop asíncrono
                results = await asyncio.to_thread(_search_ddg)
                
                if results:
                    # Consolidar los resultados encontrados en un bloque de texto
                    text_snippets = []
                    for idx, r in enumerate(results):
                        title = r.get('title', '')
                        body = r.get('body', '')
                        text_snippets.append(f"Resultado {idx+1}:\nTítulo: {title}\nFragmento: {body}\n")
                    
                    consolidated_text = "\n".join(text_snippets)
                    
                    return {
                        # Pasamos el texto crudo en el campo título para que la IA decida
                        "titulo": f"[TEXTO EXTRAÍDO DE INTERNET]\n{consolidated_text}",
                        "autores": "Extraer del texto",
                        "editorial": "Extraer del texto",
                        "anio_publicacion": "Extraer del texto",
                        "fuente": "Búsqueda Web (DuckDuckGo)"
                    }
            except Exception:
                pass # Si DDGS falla o nos bloquea, simplemente continuamos

        # Si todas fallan o no hay datos, devolvemos None
        return None
