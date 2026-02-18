import os
import fitz
import base64
# import time
import boto3
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from common.secrets import load_config

# --- CONFIGURATION ---
try:
    CONFIG = load_config()
    GOOGLE_API_KEY = CONFIG["GOOGLE_API_KEY"]
except Exception:
    # print(f"Config Error in Ingest: {e}")
    GOOGLE_API_KEY = None

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash", 
    google_api_key=GOOGLE_API_KEY,
    temperature=0
)

USE_S3 = os.getenv("UPLOAD_TO_S3", "false").lower() == "true"
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
if USE_S3:
    s3_client = boto3.client('s3')

def generate_doc_metadata(text):
    """
    Asks Gemini for a summary and a list of 'Information Needs' for inference.
    """
    prompt = f"""
    Analyze the following document text.
    1. Provide a 2-sentence summary of what this document is about.
    2. Identify specific outside topics or documents this text infers a need for to be fully understood.
    3. List any explicit filenames mentioned.

    Text: {text[:4000]}...

    Format your response exactly as:
    SUMMARY: <summary>
    NEEDS: <comma_separated_needs>
    EXPLICIT: <comma_separated_filenames_or_NONE>
    """
    try:
        response = llm.invoke(prompt)
        content = response.content
        
        # Simple parsing
        summary = content.split("SUMMARY:")[1].split("NEEDS:")[0].strip()
        needs = [n.strip() for n in content.split("NEEDS:")[1].split("EXPLICIT:")[0].split(",")]
        explicit = [e.strip() for e in content.split("EXPLICIT:")[1].split(",")]
        
        return summary, needs, [] if "NONE" in explicit else explicit
    except Exception:
        return "Summary unavailable", [], []

def save_image(image_bytes, filename_base, page_num, img_index, image_ext):
    filename = f"{filename_base}_p{page_num}_img{img_index}.{image_ext}"
    if USE_S3:
        s3_key = f"assets/{filename_base}/{filename}"
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=image_bytes, ContentType=f"image/{image_ext}")
        return f"s3://{S3_BUCKET_NAME}/{s3_key}"
    return f"local_assets/{filename}"

def analyze_image(image_bytes):
    img_base64 = base64.b64encode(image_bytes).decode("utf-8")
    message = HumanMessage(content=[
        {"type": "text", "text": "Describe this image in detail for a technical RAG system."},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
    ])
    try:
        return llm.invoke([message]).content
    except Exception:
        return "Image analysis failed."

def process_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    content_blocks = []
    full_text = ""
    filename_base = os.path.basename(pdf_path).replace(".pdf", "")

    for page_num, page in enumerate(doc):
        text = page.get_text()
        full_text += text
        if text.strip():
            content_blocks.append({"type": "text", "content": text, "page": page_num + 1, "source": pdf_path})
        
        for img_index, img in enumerate(page.get_images(full=True)):
            image_bytes = doc.extract_image(img[0])["image"]
            image_path = save_image(image_bytes, filename_base, page_num + 1, img_index + 1, "png")
            description = analyze_image(image_bytes)
            content_blocks.append({"type": "image_description", "content": f"[IMAGE]: {description}", "image_path": image_path, "page": page_num + 1, "source": pdf_path})
            
    # Generate Semantic Metadata
    summary, needs, explicit = generate_doc_metadata(full_text)
    return content_blocks, summary, needs, explicit

def chunk_content(content_blocks):
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    final_chunks = []
    for block in content_blocks:
        chunks = splitter.split_text(block["content"])
        for c in chunks:
            final_chunks.append({"text": c, "metadata": {"source": block["source"], "page": block["page"]}})
    return final_chunks