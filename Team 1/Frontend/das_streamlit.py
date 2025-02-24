import streamlit as st
import requests
from datetime import datetime
import base64
import io
import markdown
from PIL import Image

# FastAPI backend URL
API_URL = "http://localhost:8000/api/v1"  # Replace with your deployed FastAPI URL if hosted remotely

def create_markdown_download(content: list, filename: str = "extracted_text.md") -> str:
    """Create a markdown file for download"""
    markdown_content = "\n\n".join(content)
    b64 = base64.b64encode(markdown_content.encode()).decode()
    return f'<a href="data:file/markdown;base64,{b64}" download="{filename}">Download Markdown</a>'

def display_image_from_bytes(image_bytes, caption=""):
    """Display image from bytes data"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        st.image(image, caption=caption, use_column_width=True)
    except Exception as e:
        st.error(f"Error displaying image: {str(e)}")

# Streamlit app title
st.set_page_config(page_title="Document Processing App", layout="wide")
st.title("📄 Document Processing App")

# Add this at the top of your Streamlit app
st.markdown("""
    <style>
    .button {
        display: inline-block;
        padding: 0.5em 1em;
        background-color: #4CAF50;
        color: white;
        text-decoration: none;
        border-radius: 4px;
        margin: 10px 0;
    }
    .button:hover {
        background-color: #45a049;
    }
    </style>
    """, unsafe_allow_html=True)

# Tabs for different functionalities
tab1, tab2, tab3 = st.tabs(["📤 Process PDF", "🌐 Process Webpage", "⚙️ Health Check"])

# Tab 1: Process PDF
with tab1:
    st.header("Upload and Process a PDF File")
    
    # Select processor type
    processor_type = st.radio(
        "Select Processor",
        ["Opensource (PyMuPDF)", "Enterprise (Azure Document Intelligence)"],
        horizontal=True
    )
    
    uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

    if uploaded_file is not None:
        # Display file details
        st.write("### File Details")
        st.write(f"**Filename:** {uploaded_file.name}")
        st.write(f"**File Size:** {uploaded_file.size / 1024:.2f} KB")

        # Process button
        if st.button("🚀 Process PDF"):
            with st.spinner("Processing your PDF..."):
                try:
                    # Determine endpoint based on processor type
                    endpoint = "opensource" if "Opensource" in processor_type else "enterprise"
                    
                    # Send file to FastAPI endpoint
                    files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
                    response = requests.post(f"{API_URL}/{endpoint}/process-pdf", files=files)

                    if response.status_code == 200:
                        result = response.json()

                        # Display success message and results
                        st.success("PDF processed successfully!")
                        
                        # Create columns for layout
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            # Display extracted content
                            st.write("### Extracted Content")
                            
                            # Display text content
                            if "text" in result["content"]:
                                st.write("#### Text Content")
                                
                                # Create markdown download button
                                st.markdown(
                                    create_markdown_download(result["content"]["text"], 
                                    f"{uploaded_file.name}_extracted.md"),
                                    unsafe_allow_html=True
                                )
                                
                                for page_num, text in enumerate(result["content"]["text"], 1):
                                    with st.expander(f"Page {page_num}"):
                                        st.markdown(text)

                            # Display tables
                            if "tables" in result["content"] and result["content"]["tables"]:
                                st.write("#### Tables")
                                for table_num, table in enumerate(result["content"]["tables"], 1):
                                    with st.expander(f"Table {table_num}"):
                                        st.table(table)
                                        
                                        # Add CSV download button for each table
                                        csv = '\n'.join([','.join(map(str, row)) for row in table])
                                        b64 = base64.b64encode(csv.encode()).decode()
                                        href = f'<a href="data:file/csv;base64,{b64}" download="table_{table_num}.csv">Download CSV</a>'
                                        st.markdown(href, unsafe_allow_html=True)

                            # Display key-value pairs (for enterprise)
                            if "key_value_pairs" in result["content"]:
                                st.write("#### Key-Value Pairs")
                                for key, value in result["content"]["key_value_pairs"].items():
                                    st.write(f"**{key}:** {value}")
                        
                        with col2:
                            # Display metadata
                            st.write("### Metadata")
                            st.json(result["metadata"])

                            # Display storage paths
                            if "storage_paths" in result["metadata"]:
                                st.write("#### Storage Paths")
                                for key, path in result["metadata"]["storage_paths"].items():
                                    st.write(f"**{key}:** `{path}`")

                            # Display images if available
                            if "images" in result["content"]:
                                st.write("#### Images")
                                for img_num, img in enumerate(result["content"]["images"], 1):
                                    with st.expander(f"Image {img_num}"):
                                        if "data" in img:
                                            display_image_from_bytes(
                                                img["data"],
                                                f"Page {img['page']}, Index {img['index']}"
                                            )
                                            
                                            # Add image download button
                                            b64 = base64.b64encode(img["data"]).decode()
                                            href = f'<a href="data:image/{img["ext"]};base64,{b64}" download="image_{img_num}.{img["ext"]}">Download Image</a>'
                                            st.markdown(href, unsafe_allow_html=True)

                    else:
                        # Handle errors from the API
                        error_message = response.json().get("detail", "Unknown error occurred.")
                        st.error(f"Failed to process PDF: {error_message}")

                except Exception as e:
                    # Handle client-side errors
                    st.error(f"An error occurred while processing the PDF: {str(e)}")

# Tab 2: Process Webpage
with tab2:
    st.header("Process a Webpage")
    
    # Select processor type
    processor_type = st.radio(
        "Select Processor",
        ["Opensource (BeautifulSoup)", "Enterprise (Diffbot)"],
        horizontal=True,
        key="webpage_processor"
    )
    
    # URL input
    url = st.text_input("Enter webpage URL", "https://")
    
    # Process button
    if st.button("🚀 Process Webpage"):
        if url and url != "https://":
            with st.spinner("Processing webpage..."):
                try:
                    # Determine endpoint based on processor type
                    endpoint = "opensource" if "Opensource" in processor_type else "enterprise"
                    
                    # Send request to FastAPI endpoint
                    response = requests.post(
                        f"{API_URL}/{endpoint}/process-webpage",
                        json={"url": url}
                    )

                    if response.status_code == 200:
                        result = response.json()

                        # Display success message and results
                        st.success("Webpage processed successfully!")
                        
                        # Create columns for layout
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            # Generate and display markdown content
                            st.write("### Extracted Content")
                            
                            # Create markdown content
                            markdown_lines = []
                            
                            # Add title if available
                            if "title" in result["metadata"]:
                                markdown_lines.append(f"# {result['metadata']['title']}\n")
                            
                            # Add metadata section
                            markdown_lines.append("## Metadata\n")
                            for key, value in result["metadata"].items():
                                if key != "storage_paths":
                                    markdown_lines.append(f"- **{key}**: {value}")
                            markdown_lines.append("\n")
                            
                            # Add main content
                            markdown_lines.append("## Content\n")
                            if "text" in result["content"]:
                                markdown_lines.extend(result["content"]["text"])
                            
                            # Add images section
                            if "images" in result["content"] and result["content"]["images"]:
                                markdown_lines.append("\n## Images\n")
                                for img in result["content"]["images"]:
                                    alt_text = img.get('alt', '') or img.get('title', 'Image')
                                    markdown_lines.append(f"![{alt_text}]({img['url']})\n")
                            
                            # Add tables section
                            if "tables" in result["content"] and result["content"]["tables"]:
                                markdown_lines.append("\n## Tables\n")
                                for table in result["content"]["tables"]:
                                    if table:
                                        # Display table in markdown format
                                        st.write("#### Table")
                                        st.table(table)
                            
                            # Add links section
                            if "links" in result["content"] and result["content"]["links"]:
                                markdown_lines.append("\n## Links\n")
                                for link in result["content"]["links"]:
                                    markdown_lines.append(f"- [{link['text']}]({link['url']})")
                            
                            # Join all markdown content
                            markdown_content = "\n".join(markdown_lines)
                            
                            # Display markdown content
                            st.markdown(markdown_content)
                            
                            # Create download button for markdown
                            b64 = base64.b64encode(markdown_content.encode()).decode()
                            filename = "extracted_webpage.md"
                            st.markdown(
                                f'<a href="data:file/markdown;base64,{b64}" download="{filename}" '
                                'class="button">📥 Download Markdown</a>',
                                unsafe_allow_html=True
                            )
                            
                        with col2:
                            # Display metadata and storage paths
                            st.write("### Metadata")
                            st.json(result["metadata"])

                            # Display storage paths
                            if "storage_paths" in result["metadata"]:
                                st.write("#### Storage Paths")
                                for key, path in result["metadata"]["storage_paths"].items():
                                    st.write(f"**{key}:** `{path}`")

                            # Display images in sidebar
                            if "images" in result["content"] and result["content"]["images"]:
                                st.write("### Images")
                                for img_num, img in enumerate(result["content"]["images"], 1):
                                    with st.expander(f"Image {img_num}"):
                                        if "url" in img:
                                            st.image(img["url"], 
                                                    caption=img.get("title", "") or img.get("alt", ""),
                                                    use_column_width=True)

                    else:
                        # Handle errors from the API
                        error_message = response.json().get("detail", "Unknown error occurred.")
                        st.error(f"Failed to process webpage: {error_message}")

                except Exception as e:
                    # Handle client-side errors
                    st.error(f"An error occurred while processing the webpage: {str(e)}")
                    st.error(f"Details: {str(e)}")
        else:
            st.warning("Please enter a valid URL")

# Tab 3: Health Check
with tab3:
    st.header("Health Check")
    if st.button("🔍 Check API Health"):
        with st.spinner("Checking API health..."):
            try:
                # Check both opensource and enterprise health
                os_response = requests.get(f"{API_URL}/opensource/health")
                ent_response = requests.get(f"{API_URL}/enterprise/health")
                
                if os_response.status_code == 200 and ent_response.status_code == 200:
                    os_status = os_response.json()
                    ent_status = ent_response.json()
                    
                    st.success("API is healthy!")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("#### Opensource Services")
                        st.json(os_status)
                    with col2:
                        st.write("#### Enterprise Services")
                        st.json(ent_status)
                else:
                    st.error("Health check failed")
                    if os_response.status_code != 200:
                        st.error(f"Opensource API: {os_response.status_code}")
                    if ent_response.status_code != 200:
                        st.error(f"Enterprise API: {ent_response.status_code}")
            except Exception as e:
                st.error(f"An error occurred while checking API health: {str(e)}")
