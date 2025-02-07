import logging
from functools import wraps

from neo4j import GraphDatabase

from .config import config

neo4j_log = logging.getLogger("neo4j")
neo4j_log.setLevel(logging.CRITICAL)

MG_HOST = config.mg_host
MG_PORT = config.mg_port
MG_USER = config.mg_user
MG_PASS = config.mg_pass


def connect_to_db(f):
    @wraps(f)
    def with_connection_(*args, **kwargs):

        try:
            URI = f"bolt://{MG_HOST}:{MG_PORT}"
            AUTH = (MG_USER, MG_PASS)
            with GraphDatabase.driver(URI, auth=AUTH) as db:
                db.verify_connectivity()
                return f(*args, db, **kwargs)
        except Exception as e:
            raise ValueError(e)
        finally:
            db.close()

    return with_connection_
