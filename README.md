# catalog
### tool for creating catalog from .csv tables into duckdb/sqlite storage


---

## Extractor

parse .csv file's and transform data into a format suitable for storage

Set csv file to extraction
> `extractor.file <file_to_csv>`

Set separator in csv
> `extractor.sep <separator>`

Edit default headers
> `extractor.headers <header> <header> <...>`

Preview the file
> `extractor.preview`

Start extraction process
> `extractor.run`

---

### Storage

operations with data in duckdb/sqlite storage
