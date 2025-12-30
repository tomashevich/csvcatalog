# CSVCatalog

a simple cli tool for wrangling csv files and shoving them into a sqlite database. no more manual scripts, no more headaches

## What's this? 🤔

tired of messing around with csvs and databases separately? me too. that's why i built catalog. it's a simple, no-nonsense tool that lets you:

*   **import csv files** into a sqlite database with an interactive wizard.
*   **search your data** with a powerful, flexible query syntax.
*   **export your data** back to csv whenever you need it.
*   **manage your database** with a set of easy-to-use commands.

## Getting Started 🚀

1.  install

```bash
pip install csvcatalog
```

2.  run a command

the basic structure is `csvcatalog COMMAND [ARGS]`. for example, to see all tables:

```bash
csvcatalog --help
```

by default, the database is stored in a user-specific data directory. you can specify a custom database file with the `dbfile` command:

```bash
# Optional
csvcatalog settings dbfile /path/to/your/database.db
```

you can setup aes256 encryption for database file

```bash
# Optional
csvcatalog settings encryption true
```

3.  extract your csv data table

```bash
csvcatalog extract path/to/my/data.csv
```

## Commands 🕹️

`typer` provides help for all commands. just run `csvcatalog --help` or `csvcatalog <command> --help` for more details.

*   `extract <file.csv>`: run an interactive wizard to import a csv file. you can map columns, select which ones to import, and apply regex filters to include/exclude specific rows.
*   `tables <optional: description filter>`: list all tables in the database, with their columns and row counts.
*   `describe <table_name> <description>`: add or update the description for a table.
*   `search <value> [targets...]`: search for a value across one or more tables and columns.
*   `export [table_names...]`: export one or more tables to csv files.
    *   if one table is specified, runs a full interactive wizard.
    *   if multiple tables are specified (or none, for all tables), runs a bulk export. you can choose to configure filters for specific tables.
*   `delete <table_name>`: delete a table from the database.
*   `sql "<query>"`: execute a raw sql query on the database.
*   `purge`: delete all tables from the database.

### Command Groups

these commands group related functionality.

#### `settings`
manage application settings. running `csvcatalog settings` will show current settings.

*   `settings dbfile <path>`: set a custom path for the database file.
*   `settings encryption <true|false>`: enable or disable database encryption.

#### `filters`
manage saved reusable regex filters for `extract` and `export`. running `csvcatalog filters` will list all saved filters.

*   `filters add <name> <regex>`: create a new named filter.
*   `filters remove [name]`: remove a filter by name, or run interactively if no name is provided.

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
