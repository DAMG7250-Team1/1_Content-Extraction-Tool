# pdf_processor.py
import logging
import io
import os
import fitz  # PyMuPDF
from typing import Dict, Any, BinaryIO
from datetime import datetime
import pandas as pd
import tabula  # for table extraction
import hashlib
import json

logger = logging.getLogger(__name__)

class PDFProcessor:
    def __init__(self, storage_client=None):
        """Initialize PDFProcessor"""
        self.storage_client = storage_client
        self.base_path = "PDF/Opensource/"

    def _generate_document_id(self, file_path: str) -> str:
        """Generate a unique document ID based on file content and timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(file_path)
        return f"pdf_os_{filename}_{timestamp}"

    async def _extract_content(self, file_path: str) -> Dict[str, Any]:
        """Extract content from PDF using PyMuPDF"""
        try:
            doc = fitz.open(file_path)
            
            text_content = []
            images = []
            tables = []  # PyMuPDF doesn't extract tables directly
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text
                text = page.get_text()
                if text.strip():
                    text_content.append(text)
                
                # Extract images
                image_list = page.get_images(full=True)
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        if base_image:
                            image_data = {
                                'data': base_image["image"],
                                'ext': base_image["ext"],
                                'page': page_num + 1,
                                'index': img_index
                            }
                            images.append(image_data)
                    except Exception as img_error:
                        logger.warning(f"Error extracting image {img_index} from page {page_num}: {str(img_error)}")
                        continue
            
            # Get document metadata
            metadata = {
                'title': doc.metadata.get('title', ''),
                'author': doc.metadata.get('author', ''),
                'subject': doc.metadata.get('subject', ''),
                'keywords': doc.metadata.get('keywords', ''),
                'page_count': len(doc),
                'file_size': os.path.getsize(file_path),
                'creation_date': doc.metadata.get('creationDate', ''),
                'modification_date': doc.metadata.get('modDate', '')
            }
            
            doc.close()
            
            return {
                'text_content': text_content,
                'images': images,
                'tables': tables,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Error extracting content from PDF: {str(e)}")
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

                # Store images
                if content['images']:
                    images_folder = f"{base_folder}/images"
                    for idx, img in enumerate(content['images']):
                        img_key = f"{images_folder}/image_{idx}.{img['ext']}"
                        self.storage_client.upload(
                            img['data'],
                            img_key
                        )
                        storage_paths[f'image_{idx}'] = img_key

            return storage_paths

        except Exception as e:
            logger.error(f"Error storing content: {str(e)}")
            return {}  # Return empty dict if storage fails

    async def process_pdf(self, file_path: str) -> Dict[str, Any]:
        """Process PDF file"""
        try:
            # Generate document ID
            doc_id = self._generate_document_id(file_path)
            
            # Extract content
            content = await self._extract_content(file_path)
            
            # Store content if storage client is available
            storage_paths = {}
            if self.storage_client:
                try:
                    storage_paths = await self._store_content(content, doc_id)
                except Exception as storage_error:
                    logger.error(f"Error storing content: {str(storage_error)}")
                    # Continue processing even if storage fails
            
            # Prepare result
            result = {
                "document_id": doc_id,
                "content": {
                    "text": content["text_content"],
                    "tables": content["tables"]
                },
                "metadata": {
                    **content["metadata"],
                    "storage_paths": storage_paths,
                    "processor": "PyMuPDF",
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # Add images data if available
            if content["images"]:
                result["content"]["images"] = [
                    {
                        'page': img['page'],
                        'index': img['index'],
                        'ext': img['ext']
                    } for img in content["images"]
                ]
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            raise

    