Assignment 1

Web Scraping & Data Processing for AI Application

The project provides a centralized viewpoint on different tools ranging from Open source to enterprise solutions which would be utilized to scrape data for extractions from different PDF documents and websites.The project helps: Examine different approaches for the same requirement of data extraction, Understand the Pros and Cons of the tools used from a centralized application point of view Access the extracted results in a configured storage of S3 buckets Users can observe the data extraction results and capabilities of different tools to make an informed decision on which tool to use based on personalized use case requirements.

Team

1.Husain

2.Sahil Kasliwal

3.Dhrumil Patel

Application-Streamlit : https://content-extraction-tool-hh9cxuyufdcnur47bpteae.streamlit.app/

Backend API-Google Cloud: https://content-extraction-api-607698884796.us-central1.run.app/docs

Google Codelab: https://codelabs-preview.appspot.com/?file_id=1bhb4Ao13vP9LmXGrna4FjiTFQRoALbYzsEr-Q4W_1Wg#0


Technologies Used

Streamlit : Frontend Framework

FastAPI : Backend API Framework

Google Cloud : API Deployment

AWS S3 : Cloud Storage of extracted images ,texts and tables and generated markdown file

BeautifulSoup : Website Data Extraction Open Source Tool

PyMuPDF : PDF Data Extraction Open Source Tool

Diffbot : Website Data Extraction Enterprise Tool

Microsoft Document Intelligence : PDF Data Extraction Enterprise Tool

Docling : Conversion Tool for markdown file

Architecture Diagram

![image (2)](https://github.com/user-attachments/assets/7bcb41de-426a-4733-ab34-0ea3f72e01df)

Workflow for PDF/Web Extraction and Processing

1. User Interaction via Streamlit
   
The user accesses the Streamlit interface.
They select whether they want to extract content from:
PDF
Webpage

Based on their selection, they proceed to choose the extraction tool:
Open Source (e.g., PyMuPDF for PDFs; BeautifulSoup for Web)
Enterprise Service (e.g., Microsoft Document Intelligence for PDF ; Diffbot for enterprise)

2. API Triggering in Backend (FastAPI)
Upon selection, the corresponding API is triggered in FastAPI.

If PDF is selected:
The PDF file is uploaded.
The API processes the PDF using the chosen tool.

If Webpage is selected:
The user enters the webpage URL.
The API fetches and processes the content using the chosen tool.

3. Data Extraction and Processing
The selected tool extracts content, including text, images, tables, and charts.
Extracted data is converted into Markdown format using:
Docling


4. Storage in AWS S3
Extracted content (Markdown files and associated images) is uploaded to an S3 bucket.
Metadata tagging is applied for organization and retrieval.

5. Rendering in Streamlit
The generated Markdown content is retrieved and rendered on the Streamlit frontend for user preview.
The user can download the Markdown file from the interface.

6. Summary and Logging
Process logs, tool performance metrics, and extraction success/failure details are stored.
A structured report summarizing the comparison between open-source and enterprise tools is generated.

Contributions

Sahil Kasliwal - 50%
