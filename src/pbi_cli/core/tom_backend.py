"""TOM (Tabular Object Model) operations.

All functions accept TOM objects (model, server, database) and return
plain Python dicts. This is the single point of .NET interop for
read/write operations on the semantic model.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_table(model: Any, table_name: str) -> Any:
    """Get a table by name, raising on not found."""
    for table in model.Tables:
        if table.Name == table_name:
            return table
    raise ValueError(f"Table '{table_name}' not found")


def _get_column(table: Any, column_name: str) -> Any:
    """Get a column by name, raising on not found."""
    for col in table.Columns:
        if col.Name == column_name:
            return col
    raise ValueError(f"Column '{column_name}' not found in table '{table.Name}'")


def _get_measure(table: Any, measure_name: str) -> Any:
    """Get a measure by name, raising on not found."""
    for m in table.Measures:
        if m.Name == measure_name:
            return m
    raise ValueError(f"Measure '{measure_name}' not found in table '{table.Name}'")


def _get_relationship(model: Any, name: str) -> Any:
    """Get a relationship by name, raising on not found."""
    for rel in model.Relationships:
        if rel.Name == name:
            return rel
    raise ValueError(f"Relationship '{name}' not found")


def _first_partition_mode(table: Any) -> str:
    """Get the mode of the first partition, or empty string."""
    for p in table.Partitions:
        return _safe_str(p.Mode)
    return ""


def _safe_str(val: Any) -> str:
    """Convert a .NET value to string, handling None."""
    if val is None:
        return ""
    try:
        return str(val)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Model operations
# ---------------------------------------------------------------------------


def model_get(model: Any, database: Any) -> dict[str, Any]:
    """Return model metadata."""
    return {
        "name": str(model.Name),
        "culture": _safe_str(model.Culture),
        "compatibilityLevel": int(database.CompatibilityLevel),
        "defaultMode": str(model.DefaultMode),
        "tables": model.Tables.Count,
        "relationships": model.Relationships.Count,
    }


def model_get_stats(model: Any) -> dict[str, Any]:
    """Return model statistics: counts of tables, columns, measures, etc."""
    table_count = 0
    column_count = 0
    measure_count = 0
    relationship_count = model.Relationships.Count
    partition_count = 0

    for table in model.Tables:
        table_count += 1
        column_count += table.Columns.Count
        measure_count += table.Measures.Count
        partition_count += table.Partitions.Count

    return {
        "tables": table_count,
        "columns": column_count,
        "measures": measure_count,
        "relationships": relationship_count,
        "partitions": partition_count,
    }


# ---------------------------------------------------------------------------
# Table operations
# ---------------------------------------------------------------------------


def table_list(model: Any) -> list[dict[str, Any]]:
    """List all tables with summary info."""
    results: list[dict[str, Any]] = []
    for table in model.Tables:
        results.append(
            {
                "name": str(table.Name),
                "columns": table.Columns.Count,
                "measures": table.Measures.Count,
                "partitions": table.Partitions.Count,
                "isHidden": bool(table.IsHidden),
                "description": _safe_str(table.Description),
            }
        )
    return results


def table_get(model: Any, table_name: str) -> dict[str, Any]:
    """Get detailed metadata for a single table."""
    table = _get_table(model, table_name)
    return {
        "name": str(table.Name),
        "columns": table.Columns.Count,
        "measures": table.Measures.Count,
        "partitions": table.Partitions.Count,
        "isHidden": bool(table.IsHidden),
        "description": _safe_str(table.Description),
        "defaultMode": _first_partition_mode(table),
    }


def table_get_schema(model: Any, table_name: str) -> list[dict[str, Any]]:
    """Get the column schema for a table."""
    table = _get_table(model, table_name)
    results: list[dict[str, Any]] = []
    for col in table.Columns:
        results.append(
            {
                "name": str(col.Name),
                "dataType": str(col.DataType),
                "type": str(col.Type),
                "isHidden": bool(col.IsHidden),
                "formatString": _safe_str(col.FormatString),
            }
        )
    return results


def table_create(
    model: Any,
    name: str,
    mode: str = "Import",
    m_expression: str | None = None,
    dax_expression: str | None = None,
    description: str | None = None,
    is_hidden: bool = False,
) -> dict[str, Any]:
    """Create a new table with a single partition."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    Table, Partition, ModeType = get_tom_classes("Table", "Partition", "ModeType")

    t = Table()
    t.Name = name
    if description is not None:
        t.Description = description
    if is_hidden:
        t.IsHidden = True

    p = Partition()
    p.Name = name

    mode_map = {
        "Import": ModeType.Import,
        "DirectQuery": ModeType.DirectQuery,
        "Dual": ModeType.Dual,
    }
    if mode in mode_map:
        p.Mode = mode_map[mode]

    if m_expression is not None:
        from pbi_cli.core.dotnet_loader import get_tom_classes as _gtc

        (MPartitionSource,) = _gtc("MPartitionSource")
        src = MPartitionSource()
        src.Expression = m_expression
        p.Source = src
    elif dax_expression is not None:
        from pbi_cli.core.dotnet_loader import get_tom_classes as _gtc

        (CalculatedPartitionSource,) = _gtc("CalculatedPartitionSource")
        src = CalculatedPartitionSource()
        src.Expression = dax_expression
        p.Source = src

    t.Partitions.Add(p)
    model.Tables.Add(t)
    model.SaveChanges()
    return {"status": "created", "name": name}


