import sqlite3

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
            self.execute(b"SELECT * FROM events LIMIT 1")
            self.execute(b"SELECT * FROM dfdash_config LIMIT 1")
        except sqlite3.OperationalError:
            self._db.executescript(DB.SCHEMA)
            self.execute(b"SELECT * FROM events LIMIT 1")
            self.execute(b"SELECT * FROM dfdash_config LIMIT 1")

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
        return self.execute(
            b"INSERT OR REPLACE INTO `dfdash_config` VALUES (?, ?)",
            (key, value), True)

    def config_get(self, key):
        try:
            # noinspection PyPep8
            value = self.execute(
                b"SELECT `value` FROM `dfdash_config` WHERE `key` LIKE ? LIMIT 1",
                (key,)
            )[0]
            return value[b"value"]
        except IndexError:
            return None
