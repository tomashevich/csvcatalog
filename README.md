# Catalog

Catalog made for wrangling CSV files and shoving them into a database. Makes the tedious task of managing CSV data a breeze. No more manual scripts, no more headaches

## What's this? 🤔

Tired of messing around with CSVs and databases separately? Me too. That's why I built Catalog. It's a simple, no-nonsense tool that lets you:

*   **Import CSV files** into a single SQLite database
*   **Manage your data** with a set of easy-to-use commands
*   **Export your data** back to CSV whenever you need it

## Features 🔥

*   **Interactive CLI:** A user-friendly interface that feels like you're chatting with a buddy
*   **CSV Parsing:** Automatically handles CSV files, with options to customize the separator and headers
*   **Database Storage:** Uses SQLite to store your data, so it's all in one place
*   **Data Management:** A rich set of commands to manage your tables
*   **Data Export:** Easily export your tables back to CSV files, with the ability to select specific columns and a limited number of rows

## Getting Started 🚀

1. Install

```bash
pip install csvcatalog
```

2. Run the cli

```bash
csvcatalog
```

2.1 You can also specify a custom database file if you want:

```bash
csvcatalog --db /path/to/your/database.db
```

## Commands 🕹️

Here's a quick rundown of the commands you'll be using

### Global Commands

Standart list of commands

*   `help`: Shows you all the available commands
*   `clear`: Clears the screen
*   `exit`: Quits the application
*   `system <command>`: Lets you run any shell command without leaving the CLI

### The `file` Module

*   `file.help`: Shows you the commands of the `file` module
*   `file.set <path_to_csv>`: Tells Catalog which CSV file you want to work with
*   `file.sep <separator>`: Sets the CSV separator. Because not everyone uses commas
*   `file.headers <header1> <header2> ...`: Lets you set custom headers for your data
*   `file.preview <optional: lines count>`: To make sure everything looks right
*   `file.run`: Extracts your data and saves it to a table

### The `storage` Module

*   `storage.help`: Shows you the commands of the `storage` module
*   `storage.db <path_to_db>`: Switches to a different database file
*   `storage.reload`: Reloads the database connection
*   `storage.tables`: Lists all the tables in your database
*   `storage.del.table <table_name>`: Deletes a table
*   `storage.purge`: Wipes the entire database clean
*   `storage.sql <stmt>`: Executes a pure SQL statement on the database
*   `storage.export <table_name>`: Exports a table to a CSV file

## Contributing are welcome 🤝
