import ssl
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, Any
import logging
import hashlib
import json
import os
from urllib.parse import urljoin
import io
import certifi

logger = logging.getLogger(__name__)

class WebEnterpriseProcessor:
    def __init__(self, storage_client=None):
        """Initialize WebEnterpriseProcessor"""
        self.storage_client = storage_client
        self.base_path = "Web/Enterprise/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Initialize Diffbot token
        self.diffbot_token = os.getenv("DIFFBOT_TOKEN")
        self.diffbot_api_url = "https://api.diffbot.com/v3/article"

    async def process_webpage(self, url: str) -> Dict[str, Any]:
        """Process webpage using Diffbot or fallback to BeautifulSoup"""
        try:
            # Generate document ID
            doc_id = self._generate_document_id(url)
            timestamp = datetime.now().isoformat()

            if self.diffbot_token:
                content = await self._extract_content_diffbot(url)
            else:
                logger.warning("Diffbot token not found, falling back to BeautifulSoup")
                content = await self._extract_content_fallback(url)

            # Store content if storage client is available
            storage_paths = {}
            if self.storage_client:
                storage_paths = await self._store_content(content, doc_id)

            return {
                "status": "success",
                "message": "Webpage processed successfully",
                "document_id": doc_id,
                "timestamp": timestamp,
                "content": {
                    "text": content["text"],
                    "title": content["title"],
                    "images": content["images"],
                    "links": content["links"]
                },
                "metadata": {
                    "url": url,
                    "processor": "Diffbot" if self.diffbot_token else "BeautifulSoup (fallback)",
                    "timestamp": timestamp,
                    "storage_paths": storage_paths
                }
            }

        except Exception as e:
            logger.error(f"Error processing webpage: {str(e)}", exc_info=True)
            raise

    async def _extract_content_diffbot(self, url: str) -> Dict[str, Any]:
        """Extract content using Diffbot API"""
        # Create SSL context that verifies certificates
        ssl_context = ssl.create_default_context()
        
        # Create TCP connector with SSL context
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            try:
                params = {
                    'token': self.diffbot_token,
                    'url': url,
                    'discussion': 'false'
                }
                
                async with session.get(self.diffbot_api_url, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if 'objects' not in data or not data['objects']:
                        logger.warning("No content extracted by Diffbot, falling back to BeautifulSoup")
                        return await self._extract_content_fallback(url)
                        
                    article = data['objects'][0]
                    
                    return {
                        'text': article.get('text', ''),
                        'title': article.get('title', ''),
                        'images': article.get('images', []),
                        'links': article.get('links', []),
                        'html': article.get('html', ''),
                        'author': article.get('author', ''),
                        'date': article.get('date', ''),
                        'siteName': article.get('siteName', '')
                    }
                    
            except aiohttp.ClientError as e:
                logger.warning(f"Diffbot API error: {str(e)}, falling back to BeautifulSoup")
                return await self._extract_content_fallback(url)
            except Exception as e:
                logger.error(f"Error with Diffbot API: {str(e)}")
                raise

    async def _extract_content_fallback(self, url: str) -> Dict[str, Any]:
        """Fallback extraction using BeautifulSoup"""
        # Create SSL context that verifies certificates
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Create TCP connector with SSL context
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            try:
                async with session.get(url, headers=self.headers) as response:
                    response.raise_for_status()
                    html = await response.text()
                
                soup = BeautifulSoup(html, 'html.parser')
                
                text_content = []
                for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    text = p.get_text().strip()
                    if text:
                        text_content.append(text)

                images = []
                for img in soup.find_all('img'):
                    src = img.get('src')
                    if src:
                        if not src.startswith(('http://', 'https://')):
                            src = urljoin(url, src)
                        images.append({
                            'url': src,
                            'alt': img.get('alt', ''),
                            'title': img.get('title', '')
                        })

                links = []
                for link in soup.find_all('a'):
                    href = link.get('href')
                    if href:
                        if not href.startswith(('http://', 'https://')):
                            href = urljoin(url, href)
                        links.append({
                            'url': href,
                            'text': link.get_text().strip()
                        })

                return {
                    'text': '\n'.join(text_content),
                    'title': soup.title.string if soup.title else '',
                    'images': images,
                    'links': links,
                    'html': str(soup)
                }

            except Exception as e:
                logger.error(f"Error in fallback extraction: {str(e)}")
                raise

    async def _store_content(self, content: Dict, doc_id: str) -> Dict[str, str]:
        """Store extracted content"""
        try:
            storage_paths = {}
            base_folder = f"{self.base_path}{doc_id}"

            if self.storage_client:
                loop = asyncio.get_event_loop()

                # Store text content
                text_key = f"{base_folder}/content.txt"
                await loop.run_in_executor(
                    None,
                    lambda: self.storage_client.upload(
                        io.BytesIO(content['text'].encode('utf-8')),
                        text_key,
                        'text/plain'
                    )
                )
                storage_paths['text'] = text_key

                # Store HTML content
                html_key = f"{base_folder}/content.html"
                await loop.run_in_executor(
                    None,
                    lambda: self.storage_client.upload(
                        io.BytesIO(content['html'].encode('utf-8')),
                        html_key,
                        'text/html'
                    )
                )
                storage_paths['html'] = html_key

                # Store metadata
                metadata = {
                    'title': content['title'],
                    'image_count': len(content['images']),
                    'link_count': len(content['links'])
                }
                metadata_key = f"{base_folder}/metadata.json"
                await loop.run_in_executor(
                    None,
                    lambda: self.storage_client.upload(
                        io.BytesIO(json.dumps(metadata).encode('utf-8')),
                        metadata_key,
                        'application/json'
                    )
                )
                storage_paths['metadata'] = metadata_key

            return storage_paths

        except Exception as e:
            logger.error(f"Error storing content: {str(e)}")
            return {}

    def _generate_document_id(self, url: str) -> str:
        """Generate a unique document ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"web_enterprise_{url_hash}_{timestamp}"
