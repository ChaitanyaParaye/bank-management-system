# Bank Management System (Python + MySQL)

A menu-driven console banking application built with Python and MySQL.

## Features
- Create account (customer and account created together)
- Deposit and withdraw money with balance validation
- Transfer funds between accounts
- Balance enquiry and account details
- Transaction history (last 10 transactions with running balance)

## Technical highlights
- ACID-safe operations: every money movement is a database transaction with commit/rollback
- Row-level locking (SELECT ... FOR UPDATE) to prevent balance corruption
- Parameterised queries to prevent SQL injection
- Decimal for money handling instead of float
- Normalised schema: Customers, Accounts, BankTransactions with foreign keys
- No hard-coded credentials (environment variables or hidden prompt)

## Tech stack
Python 3, MySQL, mysql-connector-python

## How to run
1. Install and start MySQL
2. pip install mysql-connector-python
3. python3 bank_management_system.py
4. Enter your MySQL root password when asked (press Enter if none)

The database and tables are created automatically on first run.
