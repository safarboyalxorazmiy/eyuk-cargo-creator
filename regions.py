import json
import psycopg2

def create_regions_table(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS regions (
                id INT PRIMARY KEY,
                name_uz TEXT,
                name_cy TEXT,
                name_ru TEXT
            );
        """)
    conn.commit()
    print("🧱 Table 'regions' created (if not existed).")

def insert_regions_from_file(conn, file_path: str):
    with open(file_path, 'r', encoding='utf-8') as f:
        regions = json.load(f)

    with conn.cursor() as cursor:
        for region in regions:
            cursor.execute("""
                INSERT INTO regions (id, name_uz, name_cy, name_ru)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING;
            """, (
                int(region["id"]),
                region["name_uz"],
                region["name_oz"],  # name_oz → goes to name_cy
                region["name_ru"]
            ))

    conn.commit()
    print(f"✅ Inserted {len(regions)} regions successfully.")

if __name__ == "__main__":
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="postgres",
        host="localhost",
        port=5432
    )

    create_regions_table(conn)
    insert_regions_from_file(conn, "regions.txt")
    conn.close()
