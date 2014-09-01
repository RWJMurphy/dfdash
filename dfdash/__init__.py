#!/usr/bin/env python
from __future__ import print_function, unicode_literals

import codecs
import os
import os.path
import re
from sqlite3 import OperationalError
import threading
import time

from flask import Flask

from watchdog.events import FileSystemEvent
from watchdog.observers.polling import PollingObserver

from db import DB
from event import Event, EventHandler
from stats import Stats

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
        self.line_count = 0
        self.line_limit = limit

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
        self._on_log_change(db)
        self.watch_log()
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
        db = DB(self._db_path)
        try:
            db.execute("SELECT instr('foo', 'f')")
        except OperationalError as soe:
            if soe.message == "no such function: instr":
                def instr(a, b):
                    """
                    :type a: str | unicode
                    :type b: str | unicode
                    :rtype: int
                    """
                    if None in (a, b):
                        return None
                    return a.find(b) + 1
                db._db.create_function("instr", 2, instr)
            else:
                raise
        return db

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
            self._on_log_change(db, print_events=True)

    def _on_log_change(self, db, print_events=False):
        last_line = None
        while True:
            line = self._log_file.readline()
            line_length = len(line)
            line = line.rstrip()
            if line == "":
                break
            if re.match(r'^x[0-9]+$', line):
                if last_line is None:
                    print("Got line '{}' but last_line is None :S".format(line))
                    self.line_count += 1
                    self._log_offset += line_length
                    continue
                else:
                    #print("Got line '{}', repeating last line".format(line))
                    line = last_line
            events = Event.from_text(line)
            for event in events:
                commit = False
                if print_events:
                    print("{}: {}".format(event.event_type, event.message))
                if self.line_count is not None and self.line_count % COMMIT_EVERY == 0:
                    commit = True
                event.put(db, commit)
            last_line = line
            self.line_count += 1
            self._log_offset += line_length
            if self.line_count % COMMIT_EVERY == 0:
                self.store_seek(db)
                print("{}...".format(self.line_count))
            if self.line_count == self.line_limit:
                self._log_offset += line_length
                self.store_seek(db)
                raise UserWarning("Limit reached.")
        self.store_seek(db)
        print("Death causes: {!r}".format(Stats.deaths(db)))

DF_PATH = r'\\BELGAER\Games\Dwarf Fortress\Dwarf Fortress 40_05 Starter Pack r2\Dwarf Fortress 0.40.05'
DB_PATH = os.path.join(os.environ['APPDATA'], "DFDash", "dfdash.db")
PROFILE = True
COMMIT_EVERY = 1000

if __name__ == "__main__":
    dfdash = DFDash(os.path.normpath(DF_PATH), db=DB_PATH)
    dfdash.run()
