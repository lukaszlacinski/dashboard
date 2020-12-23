from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session


DBSession = scoped_session(sessionmaker())
Base = declarative_base()


class TransferModel(Base):
    __tablename__ = "transfer"

    id = Column(Integer, primary_key=True)
    uuid = Column(String)
    tstamp = Column(DateTime, default=datetime.utcnow)
    set = Column(String)
    source = Column(String)
    destination = Column(String)
    dataset = Column(String)
    status = Column(Integer)
    rate = Column(BigInteger)
    message = Column(String)
    faults = Column(Integer)

    def __repr__(self):
        return "Transfer(id={}, uuid={}, tstamp={}, source={}, destination={}, dataset={}, status={}, rate={}, faults={})".format(
            self.id, self.uuid, self.tstamp, self.source, self.destination, self.dataset, self.status, self.rate, self.faults)
