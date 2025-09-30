#!/usr/bin/env python3
"""
SQLite MCP Tool to interact with an SQL-database with all essential SQL operations: SELECT, INSERT, UPDATE, DELETE, JOINs.
Designed to be used with via MCP protocol with LLMs frontends such as LM-Studio.
"""

import os
import sys
import time
import logging
import sqlite3
from fastmcp import FastMCP
from typing import List, Dict, Any, Optional

# Configure a simple logger
logger = logging.getLogger("SQLite-tool")
logging.basicConfig(level=logging.INFO)


# Create a FastMCP server instance
mcp = FastMCP("SQLite-tool")


@mcp.tool(description="Execute a SQL query on a local SQLite database, for complex queries - write raw SQL.")
def execute_sql_query(query: str, db_path: str) -> List[Dict[str, Any]]:
    """
    Execute a SQL query on a local SQLite database.
    
    Supports SELECT, INSERT, UPDATE, DELETE.
    Returns results as list of dicts for SELECT; affected row count otherwise.
    
    Args:
        query: The SQL query to execute (e.g., "SELECT * FROM customers WHERE city = 'New York'")
        db_path: Path to the SQLite database file
        
    Returns:
        List of dictionaries for SELECT queries, or [{"rows_affected": n}] otherwise.
        On error: [{"error": "message"}]
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        logger.info(f"Executing SQL query: {query}")
        cursor.execute(query)

        # If it's a SELECT, return results as list of dicts
        if query.strip().upper().startswith('SELECT'):
            column_names = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            results = [dict(zip(column_names, row)) for row in rows]
            return results
        else:
            # For INSERT/UPDATE/DELETE: commit and return row count
            conn.commit()
            return [{"rows_affected": cursor.rowcount}]

    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        return [{"error": str(e)}]
    finally:
        if 'conn' in locals():
            conn.close()


@mcp.tool(description="Get the schema of all tables in the SQLite database.")
def get_database_schema(db_path: str) -> List[Dict[str, Any]]:
    """
    Get the schema of all tables in the SQLite database.
    Returns table names and column details (name, type, notnull, default, primary_key).
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        List of tables with their column definitions.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = cursor.fetchall()
        
        schema_info = []
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            table_info = {
                "table": table_name,
                "columns": []
            }
            
            for col in columns:
                table_info["columns"].append({
                    "name": col[1],
                    "type": col[2],
                    "notnull": bool(col[3]),
                    "default": col[4],
                    "primary_key": bool(col[5])
                })
            
            schema_info.append(table_info)
        
        return schema_info
        
    except Exception as e:
        logger.error(f"Error retrieving database schema: {str(e)}")
        return [{"error": str(e)}]
    finally:
        if 'conn' in locals():
            conn.close()


