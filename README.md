# CSVCatalog

a simple cli tool for wrangling csv files and shoving them into a sqlite database. no more manual scripts, no more headaches

## What's this? 🤔

tired of messing around with csvs and databases separately? me too. that's why i built catalog. it's a simple, no-nonsense tool that lets you:

*   **import csv files** into a sqlite database with an interactive wizard
*   **search your data** with a powerful, flexible query syntax
*   **export your data** back to csv whenever you need it
*   **manage your database** with a set of easy-to-use commands

all output is beautifully formatted using `rich` 💅.

## Getting Started 🚀

1.  install

```bash
pip install csvcatalog
```

2.  run a command

the basic structure is `csvcatalog [OPTIONS] COMMAND [ARGS]`. for example, to see all tables:

```bash
csvcatalog tables
```

by default, the database is stored in a user-specific data directory. you can specify a custom database file with the `--db` option:

```bash
csvcatalog --db /path/to/your/database.db tables
```

## Commands 🕹️

`typer` provides help for all commands. just run `csvcatalog --help` or `csvcatalog <command> --help`.

*   `extract <file.csv>`: run an interactive wizard to import a csv file into the database. you'll be prompted to set the separator, rename columns, select columns to import, and name the table.
*   `tables`: list all tables in the database, with their columns and row counts.
*   `search <value> [targets...]`: search for a value. this is the most powerful command.
*   `sql "<query>"`: execute a raw sql query on the database.
*   `export <table_name>`: export a table to a csv file, with an interactive prompt to select columns and limit rows.
*   `delete <table_name>`: delete a table from the database.
*   `purge`: delete all tables from the database.

### the mighty `search` command

the `search` command lets you specify exactly where to look for your data. a "target" can be a table, a specific column in a table, or a column across all tables.

**search for a value in all tables (default behavior):**
```bash
# looks for 'jane' everywhere
csvcatalog search "jane"
```

**search for a value in specific tables:**
```bash
# looks for 'jane' in the 'users' and 'customers' tables
csvcatalog search "jane" users customers
```

**search for a value in a specific column of a specific table:**
```bash
# looks for the email in the 'email' column of the 'users' table
csvcatalog search "jane.doe@example.com" users.email
```

**search for a value in a specific column across all tables:**
```bash
# finds any entry with a 'status' of 'active' in any table
csvcatalog search "active" "*.status"
```

**combine any of these targets in one command:**
```bash
# a totally valid and powerful query
csvcatalog search "jane" users.name products
```

## contributing are welcome 🤝
