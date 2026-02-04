import sqlite3

DB_PATH = "radar.db"

def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # ensure tables exist by running builder at least once
    cur.executescript("""
    CREATE VIEW IF NOT EXISTS v03_chain_edges_latest AS
      SELECT *
      FROM chain_edges_v10
      WHERE ts = (SELECT MAX(ts) FROM chain_edges_v10);

    CREATE VIEW IF NOT EXISTS v03_series_chain_latest AS
      SELECT *
      FROM series_chain_v10
      WHERE ts = (SELECT MAX(ts) FROM series_chain_v10);
    """)
    con.commit()
    con.close()
    print("OK: created v03_chain_edges_latest + v03_series_chain_latest")

if __name__ == "__main__":
    main()