def table_delete(model: Any, table_name: str) -> dict[str, Any]:
    """Delete a table."""
    table = _get_table(model, table_name)
    model.Tables.Remove(table)
    model.SaveChanges()
    return {"status": "deleted", "name": table_name}


def table_refresh(model: Any, table_name: str, refresh_type: str = "Automatic") -> dict[str, Any]:
    """Request a table refresh."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    (RefreshType,) = get_tom_classes("RefreshType")

    table = _get_table(model, table_name)
    rt_map = {
        "Full": RefreshType.Full,
        "Automatic": RefreshType.Automatic,
        "Calculate": RefreshType.Calculate,
        "DataOnly": RefreshType.DataOnly,
    }
    rt = rt_map.get(refresh_type, RefreshType.Automatic)
    table.RequestRefresh(rt)
    model.SaveChanges()
    return {"status": "refreshed", "name": table_name, "refreshType": refresh_type}


def table_rename(model: Any, old_name: str, new_name: str) -> dict[str, Any]:
    """Rename a table."""
    table = _get_table(model, old_name)
    table.Name = new_name
    model.SaveChanges()
    return {"status": "renamed", "oldName": old_name, "newName": new_name}


def table_update(
    model: Any,
    table_name: str,
    description: str | None = None,
    is_hidden: bool | None = None,
) -> dict[str, Any]:
    """Update mutable properties of an existing table (description, hidden).

    Only properties explicitly passed are changed; ``None`` leaves a property
    untouched (so hidden can be toggled on or off without touching the
    description, and vice-versa).
    """
    table = _get_table(model, table_name)
    changed: list[str] = []
    if description is not None:
        table.Description = description
        changed.append("description")
    if is_hidden is not None:
        table.IsHidden = bool(is_hidden)
        changed.append("isHidden")
    if not changed:
        return {"status": "unchanged", "name": table_name, "changed": []}
    model.SaveChanges()
    return {"status": "updated", "name": table_name, "changed": changed}


def table_mark_as_date(model: Any, table_name: str, date_column: str) -> dict[str, Any]:
    """Mark a table as a date table."""
    table = _get_table(model, table_name)
    col = _get_column(table, date_column)
    table.DataCategory = "Time"
    # Set the column as the key for the date table
    col.IsKey = True
    model.SaveChanges()
    return {"status": "marked_as_date", "name": table_name, "dateColumn": date_column}


# ---------------------------------------------------------------------------
# Column operations
# ---------------------------------------------------------------------------


def column_list(model: Any, table_name: str) -> list[dict[str, Any]]:
    """List all columns in a table."""
    table = _get_table(model, table_name)
    results: list[dict[str, Any]] = []
    for col in table.Columns:
        results.append(
            {
                "name": str(col.Name),
                "dataType": str(col.DataType),
                "type": str(col.Type),
                "isHidden": bool(col.IsHidden),
                "displayFolder": _safe_str(col.DisplayFolder),
                "description": _safe_str(col.Description),
                "formatString": _safe_str(col.FormatString),
            }
        )
    return results


def column_get(model: Any, table_name: str, column_name: str) -> dict[str, Any]:
    """Get detailed metadata for a single column."""
    table = _get_table(model, table_name)
    col = _get_column(table, column_name)
    result: dict[str, Any] = {
        "name": str(col.Name),
        "tableName": str(table.Name),
        "dataType": str(col.DataType),
        "type": str(col.Type),
        "isHidden": bool(col.IsHidden),
        "displayFolder": _safe_str(col.DisplayFolder),
        "description": _safe_str(col.Description),
        "formatString": _safe_str(col.FormatString),
        "isKey": bool(col.IsKey),
    }
    # Include expression for calculated columns
    if _safe_str(col.Type) == "Calculated":
        result["expression"] = _safe_str(col.Expression)
    # Include source column for data columns
    source = _safe_str(col.SourceColumn)
    if source:
        result["sourceColumn"] = source
    return result


def column_create(
    model: Any,
    table_name: str,
    name: str,
    data_type: str,
    source_column: str | None = None,
    expression: str | None = None,
    format_string: str | None = None,
    description: str | None = None,
    display_folder: str | None = None,
    is_hidden: bool = False,
    is_key: bool = False,
) -> dict[str, Any]:
    """Create a new column (data or calculated)."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    table = _get_table(model, table_name)

    dt_map = _data_type_map()
    if data_type not in dt_map:
        raise ValueError(
            f"Unknown data type '{data_type}'. Valid types: {', '.join(sorted(dt_map.keys()))}"
        )

    if expression is not None:
        (CalculatedColumn,) = get_tom_classes("CalculatedColumn")
        col = CalculatedColumn()
        col.Expression = expression
    else:
        (DataColumn,) = get_tom_classes("DataColumn")
        col = DataColumn()
        if source_column is not None:
            col.SourceColumn = source_column

    col.Name = name
    col.DataType = dt_map[data_type]
    if format_string is not None:
        col.FormatString = format_string
    if description is not None:
        col.Description = description
    if display_folder is not None:
        col.DisplayFolder = display_folder
    if is_hidden:
        col.IsHidden = True
    if is_key:
        col.IsKey = True

    table.Columns.Add(col)
    model.SaveChanges()
    return {"status": "created", "name": name, "tableName": table_name}


