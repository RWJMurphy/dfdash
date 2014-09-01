class Stats:
    @staticmethod
    def deaths(db):
        query = """SELECT substr(type, instr(type, 'death.') + 6) as death_type, COUNT(*) as count
            FROM events
            WHERE type LIKE '%.death%'
            AND type NOT LIKE '%.death.butchered'
            GROUP BY substr(type, instr(type, 'death.') + 6)
            ORDER BY COUNT(*) DESC"""
        rows = db.execute(query)
        deaths = {}
        for row in rows:
            deaths[row['death_type']] = row['count']
        return deaths

