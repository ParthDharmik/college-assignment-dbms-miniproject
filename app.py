from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, send_file)
import pymysql
import pymysql.cursors
from decimal import Decimal, InvalidOperation
from functools import wraps
from contextlib import contextmanager
from werkzeug.security import check_password_hash, generate_password_hash
import csv, io

app = Flask(__name__)
app.secret_key = "change-this-in-real-life"

DB_CONFIG = {
    "host": "localhost", "user": "flask", "password": "flask",
    "database": "BankDB", "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}

def get_db(): return pymysql.connect(**DB_CONFIG)

def query(sql, args=None, one=False):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            rows = cur.fetchall()
        return rows[0] if one and rows else (None if one else rows)
    finally:
        conn.close()

def execute(sql, args=None):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
        conn.commit()
    finally:
        conn.close()

@contextmanager
def transaction():
    conn = get_db()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        conn.close()

def log_action(action):
    try:
        actor = session.get("user_name") or session.get("user_id", "anonymous")
        execute("INSERT INTO Audit_Log (Actor, Action) VALUES (%s, %s)",
                (str(actor), action))
    except Exception:
        pass

def login_required(role=None):
    def deco(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if "user_id" not in session:
                return redirect(url_for("index"))
            if role and session.get("role") != role:
                flash("Access denied", "error")
                return redirect(url_for("index"))
            return f(*a, **kw)
        return wrapper
    return deco

@app.route("/")
def index(): return render_template("front.html")

@app.route("/logout")
def logout():
    log_action("logout"); session.clear()
    return redirect(url_for("index"))

@app.route("/employees", methods=["GET", "POST"])
def employee_login():
    if request.method == "POST":
        emp = query("SELECT * FROM Employee WHERE Employee_ID = %s",
                    (request.form.get("id"),), one=True)
        if not emp or not check_password_hash(emp["Password"], request.form.get("password", "")):
            flash("Invalid credentials", "error")
            return redirect(url_for("employee_login"))
        session.update(user_id=emp["Employee_ID"], user_name=emp["Employee_Name"],
                       role="employee", emp_role=emp["Role"])
        log_action(f"login: {emp['Employee_Name']}")
        return redirect(url_for("dashboard"))
    return render_template("employee_login.html")

@app.route("/dashboard")
@login_required(role="employee")
def dashboard():
    counts = {
        "banks":        query("SELECT COUNT(*) c FROM Bank", one=True)["c"],
        "branches":     query("SELECT COUNT(*) c FROM Branch", one=True)["c"],
        "customers":    query("SELECT COUNT(*) c FROM Customer", one=True)["c"],
        "accounts":     query("SELECT COUNT(*) c FROM Account", one=True)["c"],
        "loans":        query("SELECT COUNT(*) c FROM Loan", one=True)["c"],
        "transactions": query("SELECT COUNT(*) c FROM `Transaction`", one=True)["c"],
    }
    totals = {
        "deposits": query("SELECT COALESCE(SUM(Balance),0) s FROM Account", one=True)["s"],
        "loans":    query("SELECT COALESCE(SUM(Amount),0)  s FROM Loan",    one=True)["s"],
    }
    by_branch = query("""SELECT b.Branch_Name, b.City,
               COUNT(a.Account_ID) AS accounts,
               COALESCE(SUM(a.Balance),0) AS total_balance
        FROM Branch b LEFT JOIN Account a ON a.Branch_ID = b.Branch_ID
        GROUP BY b.Branch_ID, b.Branch_Name, b.City ORDER BY total_balance DESC""")
    top_customers = query("""SELECT c.Customer_Name, COUNT(a.Account_ID) AS accounts,
               COALESCE(SUM(a.Balance),0) AS total_balance
        FROM Customer c LEFT JOIN Account a ON a.Customer_ID = c.Customer_ID
        GROUP BY c.Customer_ID, c.Customer_Name ORDER BY total_balance DESC LIMIT 5""")
    loan_mix = query("""SELECT Loan_Type AS label, COUNT(*) AS cnt,
               COALESCE(SUM(Amount),0) AS total FROM Loan GROUP BY Loan_Type""")
    txn_series = query("""SELECT DATE_FORMAT(Transaction_Date,'%%Y-%%m-%%d') AS d,
               SUM(CASE WHEN Transaction_Type='Deposit'  THEN Amount ELSE 0 END) AS deposits,
               SUM(CASE WHEN Transaction_Type='Withdraw' THEN Amount ELSE 0 END) AS withdrawals
        FROM `Transaction` WHERE Transaction_Date >= CURDATE() - INTERVAL 30 DAY
        GROUP BY d ORDER BY d""")
    recent = query("""SELECT Actor, Action, Created_At FROM Audit_Log
                     ORDER BY Log_ID DESC LIMIT 8""")
    return render_template("dashboard.html", counts=counts, totals=totals,
                           by_branch=by_branch, top_customers=top_customers,
                           loan_mix=loan_mix, txn_series=txn_series, recent=recent)

@app.route("/customers")
@login_required(role="employee")
def customers():
    q = request.args.get("q", "").strip()
    where, args = "", []
    if q:
        where = "WHERE c.Customer_Name LIKE %s OR c.Phone_No LIKE %s OR c.Email LIKE %s"
        args = [f"%{q}%"] * 3
    rows = query(f"""SELECT c.Customer_ID, c.Customer_Name, c.Phone_No, c.Email, c.Address,
               COUNT(DISTINCT a.Account_ID) AS accounts,
               COALESCE(SUM(a.Balance),0)  AS total_balance,
               COUNT(DISTINCT l.Loan_ID)   AS loans
        FROM Customer c
        LEFT JOIN Account a ON a.Customer_ID = c.Customer_ID
        LEFT JOIN Loan    l ON l.Customer_ID = c.Customer_ID
        {where}
        GROUP BY c.Customer_ID, c.Customer_Name, c.Phone_No, c.Email, c.Address
        ORDER BY c.Customer_ID""", args)
    return render_template("customers.html", customers=rows, q=q)

@app.route("/customers/new", methods=["GET", "POST"])
@login_required(role="employee")
def customer_new():
    if request.method == "POST":
        name = request.form.get("name")
        if not name:
            flash("Name required", "error"); return redirect(url_for("customer_new"))
        execute("""INSERT INTO Customer
            (Customer_Name, Phone_No, Email, Address, DOB, Password)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (name, request.form.get("phone"), request.form.get("email"),
             request.form.get("address"), request.form.get("dob") or None,
             generate_password_hash("password")))
        log_action(f"created customer {name}")
        flash(f"Customer '{name}' created (default password: password)", "success")
        return redirect(url_for("customers"))
    return render_template("customer_new.html")

@app.route("/employees/customer/<int:cid>")
@login_required(role="employee")
def customer_detail(cid):
    customer = query("SELECT * FROM Customer WHERE Customer_ID = %s", (cid,), one=True)
    if not customer:
        flash("Customer not found", "error"); return redirect(url_for("customers"))
    accounts = query("""SELECT a.*, b.Branch_Name FROM Account a
        JOIN Branch b ON b.Branch_ID = a.Branch_ID WHERE a.Customer_ID = %s""", (cid,))
    loans = query("SELECT * FROM Loan WHERE Customer_ID = %s", (cid,))
    txns = query("""SELECT t.*, a.Account_ID FROM `Transaction` t
        JOIN Account a ON a.Account_ID = t.Account_ID
        WHERE a.Customer_ID = %s
        ORDER BY t.Transaction_Date DESC, t.Transaction_ID DESC LIMIT 20""", (cid,))
    return render_template("customer_detail.html", customer=customer,
                           accounts=accounts, loans=loans, transactions=txns)

@app.route("/accounts")
@login_required(role="employee")
def accounts():
    q = request.args.get("q", "").strip()
    type_f = request.args.get("type", "").strip()
    clauses, args = [], []
    if q:
        clauses.append("(c.Customer_Name LIKE %s OR a.Account_ID LIKE %s)")
        args += [f"%{q}%", f"%{q}%"]
    if type_f:
        clauses.append("a.Account_Type = %s"); args.append(type_f)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = query(f"""SELECT a.Account_ID, a.Balance, a.Account_Type, a.Opening_Date, a.Status,
               c.Customer_Name, b.Branch_Name
        FROM Account a
        JOIN Customer c ON c.Customer_ID = a.Customer_ID
        JOIN Branch   b ON b.Branch_ID   = a.Branch_ID
        {where} ORDER BY a.Account_ID""", args)
    return render_template("accounts.html", accounts=rows, q=q, type_f=type_f)

@app.route("/accounts/new", methods=["GET", "POST"])
@login_required(role="employee")
def account_new():
    customers = query("SELECT Customer_ID, Customer_Name FROM Customer ORDER BY Customer_Name")
    branches  = query("SELECT Branch_ID, Branch_Name, City FROM Branch ORDER BY Branch_Name")
    if request.method == "POST":
        try:
            cust = int(request.form.get("customer_id"))
            br   = int(request.form.get("branch_id"))
            typ  = request.form.get("account_type")
            bal  = Decimal(request.form.get("balance", "0"))
            if typ not in ("Savings","Current","Fixed"): raise ValueError("Bad type")
            if bal < 0: raise ValueError("Negative balance")
        except (ValueError, InvalidOperation, TypeError) as e:
            flash(f"Invalid input: {e}", "error"); return redirect(url_for("account_new"))
        execute("""INSERT INTO Account
            (Customer_ID, Branch_ID, Account_Type, Balance, Status)
            VALUES (%s,%s,%s,%s,'Active')""", (cust, br, typ, bal))
        log_action(f"created account for customer {cust}")
        flash("Account created", "success")
        return redirect(url_for("accounts"))
    return render_template("account_new.html", customers=customers, branches=branches)

@app.route("/accounts/<int:aid>")
@login_required(role="employee")
def account_detail(aid):
    acc = query("""SELECT a.*, c.Customer_Name, b.Branch_Name FROM Account a
        JOIN Customer c ON c.Customer_ID = a.Customer_ID
        JOIN Branch   b ON b.Branch_ID   = a.Branch_ID
        WHERE a.Account_ID = %s""", (aid,), one=True)
    if not acc:
        flash("Account not found", "error"); return redirect(url_for("accounts"))
    txns = query("""SELECT * FROM `Transaction` WHERE Account_ID = %s
        ORDER BY Transaction_Date DESC, Transaction_ID DESC LIMIT 30""", (aid,))
    return render_template("account_detail.html", account=acc, transactions=txns)

@app.route("/loans")
@login_required(role="employee")
def loans():
    status_f = request.args.get("status", "").strip()
    where, args = "", []
    if status_f in ("Pending","Approved","Rejected"):
        where = "WHERE l.Status = %s"; args = [status_f]
    rows = query(f"""SELECT l.*, c.Customer_Name FROM Loan l
        JOIN Customer c ON c.Customer_ID = l.Customer_ID
        {where} ORDER BY l.Loan_ID DESC""", args)
    return render_template("loans.html", loans=rows, status_f=status_f)

@app.route("/loans/new", methods=["GET", "POST"])
@login_required(role="employee")
def loan_new():
    customers = query("SELECT Customer_ID, Customer_Name FROM Customer ORDER BY Customer_Name")
    if request.method == "POST":
        try:
            cust = int(request.form.get("customer_id"))
            typ  = request.form.get("loan_type")
            amt  = Decimal(request.form.get("amount"))
            rate = Decimal(request.form.get("interest_rate", "8.5"))
            dur  = int(request.form.get("duration_months", 12))
            if typ not in ("Home","Car","Personal","Education","Business"):
                raise ValueError("Bad type")
            if amt <= 0 or rate < 0 or dur <= 0: raise ValueError("Bad values")
        except (ValueError, InvalidOperation, TypeError) as e:
            flash(f"Invalid input: {e}", "error"); return redirect(url_for("loan_new"))
        execute("""INSERT INTO Loan
            (Customer_ID, Loan_Type, Amount, Interest_Rate, Duration_Months, Status)
            VALUES (%s,%s,%s,%s,%s,'Pending')""", (cust, typ, amt, rate, dur))
        log_action(f"created loan for customer {cust}")
        flash("Loan created (pending approval)", "success")
        return redirect(url_for("loans"))
    return render_template("loan_new.html", customers=customers)

@app.route("/loans/<int:loan_id>/status", methods=["POST"])
@login_required(role="employee")
def set_loan_status(loan_id):
    s = request.form.get("status")
    if s not in ("Approved","Rejected","Pending"):
        flash("Invalid status", "error"); return redirect(url_for("loans"))
    execute("UPDATE Loan SET Status = %s WHERE Loan_ID = %s", (s, loan_id))
    log_action(f"loan {loan_id} -> {s}")
    flash(f"Loan {loan_id} set to {s}", "success")
    return redirect(url_for("loans"))

@app.route("/branches")
@login_required(role="employee")
def branches():
    branch_rows = query("""SELECT b.*, bk.Bank_Name,
          (SELECT COUNT(*) FROM Employee e WHERE e.Branch_ID = b.Branch_ID) AS employees,
          (SELECT COUNT(*) FROM Account  a WHERE a.Branch_ID = b.Branch_ID) AS accounts,
          (SELECT COALESCE(SUM(a.Balance),0) FROM Account a
             WHERE a.Branch_ID = b.Branch_ID) AS total_deposits
        FROM Branch b JOIN Bank bk ON bk.Bank_ID = b.Bank_ID
        ORDER BY b.Branch_ID""")
    banks = query("SELECT * FROM Bank ORDER BY Bank_ID")
    employees = query("""SELECT e.Employee_ID, e.Employee_Name, e.Role,
        COALESCE(b.Branch_Name,'—') AS Branch_Name FROM Employee e
        LEFT JOIN Branch b ON b.Branch_ID = e.Branch_ID ORDER BY e.Employee_ID""")
    return render_template("branches.html", branches=branch_rows,
                           banks=banks, employees=employees)

@app.route("/branches/<int:bid>")
@login_required(role="employee")
def branch_detail(bid):
    branch = query("""SELECT b.*, bk.Bank_Name FROM Branch b
        JOIN Bank bk ON bk.Bank_ID = b.Bank_ID WHERE b.Branch_ID = %s""", (bid,), one=True)
    if not branch:
        flash("Branch not found", "error"); return redirect(url_for("branches"))
    emps = query("SELECT * FROM Employee WHERE Branch_ID = %s", (bid,))
    accs = query("""SELECT a.*, c.Customer_Name FROM Account a
        JOIN Customer c ON c.Customer_ID = a.Customer_ID
        WHERE a.Branch_ID = %s ORDER BY a.Balance DESC""", (bid,))
    return render_template("branch_detail.html", branch=branch,
                           employees=emps, accounts=accs)

@app.route("/transactions")
@login_required(role="employee")
def transactions():
    ttype = request.args.get("type", "").strip()
    where, args = "", []
    if ttype in ("Deposit","Withdraw"):
        where = "WHERE t.Transaction_Type = %s"; args = [ttype]
    rows = query(f"""SELECT t.*, c.Customer_Name FROM `Transaction` t
        JOIN Account  a ON a.Account_ID  = t.Account_ID
        JOIN Customer c ON c.Customer_ID = a.Customer_ID
        {where} ORDER BY t.Transaction_Date DESC, t.Transaction_ID DESC LIMIT 200""", args)
    return render_template("transactions.html", transactions=rows, type_f=ttype)

@app.route("/transactions/export.csv")
@login_required(role="employee")
def transactions_export():
    rows = query("""SELECT t.Transaction_ID, t.Transaction_Date, t.Transaction_Type,
        t.Amount, t.Account_ID, c.Customer_Name FROM `Transaction` t
        JOIN Account  a ON a.Account_ID  = t.Account_ID
        JOIN Customer c ON c.Customer_ID = a.Customer_ID
        ORDER BY t.Transaction_Date DESC, t.Transaction_ID DESC""")
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["ID","Date","Type","Amount","Account","Customer"])
    for r in rows:
        w.writerow([r["Transaction_ID"], r["Transaction_Date"], r["Transaction_Type"],
                    r["Amount"], r["Account_ID"], r["Customer_Name"]])
    buf.seek(0)
    return send_file(io.BytesIO(buf.read().encode()), mimetype="text/csv",
                     as_attachment=True, download_name="transactions.csv")

@app.route("/profile")
@login_required(role="employee")
def profile():
    emp = query("""SELECT e.*, b.Branch_Name FROM Employee e
        LEFT JOIN Branch b ON b.Branch_ID = e.Branch_ID
        WHERE e.Employee_ID = %s""", (session["user_id"],), one=True)
    logs = query("""SELECT * FROM Audit_Log WHERE Actor LIKE %s
        ORDER BY Log_ID DESC LIMIT 20""", (f"%{emp['Employee_Name']}%",))
    return render_template("profile.html", emp=emp, logs=logs)

@app.route("/users", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        acc = query("""SELECT a.Account_ID, c.Password, c.Customer_Name
            FROM Account a JOIN Customer c ON c.Customer_ID = a.Customer_ID
            WHERE a.Account_ID = %s""", (request.form.get("account_number"),), one=True)
        if not acc or not check_password_hash(acc["Password"], request.form.get("password", "")):
            flash("Invalid credentials", "error")
            return redirect(url_for("user_login"))
        session.update(user_id=acc["Account_ID"], role="customer",
                       user_name=acc["Customer_Name"])
        log_action(f"customer login: {acc['Customer_Name']}")
        return redirect(url_for("user_dashboard"))
    return render_template("user_login.html")

@app.route("/users/dashboard", methods=["GET", "POST"])
@login_required(role="customer")
def user_dashboard():
    account_id = session["user_id"]
    cust_row = query("SELECT Customer_ID FROM Account WHERE Account_ID = %s",
                     (account_id,), one=True)
    customer_id = cust_row["Customer_ID"] if cust_row else None

    if request.method == "POST":
        action = request.form.get("action")

        # ---------- LOAN REQUEST ----------
        if action == "request_loan":
            try:
                loan_type = request.form.get("loan_type")
                amount = Decimal(request.form.get("loan_amount", "0"))
                rate = Decimal(request.form.get("loan_rate", "8.5"))
                months = int(request.form.get("loan_months", "12"))
                if loan_type not in ("Home","Car","Personal","Education","Business"):
                    raise ValueError("Invalid loan type")
                if amount <= 0 or months <= 0 or rate < 0:
                    raise ValueError("Invalid loan values")
            except (ValueError, InvalidOperation, TypeError) as e:
                flash(f"Loan request failed: {e}", "error")
                return redirect(url_for("user_dashboard"))
            execute("""INSERT INTO Loan
                (Customer_ID, Loan_Type, Amount, Interest_Rate, Duration_Months, Status)
                VALUES (%s,%s,%s,%s,%s,'Pending')""",
                (customer_id, loan_type, amount, rate, months))
            log_action(f"loan request: {loan_type} Rs.{amount} by customer {customer_id}")
            flash(f"Loan request submitted! Rs.{amount:,.2f} {loan_type} - pending review.", "success")
            return redirect(url_for("user_dashboard"))

        # ---------- MONEY ACTIONS ----------
        try:
            amount = Decimal(request.form.get("amount", "0"))
            if amount <= 0: raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            flash("Invalid amount", "error"); return redirect(url_for("user_dashboard"))

        try:
            with transaction() as cur:
                if action == "deposit":
                    cur.execute("UPDATE Account SET Balance = Balance + %s WHERE Account_ID = %s",
                                (amount, account_id))
                    cur.execute("""INSERT INTO `Transaction`
                        (Amount, Transaction_Date, Transaction_Type, Account_ID)
                        VALUES (%s, CURDATE(), 'Deposit', %s)""", (amount, account_id))
                    flash(f"Deposited Rs.{amount:,.2f}", "success")
                elif action == "withdraw":
                    cur.execute("SELECT Balance FROM Account WHERE Account_ID = %s FOR UPDATE",
                                (account_id,))
                    row = cur.fetchone()
                    if not row or row["Balance"] < amount:
                        raise ValueError("Insufficient balance")
                    cur.execute("UPDATE Account SET Balance = Balance - %s WHERE Account_ID = %s",
                                (amount, account_id))
                    cur.execute("""INSERT INTO `Transaction`
                        (Amount, Transaction_Date, Transaction_Type, Account_ID)
                        VALUES (%s, CURDATE(), 'Withdraw', %s)""", (amount, account_id))
                    flash(f"Withdrew Rs.{amount:,.2f}", "success")
                elif action == "transfer":
                    target = request.form.get("account_number")
                    if target == str(account_id):
                        raise ValueError("Cannot transfer to yourself")
                    cur.execute("SELECT Balance FROM Account WHERE Account_ID = %s FOR UPDATE",
                                (account_id,))
                    src = cur.fetchone()
                    cur.execute("SELECT Account_ID FROM Account WHERE Account_ID = %s", (target,))
                    dst = cur.fetchone()
                    if not src or not dst: raise ValueError("Account not found")
                    if src["Balance"] < amount: raise ValueError("Insufficient balance")
                    cur.execute("UPDATE Account SET Balance = Balance - %s WHERE Account_ID = %s",
                                (amount, account_id))
                    cur.execute("UPDATE Account SET Balance = Balance + %s WHERE Account_ID = %s",
                                (amount, target))
                    cur.execute("""INSERT INTO `Transaction`
                        (Amount, Transaction_Date, Transaction_Type, Account_ID)
                        VALUES (%s, CURDATE(), 'Withdraw', %s)""", (amount, account_id))
                    cur.execute("""INSERT INTO `Transaction`
                        (Amount, Transaction_Date, Transaction_Type, Account_ID)
                        VALUES (%s, CURDATE(), 'Deposit', %s)""", (amount, target))
                    flash(f"Sent Rs.{amount:,.2f} to {target}", "success")
                else:
                    raise ValueError("Unknown action")
        except ValueError as e:
            flash(str(e), "error")
        except Exception as e:
            flash(f"Failed: {e}", "error")
        return redirect(url_for("user_dashboard"))

    acc = query("""SELECT a.Account_ID, a.Balance, a.Account_Type, a.Status,
        a.Opening_Date, c.Customer_ID, c.Customer_Name, c.Email, c.Phone_No, b.Branch_Name
        FROM Account a JOIN Customer c ON c.Customer_ID = a.Customer_ID
        JOIN Branch b ON b.Branch_ID = a.Branch_ID
        WHERE a.Account_ID = %s""", (account_id,), one=True)

    txns = query("""SELECT Transaction_ID, Transaction_Date, Transaction_Type, Amount
        FROM `Transaction` WHERE Account_ID = %s
        ORDER BY Transaction_Date DESC, Transaction_ID DESC LIMIT 20""", (account_id,))

    loans = query("""SELECT * FROM Loan WHERE Customer_ID = %s
        ORDER BY Loan_ID DESC""", (customer_id,))

    series = query("""SELECT DATE_FORMAT(Transaction_Date,'%%Y-%%m-%%d') d,
        SUM(CASE WHEN Transaction_Type='Deposit'  THEN Amount ELSE 0 END) deposits,
        SUM(CASE WHEN Transaction_Type='Withdraw' THEN Amount ELSE 0 END) withdrawals
        FROM `Transaction`
        WHERE Account_ID = %s AND Transaction_Date >= CURDATE() - INTERVAL 14 DAY
        GROUP BY d ORDER BY d""", (account_id,))

    return render_template("user_dashboard.html", account=acc, transactions=txns,
                           loans=loans, series=series)


if __name__ == "__main__":
    app.run(debug=True)