def column_delete(model: Any, table_name: str, column_name: str) -> dict[str, Any]:
    """Delete a column."""
    table = _get_table(model, table_name)
    col = _get_column(table, column_name)
    table.Columns.Remove(col)
    model.SaveChanges()
    return {"status": "deleted", "name": column_name, "tableName": table_name}


def column_rename(model: Any, table_name: str, old_name: str, new_name: str) -> dict[str, Any]:
    """Rename a column."""
    table = _get_table(model, table_name)
    col = _get_column(table, old_name)
    col.Name = new_name
    model.SaveChanges()
    return {"status": "renamed", "oldName": old_name, "newName": new_name}


def _data_type_map() -> dict[str, Any]:
    """Return a mapping from string data type names to TOM DataType enums."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    (DataType,) = get_tom_classes("DataType")
    return {
        "string": DataType.String,
        "int64": DataType.Int64,
        "double": DataType.Double,
        "datetime": DataType.DateTime,
        "decimal": DataType.Decimal,
        "boolean": DataType.Boolean,
        "binary": DataType.Binary,
        "variant": DataType.Variant,
    }


# ---------------------------------------------------------------------------
# Measure operations
# ---------------------------------------------------------------------------


def measure_list(model: Any, table_name: str | None = None) -> list[dict[str, Any]]:
    """List measures, optionally filtered by table."""
    results: list[dict[str, Any]] = []
    for table in model.Tables:
        if table_name and str(table.Name) != table_name:
            continue
        for m in table.Measures:
            results.append(
                {
                    "name": str(m.Name),
                    "tableName": str(table.Name),
                    "expression": _safe_str(m.Expression),
                    "displayFolder": _safe_str(m.DisplayFolder),
                    "description": _safe_str(m.Description),
                    "isHidden": bool(m.IsHidden),
                }
            )
    return results


def measure_get(model: Any, table_name: str, measure_name: str) -> dict[str, Any]:
    """Get detailed metadata for a single measure."""
    table = _get_table(model, table_name)
    m = _get_measure(table, measure_name)
    return {
        "name": str(m.Name),
        "tableName": str(table.Name),
        "expression": _safe_str(m.Expression),
        "displayFolder": _safe_str(m.DisplayFolder),
        "description": _safe_str(m.Description),
        "formatString": _safe_str(m.FormatString),
        "isHidden": bool(m.IsHidden),
    }


def measure_create(
    model: Any,
    table_name: str,
    name: str,
    expression: str,
    format_string: str | None = None,
    description: str | None = None,
    display_folder: str | None = None,
    is_hidden: bool = False,
) -> dict[str, Any]:
    """Create a new measure."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    (Measure,) = get_tom_classes("Measure")

    table = _get_table(model, table_name)
    m = Measure()
    m.Name = name
    m.Expression = expression
    if format_string is not None:
        m.FormatString = format_string
    if description is not None:
        m.Description = description
    if display_folder is not None:
        m.DisplayFolder = display_folder
    if is_hidden:
        m.IsHidden = True
    table.Measures.Add(m)
    model.SaveChanges()
    return {"status": "created", "name": name, "tableName": table_name}


