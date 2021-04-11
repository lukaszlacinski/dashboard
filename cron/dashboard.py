from threading import Lock
import logging
import argparse
import os
import json
from time import sleep
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor as Executor
from globus_sdk import TransferClient, TransferData
from fair_research_login.client import NativeClient
from sqlalchemy import create_engine
from models import DBSession, Base, TransferModel
import local_settings as settings

"""
local_settings.py module includes credentials to the database and Globus.
It has the following format:

database = {
    "url": "postgresql://<username>:<password>@localhost:5432/<database>"
}

globus = {
    "client_id": <client_id>,
    "redirect_uri": "https://auth.globus.org/v2/web/auth-code",
    "scopes": "openid urn:globus:auth:scope:transfer.api.globus.org:all"
}
"""


logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "WARNING"),
    format="%(asctime)s:%(name)s:%(levelname)s:%(message)s",
    filename=os.environ.get("LOGFILE", "log/globus-dashboard.log")
)
logger = logging.getLogger(__name__)


SUCCEEDED = 0
DEADLINE = -1
PAUSED = -2
FAILED = -3
EXCEPTION = -4


class Globus:
    transfer_client = None
    def __init__(self):
        # initialize a transfer_client if it has not been done already
        if Globus.transfer_client == None:
            native_client = NativeClient(
                client_id=settings.globus.get("client_id"),
                app_name="Globus Endpoint Performance Dashboard",
                default_scopes=settings.globus.get("scopes")
            )
            native_client.login(no_local_server=True, refresh_tokens=True)
            transfer_authorizer = native_client.get_authorizers().get("transfer.api.globus.org")
            Globus.transfer_client = TransferClient(transfer_authorizer)


class Endpoint(Globus):
    def __init__(self, data):
        super().__init__()
        for key in data:
            setattr(self, key, data.get(key))
        r = Globus.transfer_client.endpoint_autoactivate(self.uuid)
        if r["code"] == "AutoActivationFailed":
            logger.error("Endpoint autoactivation failed for endpoint {}: {}".format(self.uuid, r["message"]))
        self.lock = Lock()

    def available(self):
        return not self.lock.locked()

    def acquire(self):
        self.lock.acquire()

    def release(self):
        self.lock.release()

    def __str__(self):
        return self.name