@mcp.tool(description="Get the list of all table names in the SQLite database.")
def list_tables(db_path: str) -> List[str]:
    """
    Return a list of all table names in the database.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        List of table names
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
        return tables
    except Exception as e:
        logger.error(f"Error listing tables: {str(e)}")
        return [f"error: {str(e)}"]
    finally:
        if 'conn' in locals():
            conn.close()


@mcp.tool(description="A dedicated function to insert a single row into a specified table.")
def insert_row(table: str, data: Dict[str, Any], db_path: str) -> List[Dict[str, Any]]:
    """
    Insert a single row into a specified table.
    
    Args:
        table: Name of the target table
        data: Dictionary mapping column names to values (e.g., {"name": "Alice", "email": "alice@example.com"})
        db_path: Path to the SQLite database file

    Returns:
        [{"inserted_id": id}] on success, or [{"error": "..."}] on failure
    """
    if not data:
        logger.error("No data provided for insertion")
        return [{"error": "No data provided"}]

    columns = list(data.keys())
    placeholders = ", ".join(["?" for _ in columns])

    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    logger.info(f"Executing SQL command: {sql} with data {list(data.values())}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql, list(data.values()))
        conn.commit()
        inserted_id = cursor.lastrowid
        return [{"inserted_id": inserted_id}]

    except Exception as e:
        logger.error(f"Error inserting row into {table}: {str(e)}")
        return [{"error": str(e)}]
    finally:
        if 'conn' in locals():
            conn.close()


@mcp.tool(description="A dedicated function to update rows in a specified table with WHERE conditions.")
def update_rows(table: str, data: Dict[str, Any], where: Dict[str, Any], db_path: str) -> List[Dict[str, Any]]:
    """
    Update rows in a table based on WHERE conditions.
    
    Args:
        table: Name of the target table
        data: Dictionary mapping column names to values to update new values (e.g., {"email": "new@example.com"})
        where: Dictionary mapping with conditions to identify rows (e.g., {"id": 5})
        db_path: Path to the SQLite database file
        
    Returns:
        [{"rows_affected": n}] or [{"error": "..."}]
    """
    if not data or not where:
        logger.error("Both 'data' and 'where' must be provided for update operation")
        return [{"error": "Both 'data' and 'where' must be provided"}]

    set_clause = ", ".join([f"{col} = ?" for col in data.keys()])
    where_clause = " AND ".join([f"{col} = ?" for col in where.keys()])

    sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
    params = list(data.values()) + list(where.values())

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return [{"rows_affected": cursor.rowcount}]
        
    except Exception as e:
        logger.error(f"Error updating rows in {table}: {str(e)}")
        return [{"error": str(e)}]
    finally:
        if 'conn' in locals():
            conn.close()


@mcp.tool(description="A dedicated function to delete rows from a specified table with WHERE conditions.")
def delete_rows(table: str, where: Dict[str, Any], db_path: str) -> List[Dict[str, Any]]:
    """
    Delete rows from a table based on WHERE conditions.

    Args:
        table: Name of the target table
        where: Dictionary mapping with conditions to identify rows (e.g., {"customer_id": 1})
        db_path: Path to the SQLite database file

    Returns:
        [{"rows_affected": n}] or [{"error": "..."}]
    """
    if not where:
        logger.error("'where' condition required to avoid accidental deletion")
        return [{"error": "'where' condition required to avoid accidental deletion"}]
    
    where_clause = " AND ".join([f"{col} = ?" for col in where.keys()])
    sql = f"DELETE FROM {table} WHERE {where_clause}"
    params = list(where.values())
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return [{"rows_affected": cursor.rowcount}]
        
    except Exception as e:
        logger.error(f"Error deleting rows from {table}: {str(e)}")
        return [{"error": str(e)}]
    finally:
        if 'conn' in locals():
            conn.close()


@mcp.tool(description="Add a new column(field) to an existing table in the SQLite database.")
def add_column(table: str, column_name: str, data_type: str, db_path: str) -> List[Dict[str, Any]]:
    """
    Add a new column to an existing table in the SQLite database.
    The default SQLite behavior is that all existing rows automatically get NULL for the new column.

    Args:
        table: Name of the target table
        column_name: Name of the new column to add
        data_type: SQLite data type (e.g., "TEXT", "INTEGER", "REAL", "DATE")
        db_path: Path to the SQLite database file
        
    Returns:
        [{"success": true, "message": "..."}] on success
        [{"error": "..."}] on failure

    Notes:
        - SQLite only allows adding columns to the end of a table
        - Cannot add PRIMARY KEY or NOT NULL without DEFAULT value (unless column is nullable)
        - Column names must be valid identifiers (no spaces, reserved words)
    """ 
    # Validate inputs
    if not table.strip():
        logger.error("Table name cannot be empty")
        return [{"error": "Table name cannot be empty"}]
    if not column_name.strip():
        logger.error("Column name cannot be empty")
        return [{"error": "Column name cannot be empty"}]

    # Allowed SQLite types (common ones)
    allowed_types = {"TEXT", "INTEGER", "REAL", "NUMERIC", "BLOB", "DATE", "DATETIME"}
    if data_type.upper() not in allowed_types:
        logger.error(f"Invalid data type: {data_type}, must be one of {', '.join(allowed_types)}")
        return [{"error": f"Data type must be one of: {', '.join(allowed_types)}"}]

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        sql = f"ALTER TABLE {table} ADD COLUMN {column_name} {data_type}"
        cursor.execute(sql)
        conn.commit()
        return [{"success": True, "message": f"Column '{column_name}' ({data_type}) added to table '{table}'"}]

    except sqlite3.OperationalError as e:
        # Common errors:
        if "duplicate column name" in str(e).lower():
            return [{"error": f"Column '{column_name}' already exists in table '{table}'"}]
        elif "no such table" in str(e).lower():
            return [{"error": f"Table '{table}' does not exist"}]
        else:
            return [{"error": f"SQLite error: {str(e)}"}]
    except Exception as e:
        logger.error(f"Error adding new column {column_name} to {table}: {str(e)}")
        return [{"error": f"Unexpected error: {str(e)}"}]
    finally:
        if 'conn' in locals():
            conn.close()


def main() -> None:
    """
    Launch the MCP server that hosts the 2 MCP functions defined above. FastMCP will pick an available port automatically. 
    LM-Studio will launch this file via the command you configured in *mcp.json*.
    """
    try:
        # Write to stderr immediately so LM Studio knows we're alive
        print("SQLite-tool MCP server starting...", file=sys.stderr)

        # OPTIONAL: Add a tiny delay if you have heavy module imports
        # This gives LM Studio time to connect before your server is ready
        # Remove this in production if you don't need it.
        time.sleep(0.5)

        # Start the server — this will block and wait for MCP messages
        print("SQLite-tool MCP server ready to receive requests...", file=sys.stderr)
        mcp.run(transport="stdio")

    except Exception as e:
        print(f"SQLite-tool MCP server crashed: {type(e).__name__}: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
