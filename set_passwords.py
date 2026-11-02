import pymysql
from werkzeug.security import generate_password_hash

conn = pymysql.connect(user="flask", password="flask", database="BankDB")
cur = conn.cursor()
pw = generate_password_hash("password")
cur.execute("UPDATE Customer SET Password=%s", (pw,))
cur.execute("UPDATE Employee SET Password=%s", (pw,))
conn.commit()
conn.close()
print("✅ All passwords set to 'password'")