def measure_update(
    model: Any,
    table_name: str,
    name: str,
    expression: str | None = None,
    format_string: str | None = None,
    description: str | None = None,
    display_folder: str | None = None,
) -> dict[str, Any]:
    """Update an existing measure's properties."""
    table = _get_table(model, table_name)
    m = _get_measure(table, name)
    if expression is not None:
        m.Expression = expression
    if format_string is not None:
        m.FormatString = format_string
    if description is not None:
        m.Description = description
    if display_folder is not None:
        m.DisplayFolder = display_folder
    model.SaveChanges()
    return {"status": "updated", "name": name, "tableName": table_name}


def measure_delete(model: Any, table_name: str, name: str) -> dict[str, Any]:
    """Delete a measure."""
    table = _get_table(model, table_name)
    m = _get_measure(table, name)
    table.Measures.Remove(m)
    model.SaveChanges()
    return {"status": "deleted", "name": name, "tableName": table_name}


def measure_rename(model: Any, table_name: str, old_name: str, new_name: str) -> dict[str, Any]:
    """Rename a measure."""
    table = _get_table(model, table_name)
    m = _get_measure(table, old_name)
    m.Name = new_name
    model.SaveChanges()
    return {"status": "renamed", "oldName": old_name, "newName": new_name}


def measure_move(model: Any, table_name: str, name: str, dest_table_name: str) -> dict[str, Any]:
    """Move a measure to a different table."""
    src_table = _get_table(model, table_name)
    dest_table = _get_table(model, dest_table_name)
    m = _get_measure(src_table, name)

    # Store properties, remove from source, recreate in dest
    expr = _safe_str(m.Expression)
    fmt = _safe_str(m.FormatString)
    desc = _safe_str(m.Description)
    folder = _safe_str(m.DisplayFolder)
    hidden = bool(m.IsHidden)

    src_table.Measures.Remove(m)

    from pbi_cli.core.dotnet_loader import get_tom_classes

    (Measure,) = get_tom_classes("Measure")
    new_m = Measure()
    new_m.Name = name
    new_m.Expression = expr
    if fmt:
        new_m.FormatString = fmt
    if desc:
        new_m.Description = desc
    if folder:
        new_m.DisplayFolder = folder
    if hidden:
        new_m.IsHidden = True
    dest_table.Measures.Add(new_m)
    model.SaveChanges()
    return {
        "status": "moved",
        "name": name,
        "fromTable": table_name,
        "toTable": dest_table_name,
    }


# ---------------------------------------------------------------------------
# Relationship operations
# ---------------------------------------------------------------------------


def relationship_list(model: Any) -> list[dict[str, Any]]:
    """List all relationships."""
    results: list[dict[str, Any]] = []
    for rel in model.Relationships:
        results.append(_relationship_to_dict(rel))
    return results


def relationship_get(model: Any, name: str) -> dict[str, Any]:
    """Get a specific relationship by name."""
    rel = _get_relationship(model, name)
    return _relationship_to_dict(rel)


def relationship_find(model: Any, table_name: str) -> list[dict[str, Any]]:
    """Find all relationships involving a table."""
    results: list[dict[str, Any]] = []
    for rel in model.Relationships:
        from_table = _safe_str(rel.FromTable.Name)
        to_table = _safe_str(rel.ToTable.Name)
        if from_table == table_name or to_table == table_name:
            results.append(_relationship_to_dict(rel))
    return results


