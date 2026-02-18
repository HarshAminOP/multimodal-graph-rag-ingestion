
from neo4j import GraphDatabase
from common.secrets import load_config
import logging

try:
    CONFIG = load_config()
    URI = CONFIG["NEO4J_URI"]
    AUTH = (CONFIG["NEO4J_USERNAME"], CONFIG["NEO4J_PASSWORD"])
except Exception:
    URI, AUTH = None, None

logger = logging.getLogger(__name__)

class GraphManager:
    def __init__(self):
        if not URI: 
            raise ValueError("DB Config Missing")
        self.driver = GraphDatabase.driver(URI, auth=AUTH)

    def close(self):
        self.driver.close()

    def delete_document_data(self, filename):
        query = "MATCH (d:Document {id: $filename}) OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk) DETACH DELETE d, c"
        with self.driver.session() as session:
            session.run(query, filename=filename)

    def create_document_node(self, filename, summary, needs, explicit):
        query = """
        MERGE (d:Document {id: $filename})
        SET d.filename = $filename, d.summary = $summary, 
            d.semantic_needs = $needs, d.explicit_refs = $explicit,
            d.updated_at = datetime()
        """
        with self.driver.session() as session:
            session.run(query, filename=filename, summary=summary, needs=needs, explicit=explicit)

    def run_targeted_linker(self, filename):
        """
        Surgical Linking: Matches current file's 'needs' against others' 'summaries'.
        """
        logger.info(f"🔗 Semantic Linking for: {filename}")
        query = """
        MATCH (this:Document {id: $filename})
        MATCH (target:Document) WHERE target.id <> this.id
        
        // Match if any of our needs appear in their summary OR explicit name match
        WITH this, target
        WHERE any(need IN this.semantic_needs WHERE toLower(target.summary) CONTAINS toLower(need))
           OR any(ref IN this.explicit_refs WHERE toLower(target.id) CONTAINS toLower(ref))
        
        MERGE (this)-[r:REFERENCES]->(target)
        SET r.type = 'inferred', r.updated_at = datetime()
        RETURN count(r) as links
        """
        with self.driver.session() as session:
            result = session.run(query, filename=filename)
            logger.info(f"Links established: {result.single()['links']}")