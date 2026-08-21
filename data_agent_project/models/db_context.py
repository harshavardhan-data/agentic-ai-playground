from dataclasses import dataclass

@dataclass
class DatabaseContext:
    dialect: str
    database_name: str
    execution_mode: str
    views: list[str]
    temporary_tables: list[str]
    max_rows: int

    