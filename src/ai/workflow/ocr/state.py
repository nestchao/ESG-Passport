"""SQLite job deduplication, circuit state and conservative spend reservations."""
from decimal import Decimal, ROUND_CEILING
import json
import sqlite3


def micros(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError('Finite nonnegative MYR amount required')
    return int((amount * 1000000).to_integral_value(rounding=ROUND_CEILING))


class OCRState:
    def __init__(self, path):
        # Caller selects private persistent storage. A database file is not encryption.
        self.db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY, signature TEXT NOT NULL, result TEXT);
          CREATE TABLE IF NOT EXISTS attempts (
            job_id TEXT, provider TEXT, status TEXT NOT NULL,
            reserved_micros INTEGER NOT NULL DEFAULT 0, exposure_micros INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(job_id, provider));
          CREATE TABLE IF NOT EXISTS circuits (provider TEXT PRIMARY KEY, open_until REAL NOT NULL);
        ''')

    def close(self):
        self.db.close()

    def claim(self, job_id, signature):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old = self.db.execute('SELECT signature,result FROM jobs WHERE job_id=?', (job_id,)).fetchone()
            if old:
                if old[0] != signature:
                    raise ValueError('Job ID reused with different input or routing configuration')
                if old[1] is None:
                    raise RuntimeError('Job in progress or interrupted; do not resend cloud requests')
                result = json.loads(old[1])
            else:
                self.db.execute('INSERT INTO jobs(job_id,signature) VALUES (?,?)', (job_id, signature))
                result = None
            self.db.execute('COMMIT')
            return result
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def finish(self, job_id, result):
        self.db.execute('UPDATE jobs SET result=? WHERE job_id=?',
                        (json.dumps(result, ensure_ascii=False, allow_nan=False), job_id))

    def circuit_open(self, provider, now):
        row = self.db.execute('SELECT open_until FROM circuits WHERE provider=?', (provider,)).fetchone()
        return bool(row and row[0] > now)

    def trip(self, provider, until):
        self.db.execute('INSERT OR REPLACE INTO circuits VALUES (?,?)', (provider, until))

    def reset(self, provider):
        self.db.execute('DELETE FROM circuits WHERE provider=?', (provider,))

    def reserve(self, job_id, provider, amount, limit):
        requested, cap = micros(amount), micros(limit)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            used = self.db.execute('SELECT COALESCE(SUM(exposure_micros),0) FROM attempts').fetchone()[0]
            if requested and used + requested > cap:
                self.db.execute('ROLLBACK')
                return False
            self.db.execute('INSERT INTO attempts VALUES (?,?,?,?,?)',
                            (job_id, provider, 'started', requested, requested))
            self.db.execute('COMMIT')
            return True
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def settle(self, job_id, provider, *, success, actual_myr=None):
        # An error/timeout/unknown charge keeps its full reservation. Never assume free failure.
        if success and actual_myr is not None:
            self.db.execute('UPDATE attempts SET status=?,exposure_micros=? WHERE job_id=? AND provider=?',
                            ('success', micros(actual_myr), job_id, provider))
        else:
            self.db.execute('UPDATE attempts SET status=? WHERE job_id=? AND provider=?',
                            ('success' if success else 'error', job_id, provider))

    def exposure_myr(self):
        used = self.db.execute('SELECT COALESCE(SUM(exposure_micros),0) FROM attempts').fetchone()[0]
        return str(Decimal(used) / 1000000)
