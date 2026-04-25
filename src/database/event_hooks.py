from sqlalchemy import event
from database.mysql_connection import write_engine, read_engine
from common.const.settings import settings

if settings.ENV == "development":
    pass
