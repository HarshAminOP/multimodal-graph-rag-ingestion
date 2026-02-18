from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_neo4j import Neo4jVector
from langchain_core.documents import Document as LangChainDocument
from neo4j import GraphDatabase
from common.secrets import load_config
import logging

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
try:
    CONFIG = load_config()
    GOOGLE_API_KEY = CONFIG["GOOGLE_API_KEY"]
    URI = CONFIG["NEO4J_URI"]
    AUTH = (CONFIG["NEO4J_USERNAME"], CONFIG["NEO4J_PASSWORD"])
except Exception as e:
    logger.warning(f"Config Error in Loader: {e}")
    GOOGLE_API_KEY, URI, AUTH = None, None, None

# Using 3.13 compatible model
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004",
    google_api_key=GOOGLE_API_KEY
)

def store_in_graph(chunks, filename):
    """
    1. Embeds text chunks.
    2. Stores them as Vector nodes.
    3. Connects Chunks to the Parent Document node.
    """
    logger.info(f"Vectorizing {len(chunks)} chunks for '{filename}'...")

    if not URI or not AUTH:
        raise ValueError("Cannot store vectors: Missing Database Credentials")

    # 1. Convert dictionary chunks to LangChain Documents
    langchain_docs = []
    for i, chunk_data in enumerate(chunks):
        metadata = chunk_data["metadata"]
        metadata["chunk_index"] = i
        metadata["parent_doc"] = filename
        
        langchain_docs.append(
            LangChainDocument(
                page_content=chunk_data["text"],
                metadata=metadata
            )
        )

    # 2. Batch Insert Vectors (Modern LangChain-Neo4j Integration)
    try:
        Neo4jVector.from_documents(
            langchain_docs,
            embeddings,
            url=URI,
            username=AUTH[0],
            password=AUTH[1],
            index_name="vector_index",
            node_label="Chunk",
            text_node_property="text",
            embedding_node_property="embedding"
        )
        
        # 3. Link Parent Document -> Child Chunks
        with GraphDatabase.driver(URI, auth=AUTH) as driver:
            with driver.session() as session:
                session.run(
                    """
                    MATCH (d:Document {id: $filename})
                    MATCH (c:Chunk)
                    WHERE c.parent_doc = $filename
                    MERGE (d)-[:HAS_CHUNK]->(c)
                    """,
                    filename=filename
                )
        logger.info("Vector Storage and Parent-Child Linking Complete.")

    except Exception as e:
        logger.error(f"Error during vector storage: {e}")
        raise e