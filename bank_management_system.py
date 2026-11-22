"""
Bank Management System - Python + MySQL
Menu-driven console app: accounts, deposits, withdrawals, transfers,
balance enquiry and transaction history.
Setup: pip install mysql-connector-python
"""

import os
import getpass
from decimal import Decimal, InvalidOperation

import mysql.connector
from mysql.connector import Error

MAX_AMOUNT = Decimal("9999999999.99")  # fits DECIMAL(12,2)


def connect_server():
    host = os.getenv("DB_HOST", "localhost")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD")
    if password is None:
        password = getpass.getpass(f"MySQL password for {user}@{host}: ")
    return mysql.connector.connect(host=host, user=user, password=password)


def init_database(conn, db_name):
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
    cur.execute(f"USE `{db_name}`")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS Customers (
            customer_id INT AUTO_INCREMENT PRIMARY KEY,
            first_name  VARCHAR(50)  NOT NULL,
            last_name   VARCHAR(50)  NOT NULL,
            phone       VARCHAR(15)  NOT NULL,
            address     VARCHAR(100),
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS Accounts (
            account_no   BIGINT AUTO_INCREMENT PRIMARY KEY,
            customer_id  INT NOT NULL,
            account_type ENUM('Savings', 'Current') NOT NULL,
            balance      DECIMAL(12,2) NOT NULL DEFAULT 0.00,
            opened_on    DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_balance CHECK (balance >= 0),
            FOREIGN KEY (customer_id) REFERENCES Customers(customer_id)
        ) AUTO_INCREMENT = 10001
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS BankTransactions (
            transaction_id   INT AUTO_INCREMENT PRIMARY KEY,
            account_no       BIGINT NOT NULL,
            transaction_type ENUM('Deposit', 'Withdrawal',
                                  'Transfer In', 'Transfer Out') NOT NULL,
            amount           DECIMAL(12,2) NOT NULL,
            balance_after    DECIMAL(12,2) NOT NULL,
            transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_no) REFERENCES Accounts(account_no)
        )
    """)
    conn.commit()
    cur.close()


def read_amount(prompt, allow_zero=False):
    while True:
        raw = input(prompt).strip()
        try:
            amount = Decimal(raw)
        except InvalidOperation:
            print("  Please enter a valid number.")
            continue
        if not amount.is_finite():
            print("  Please enter a valid number.")
            continue
        if amount < 0 or (amount == 0 and not allow_zero):
            print("  Amount must be greater than zero.")
            continue
        if amount != amount.quantize(Decimal("0.01")):
            print("  Use at most 2 decimal places.")
            continue
        if amount > MAX_AMOUNT:
            print("  Amount is too large.")
            continue
        return amount


def read_account_no(prompt="Enter Account Number: "):
    while True:
        raw = input(prompt).strip()
        if raw.isdigit():
            return int(raw)
        print("  Account number must contain digits only.")


def read_text(prompt, max_len=50, required=True):
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value[:max_len]
        print("  This field cannot be empty.")


def read_phone(prompt="Phone Number (10 digits): "):
    while True:
        phone = input(prompt).strip()
        if phone.isdigit() and len(phone) == 10:
            return phone
        print("  Phone number must be exactly 10 digits.")


def read_account_type():
    while True:
        choice = input("Account Type (1 = Savings, 2 = Current): ").strip()
        if choice == "1":
            return "Savings"
        if choice == "2":
            return "Current"
        print("  Enter 1 or 2.")


def money(value):
    return f"Rs. {value:,.2f}"


def log_transaction(cur, account_no, txn_type, amount, balance_after):
    cur.execute(
        """
        INSERT INTO BankTransactions
            (account_no, transaction_type, amount, balance_after)
        VALUES (%s, %s, %s, %s)
        """,
        (account_no, txn_type, amount, balance_after),
    )


def lock_balance(cur, account_no):
    cur.execute(
        "SELECT balance FROM Accounts WHERE account_no = %s FOR UPDATE",
        (account_no,),
    )
    row = cur.fetchone()
    return row[0] if row else None


def create_account(conn):
    print("\n--- Create New Account ---")
    first = read_text("First Name: ")
    last = read_text("Last Name: ")
    phone = read_phone()
    address = read_text("Address: ", max_len=100, required=False)
    acc_type = read_account_type()
    opening = read_amount("Opening Balance (0 for none): ", allow_zero=True)

    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO Customers (first_name, last_name, phone, address)
            VALUES (%s, %s, %s, %s)
            """,
            (first, last, phone, address),
        )
        customer_id = cur.lastrowid

        cur.execute(
            """
            INSERT INTO Accounts (customer_id, account_type, balance)
            VALUES (%s, %s, %s)
            """,
            (customer_id, acc_type, opening),
        )
        account_no = cur.lastrowid

        if opening > 0:
            log_transaction(cur, account_no, "Deposit", opening, opening)

        conn.commit()
        print(f"\nAccount created successfully. Your account number is {account_no}.")
    except Error as err:
        conn.rollback()
        print(f"\nCould not create account: {err}")
    finally:
        cur.close()


