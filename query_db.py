import sqlite3
conn = sqlite3.connect(r'C:\Users\Liyander\Downloads\TomCTF\CTFd\CTFd\ctfd.db')
c = conn.cursor()

print('=== TABLES ===')
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for r in c.fetchall():
    print(r[0])

print()
print('=== docker_challenges columns ===')
try:
    c.execute('PRAGMA table_info(docker_challenges)')
    print([r[1] for r in c.fetchall()])
    c.execute('SELECT * FROM docker_challenges')
    for r in c.fetchall():
        print(r)
except Exception as e:
    print(e)

print()
print('=== ALL challenges ===')
c.execute('SELECT id, name, type, category FROM challenges')
for r in c.fetchall():
    print(r)

print()
print('=== docker_config ===')
try:
    c.execute('SELECT * FROM docker_config')
    for r in c.fetchall():
        print(r)
except Exception as e:
    print(e)

print()
print('=== docker_challenge_tracker ===')
try:
    c.execute('SELECT * FROM docker_challenge_tracker')
    for r in c.fetchall():
        print(r)
except Exception as e:
    print(e)

conn.close()
