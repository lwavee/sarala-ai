# Security Expert Knowledge - SQL Injection

## What is SQL Injection (SQLi)?
SQL Injection is a web security vulnerability that allows an attacker to interfere with the queries that an application makes to its database. It can allow attackers to view data they are not normally able to retrieve.

## How it Happens
It happens when an application uses user-supplied data directly in a SQL query without proper sanitization or parameterization.

## Example (Vulnerable Code)
```python
# VULNERABLE CODE - DO NOT USE
username = input("Enter username: ")
query = "SELECT * FROM users WHERE username = '" + username + "'"
# If user enters: admin' OR '1'='1
# The query becomes: SELECT * FROM users WHERE username = 'admin' OR '1'='1'
```

## How to Prevent
1. **Parameterized Queries (Prepared Statements):** Always use placeholders.
2. **Input Validation:** Use allow-lists for input.
3. **Least Privilege:** Ensure the database user has minimal necessary permissions.

## Example (Secure Code)
```python
# SECURE CODE
import sqlite3
db = sqlite3.connect("users.db")
cursor = db.cursor()
username = input("Enter username: ")
# Use ? as placeholder
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
```

## Next Steps
- Learn about **Cross-Site Scripting (XSS)**.
- Explore **OWASP Top 10** for more vulnerabilities.
- Practice in a **controlled lab environment** (like DVWA).
