"""A small Base query model that refreshes one owned Calc report sheet."""
from pathlib import Path
import re

REPORT = "Warehouse Activity"
QUERY = "Daily Activity"
COLUMNS = ("Day", "Category", "Plays", "Minutes")
MAX_ROWS = 500
SQL = ('SELECT activity_day, category, plays, minutes '
       'FROM calc_reporting.daily_activity ORDER BY activity_day, category LIMIT 501')


def setting(name, value):
    import uno
    entry = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    entry.Name, entry.Value = name, value
    return entry


def datasource_url(host, port, database, certificate):
    certificate = Path(certificate).resolve(strict=True)
    if not re.fullmatch(r"[a-zA-Z0-9.-]+", host) or not re.fullmatch(r"[a-zA-Z0-9_]+", database):
        raise ValueError("Invalid database host or name.")
    if not 1 <= port <= 65535 or not certificate.is_file():
        raise ValueError("Provide a valid port and CA certificate.")
    ca = str(certificate).replace("\\", "\\\\").replace("'", "\\'")
    return f"sdbc:postgresql:host={host} port={port} dbname={database} connect_timeout=5 sslmode=verify-full sslrootcert='{ca}'"


def create_model(context, url, username, destination):
    service = context.ServiceManager
    database = service.createInstanceWithContext("com.sun.star.sdb.DatabaseContext", context)
    source = database.createInstance()
    source.URL = url
    source.User = username
    source.IsPasswordRequired = True
    queries = source.getQueryDefinitions()
    query = queries.createInstance()
    query.Command = SQL
    query.EscapeProcessing = False
    queries.insertByName(QUERY, query)
    document = source.DatabaseDocument
    document.storeAsURL(Path(destination).resolve().as_uri(), (setting("Overwrite", False),))
    return document


def load_report(source, password):
    """Query the named model using the database's read-only role."""
    connection = source.getConnection(source.User, password)
    try:
        statement = connection.createStatement()
        statement.execute("SET statement_timeout = '5s'")
        state = statement.executeQuery("SHOW transaction_read_only")
        if not state.next() or state.getString(1) != "on":
            raise ValueError("The warehouse connection must default to read-only transactions.")
        state.close()
        query = source.getQueryDefinitions().getByName(QUERY)
        if query.Command != SQL:
            raise ValueError("The saved model query differs from the approved projection.")
        rows = statement.executeQuery(query.Command)
        data = []
        while rows.next():
            row = (rows.getString(1), rows.getString(2), rows.getDouble(3), rows.getDouble(4))
            if len(data) >= MAX_ROWS or any(len(value) > 512 for value in row[:2]):
                raise ValueError("The warehouse result exceeds the report bounds.")
            data.append(row)
        rows.close()
        return tuple(data)
    finally:
        connection.close()


def refresh_report(document, rows):
    """Replace the owned snapshot without touching other sheets or formulas."""
    if document.isReadonly():
        raise ValueError("Close the workbook in other applications before refreshing.")
    sheets = document.Sheets
    ranges = document.DatabaseRanges
    if sheets.hasByName(REPORT):
        if not ranges.hasByName(REPORT):
            raise ValueError("The workbook already uses the report sheet name.")
        sheet = sheets.getByName(REPORT)
        report = ranges.getByName(REPORT)
        old = report.getDataArea()
        if sheet.isProtected():
            raise ValueError("The report sheet is protected.")
        area = sheet.getCellRangeByPosition(0, 0, len(COLUMNS) - 1, max(old.EndRow, len(rows)))
        origin = area.getRangeAddress()
        if (old.Sheet != origin.Sheet or old.StartColumn != 0 or old.StartRow != 0 or
                old.EndColumn != len(COLUMNS) - 1 or old.EndRow > MAX_ROWS or
                sheet.getCellRangeByPosition(0, 0, len(COLUMNS) - 1, 0).getDataArray() != (COLUMNS,)):
            raise ValueError("The report range no longer matches the expected layout.")
        if len(rows) > old.EndRow:
            expansion = sheet.getCellRangeByPosition(0, old.EndRow + 1, len(COLUMNS) - 1, len(rows))
            if any(value != "" for row in expansion.getFormulaArray() for value in row):
                raise ValueError("Report growth would overwrite existing cells.")
    else:
        if ranges.hasByName(REPORT):
            raise ValueError("The workbook already uses the report range name.")
        sheets.insertNewByName(REPORT, sheets.Count)
        sheet = sheets.getByName(REPORT)
        report = None
        area = sheet.getCellRangeByPosition(0, 0, len(COLUMNS) - 1, len(rows))
    blank = ("",) * len(COLUMNS)
    data = (COLUMNS, *rows)
    height = area.getRangeAddress().EndRow + 1
    area.setDataArray(data + (blank,) * (height - len(data)))
    current = sheet.getCellRangeByPosition(0, 0, len(COLUMNS) - 1, len(rows))
    if report is None:
        ranges.addNewByName(REPORT, current.getRangeAddress())
    else:
        report.setDataArea(current.getRangeAddress())
    sheet.getCellRangeByPosition(0, 0, len(COLUMNS) - 1, 0).CharWeight = 150