class GlobusTransfer(Globus):
    # default deadline for all transfers: 3600 seconds
    deadline = 3600
    transfers2do = 0
    lock = Lock()

    @staticmethod
    def convert_bps(bps):
        suffix = "B/s"
        if bps > 1000:
            bps = bps / 1000
            suffix = "kB/s"
            if bps > 1000:
                bps = bps / 1000
                suffix = "MB/s"
            if bps > 1000:
                bps = bps / 1000
                suffix = "GB/s"
        if bps >= 10:
            return "{} {}".format(int(round(bps)), suffix)
        return "{} {}".format(round(bps,1), suffix)

    def __init__(self, set, source_endpoint, destination_endpoint, dataset):
        super().__init__()
        self.set = set
        self.source = source_endpoint
        self.destination = destination_endpoint
        self.dataset = dataset
        self.done = False
        GlobusTransfer.transfers2do += 1

    def __str__(self):
        return f"{self.source} -> {self.destination}: {self.dataset}"

    def acquire(self):
        """
        Check if the source or destination endpoint are not being used by
        another active transfer. If both source and destination endpoints locks
        are not locked, lock them for this transfer.
        """
        with GlobusTransfer.lock:
            if self.source.available() and self.destination.available():
                self.source.acquire()
                if self.source != self.destination:
                    self.destination.acquire()
                return True
        return False

    def release(self):
        self.source.release()
        if self.source != self.destination:
            self.destination.release()

    def get_error_events(self, tc, task_id):
        events = tc.task_event_list(task_id, num_results=5, filter="is_error:1")
        message = ""
        try:
            event = next(events)
            message = "{}".format(event.get("details"))
        except StopIteration:
            return message
        while True:
            try:
                event = next(events)
                message += "\n---------------------------------\n{}".format(event.get("details"))
            except StopIteration:
                return message

    def run(self):
        logger.info(f"{self} - started")
        source = self.source
        destination = self.destination
        src_path = os.path.join(source.src_path, self.dataset)
        dst_path = destination.dst_path
        tc = GlobusTransfer.transfer_client
        td = TransferData(tc, source.uuid, destination.uuid)
        td.add_item(src_path, dst_path, recursive=True)

        try:
            task = tc.submit_transfer(td)
            request_time = datetime.utcnow()
            task_id = task.get("task_id")
            """
            A Globus transfer job (task) can be in one of the three states:
            ACTIVE, SUCCEEDED, FAILED. The script every 60 seconds polls a
            status of the transfer job (task) from the Globus Transfer service,
            with 60 second timeout limit. If the task is ACTIVE after time runs
            out 'task_wait' returns False, and True otherwise.
            """
            while not tc.task_wait(task_id, 60, 60):
                if datetime.utcnow() - request_time >= timedelta(seconds=GlobusTransfer.deadline):
                    break
                task = tc.get_task(task_id)
                if task.get("is_paused"):
                    break
            """
            The Globus transfer job (task) has been finished (SUCCEEDED or FAILED),
            or is still active (ACTIVE). Check if the transfer SUCCEEDED or FAILED.
            """
            task = tc.get_task(task_id)
            if task["status"] == "SUCCEEDED":
                bps = task.get("effective_bytes_per_second")
                rate = GlobusTransfer.convert_bps(bps)
                logger.info(f"Globus transfer {task_id}, from {source.uuid}{src_path} to {destination.uuid}{dst_path} succeeded")
                logger.info("{} - files transferred: {}, bytes transferred: {}, effective transfer rate: {}, faults: {}".format(self, task.get("files_transferred"), task.get("bytes_transferred"), rate, task.get("faults")))
                faults = task.get("faults")
                message = None
                if faults > 0:
                    message = self.get_error_events(tc, task_id)
                t = TransferModel(uuid=task_id, set=self.set, source=source.name, destination=destination.name, dataset=self.dataset, status=SUCCEEDED, rate=bps, message=message, faults=faults)
            elif task.get("status") == "ACTIVE":
                if task.get("is_paused"):
                    pause_info = tc.task_pause_info(task_id)
                    paused_rules = pause_info.get("pause_rules")
                    reason = paused_rules[0].get("message")
                    message = f"The task was paused. Reason: {reason}"
                    status = PAUSED
                    logger.info("{} - {}".format(self, message))
                else:
                    message = f"The task reached a {GlobusTransfer.deadline} second deadline\n"
                    events = tc.task_event_list(task_id, num_results=5, filter="is_error:1")
                    message += self.get_error_events(tc, task_id)
                    status = DEADLINE
                    logger.warning("{} - faults: {}, error: {}".format(self, task.get("faults"), message))
                tc.cancel_task(task_id)
                t = TransferModel(uuid=task_id, set=self.set, source=source.name, destination=destination.name, dataset=self.dataset, status=status, message=message, faults=task.get("faults"))
            else:
                t = TransferModel(uuid=task_id, set=self.set, source=source.name, destination=destination.name, dataset=self.dataset, status=FAILED)
        except Exception as e:
            logger.error(f"{self} - exception: {e}")
            t = TransferModel(set=self.set, source=source.name, destination=destination.name, dataset=self.dataset, status=EXCEPTION, message=f"Globus SDK Exception: {e}")

        self.done = True
        GlobusTransfer.transfers2do -= 1
        session = DBSession()
        session.add(t)
        session.commit()
        DBSession.remove()
        self.release()
        logger.info(f"{self} - finished")


def main(set, config):
    engine = create_engine(settings.database.get("url"))
    DBSession.configure(bind=engine)
    Base.metadata.create_all(engine)

    """
    Lists of Endpoint and Transfer objectwith locks are shared between threads.
    The classes and objects store all locks and necessary information to
    sychronized transfers.
    """
    global endpoints
    global transfers

    endpoints = [Endpoint(e) for e in config.get("endpoints")]
    datasets = list(config.get("datasets").keys())
    params = config.get("params")
    if params:
        GlobusTransfer.deadline = params.get("deadline", 3600)
    transfers = [GlobusTransfer(set, s, d, t) for s in endpoints for d in endpoints for t in datasets]

    executor = Executor(max_workers=4)
    while GlobusTransfer.transfers2do > 0:
        for t in transfers:
            if t.done:
                continue
            if t.acquire():
                executor.submit(t.run)
        sleep(10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Submit data transfers beetwen Globus endpoints")
    parser.add_argument("-c", "--config", required=True, help="configuration file in the JSON format")
    parser.add_argument("-s", "--set", required=True, help="name of the set of the endpoints that all records in the database will be associated with")
    args = parser.parse_args()
    with open(args.config, "r") as f:
        config = json.load(f)
        main(args.set, config)
