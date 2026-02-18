import json
from common.graph_manager import GraphManager
import logging

logger = logging.getLogger(__name__)

def handler(event, context):
    """
    STEP 2: TARGETED LINKING WORKER
    Triggered by Step Function after IngestWorker (or Choice state).
    Input: { "filename": "example.pdf", "status": "ingested", ... }
    """
    logger.info(f"🔗 Linker Worker Received: {json.dumps(event)}")
    
    # The filename comes from the output of the previous 'IngestDocument' task
    filename = event.get("filename")
    
    if not filename:
        logger.error("Error: No filename found in event payload.")
        return {"status": "error", "message": "Missing filename"}

    try:
        gm = GraphManager()
        
        # Perform the surgical update
        gm.run_targeted_linker(filename)
        
        gm.close()
        
        return {
            "status": "linking_complete",
            "filename": filename,
            "processed_at": "datetime_placeholder" # You can add real timestamp if needed
        }

    except Exception as e:
        logger.error(f"Linking Worker Critical Failure: {str(e)}")
        # Raise exception to trigger Step Function Retry/Fail logic
        raise e