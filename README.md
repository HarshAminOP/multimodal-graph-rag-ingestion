# 📜 Multimodal Semantic Graph RAG Pipeline

**Production-Grade Serverless Ingestion Engine**

A serverless, event-driven architecture that transforms unstructured PDFs into a **Semantic Knowledge Graph**. Built with **Python 3.13**, **AWS Step Functions**, and **Neo4j**, it utilizes **Google Gemini 1.5 Flash** for multimodal analysis (text + vision) and "semantic inference" linking.


---
## 🛠️ Setup & Deployment

### 1. Prerequisites
* **AWS CLI** & **AWS CDK** installed.
* **Docker Desktop** running (for building Lambda images).
* **Neo4j Database** (AuraDB or Self-Hosted).
* **Google Gemini API Key**.

### 2. AWS Secrets Configuration
Create a secret in **AWS Secrets Manager** named `GraphRAG/Production/Secrets` with this JSON structure:

```json
{
  "NEO4J_URI": "neo4j+s://your-db-url",
  "NEO4J_USERNAME": "neo4j",
  "NEO4J_PASSWORD": "your-password",
  "GOOGLE_API_KEY": "your-gemini-key"
}
```

### 3. Deployment

``` bash
# 1. Install Dependencies
pip install -r requirements.txt

# 2. Bootstrap CDK (One-time setup per region)
cdk bootstrap

# 3. Deploy Stack
cdk deploy
```
---
## 🏗️ System Architecture

**The Two-Stage Pipeline:**

1.  **IngestWorker (Docker/Lambda):**
    * Triggered by S3 `ObjectCreated`.
    * Downloads PDF → Extracts Text/Images → Generates Metadata.
    * Stores Vectors in Neo4j (Search).
    * Stores Graph Nodes (Structure).
2.  **LinkWorker (Docker/Lambda):**
    * Triggered after Ingest success.
    * Runs **Targeted Linker Query**.
    * **Outbound:** Links the new file to existing files it needs.
    * **Inbound:** Links existing files to the new file (repairing "orphaned" references).

---
## 🚀 Key Features

### 1. 🧠 Multimodal Ingestion
* **Text & Tables:** Extracts high-fidelity text using `PyMuPDF`.
* **Vision AI:** Automatically extracts images from PDFs and uses **Gemini 1.5 Flash** to generate technical descriptions for diagrams, charts, and photos.
* **Smart Chunking:** Splits content into semantic chunks while preserving metadata (page number, source file).

### 2. 🔗 Semantic "Inference" Linking
* **Beyond Keywords:** Documents are linked by *intent*, not just filenames.
* **The Logic:**
    * **Identity:** Gemini generates a 2-sentence summary of every document.
    * **Wishlist:** Gemini identifies "Semantic Needs" (e.g., "This document needs the Q3 Audit Report").
    * **The Stitch:** A surgical Cypher query links Doc A to Doc B if Doc B's summary satisfies Doc A's needs.

### 3. ♻️ Lifecycle Awareness (Sync with S3)
* **Kill & Fill:** Updates are idempotent. Re-uploading a file wipes the old nodes/vectors before adding new ones.
* **Auto-Prune:** Deleting a file from S3 triggers a cleanup event that removes the `Document` node, `Chunk` nodes, and all relationships from Neo4j.

### 4. 🛡️ Enterprise Security
* **Zero-Trust:** No API keys in environment variables.
* **Secrets Manager:** All credentials (Neo4j, Google, etc.) are fetched at runtime from AWS Secrets Manager using a secure, region-agnostic loader.
* **Least Privilege:** IAM roles are scoped strictly to required resources (S3 buckets, Secrets).

### 5. ⚡ Decoupled Orchestration
* **Step Functions:** Uses a visual workflow to manage retries and error handling.
* **Worker Pattern:** Separates "Ingestion" (Heavy Compute/AI) from "Linking" (Graph Operations), allowing independent scaling and failure recovery.

---

## 📂 Repository Structure

```text
.
├── common/
│   ├── secrets.py          # Secure Config Loader (AWS Secrets Manager + Local .env)
│   ├── graph_manager.py    # Neo4j Controller (Cypher queries for Linking & CRUD)
│   ├── ingest.py           # AI Engine (Gemini Parsing, Summarization, Vision)
│   ├── loader.py           # LangChain Vector Store Integration
│   ├── ingest_worker.py    # Lambda Handler: Stage 1 (Ingestion)
│   └── link_worker.py      # Lambda Handler: Stage 2 (Linking)
├── infra_stack.py          # AWS CDK Infrastructure Definition (Python)
├── statemachine.asl.json   # Step Functions Workflow Definition (ASL)
├── Dockerfile              # Python 3.13 Production Image
├── requirements.txt        # Pinned Dependencies
└── README.md               # Documentation
```