def relationship_create(
    model: Any,
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
    name: str | None = None,
    cross_filter: str = "OneDirection",
    is_active: bool = True,
) -> dict[str, Any]:
    """Create a new relationship between two tables."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    Relationship, CrossFilteringBehavior = get_tom_classes(
        "SingleColumnRelationship", "CrossFilteringBehavior"
    )

    ft = _get_table(model, from_table)
    fc = _get_column(ft, from_column)
    tt = _get_table(model, to_table)
    tc = _get_column(tt, to_column)

    rel = Relationship()
    if name:
        rel.Name = name
    rel.FromColumn = fc
    rel.ToColumn = tc
    rel.IsActive = is_active

    cf_map = {
        "OneDirection": CrossFilteringBehavior.OneDirection,
        "BothDirections": CrossFilteringBehavior.BothDirections,
        "Automatic": CrossFilteringBehavior.Automatic,
    }
    if cross_filter in cf_map:
        rel.CrossFilteringBehavior = cf_map[cross_filter]

    model.Relationships.Add(rel)
    model.SaveChanges()
    return {"status": "created", "name": str(rel.Name)}


def relationship_delete(model: Any, name: str) -> dict[str, Any]:
    """Delete a relationship by name."""
    rel = _get_relationship(model, name)
    model.Relationships.Remove(rel)
    model.SaveChanges()
    return {"status": "deleted", "name": name}


def relationship_set_active(model: Any, name: str, active: bool) -> dict[str, Any]:
    """Activate or deactivate a relationship."""
    rel = _get_relationship(model, name)
    rel.IsActive = active
    model.SaveChanges()
    state = "activated" if active else "deactivated"
    return {"status": state, "name": name}


def _relationship_to_dict(rel: Any) -> dict[str, Any]:
    """Convert a TOM Relationship to a plain dict."""
    return {
        "name": str(rel.Name),
        "fromTable": _safe_str(rel.FromTable.Name),
        "fromColumn": _safe_str(rel.FromColumn.Name),
        "toTable": _safe_str(rel.ToTable.Name),
        "toColumn": _safe_str(rel.ToColumn.Name),
        "crossFilteringBehavior": str(rel.CrossFilteringBehavior),
        "isActive": bool(rel.IsActive),
    }


# ---------------------------------------------------------------------------
# Partition operations
# ---------------------------------------------------------------------------


def partition_list(model: Any, table_name: str) -> list[dict[str, Any]]:
    """List partitions in a table."""
    table = _get_table(model, table_name)
    results: list[dict[str, Any]] = []
    for p in table.Partitions:
        results.append(
            {
                "name": str(p.Name),
                "tableName": str(table.Name),
                "mode": _safe_str(p.Mode),
                "sourceType": _safe_str(p.SourceType),
                "state": _safe_str(p.State),
            }
        )
    return results


def _get_partition(table: Any, partition_name: str) -> Any:
    """Get a partition by name."""
    for p in table.Partitions:
        if p.Name == partition_name:
            return p
    raise ValueError(f"Partition '{partition_name}' not found in table '{table.Name}'")


def partition_create(
    model: Any,
    table_name: str,
    name: str,
    expression: str | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    """Create a partition."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    Partition, MPartitionSource, ModeType = get_tom_classes(
        "Partition", "MPartitionSource", "ModeType"
    )

    table = _get_table(model, table_name)
    p = Partition()
    p.Name = name

    if expression is not None:
        src = MPartitionSource()
        src.Expression = expression
        p.Source = src

    if mode is not None:
        mode_map = {
            "Import": ModeType.Import,
            "DirectQuery": ModeType.DirectQuery,
            "Dual": ModeType.Dual,
        }
        if mode in mode_map:
            p.Mode = mode_map[mode]

    table.Partitions.Add(p)
    model.SaveChanges()
    return {"status": "created", "name": name, "tableName": table_name}


def partition_delete(model: Any, table_name: str, name: str) -> dict[str, Any]:
    """Delete a partition."""
    table = _get_table(model, table_name)
    p = _get_partition(table, name)
    table.Partitions.Remove(p)
    model.SaveChanges()
    return {"status": "deleted", "name": name, "tableName": table_name}


def partition_refresh(model: Any, table_name: str, name: str) -> dict[str, Any]:
    """Refresh a partition."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    (RefreshType,) = get_tom_classes("RefreshType")

    table = _get_table(model, table_name)
    p = _get_partition(table, name)
    p.RequestRefresh(RefreshType.Full)
    model.SaveChanges()
    return {"status": "refreshed", "name": name, "tableName": table_name}


# ---------------------------------------------------------------------------
# Security role operations
# ---------------------------------------------------------------------------


def role_list(model: Any) -> list[dict[str, Any]]:
    """List all security roles."""
    results: list[dict[str, Any]] = []
    for role in model.Roles:
        results.append(
            {
                "name": str(role.Name),
                "description": _safe_str(role.Description),
                "modelPermission": str(role.ModelPermission),
            }
        )
    return results


def _get_role(model: Any, name: str) -> Any:
    """Get a role by name."""
    for role in model.Roles:
        if role.Name == name:
            return role
    raise ValueError(f"Role '{name}' not found")


def role_get(model: Any, name: str) -> dict[str, Any]:
    """Get details of a security role."""
    role = _get_role(model, name)
    filters: list[dict[str, str]] = []
    for tp in role.TablePermissions:
        filters.append(
            {
                "tableName": str(tp.Table.Name),
                "filterExpression": _safe_str(tp.FilterExpression),
            }
        )
    return {
        "name": str(role.Name),
        "description": _safe_str(role.Description),
        "modelPermission": str(role.ModelPermission),
        "tablePermissions": filters,
    }


def role_create(model: Any, name: str, description: str | None = None) -> dict[str, Any]:
    """Create a security role."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    ModelRole, ModelPermission = get_tom_classes("ModelRole", "ModelPermission")
    role = ModelRole()
    role.Name = name
    role.ModelPermission = ModelPermission.Read
    if description is not None:
        role.Description = description
    model.Roles.Add(role)
    model.SaveChanges()
    return {"status": "created", "name": name}


