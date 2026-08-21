import logging
import json
from datetime import datetime,UTC


class JSONFormatter(logging.Formatter):
    def format(self,record):
        log_record={
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName
        }
        


        # Include any extra kwargs passed to the logger
        if hasattr(record, 'extra_data'):
            log_record.update(record.extra_data)
        return json.dumps(log_record)

def get_logger(name):
    logger=logging.getLogger(name)
    if not logger.handlers:
        handler=logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
            
    return logger