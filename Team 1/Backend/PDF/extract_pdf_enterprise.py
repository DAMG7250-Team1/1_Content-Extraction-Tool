from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from datetime import datetime
from typing import Dict, Any, BinaryIO
import logging
import json
import io
import os
import pandas as pd
from pathlib import Path
import fitz  # PyMuPDF for image extraction
import asyncio
from functools import wraps
from fastapi import HTTPException
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@asynccontextmanager
async def async_timeout(timeout: float):
    try:
        async with asyncio.timeout(timeout):
            yield
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=500,
            detail=f"Operation timed out after {timeout} seconds"
        )

class PDFEnterpriseProcessor:
    def __init__(self, storage_client=None, timeout: int = 300, max_retries: int = 3, retry_delay: int = 5):
        """Initialize PDFEnterpriseProcessor with Azure Document Intelligence client"""
        self.storage_client = storage_client
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.base_path = "PDF/Enterprise/"
        
        # Initialize Azure credentials
        self.endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        self.key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        
        if not self.endpoint or not self.key:
            logger.warning("Azure Document Intelligence credentials not found. Using PyMuPDF as fallback.")
            self.document_analysis_client = None
            self.use_fallback = True
        else:
            try:
                self.document_analysis_client = DocumentAnalysisClient(
                    endpoint=self.endpoint,
                    credential=AzureKeyCredential(self.key)
                )
                self.use_fallback = False
                logger.info("Azure Document Intelligence client initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing Azure Document Intelligence client: {str(e)}")
                self.document_analysis_client = None
                self.use_fallback = True

    def _extract_images_from_pdf(self, pdf_file: BinaryIO) -> list:
        """Extract images from PDF using PyMuPDF"""
        images = []
        try:
            # Create a temporary copy of the PDF file
            temp_pdf = io.BytesIO(pdf_file.read())
            pdf_file.seek(0)  # Reset file pointer for later use
            
            # Open PDF with PyMuPDF
            doc = fitz.open(stream=temp_pdf, filetype="pdf")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()
                
                for img_idx, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_data = {
                            'data': base_image["image"],
                            'ext': base_image["ext"],
                            'page': page_num + 1,
                            'index': img_idx + 1
                        }
                        images.append(image_data)
                    except Exception as e:
                        logger.warning(f"Failed to extract image {img_idx} from page {page_num + 1}: {str(e)}")
            
            doc.close()
            return images
            
        except Exception as e:
            logger.error(f"Error extracting images from PDF: {str(e)}")
            return []

    def _extract_content(self, pdf_file: BinaryIO) -> Dict:
        """Extract content using Azure Document Intelligence"""
        if not self.document_analysis_client:
            raise ValueError("Azure Document Intelligence client not initialized")

        try:
            # Extract images first using PyMuPDF
            images = self._extract_images_from_pdf(pdf_file)
            
            # Process with Azure Document Intelligence
            poller = self.document_analysis_client.begin_analyze_document(
                "prebuilt-document", document=pdf_file
            )
            result = poller.result()

            # Extract text content page by page
            text_content = []
            for page in result.pages:
                page_text = ""
                for line in page.lines:
                    page_text += line.content + "\n"
                text_content.append(page_text)

            # Extract tables with proper structure
            tables = []
            for table in result.tables:
                table_data = []
                rows = max(cell.row_index for cell in table.cells) + 1
                cols = max(cell.column_index for cell in table.cells) + 1
                
                # Initialize empty table
                for _ in range(rows):
                    table_data.append([''] * cols)
                
                # Fill in the data
                for cell in table.cells:
                    table_data[cell.row_index][cell.column_index] = cell.content
                
                tables.append(table_data)

            # Extract key-value pairs
            key_value_pairs = {}
            for kv_pair in result.key_value_pairs:
                if kv_pair.key and kv_pair.value:
                    key_value_pairs[kv_pair.key.content] = kv_pair.value.content

            return {
                "text_content": text_content,
                "tables": tables,
                "images": images,
                "key_value_pairs": key_value_pairs,
                "pages": len(result.pages)
            }

        except Exception as e:
            logger.error(f"Error in content extraction: {str(e)}")
            raise

    async def _store_content(self, content: Dict, doc_id: str) -> Dict[str, str]:
        """Store extracted content in different formats"""
        try:
            storage_paths = {}
            base_folder = f"{self.base_path}{doc_id}"

            if self.storage_client:
                # Run storage operations in thread pool
                loop = asyncio.get_event_loop()
                
                # Store text content
                text_content = "\n\n".join(content["text_content"])
                text_key = f"{base_folder}/text_content.txt"
                await loop.run_in_executor(
                    None,
                    lambda: self.storage_client.upload(
                        io.BytesIO(text_content.encode('utf-8')),
                        text_key,
                        'text/plain'
                    )
                )
                storage_paths['text'] = text_key

                # Store tables as CSV files
                for idx, table in enumerate(content["tables"]):
                    df = pd.DataFrame(table)
                    csv_buffer = io.StringIO()
                    df.to_csv(csv_buffer, index=False)
                    table_key = f"{base_folder}/table_{idx+1}.csv"
                    await loop.run_in_executor(
                        None,
                        lambda: self.storage_client.upload(
                            io.BytesIO(csv_buffer.getvalue().encode('utf-8')),
                            table_key,
                            'text/csv'
                        )
                    )
                    storage_paths[f'table_{idx+1}'] = table_key

                # Store metadata
                metadata_key = f"{base_folder}/metadata.json"
                metadata_json = json.dumps(content["metadata"])
                await loop.run_in_executor(
                    None,
                    lambda: self.storage_client.upload(
                        io.BytesIO(metadata_json.encode('utf-8')),
                        metadata_key,
                        'application/json'
                    )
                )
                storage_paths['metadata'] = metadata_key

            return storage_paths

        except Exception as e:
            logger.error(f"Error storing content: {str(e)}")
            raise

    async def process_pdf(self, file_path: str) -> Dict[str, Any]:
        """Process PDF file with retry mechanism"""
        try:
            # Generate document ID first
            doc_id = self._generate_document_id(file_path)
            timestamp = datetime.now().isoformat()

            if self.use_fallback:
                result = await self._extract_content_fallback(file_path)
            else:
                result = await self._extract_content_azure(file_path)
            
            # Store content if storage client is available
            storage_paths = {}
            if self.storage_client:
                storage_paths = await self._store_content(result, doc_id)
            
            return {
                "status": "success",
                "message": "PDF processed successfully",
                "document_id": doc_id,
                "timestamp": timestamp,
                "content": {
                    "text": result.get("text_content", []),
                    "tables": result.get("tables", []),
                    "images": result.get("images", []),
                    "key_value_pairs": result.get("key_value_pairs", {})
                },
                "metadata": {
                    "filename": os.path.basename(file_path),
                    "timestamp": timestamp,
                    "processor": "PyMuPDF (fallback)" if self.use_fallback else "Azure Document Intelligence",
                    "page_count": result.get("metadata", {}).get("page_count", 0),
                    "storage_paths": storage_paths
                }
            }

        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error processing PDF: {str(e)}"
            )

    async def _extract_content_azure(self, file_path: str) -> Dict[str, Any]:
        """Extract content using Azure Document Intelligence"""
        try:
            # Run the Azure processing in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            async with async_timeout(self.timeout):
                result = await loop.run_in_executor(None, self._process_with_azure, file_path)
            
            return result
            
        except asyncio.TimeoutError:
            logger.error("Azure processing timed out")
            raise HTTPException(
                status_code=500,
                detail="Azure processing timed out"
            )
        except Exception as e:
            logger.error(f"Error in Azure PDF processing: {str(e)}")
            raise

    def _process_with_azure(self, file_path: str) -> Dict[str, Any]:
        """Synchronous Azure processing"""
        with open(file_path, "rb") as f:
            poller = self.document_analysis_client.begin_analyze_document(
                "prebuilt-document", document=f
            )
            result = poller.result()

        text_content = []
        tables = []
        key_value_pairs = {}
        
        for page in result.pages:
            page_text = []
            for line in page.lines:
                page_text.append(line.content)
            text_content.append('\n'.join(page_text))

        for table in result.tables:
            table_data = []
            for row_idx in range(table.row_count):
                row_data = []
                for col_idx in range(table.column_count):
                    cell = next((cell for cell in table.cells 
                               if cell.row_index == row_idx 
                               and cell.column_index == col_idx), None)
                    row_data.append(cell.content if cell else '')
                table_data.append(row_data)
            if table_data:
                tables.append(table_data)

        for kv in result.key_value_pairs:
            if kv.key and kv.value:
                key_value_pairs[kv.key.content] = kv.value.content

        return {
            'text_content': text_content,
            'tables': tables,
            'key_value_pairs': key_value_pairs,
            'metadata': {
                'page_count': len(result.pages),
                'processor': 'Azure Document Intelligence',
                'timestamp': datetime.now().isoformat()
            }
        }

    async def _extract_content_fallback(self, file_path: str) -> Dict[str, Any]:
        """Extract content using PyMuPDF as fallback"""
        try:
            # Run PyMuPDF in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            async with async_timeout(self.timeout):
                result = await loop.run_in_executor(None, self._process_with_pymupdf, file_path)
            
            return result
            
        except asyncio.TimeoutError:
            logger.error("PyMuPDF processing timed out")
            raise HTTPException(
                status_code=500,
                detail="PDF processing timed out"
            )
        except Exception as e:
            logger.error(f"Error in fallback PDF processing: {str(e)}")
            raise

    def _process_with_pymupdf(self, file_path: str) -> Dict[str, Any]:
        """Synchronous PyMuPDF processing"""
        doc = None
        try:
            doc = fitz.open(file_path)
            text_content = []
            images = []
            tables = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_content.append(text)
                
                # Extract images
                for img_index, img in enumerate(page.get_images(full=True)):
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
                        logger.warning(f"Error extracting image {img_index} from page {page_num + 1}: {str(img_error)}")
            
            return {
                'text_content': text_content,
                'images': images,
                'tables': tables,
                'metadata': {
                    'page_count': len(doc),
                    'processor': 'PyMuPDF (fallback)',
                    'timestamp': datetime.now().isoformat()
                }
            }
            
        finally:
            if doc:
                doc.close()

    def _generate_document_id(self, file_path: str) -> str:
        """Generate a unique document ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(file_path)
        return f"pdf_{'fallback' if self.use_fallback else 'azure'}_{filename}_{timestamp}"

    def get_supported_languages(self) -> list:
        """Return list of supported languages"""
        return [
            "en", "es", "de", "fr", "it", "pt", "nl", 
            "ja", "ko", "zh-Hans", "zh-Hant", "ar"
        ]