def role_delete(model: Any, name: str) -> dict[str, Any]:
    """Delete a security role."""
    role = _get_role(model, name)
    model.Roles.Remove(role)
    model.SaveChanges()
    return {"status": "deleted", "name": name}


# ---------------------------------------------------------------------------
# Perspective operations
# ---------------------------------------------------------------------------


def perspective_list(model: Any) -> list[dict[str, Any]]:
    """List all perspectives."""
    results: list[dict[str, Any]] = []
    for p in model.Perspectives:
        results.append(
            {
                "name": str(p.Name),
                "description": _safe_str(p.Description),
            }
        )
    return results


def perspective_create(model: Any, name: str, description: str | None = None) -> dict[str, Any]:
    """Create a perspective."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    (Perspective,) = get_tom_classes("Perspective")
    p = Perspective()
    p.Name = name
    if description is not None:
        p.Description = description
    model.Perspectives.Add(p)
    model.SaveChanges()
    return {"status": "created", "name": name}


def _get_perspective(model: Any, name: str) -> Any:
    """Get a perspective by name."""
    for p in model.Perspectives:
        if p.Name == name:
            return p
    raise ValueError(f"Perspective '{name}' not found")


def perspective_delete(model: Any, name: str) -> dict[str, Any]:
    """Delete a perspective."""
    p = _get_perspective(model, name)
    model.Perspectives.Remove(p)
    model.SaveChanges()
    return {"status": "deleted", "name": name}


# ---------------------------------------------------------------------------
# Hierarchy operations
# ---------------------------------------------------------------------------


def hierarchy_list(model: Any, table_name: str | None = None) -> list[dict[str, Any]]:
    """List hierarchies, optionally filtered by table."""
    results: list[dict[str, Any]] = []
    for table in model.Tables:
        if table_name and str(table.Name) != table_name:
            continue
        for h in table.Hierarchies:
            levels = [str(lv.Name) for lv in h.Levels]
            results.append(
                {
                    "name": str(h.Name),
                    "tableName": str(table.Name),
                    "description": _safe_str(h.Description),
                    "levels": levels,
                }
            )
    return results


def _get_hierarchy(table: Any, name: str) -> Any:
    """Get a hierarchy by name."""
    for h in table.Hierarchies:
        if h.Name == name:
            return h
    raise ValueError(f"Hierarchy '{name}' not found in table '{table.Name}'")


def hierarchy_get(model: Any, table_name: str, name: str) -> dict[str, Any]:
    """Get hierarchy details."""
    table = _get_table(model, table_name)
    h = _get_hierarchy(table, name)
    levels = []
    for lv in h.Levels:
        levels.append(
            {
                "name": str(lv.Name),
                "ordinal": int(lv.Ordinal),
                "column": _safe_str(lv.Column.Name) if lv.Column else "",
            }
        )
    return {
        "name": str(h.Name),
        "tableName": table_name,
        "description": _safe_str(h.Description),
        "levels": levels,
    }


def hierarchy_create(
    model: Any,
    table_name: str,
    name: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Create a hierarchy (levels added separately)."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    (Hierarchy,) = get_tom_classes("Hierarchy")
    table = _get_table(model, table_name)
    h = Hierarchy()
    h.Name = name
    if description is not None:
        h.Description = description
    table.Hierarchies.Add(h)
    model.SaveChanges()
    return {"status": "created", "name": name, "tableName": table_name}


def hierarchy_delete(model: Any, table_name: str, name: str) -> dict[str, Any]:
    """Delete a hierarchy."""
    table = _get_table(model, table_name)
    h = _get_hierarchy(table, name)
    table.Hierarchies.Remove(h)
    model.SaveChanges()
    return {"status": "deleted", "name": name, "tableName": table_name}


# ---------------------------------------------------------------------------
# Calculation group operations
# ---------------------------------------------------------------------------


def calc_group_list(model: Any) -> list[dict[str, Any]]:
    """List calculation groups (tables with CalculationGroup set)."""
    results: list[dict[str, Any]] = []
    for table in model.Tables:
        cg = table.CalculationGroup
        if cg is not None:
            items = [str(ci.Name) for ci in cg.CalculationItems]
            results.append(
                {
                    "name": str(table.Name),
                    "description": _safe_str(table.Description),
                    "precedence": int(cg.Precedence),
                    "items": items,
                }
            )
    return results


def calc_group_create(
    model: Any,
    name: str,
    description: str | None = None,
    precedence: int | None = None,
) -> dict[str, Any]:
    """Create a calculation group table."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    Table, Partition, CalculationGroup, DataColumn, DataType = get_tom_classes(
        "Table", "Partition", "CalculationGroup", "DataColumn", "DataType"
    )

    t = Table()
    t.Name = name
    if description is not None:
        t.Description = description

    cg = CalculationGroup()
    if precedence is not None:
        cg.Precedence = precedence
    t.CalculationGroup = cg

    # CG tables require a "Name" column of type String
    col = DataColumn()
    col.Name = "Name"
    col.DataType = DataType.String
    col.SourceColumn = "Name"
    t.Columns.Add(col)

    p = Partition()
    p.Name = name
    t.Partitions.Add(p)

    model.Tables.Add(t)
    model.SaveChanges()
    return {"status": "created", "name": name}


