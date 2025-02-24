from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import logging
import io
import os
import httpx
import asyncio
import tempfile
from contextlib import asynccontextmanager

from PDF.extract_pdf_opensource import PDFProcessor
from PDF.extract_pdf_enterprise import PDFEnterpriseProcessor
from Web.extract_web_opensource import WebProcessor
from Web.extract_web_enterprise import WebEnterpriseProcessor
from s3.s3 import StorageHandler

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize storage
try:
    storage = StorageHandler(
        bucket_name=os.getenv("AWS_BUCKET_NAME"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "us-east-1")
    )
except Exception as e:
    logger.warning(f"Failed to initialize S3 storage: {str(e)}")
    storage = None

# Initialize processors
pdf_processor_os = PDFProcessor(storage_client=storage)
pdf_processor_enterprise = PDFEnterpriseProcessor(storage_client=storage)
web_processor_os = WebProcessor()
web_processor_enterprise = WebEnterpriseProcessor(storage_client=storage)

# Pydantic models
class WebsiteRequest(BaseModel):
    url: HttpUrl

class ProcessingResponse(BaseModel):
    status: str
    message: str
    document_id: str
    timestamp: str
    content: Dict[str, Any]
    metadata: Dict[str, Any]

class URLInput(BaseModel):
    url: str

# Initialize FastAPI app
app = FastAPI(
    title="Document Processing API",
    description="API for processing documents",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create routers
os_router = APIRouter(prefix="/api/v1/opensource")
enterprise_router = APIRouter(prefix="/api/v1/enterprise")

# Create a main app variable for uvicorn
main = app

async def process_pdf(file: UploadFile) -> Dict[str, Any]:
    try:
        # Increase timeout and add retry logic
        timeout = httpx.Timeout(30.0, connect=60.0)
        max_retries = 3
        retry_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                # Read file content
                content = await file.read()
                
                # Configure your PDF processing service URL
                pdf_service_url = "your_pdf_processing_endpoint"
                
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        pdf_service_url,
                        files={"file": (file.filename, content, file.content_type)},
                        timeout=timeout
                    )
                    
                    if response.status_code == 200:
                        return response.json()
                    else:
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"PDF processing service returned error: {response.text}"
                        )
                        
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
                if attempt == max_retries - 1:  # Last attempt
                    raise HTTPException(
                        status_code=500,
                        detail=f"PDF processing service timeout after {max_retries} attempts: {str(e)}"
                    )
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )
    finally:
        await file.close()

# Opensource PDF endpoint
@os_router.post("/process-pdf", response_model=ProcessingResponse)
async def process_pdf_opensource(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Process PDF using opensource service (PyMuPDF)"""
    if not file.content_type == "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted"
        )

    try:
        # Create a temporary file to store the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            # Read the file in chunks to handle large files
            chunk_size = 1024 * 1024  # 1MB chunks
            while chunk := await file.read(chunk_size):
                temp_file.write(chunk)
            temp_file_path = temp_file.name

        try:
            # Initialize the PDF processor
            processor = PDFProcessor(storage_client=storage)

            # Process the PDF file
            result = await processor.process_pdf(temp_file_path)

            return {
                "status": "success",
                "message": "PDF processed successfully",
                "document_id": result.get("document_id", ""),
                "timestamp": result.get("timestamp", ""),
                "content": result.get("content", {}),
                "metadata": result.get("metadata", {})
            }

        finally:
            # Clean up the temporary file
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Error removing temporary file: {str(e)}")

    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )
    finally:
        await file.close()

# Enterprise PDF endpoint
@enterprise_router.post("/process-pdf")
async def process_pdf_enterprise(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Process PDF using enterprise service"""
    if not file.content_type == "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted"
        )

    try:
        # Create a temporary file to store the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            # Read the file in chunks to handle large files
            chunk_size = 1024 * 1024  # 1MB chunks
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Process the PDF file
            processor = PDFEnterpriseProcessor(storage_client=storage)
            result = await processor.process_pdf(temp_file_path)

            if not result:
                raise HTTPException(
                    status_code=500,
                    detail="PDF processing failed to return results"
                )

            return {
                "status": "success",
                "message": "PDF processed successfully",
                "document_id": result["document_id"],
                "timestamp": result["timestamp"],
                "content": result["content"],
                "metadata": result["metadata"]
            }

        finally:
            # Clean up the temporary file
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Error removing temporary file: {str(e)}")

    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )

# Opensource webpage endpoint
@os_router.post("/process-webpage", response_model=ProcessingResponse)
async def process_webpage_opensource(url_input: URLInput) -> Dict[str, Any]:
    """Process webpage using opensource service"""
    try:
        processor = WebProcessor()
        result = await processor.process_webpage(url_input.url)
        
        return {
            "status": result["status"],
            "message": result["message"],
            "document_id": result["document_id"],
            "timestamp": result["timestamp"],
            "content": result["content"],
            "metadata": result["metadata"]
        }
    except Exception as e:
        logger.error(f"Error processing webpage: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing webpage: {str(e)}"
        )

# Enterprise webpage endpoint
@enterprise_router.post("/process-webpage", response_model=ProcessingResponse)
async def process_webpage_enterprise(request: WebsiteRequest):
    try:
        result = await web_processor_enterprise.process_webpage(str(request.url))
        
        if not result:
            raise HTTPException(
                status_code=500,
                detail="Webpage processing failed to return results"
            )
            
        return {
            "status": "success",
            "message": "Webpage processed successfully using Enterprise service",
            "document_id": result["document_id"],
            "timestamp": result["timestamp"],
            "content": result["content"],
            "metadata": result["metadata"]
        }
    except Exception as e:
        logger.error(f"Error processing webpage: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing webpage: {str(e)}"
        )

# Health check endpoint
@os_router.get("/health")
@enterprise_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "opensource": {
                "pdf_processor": "available",
                "web_processor": "available"
            },
            "enterprise": {
                "azure_di": "available" if pdf_processor_enterprise.document_analysis_client else "unavailable",
                "diffbot": "available" if web_processor_enterprise.diffbot_token else "unavailable"
            }
        }
    }

# Include both routers
app.include_router(os_router)
app.include_router(enterprise_router)

@app.get("/")
async def root():
    return {"message": "Document Processing API is running"}

# This is important for Uvicorn to find the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fast_api:main", host="127.0.0.1", port=8000, reload=True)