def deposit_money(conn):
    print("\n--- Deposit Money ---")
    account_no = read_account_no()
    amount = read_amount("Deposit Amount: ")

    cur = conn.cursor()
    try:
        balance = lock_balance(cur, account_no)
        if balance is None:
            conn.rollback()
            print("\nAccount not found.")
            return

        new_balance = balance + amount
        cur.execute(
            "UPDATE Accounts SET balance = %s WHERE account_no = %s",
            (new_balance, account_no),
        )
        log_transaction(cur, account_no, "Deposit", amount, new_balance)
        conn.commit()
        print(f"\nDeposited {money(amount)}. New balance: {money(new_balance)}")
    except Error as err:
        conn.rollback()
        print(f"\nDeposit failed: {err}")
    finally:
        cur.close()


def withdraw_money(conn):
    print("\n--- Withdraw Money ---")
    account_no = read_account_no()
    amount = read_amount("Withdrawal Amount: ")

    cur = conn.cursor()
    try:
        balance = lock_balance(cur, account_no)
        if balance is None:
            conn.rollback()
            print("\nAccount not found.")
            return
        if amount > balance:
            conn.rollback()
            print(f"\nInsufficient balance. Available: {money(balance)}")
            return

        new_balance = balance - amount
        cur.execute(
            "UPDATE Accounts SET balance = %s WHERE account_no = %s",
            (new_balance, account_no),
        )
        log_transaction(cur, account_no, "Withdrawal", amount, new_balance)
        conn.commit()
        print(f"\nWithdrew {money(amount)}. New balance: {money(new_balance)}")
    except Error as err:
        conn.rollback()
        print(f"\nWithdrawal failed: {err}")
    finally:
        cur.close()


def transfer_money(conn):
    print("\n--- Transfer Money ---")
    sender = read_account_no("From Account Number: ")
    receiver = read_account_no("To Account Number: ")
    if sender == receiver:
        print("\nCannot transfer to the same account.")
        return
    amount = read_amount("Transfer Amount: ")

    cur = conn.cursor()
    try:
        # Lock accounts in ascending order so opposite transfers can't deadlock.
        balances = {}
        for acc in sorted((sender, receiver)):
            balances[acc] = lock_balance(cur, acc)

        if balances[sender] is None or balances[receiver] is None:
            conn.rollback()
            print("\nOne or both accounts were not found.")
            return
        if amount > balances[sender]:
            conn.rollback()
            print(f"\nInsufficient balance. Available: {money(balances[sender])}")
            return

        sender_new = balances[sender] - amount
        receiver_new = balances[receiver] + amount

        cur.execute("UPDATE Accounts SET balance = %s WHERE account_no = %s",
                    (sender_new, sender))
        cur.execute("UPDATE Accounts SET balance = %s WHERE account_no = %s",
                    (receiver_new, receiver))
        log_transaction(cur, sender, "Transfer Out", amount, sender_new)
        log_transaction(cur, receiver, "Transfer In", amount, receiver_new)

        conn.commit()
        print(f"\nTransferred {money(amount)} from {sender} to {receiver}.")
        print(f"Your new balance: {money(sender_new)}")
    except Error as err:
        conn.rollback()
        print(f"\nTransfer failed: {err}")
    finally:
        cur.close()


