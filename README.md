# catalog
### tool for creating catalog from .csv tables in duckdb/sqlite storage


---

## file

parse .csv file's and transform data into a format suitable for storage

Set csv file to extraction
> `file.set <path_to_csv>`

Set separator in csv
> `file.sep <separator>`

Edit default headers
> `file.headers <header> <header> <...>`

Preview the file
> `file.preview`

Start extraction process
> `file.run`

---

### storage

operations with data in duckdb/sqlite storage

Change database file
> `storage.database <path_to_database>`

Reload database connection
> `storage.reload`

Delete table
> `storage.delete <table_name>`

Get tables list
> `storage.tables`

Purge tables
> `storage.purge`

Export tables
> `storage.export <table_name>`
