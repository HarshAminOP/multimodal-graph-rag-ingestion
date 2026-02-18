import json
from common.graph_manager import GraphManager
import logging

logger = logging.getLogger(__name__)

def handler(event, context):
    """
    STEP 2: TARGETED LINKING WORKER
    Triggered by Step Function after IngestWorker (or Choice state).
    Input: { "filename": "example.pdf", "status": "ingested" }
    """
    logger.info(f"Linker Worker Received: {json.dumps(event)}")
    
    # Extract filename from the output of the IngestWorker
    filename = event.get("filename")
    status = event.get("status")
    
    # If the file was deleted, the Choice state should have skipped this,
    # but we add a safety check here just in case.
    if status == "deleted":
        logger.info(f"File {filename} was deleted. Skipping linking phase.")
        return {"status": "skipped", "filename": filename}
    
    if not filename:
        logger.error("Error: No filename found in event payload.")
        return {"status": "error", "message": "Missing filename"}

    try:
        # Initialize GraphManager (fetches credentials from Secrets Manager)
        gm = GraphManager()
        
        # Execute the surgical update:
        # 1. Links THIS file to others (Outbound)
        # 2. Links others to THIS file (Inbound/Repair)
        # 3. Uses both Explicit names and Semantic Summaries
        gm.run_targeted_linker(filename)
        
        gm.close()
        
        logger.info(f"Linking phase complete for {filename}")
        return {
            "status": "linking_complete",
            "filename": filename
        }

    except Exception as e:
        logger.error(f"Linking Worker Critical Failure: {str(e)}")
        # Raise exception to trigger Step Function Retry/Fail logic
        raise e