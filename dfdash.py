#!/usr/bin/env python
from __future__ import print_function, unicode_literals

import codecs
from collections import namedtuple
import json
import functools
import os.path
import random
import re
import sqlite3
import sys
import threading
import time

from watchdog.events import FileSystemEvent, FileSystemEventHandler
# from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

EventMapping = namedtuple("EventMapping", "pattern types")


class DFDash:
    LOGFILE_NAME = "gamelog.txt"
    DB_NAME = "DFDash.db"

    class EventHandler(FileSystemEventHandler):
        def __init__(self, on_modified, db_connector):
            self._db_connector = db_connector
            self._db_lock = threading.Lock()
            self._on_modified = on_modified

        def on_modified(self, event):
            self._db_lock.acquire()
            db = self._db_connector()
            self._on_modified(event, db)
            db.close()
            self._db_lock.release()

    # consider something faster, e.g. https://code.google.com/p/esmre/
    EVENT_MAPPINGS = map(
        lambda (pattern, types): EventMapping(re.compile(pattern), types),
        [
            (r'(?P<origin>.+) has drowned\.', 'death.drowning'),
            (r'(?P<origin>.+) has died (of|from) thirst\.', 'death.dehydration'),
            (r'(?P<origin>.+) has starved to death\.', 'death.starvation'),
            (r'(?P<origin>.+) has been struck down\.', 'death.struck_down'),
            (r'(?P<origin>.+) has been crushed by a drawbridge\.', 'death.drawbridge'),
            (r'(?P<origin>.+) has died after colliding with an obstacle\.', 'death.collision'),
            (r'(?P<origin>.+) slams into an obstacle and blows apart!', 'death.collision.hard'),
            (r'(?P<origin>.+) has bled to death\.', 'death.bled_out'),
            (r'(?P<origin>.+) has died of old age\.', 'death.age'),
            (r'(?P<origin>.+) has suffocated\.', 'death.suffocation'),
            (r'(?P<origin>.+) has been encased in ice\.', 'death.encased.ice'),
            (r'(?P<origin>.+) has been encased in cooling lava\.', 'death.encased.obsidian'),
            (r'(?P<origin>.+) has been shot and killed\.', 'death.shot'),
            (r'(?P<origin>.+) has succumbed to infection\.', 'death.infection'),
            (r'(?P<origin>.+) has been impaled on spikes\.', 'death.spikes'),
            (r'(?P<origin>.+) has killed by a flying object\.', 'death.ufo_impact'),
            (r'(?P<origin>.+) has been killed by a trap\.', 'death.trap'),
            (r'(?P<origin>.+) has been murdered by (.+)!', 'death.murder'),
            (r'(?P<origin>.+) has been scared to death by the (.+)!', 'death.fright'),

            (r'(?P<origin>.+) has been found dead\.', 'death.other'),
            (r'(?P<origin>.+) has been found dead, dehydrated\.', 'death.dehydration'),
            (r'(?P<origin>.+) has been found, starved to death\.', 'death.starvation'),
            (r'(?P<origin>.+) has been found dead, badly crushed\.', 'death.crushing'),
            (r'(?P<origin>.+) has been found dead, drowned\.', 'death.drowning'),
            (r'(?P<origin>.+) has been found dead, completely drained of blood!', 'death.vampire'),
            (r'(?P<origin>.+) has been found dead, contorted in fear!', 'death.fright'),

            (r'(?P<origin>.+) has been slaughtered\.', 'animal.butchered'),

            (r'(?P<origin>.+) \((Tame)\) has given birth to (.+)\.', 'animal.birth'),

            (r'A caravan from (?P<origin>.+) has arrived\.', ['merchant.caravan.arrived', 'merchant.arrived']),
            (r'Their wagons have bypassed your inaccessible site\.', 'merchant.caravan.bypassed'),
            (r'Their wagons have bypassed your inaccessible site\.', 'merchant.bypassed'),

            (r'(?P<origin>An animal) has become a Stray (?P<class>war|hunting) (?P<species>.+)\.', 'animal.\g<species>.trained.\g<class>'),

            (r'(?P<origin>.+) cancels (.+): (.+)\.', 'job.cancelled'),
            (r'The dwarves were unable to complete the (.+)\.', 'job.building.cancelled'),
            (r'(.+) \((?P<qty>[0-9]+)\) has been completed\.', 'job.complete'),

            (r'(?P<origin>.+) has created a masterpiece (.+)!', 'masterpiece'),

            (r'It has started raining\.', 'weather.rain'),
            (r'The weather has cleared\.', 'weather.clear'),

            (r'.*', '_.unknown'),
        ]
    )
    random.shuffle(EVENT_MAPPINGS)

    class Event:
        @classmethod
        def from_text(cls, text):
            """
            :type text: unicode
            :rtype list[DFDash.Event]
            """
            def extract_events(text, mapping):
                events = []
                matches = mapping.pattern.search(text)
                if matches:
                    types = mapping.types
                    if not isinstance(types, (list, tuple)):
                        types = [types, ]
                    for event_type in types:
                        event_type = matches.expand(event_type)
                        try:
                            origin = matches.group('origin')
                        except IndexError:
                            origin = ""
                        events.append(cls(origin=origin, message=text, type=event_type))
                return events

            events = []
            for es in map(functools.partial(extract_events, text),
                          DFDash.EVENT_MAPPINGS):
                for e in es:
                    if e is not None:
                        events.append(e)
            return events

        def __init__(self, origin, message, event_type):
            """
            :type origin: unicode
            :type message: unicode
            :type event_type: unicode
            """
            self.origin = origin
            self.message = message
            self.event_type = event_type

        def put(self, db, commit=False):
            """
            :type db: DFDash.DB
            """
            return db.execute(
                b"INSERT INTO events (message, type, json) VALUES (?, ?, ?)",
                (self.message, self.event_type, self.json),
                commit)

        @property
        def json(self):
            return json.dumps({
                "origin": self.origin,
                "message": self.message,
                "type": self.event_type,
            })

    class DB:
        SCHEMA = """CREATE TABLE IF NOT EXISTS `events` (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER DEFAULT CURRENT_TIMESTAMP,
            type TEXT,
            message TEXT,
            json TEXT
        );
        CREATE INDEX IF NOT EXISTS `idx_type` ON `events` (`type`);
        CREATE INDEX IF NOT EXISTS `idx_message` ON `events` (`message`);

        CREATE TABLE IF NOT EXISTS `dfdash_config` (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """

        def __init__(self, db_path):
            """
            :type db_path: unicode
            """
            self._path = db_path
            self._db = sqlite3.connect(db_path)
            self._db.row_factory = sqlite3.Row

        def ensure_db_initialized(self):
            try:
                self.execute("SELECT * FROM events LIMIT 1")
                self.execute("SELECT * FROM dfdash_config LIMIT 1")
            except sqlite3.OperationalError:
                self._db.executescript(DFDash.DB.SCHEMA)
                self.execute("SELECT * FROM events LIMIT 1")
                self.execute("SELECT * FROM dfdash_config LIMIT 1")

        def execute(self, query, parameters=None, commit=False):
            """
            :type query: str
            :type parameters: tuple | dict
            :rtype list[sqlite3.Row] | int
            """
            cursor = self._db.cursor()
            parameters = parameters or ()
            try:
                cursor.execute(query, parameters)
                if commit:
                    self._db.commit()
                if cursor.rowcount == -1:
                    return cursor.fetchall()
                return cursor.rowcount
            except sqlite3.Error:
                self._db.rollback()
                raise
            finally:
                cursor.close()

        def close(self):
            self._db.close()

        def config_put(self, key, value):
            return self.execute("INSERT OR REPLACE INTO `dfdash_config` VALUES (?, ?)", (key, value), True)

        def config_get(self, key):
            try:
                value = self.execute("SELECT `value` FROM `dfdash_config` WHERE `key` LIKE ? LIMIT 1", (key,))[0]
                return value[b"value"]
            except IndexError:
                return None

    def __init__(self, df, port=8080, limit=None):
        """
        :type df: unicode
        :type port: int
        """
        self.df = df
        self.limit = limit
        self._db_lock = threading.Lock()
        self._log_path = os.path.join(df, DFDash.LOGFILE_NAME)
        self._log_offset = 0
        self.port = port
        self._observer = PollingObserver()
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
        print("Storing log file offset: {}".format(offset))
        db.config_put("gamelog_seek", offset)

    def stop_watching_log(self):
        self._observer.stop()
        self._observer.join()

    def connect_db(self):
        return DFDash.DB(os.path.join(self.df, DFDash.DB_NAME))

    def watch_log(self):
        self._observer.schedule(
            DFDash.EventHandler(self._on_log_event,
                                self.connect_db),
            self.df)
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
        i = 0
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
            events = DFDash.Event.from_text(line)
            for event in events:
                commit = False
                if self.limit % COMMIT_EVERY == 0:
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
                    raise KeyboardInterrupt
        self.store_seek(db)

DF_PATH = os.path.normpath(
    r"X:\Games\Dwarf Fortress\Dwarf Fortress 40_05 Starter Pack r1\Dwarf Fortress 0.40.05")
PROFILE = True
COMMIT_EVERY = 5000

if __name__ == "__main__":
    dfdash = DFDash(DF_PATH, limit=100000)
    dfdash.run()