def calc_group_delete(model: Any, name: str) -> dict[str, Any]:
    """Delete a calculation group table."""
    table = _get_table(model, name)
    if table.CalculationGroup is None:
        raise ValueError(f"Table '{name}' is not a calculation group")
    model.Tables.Remove(table)
    model.SaveChanges()
    return {"status": "deleted", "name": name}


def calc_item_list(model: Any, group_name: str) -> list[dict[str, Any]]:
    """List calculation items in a group."""
    table = _get_table(model, group_name)
    cg = table.CalculationGroup
    if cg is None:
        raise ValueError(f"Table '{group_name}' is not a calculation group")
    results: list[dict[str, Any]] = []
    for ci in cg.CalculationItems:
        results.append(
            {
                "name": str(ci.Name),
                "expression": _safe_str(ci.Expression),
                "ordinal": int(ci.Ordinal),
            }
        )
    return results


def calc_item_create(
    model: Any,
    group_name: str,
    name: str,
    expression: str,
    ordinal: int | None = None,
) -> dict[str, Any]:
    """Create a calculation item in a group."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    (CalculationItem,) = get_tom_classes("CalculationItem")

    table = _get_table(model, group_name)
    cg = table.CalculationGroup
    if cg is None:
        raise ValueError(f"Table '{group_name}' is not a calculation group")

    ci = CalculationItem()
    ci.Name = name
    ci.Expression = expression
    if ordinal is not None:
        ci.Ordinal = ordinal
    cg.CalculationItems.Add(ci)
    model.SaveChanges()
    return {"status": "created", "name": name, "groupName": group_name}


# ---------------------------------------------------------------------------
# Named expression operations
# ---------------------------------------------------------------------------


def expression_list(model: Any) -> list[dict[str, Any]]:
    """List all named expressions (shared expressions / parameters)."""
    results: list[dict[str, Any]] = []
    for expr in model.Expressions:
        results.append(
            {
                "name": str(expr.Name),
                "kind": _safe_str(expr.Kind),
                "expression": _safe_str(expr.Expression),
                "description": _safe_str(expr.Description),
            }
        )
    return results


def _get_expression(model: Any, name: str) -> Any:
    """Get a named expression by name."""
    for expr in model.Expressions:
        if expr.Name == name:
            return expr
    raise ValueError(f"Expression '{name}' not found")


def expression_get(model: Any, name: str) -> dict[str, Any]:
    """Get a named expression."""
    expr = _get_expression(model, name)
    return {
        "name": str(expr.Name),
        "kind": _safe_str(expr.Kind),
        "expression": _safe_str(expr.Expression),
        "description": _safe_str(expr.Description),
    }


def expression_create(
    model: Any,
    name: str,
    expression: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Create a named expression."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    NamedExpression, ExpressionKind = get_tom_classes("NamedExpression", "ExpressionKind")
    e = NamedExpression()
    e.Name = name
    e.Kind = ExpressionKind.M
    e.Expression = expression
    if description is not None:
        e.Description = description
    model.Expressions.Add(e)
    model.SaveChanges()
    return {"status": "created", "name": name}


def expression_delete(model: Any, name: str) -> dict[str, Any]:
    """Delete a named expression."""
    expr = _get_expression(model, name)
    model.Expressions.Remove(expr)
    model.SaveChanges()
    return {"status": "deleted", "name": name}


# ---------------------------------------------------------------------------
# Culture operations
# ---------------------------------------------------------------------------


def culture_list(model: Any) -> list[dict[str, Any]]:
    """List all cultures."""
    results: list[dict[str, Any]] = []
    for c in model.Cultures:
        results.append({"name": str(c.Name)})
    return results


def culture_create(model: Any, name: str) -> dict[str, Any]:
    """Create a culture."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    (Culture,) = get_tom_classes("Culture")
    c = Culture()
    c.Name = name
    model.Cultures.Add(c)
    model.SaveChanges()
    return {"status": "created", "name": name}


