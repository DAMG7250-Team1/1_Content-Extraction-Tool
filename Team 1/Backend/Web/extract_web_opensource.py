import aiohttp
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, Any
import logging
import hashlib
import ssl
import certifi
import re
from urllib.parse import urlparse
import io
import json
from urllib.parse import urljoin
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebProcessor:
    def __init__(self, storage_client=None):
        """Initialize WebProcessor"""
        self.storage_client = storage_client
        self.base_path = "Web/Opensource/"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Create SSL context
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    async def process_webpage(self, url: str) -> Dict[str, Any]:
        """Process webpage using BeautifulSoup"""
        try:
            # Generate document ID
            doc_id = self._generate_document_id(url)
            timestamp = datetime.now().isoformat()
            
            # Extract content
            content = await self._extract_content(url)
            
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
                    "text": content["text_content"],
                    "tables": content["tables"],
                    "images": content["images"],
                    "links": content["links"]
                },
                "metadata": {
                    "url": url,
                    "title": content["metadata"].get("title", ""),
                    "description": content["metadata"].get("description", ""),
                    "keywords": content["metadata"].get("keywords", ""),
                    "storage_paths": storage_paths,
                    "processor": "BeautifulSoup",
                    "timestamp": timestamp
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing webpage: {str(e)}", exc_info=True)
            raise

    def _generate_document_id(self, url: str) -> str:
        """Generate a unique document ID based on URL and timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"web_os_{url_hash}_{timestamp}"

    async def _extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content using BeautifulSoup"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        timeout = aiohttp.ClientTimeout(total=30)
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        try:
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP Error {response.status}: {response.reason}")
                    html = await response.text()

                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract text content
                text_content = []
                for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    text = p.get_text().strip()
                    if text:
                        text_content.append(text)
                
                # Extract tables
                tables = []
                for table in soup.find_all('table'):
                    table_data = []
                    for row in table.find_all('tr'):
                        row_data = [cell.get_text().strip() for cell in row.find_all(['td', 'th'])]
                        if row_data:
                            table_data.append(row_data)
                    if table_data:
                        tables.append(table_data)
                
                # Extract images
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
                
                # Extract links
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
                
                # Extract metadata
                metadata = {
                    'title': soup.title.string if soup.title else '',
                    'url': url,
                    'description': soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else '',
                    'keywords': soup.find('meta', {'name': 'keywords'})['content'] if soup.find('meta', {'name': 'keywords'}) else ''
                }
                
                return {
                    'text_content': text_content,
                    'tables': tables,
                    'images': images,
                    'links': links,
                    'metadata': metadata
                }
                
        except Exception as e:
            logger.error(f"Error extracting content from webpage: {str(e)}", exc_info=True)
            raise

    async def _store_content(self, content: Dict, doc_id: str) -> Dict[str, str]:
        """Store extracted content"""
        try:
            storage_paths = {}
            base_folder = f"{self.base_path}{doc_id}"

            if self.storage_client:
                # Store text content
                text_content = "\n\n".join(content['text_content'])
                text_key = f"{base_folder}/text_content.txt"
                self.storage_client.upload(
                    io.BytesIO(text_content.encode('utf-8')).read(),
                    text_key
                )
                storage_paths['text'] = text_key

                # Store metadata
                metadata_key = f"{base_folder}/metadata.json"
                metadata_json = json.dumps(content['metadata'])
                self.storage_client.upload(
                    io.BytesIO(metadata_json.encode('utf-8')).read(),
                    metadata_key
                )
                storage_paths['metadata'] = metadata_key

            return storage_paths

        except Exception as e:
            logger.error(f"Error storing content: {str(e)}")
            return {} 