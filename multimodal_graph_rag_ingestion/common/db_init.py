import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load environment variables
load_dotenv()

URI = os.getenv("NEO4J_URI")
AUTH = (os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))

def init_graph_schema():
    """
    Initializes the Graph DB schema:
    1. Verify connection
    2. Create unique constraints for Documents and Chunks
    """
    print(f"🔌 Connecting to Neo4j at {URI}...")
    
    try:
        with GraphDatabase.driver(URI, auth=AUTH) as driver:
            driver.verify_connectivity()
            print("✅ Connection Successful!")

            # Create Constraints (Ensures we don't duplicate documents)
            queries = [
                # Ensure every Document has a unique ID
                "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
                # Ensure every Chunk has a unique ID
                "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
                # Create a Vector Index (Required for similarity search)
                # Note: We configure 768 dimensions (standard for Google embedding models)
                """
                CREATE VECTOR INDEX vector_index IF NOT EXISTS
                FOR (c:Chunk) ON (c.embedding)
                OPTIONS {indexConfig: {
                 `vector.dimensions`: 768,
                 `vector.similarity_function`: 'cosine'
                }}
                """
            ]

            with driver.session() as session:
                for q in queries:
                    session.run(q)
                    print(f"   Executed constraint: {q.split('FOR')[0].strip()}...")
            
            print("🏗️ Schema and Vector Index configured successfully.")
            
    except Exception as e:
        print(f"❌ Error connecting to Neo4j: {e}")

if __name__ == "__main__":
    init_graph_schema()