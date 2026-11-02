"""Write the Mermaid ER diagram of the SQLAlchemy models to docs/database/erd.mmd and into the
mermaid block of docs/database/ERD.md (GitHub renders it as a picture).

Run from backend/:  PYTHONPATH=.:../scripts uv run python ../scripts/erd.py
"""

import re
from pathlib import Path

from erd_columns import DESCRIPTIONS

from app.core.db import Base
from app.models import ai, catalog, logistics, orders, settings  # noqa: F401  registers tables

OUT = Path(__file__).resolve().parents[1] / "docs" / "database" / "erd.mmd"


def col_type(c) -> str:
    try:
        name = c.type.python_type.__name__
    except NotImplementedError:
        name = "json"
    return {"UUID": "uuid", "Decimal": "numeric", "datetime": "timestamptz"}.get(name, name)


columns = {f"{t.name}.{c.name}" for t in Base.metadata.sorted_tables for c in t.columns}
if unknown := set(DESCRIPTIONS) - columns:
    raise SystemExit(f"erd_columns.py describes columns that don't exist: {sorted(unknown)}")

lines = ["erDiagram"]
for t in Base.metadata.sorted_tables:
    fks = {fk.parent.name for fk in t.foreign_keys}
    lines.append(f"  {t.name} {{")
    for c in t.columns:
        desc = DESCRIPTIONS.get(f"{t.name}.{c.name}")
        is_key = c.primary_key or c.name in fks
        if is_key and not desc:
            raise SystemExit(f"describe key column {t.name}.{c.name} in erd_columns.py")
        if not desc:
            continue  # shown only when described, to keep the picture readable
        keys = ",".join(k for k, on in (("PK", c.primary_key), ("FK", c.name in fks)) if on)
        lines.append(f'    {col_type(c)} {c.name}{" " + keys if keys else ""} "{desc}"')
    lines.append("  }")
for t in Base.metadata.sorted_tables:
    for fk in t.foreign_keys:
        c = fk.parent
        one_to_one = c.unique or (c.primary_key and len(t.primary_key.columns) == 1)
        parent = "||" if not c.nullable else "|o"
        child = "|o" if one_to_one else "o{"
        lines.append(f"  {fk.column.table.name} {parent}--{child} {t.name} : {c.name}")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines) + "\n")
doc = OUT.with_name("ERD.md")
if doc.exists():
    block = "```mermaid\n" + "\n".join(lines) + "\n```"
    doc.write_text(re.sub(r"```mermaid\n.*?\n```", lambda _m: block, doc.read_text(), flags=re.S))
print(f"wrote {OUT.relative_to(OUT.parents[2])} ({len(Base.metadata.tables)} tables)")
