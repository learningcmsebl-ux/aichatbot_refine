import html
import pymysql

conn = pymysql.connect(
    host="192.168.3.57", port=3306, user="tanvir", password="tanvir",
    database="ebl_home", charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
)
cur = conn.cursor()

for pt in ("ebl_management", "ebl_director"):
    print(f"\n=== {pt} published records ===")
    cur.execute(
        "SELECT ID, post_title, guid FROM ebl_posts WHERE post_type=%s AND post_status='publish' ORDER BY ID",
        (pt,),
    )
    for row in cur.fetchall():
        print(f"  {row['ID']} | {html.unescape(row['post_title'] or '')}")

    print(f"\n=== {pt} meta keys ===")
    cur.execute(
        """
        SELECT DISTINCT m.meta_key
        FROM ebl_postmeta m
        JOIN ebl_posts p ON p.ID = m.post_id
        WHERE p.post_type=%s AND p.post_status='publish'
        ORDER BY m.meta_key
        """,
        (pt,),
    )
    for row in cur.fetchall():
        print(f"  {row['meta_key']}")

    print(f"\n=== {pt} sample full record ===")
    cur.execute(
        "SELECT ID FROM ebl_posts WHERE post_type=%s AND post_status='publish' ORDER BY ID LIMIT 1",
        (pt,),
    )
    sample = cur.fetchone()
    if sample:
        cur.execute(
            "SELECT meta_key, LEFT(meta_value, 200) v FROM ebl_postmeta WHERE post_id=%s ORDER BY meta_key",
            (sample["ID"],),
        )
        for row in cur.fetchall():
            val = html.unescape(row["v"] or "")
            print(f"  {row['meta_key']}: {val}")

    print(f"\n=== {pt} attachment/photo lookup ===")
    cur.execute(
        """
        SELECT p.ID, p.post_title, pic.meta_value AS picture_id, att.guid AS picture_url
        FROM ebl_posts p
        LEFT JOIN ebl_postmeta pic ON pic.post_id = p.ID AND pic.meta_key = 'upload_picture'
        LEFT JOIN ebl_posts att ON att.ID = CAST(pic.meta_value AS UNSIGNED)
        WHERE p.post_type=%s AND p.post_status='publish'
        ORDER BY p.post_title
        LIMIT 5
        """,
        (pt,),
    )
    for row in cur.fetchall():
        print(
            f"  {row['ID']} {html.unescape(row['post_title'] or '')} | pic_id={row['picture_id']} | {row['picture_url']}"
        )

conn.close()
