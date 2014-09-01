import functools
import json
import threading
import re
from watchdog.events import FileSystemEventHandler

from event_mappings import EVENT_MAPPINGS, EVENT_IGNORE

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


class Event:
    @classmethod
    def from_text(cls, event_line):
        """
        :type event_line: unicode
        :rtype list[DFDash.Event]
        """
        def extract_events(text, mapping):
            """
            :type mapping: EventMapping
            """
            maybe_events = []
            try:
                matches = mapping.pattern.match(text)
                if matches:
                    types = mapping.types
                    if not isinstance(types, (list, tuple)):
                        types = [types, ]
                    for event_type in types:
                        try:
                            origin = matches.group('origin')
                            event_type = matches.expand(event_type)
                        except IndexError:
                            origin = "unknown"
                            event_type = matches.expand(re.sub('\\\\g<origin>', origin, event_type))
                        except Exception as e:
                            print("Error expanding template:")
                            print(matches.groups())
                            print(event_type)
                            raise
                        maybe_events.append(
                            cls(origin=origin, message=text,
                                         event_type=event_type))
            except Exception as e:
                print("Error testing regex:")
                print(mapping.pattern.pattern)
                print(text)
                raise
            return maybe_events

        events = []
        for maybe_events in map(
                functools.partial(extract_events, event_line),
                EVENT_MAPPINGS):
            if maybe_events is not None:
                for event in maybe_events:
                        events.append(event)
        if events:
            if len(events) > 2:
                print("Got many events for line:")
                print("\t{}".format(event_line))
                for e in events:
                    print("\t{}".format(e.event_type))

            return events
        for pattern in EVENT_IGNORE:
            if pattern.match(event_line):
                return []
        #raise Exception("Unhandled event: {}".format(event_line))
        return [cls.unknown_event(event_line)]

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
            ("", self.event_type, ""),
            #(self.message, self.event_type, self.json),
            commit)

    @property
    def json(self):
        return json.dumps({
            "origin": self.origin,
            "message": self.message,
            "type": self.event_type,
        })

    @classmethod
    def unknown_event(cls, event_line):
        return cls(message=event_line, event_type="_.unknown", origin="")
