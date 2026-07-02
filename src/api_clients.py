import aiohttp
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import Optional, Dict, Any

class MetadataFetcher:
    """
    Async Client for fetching metadata from public APIs (Crossref/OpenAlex) 
    with Exponential Backoff retries, persistent sessions and Polite Pool access.
    """
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            headers = {
                "User-Agent": "PublicationValidatorBot/1.0 (mailto:soporte@tudominio.com)"
            }
            timeout = aiohttp.ClientTimeout(total=15)
            self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def fetch_doi_metadata(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetches metadata for a given DOI asynchronusly.
        """
        url = f"https://api.crossref.org/works/{doi}"
        session = await self.get_session()
        
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                message = data.get("message", {})
                
                title = message.get("title", [""])[0] if message.get("title") else ""
                authors_list = message.get("author", [])
                
                # Para evitar exceder el límite de tokens de Groq (6000 TPM) con papers que tienen
                # miles de autores (ej. papers de física), extraemos máximo los primeros 20 autores
                # y truncamos la cadena final a 800 caracteres.
                authors_str_list = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors_list[:30]]
                authors = ", ".join(authors_str_list)
                if len(authors_list) > 30:
                    authors += " [y otros...]"
                    
                # Truncar título también por seguridad
                if len(title) > 800:
                    title = title[:800] + "..."
                
                issued = message.get("issued", {}).get("date-parts", [[None]])[0][0]
                year = str(issued) if issued else ""
                
                container_title = message.get("container-title", [""])[0] if message.get("container-title") else ""
                publisher = message.get("publisher", "")
                journal_or_publisher = container_title if container_title else publisher
                if len(journal_or_publisher) > 500:
                    journal_or_publisher = journal_or_publisher[:500] + "..."
                
                pub_type = message.get("type", "")
                
                return {
                    "titulo": title,
                    "autores": authors,
                    "anio_publicacion": year,
                    "revista_editorial": journal_or_publisher,
                    "tipo_publicacion": pub_type
                }
            elif response.status == 404:
                return None
            else:
                response.raise_for_status()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def fetch_issn_metadata(self, issn: str) -> Optional[Dict[str, Any]]:
        """
        Fetches metadata for a given ISSN asynchronously.
        """
        url = f"https://api.crossref.org/journals/{issn}"
        session = await self.get_session()
        
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                message = data.get("message", {})
                
                title = message.get("title", "")
                publisher = message.get("publisher", "")
                
                return {
                    "titulo": title,
                    "editorial": publisher,
                    "tipo_publicacion": "journal"
                }
            elif response.status == 404:
                # Fallback to OpenAlex
                openalex_url = f"https://api.openalex.org/sources/issn:{issn}"
                async with session.get(openalex_url) as oa_response:
                    if oa_response.status == 200:
                        data = await oa_response.json()
                        title = data.get("display_name", "")
                        publisher = data.get("host_organization_name", "")
                        country = data.get("country_code", "")
                        return {
                            "titulo": title,
                            "editorial": publisher,
                            "pais": country,
                            "tipo_publicacion": data.get("type", "")
                        }
                    elif oa_response.status == 404:
                        return None
                    else:
                        oa_response.raise_for_status()
            else:
                response.raise_for_status()
