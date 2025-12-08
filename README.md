# catalog
### tool for creating catalog from .csv tables into duckdb/sqlite storage


---

## Extractor

parse .csv file's and transform data into a format suitable for storage

Set csv file to extraction
> `extractor.file <path_to_csv>`

Set separator in csv
> `extractor.sep <separator>`

Edit default headers
> `extractor.headers <header> <header> <...>`

Preview the file
> `extractor.preview`

Start extraction process
> `extractor.run`

---

### Saver

operations with data in duckdb/sqlite storage

Change database file
> `saver.database <path_to_database>`

Reload database connection
> `saver.reload`

Delete table
> `saver.delete <table_name>`

Get tables list
> `saver.tables`