def check_balance(conn):
    print("\n--- Balance Enquiry ---")
    account_no = read_account_no()
    cur = conn.cursor()
    try:
        cur.execute("SELECT balance FROM Accounts WHERE account_no = %s",
                    (account_no,))
        row = cur.fetchone()
        conn.commit()
        if row:
            print(f"\nAvailable balance: {money(row[0])}")
        else:
            print("\nAccount not found.")
    except Error as err:
        print(f"\nCould not fetch balance: {err}")
    finally:
        cur.close()


def account_details(conn):
    print("\n--- Account Details ---")
    account_no = read_account_no()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT a.account_no, c.first_name, c.last_name, c.phone,
                   c.address, a.account_type, a.balance, a.opened_on
            FROM Accounts a
            JOIN Customers c ON c.customer_id = a.customer_id
            WHERE a.account_no = %s
            """,
            (account_no,),
        )
        row = cur.fetchone()
        conn.commit()
        if not row:
            print("\nAccount not found.")
            return
        print(f"\nAccount No   : {row[0]}")
        print(f"Holder       : {row[1]} {row[2]}")
        print(f"Phone        : {row[3]}")
        print(f"Address      : {row[4] or '-'}")
        print(f"Account Type : {row[5]}")
        print(f"Balance      : {money(row[6])}")
        print(f"Opened On    : {row[7]:%d-%b-%Y}")
    except Error as err:
        print(f"\nCould not fetch details: {err}")
    finally:
        cur.close()


def transaction_history(conn):
    print("\n--- Transaction History ---")
    account_no = read_account_no()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM Accounts WHERE account_no = %s", (account_no,))
        if cur.fetchone() is None:
            conn.commit()
            print("\nAccount not found.")
            return

        cur.execute(
            """
            SELECT transaction_id, transaction_date, transaction_type,
                   amount, balance_after
            FROM BankTransactions
            WHERE account_no = %s
            ORDER BY transaction_id DESC
            LIMIT 10
            """,
            (account_no,),
        )
        rows = cur.fetchall()
        conn.commit()
        if not rows:
            print("\nNo transactions yet.")
            return

        print(f"\nLast {len(rows)} transactions for account {account_no}:\n")
        print(f"{'ID':<6}{'Date':<21}{'Type':<14}{'Amount':>14}{'Balance':>16}")
        print("-" * 71)
        for tid, date, ttype, amt, bal in rows:
            print(f"{tid:<6}{date:%Y-%m-%d %H:%M:%S}  {ttype:<14}"
                  f"{amt:>14,.2f}{bal:>16,.2f}")
    except Error as err:
        print(f"\nCould not fetch history: {err}")
    finally:
        cur.close()


MENU = """
==========================================
        BANK MANAGEMENT SYSTEM
==========================================
 1. Create Account
 2. Deposit Money
 3. Withdraw Money
 4. Transfer Money
 5. Check Balance
 6. Account Details
 7. Transaction History
 8. Exit
------------------------------------------"""


def main():
    db_name = os.getenv("DB_NAME", "BankDB")
    try:
        conn = connect_server()
        init_database(conn, db_name)
    except Error as err:
        print(f"Could not connect to MySQL: {err}")
        return

    actions = {
        "1": create_account,
        "2": deposit_money,
        "3": withdraw_money,
        "4": transfer_money,
        "5": check_balance,
        "6": account_details,
        "7": transaction_history,
    }

    try:
        while True:
            print(MENU)
            choice = input("Enter your choice (1-8): ").strip()
            if choice == "8":
                print("\nThank you for banking with us. Goodbye!")
                break
            action = actions.get(choice)
            if action:
                action(conn)
            else:
                print("\nInvalid choice. Please enter a number from 1 to 8.")
    except (KeyboardInterrupt, EOFError):
        print("\n\nExiting. Goodbye!")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