def _get_culture(model: Any, name: str) -> Any:
    """Get a culture by name."""
    for c in model.Cultures:
        if c.Name == name:
            return c
    raise ValueError(f"Culture '{name}' not found")


def culture_delete(model: Any, name: str) -> dict[str, Any]:
    """Delete a culture."""
    c = _get_culture(model, name)
    model.Cultures.Remove(c)
    model.SaveChanges()
    return {"status": "deleted", "name": name}


# ---------------------------------------------------------------------------
# Database operations (TMDL / TMSL / list)
# ---------------------------------------------------------------------------


def database_list(server: Any) -> list[dict[str, Any]]:
    """List all databases on the server."""
    results: list[dict[str, Any]] = []
    for db in server.Databases:
        results.append(
            {
                "name": str(db.Name),
                "id": str(db.ID),
                "compatibilityLevel": int(db.CompatibilityLevel),
                "lastUpdated": str(db.LastUpdate),
            }
        )
    return results


def export_tmdl(database: Any, folder_path: str) -> dict[str, str]:
    """Export a database to a TMDL folder."""
    from pbi_cli.core.dotnet_loader import get_tmdl_serializer

    TmdlSerializer = get_tmdl_serializer()
    TmdlSerializer.SerializeDatabaseToFolder(database, folder_path)
    return {"status": "exported", "path": folder_path}


def import_tmdl(server: Any, folder_path: str) -> dict[str, str]:
    """Import a model from a TMDL folder into the first database."""
    from pbi_cli.core.dotnet_loader import get_tmdl_serializer

    TmdlSerializer = get_tmdl_serializer()
    db = TmdlSerializer.DeserializeDatabaseFromFolder(folder_path)
    # Apply to the existing database
    target = server.Databases[0]
    target.Model.CopyFrom(db.Model)
    target.Model.SaveChanges()
    return {"status": "imported", "path": folder_path}


def export_tmsl(database: Any) -> dict[str, str]:
    """Export the database as a TMSL (JSON) script."""
    from pbi_cli.core.dotnet_loader import get_tom_classes

    (JsonSerializer,) = get_tom_classes("JsonSerializer")
    script = JsonSerializer.SerializeDatabase(database)
    return {"tmsl": str(script)}


# ---------------------------------------------------------------------------
# Trace operations
# ---------------------------------------------------------------------------


_active_trace: Any = None
_trace_events: list[dict[str, Any]] = []


def trace_start(server: Any) -> dict[str, str]:
    """Start a diagnostic trace on the server."""
    global _active_trace, _trace_events

    if _active_trace is not None:
        raise ValueError("A trace is already active. Stop it first.")

    _trace_events = []

    trace = server.Traces.Add()
    trace.Name = "pbi-cli-trace"
    trace.AutoRestart = True
    trace.Update()
    trace.Start()
    _active_trace = trace
    return {"status": "started", "traceId": str(trace.ID)}


def trace_stop() -> dict[str, str]:
    """Stop the active trace."""
    global _active_trace

    if _active_trace is None:
        raise ValueError("No active trace to stop.")

    _active_trace.Stop()
    _active_trace.Drop()
    _active_trace = None
    return {"status": "stopped"}


def trace_fetch() -> list[dict[str, Any]]:
    """Fetch collected trace events."""
    return list(_trace_events)


def trace_export(path: str) -> dict[str, Any]:
    """Export trace events to a JSON file."""
    import json

    with open(path, "w", encoding="utf-8") as f:
        json.dump(_trace_events, f, indent=2, default=str)
    return {"status": "exported", "path": path, "eventCount": len(_trace_events)}


# ---------------------------------------------------------------------------
# Transaction operations
# ---------------------------------------------------------------------------


def transaction_begin(server: Any) -> dict[str, str]:
    """Begin an explicit transaction."""
    tx_id = server.BeginTransaction()
    return {"status": "begun", "transactionId": str(tx_id)}


def transaction_commit(server: Any, transaction_id: str = "") -> dict[str, str]:
    """Commit the active or specified transaction."""
    if transaction_id:
        server.CommitTransaction(transaction_id)
    else:
        server.CommitTransaction()
    return {"status": "committed", "transactionId": transaction_id}


def transaction_rollback(server: Any, transaction_id: str = "") -> dict[str, str]:
    """Rollback the active or specified transaction."""
    if transaction_id:
        server.RollbackTransaction(transaction_id)
    else:
        server.RollbackTransaction()
    return {"status": "rolled_back", "transactionId": transaction_id}
