import aiohttp
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import Optional, Dict, Any

class MetadataFetcher:
    """
    Async Client for fetching metadata from public APIs (Crossref/OpenAlex) 
    with Exponential Backoff retries.
    """

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def fetch_doi_metadata(doi: str) -> Optional[Dict[str, Any]]:
        """
        Fetches metadata for a given DOI asynchronusly.
        """
        url = f"https://api.crossref.org/works/{doi}"
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    message = data.get("message", {})
                    
                    title = message.get("title", [""])[0] if message.get("title") else ""
                    authors_list = message.get("author", [])
                    authors = ", ".join([f"{a.get('given', '')} {a.get('family', '')}".strip() for a in authors_list])
                    
                    issued = message.get("issued", {}).get("date-parts", [[None]])[0][0]
                    year = str(issued) if issued else ""
                    
                    container_title = message.get("container-title", [""])[0] if message.get("container-title") else ""
                    publisher = message.get("publisher", "")
                    journal_or_publisher = container_title if container_title else publisher
                    
                    pub_type = message.get("type", "")
                    
                    return {
                        "titulo": title,
                        "autores": authors,
                        "anio_publicacion": year,
                        "revista_editorial": journal_or_publisher,
                        "tipo_publicacion": pub_type
                    }
                else:
                    return None

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def fetch_issn_metadata(issn: str) -> Optional[Dict[str, Any]]:
        """
        Fetches metadata for a given ISSN asynchronously.
        """
        url = f"https://api.crossref.org/journals/{issn}"
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
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
                else:
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
                        return None
