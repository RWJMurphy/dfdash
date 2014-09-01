#!/usr/bin/env python
from __future__ import print_function, unicode_literals

import codecs
import json
import os
import os.path
import random
import re
import sqlite3
import threading
import time

from flask import Flask

from watchdog.events import FileSystemEvent
from watchdog.observers.polling import PollingObserver

from db import DB
from event import Event, EventHandler

class DFDash:
    LOGFILE_NAME = "gamelog.txt"
    DB_NAME = "DFDash.db"

    class WebApplication:
        def __init__(self, port=8080):
            self._app = Flask(self.__class__.__name__)

        def run(self):
            self._app.run()

    def __init__(self, df, port=8080, db=None, limit=None):
        """
        :type df: unicode
        :type port: int
        """
        self.df = df
        self.port = port
        self.limit = limit

        self._log_path = os.path.join(df, DFDash.LOGFILE_NAME)
        self._log_offset = 0
        self._observer = PollingObserver()

        self._db_lock = threading.Lock()
        self._db_path = db or os.path.join(self.df, DFDash.DB_NAME)
        if not os.path.exists(os.path.dirname(self._db_path)):
            os.makedirs(os.path.dirname(self._db_path))
        self.connect_db().ensure_db_initialized()

        self._log_file = None
        self.open_log_file()

    def run(self):
        db = self.connect_db()
        self.watch_log()
        self._on_log_change(db)
        try:
            while True:
                time.sleep(1)
        except BaseException:
            self.stop_watching_log()
            raise

    def open_log_file(self):
        print("Opening log file: {}".format(self._log_path))
        self._log_file = codecs.open(self._log_path, "r", "cp437")
        offset = self.fetch_seek()
        print("Seeking to offset {}".format(offset))
        self._log_file.seek(offset)

    def fetch_seek(self):
        self._db_lock.acquire()
        db = self.connect_db()
        offset = db.config_get("gamelog_seek")
        db.close()
        self._db_lock.release()
        if offset is None:
            offset = 0
        else:
            offset = int(offset)
        self._log_offset = offset
        return self._log_offset

    def store_seek(self, db):
        offset = self._log_offset
        print("Storing log file offset: {}k".format(offset/1024))
        db.config_put("gamelog_seek", offset)

    def stop_watching_log(self):
        self._observer.stop()
        self._observer.join()

    def connect_db(self):
        return DB(self._db_path)

    def watch_log(self):
        self._observer.schedule(
            EventHandler(self._on_log_event,
                                self.connect_db),
            bytes(self.df))
        self._observer.start()

    def _on_log_event(self, event, db):
        """
        :type event: FileSystemEvent
        """
        if event.is_directory:
            return
        if event.src_path != self._log_path:
            return

        event_type = event.event_type
        if event_type == "modified":
            self._on_log_change(db)

    def _on_log_change(self, db):
        last_line = None
        while True:
            line = self._log_file.readline()
            line_length = len(line)
            line = line.rstrip()
            if line == "":
                self._log_offset += line_length
                self.store_seek(db)
                break
            if re.match(r'^x[0-9]+$', line):
                if last_line is None:
                    print("Got line '{}' but last_line is None :S".format(line))
                    continue
                else:
                    #print("Got line '{}', repeating last line".format(line))
                    line = last_line
            events = Event.from_text(line)
            for event in events:
                commit = False
                if self.limit is not None and self.limit % COMMIT_EVERY == 0:
                    print(event.json)
                    commit = True
                event.put(db, commit)
            self._log_offset += line_length
            last_line = line
            if self.limit is not None:
                self.limit -= 1
                if self.limit % COMMIT_EVERY == 0:
                    self.store_seek(db)
                    print("{}...".format(self.limit))
                if self.limit == 0:
                    self.store_seek(db)
                    raise UserWarning("Limit reached.")
        self.store_seek(db)

DF_PATH = r'\\BELGAER\Games\Dwarf Fortress\Dwarf Fortress 40_05 Starter Pack r2\Dwarf Fortress 0.40.05'
DB_PATH = os.path.join(os.environ['APPDATA'], "DFDash", "dfdash.db")
PROFILE = True
COMMIT_EVERY = 5000

if __name__ == "__main__":
    dfdash = DFDash(os.path.normpath(DF_PATH), db=DB_PATH)
    dfdash.run()
