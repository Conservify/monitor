import sqlite3

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

class Parser(object):
    pass

class NatGeoDemoSubParser(Parser):
    def parse(self, transmission, fields):
        return {
            'id': transmission['id'],
            'time': transmission['time'],
            'source': transmission['source'],
            'age': float(transmission['age']),
            'name': fields[1],
            'lat': float(fields[2]),
            'lon': float(fields[3]),
            'altitude': float(fields[4]),
            'temperature': float(fields[5]),
            'humidity': float(fields[6]),
            'battery': 0.0,
            'charge': float(fields[7]) * 100,
            'uptime': float(fields[8]),
        }

class NoopSubParser(Parser):
    def parse(self, transmission, fields):
        return {
            'id': transmission.get('tid', None),
            'name': fields[1],
            'time': transmission['time'],
            'source': transmission['source'],
            'age': float(transmission['age']),
            'battery': 0.0,
            'charge': 0.0,
            'lat': 0.0,
            'lon': 0.0
        }

class RockBlockParser(Parser):
    parsers = {
        ('NGD-Shah', 9): NatGeoDemoSubParser(),
        ('NGD-Shah', 10): NatGeoDemoSubParser(),
        ('NGD-Jacob', 9): NatGeoDemoSubParser(),
        ('NGD-Jacob', 10): NatGeoDemoSubParser(),
        ('NGD-Demo1', 9): NatGeoDemoSubParser(),
        ('NGD-Demo1', 10): NatGeoDemoSubParser(),
        ('NGD-Demo2', 9): NatGeoDemoSubParser(),
        ('NGD-Demo2', 10): NatGeoDemoSubParser(),
        ('A1', 8): NoopSubParser(),
        ('A1', 11): NoopSubParser(),
        ('A1', 6): NoopSubParser(),
        ('A3', 6): NoopSubParser(),
        ('A3', 8): NoopSubParser(),
        ('A3', 11): NoopSubParser(),
        ('A2', 6): NoopSubParser(),
    }

    def parse(self, transmission):
        fields = transmission['data'].split(',')
        number_of_fields = len(fields)
        if number_of_fields <= 1:
            return None
        parser = RockBlockParser.parsers[(fields[1], number_of_fields)]
        return parser.parse(transmission, fields)

class ParticleParser(Parser):
    def parse(self, transmission):
        fields = transmission['data'].split(',')
        names = {
            '200051000e51353432393339': 'Jacob',
            '4f003c000b51343334363138': 'SharkOne',
            '4d0049000d51353432393339': 'SharkTwo',
            '250042000e51353432393339': 'SharkThree',
            '50002e000551353437353039': 'SharkFour',
            '280040000e51353432393339': 'SharkFive',
        }
        return {
            'id': transmission.get('tid', None),
            'age': float(transmission['age']),
            'time': transmission['time'],
            'source': transmission['source'],
            'name': names.get(transmission['id'], transmission['id']),
            'battery': float(fields[0]),
            'charge': float(fields[1]),
            'lat': float(fields[2]),
            'lon': float(fields[3]),
        }

class TwilioParser(Parser):
    def parse(self, transmission):
        fields = transmission['data'].split(',')
        names = {
            '+12039098762' : 'Jacob-Ting-SMS',
        }
        battery = 0.0
        charge = 0.0
        if len(fields) == 10:
            battery = float(fields[2])
            charge = float(fields[3]) * 100.0
        return {
            'id': transmission.get('tid', None),
            'age': float(transmission['age']),
            'time': transmission['time'],
            'source': transmission['source'],
            'name': names[transmission['id']],
            'battery': battery,
            'charge': charge,
            'lat': 0.0,
            'lon': 0.0,
        }

class MonitorDatabase(object):
    def __init__(self, path = '/app/data/monitor.db'):
        self.dbc = sqlite3.connect(path)
        self.dbc.row_factory = dict_factory
        self.dbc.execute('''CREATE TABLE IF NOT EXISTS transmissions (tid INTEGER PRIMARY KEY AUTOINCREMENT, id text, time timestamp, data text, source text)''')
        self.dbc.execute('''CREATE TABLE IF NOT EXISTS latest_transmissions (id text primary key, time timestamp, data text, source text)''')
        self.dbc.execute('''CREATE TABLE IF NOT EXISTS feeds (id text primary key, name TEXT)''')
        self.dbc.execute('''CREATE TABLE IF NOT EXISTS streams (id text primary key, feed_id INTEGER NOT NULL, transmission_id integer NOT NULL, data text)''')

    def fetch_transmissions(self):
        return self.dbc.execute("SElECT *, (julianday('now') - julianday(time)) * 24 * 60 * 60 AS age FROM transmissions").fetchall()

    def fetch_latest_transmissions(self):
        return self.dbc.execute("SELECT id, time, data, source, (julianday('now') - julianday(time)) * 24 * 60 * 60 AS age FROM latest_transmissions").fetchall()

    def add_transmission(self, instance, time, data, source):
        self.dbc.execute("INSERT OR REPLACE INTO latest_transmissions (id, time, data, source) VALUES (?, ?, ?, ?)", (instance, time, data.strip(), source))
        self.dbc.execute("INSERT INTO transmissions (id, time, data, source) VALUES (?, ?, ?, ?)", (instance, time, data.strip(), source))
        self.dbc.commit()

    def close(self):
        self.dbc.close()

    def fetch_and_parse_latest(self):
        return [self._parse_row(row) for row in self.fetch_latest_transmissions()]

    def fetch_and_parse(self):
        return [self._parse_row(row) for row in self.fetch_transmissions()]

    parsers = {
        'rockblock': RockBlockParser(),
        'particle': ParticleParser(),
        'twilio': TwilioParser()
    }

    def _parse_row(self, row):
        parser = MonitorDatabase.parsers[row['source']]
        parsed = parser.parse(row)
        return parsed

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.dbc.close()
