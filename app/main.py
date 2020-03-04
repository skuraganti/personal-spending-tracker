"""Loopback-only historical statement review API and local browser workspace."""
from contextlib import asynccontextmanager
import datetime as dt
from pathlib import Path
import re
import sqlite3

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import analysis
from .config import get_settings
from .db import connect, initialize, reclassify, rules
from .imports import ImportFailure, import_statement


class BodyLimit:
    """Bound request bytes before the multipart parser can spool files to disk."""
    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        chunks, length = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            length += len(chunk)
            if length > self.limit:
                return await JSONResponse({"detail": "Request body exceeds local limit"}, status_code=413)(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body"):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()
        await self.app(scope, bounded_receive, send)


def month_value(value):
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError("Month must be YYYY-MM")
    dt.date.fromisoformat(value+"-01")
    return value


class RuleInput(BaseModel):
    pattern: str = Field(default="", max_length=100)
    transaction_type: str = Field(default="", max_length=20)
    category: str = Field(min_length=1, max_length=50)
    priority: int = Field(default=100, ge=-10000, le=10000, strict=True)

    @field_validator("pattern", "transaction_type", "category")
    @classmethod
    def clean(cls, value):
        if "\x00" in value:
            raise ValueError("Null characters are not allowed")
        return value.strip()

    @model_validator(mode="after")
    def meaningful(self):
        if not self.category or not (self.pattern or self.transaction_type):
            raise ValueError("A category and a description or type condition are required")
        self.transaction_type = self.transaction_type.upper()
        return self


class BudgetInput(BaseModel):
    month: str
    category: str = Field(min_length=1, max_length=50)
    limit_pence: int = Field(ge=0, le=10**14, strict=True)
    threshold_percent: int = Field(default=80, ge=1, le=100, strict=True)

    @field_validator("month")
    @classmethod
    def valid_month(cls, value):
        return month_value(value)

    @field_validator("category")
    @classmethod
    def category_value(cls, value):
        if not value.strip() or "\x00" in value:
            raise ValueError("Category is required")
        return value.strip()


class OverrideInput(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=50)


def create_app(settings=None):
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application):
        initialize(settings.db_path)
        yield

    app = FastAPI(title="Ledger · local historical statement review", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(BodyLimit, limit=settings.max_import_bytes+65536)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("sec-fetch-site") == "cross-site" or (origin is not None and origin != str(request.base_url).rstrip("/")):
                return JSONResponse({"detail": "Same-origin local requests required"}, status_code=403)
        response = await call_next(request)
        response.headers.update({"Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
                                 "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})
        return response

    @app.exception_handler(ImportFailure)
    async def import_error(request, error):
        return JSONResponse({"detail": str(error), "diagnostics": error.diagnostics}, status_code=400)

    @app.exception_handler(sqlite3.IntegrityError)
    async def constraint_error(request, error):
        return JSONResponse({"detail": "This change conflicts with existing local state"}, status_code=409)

    def selected_month(db, month):
        if month:
            try:
                return month_value(month)
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
        row = db.execute("SELECT max(substr(date,1,7)) FROM transactions").fetchone()
        return row[0] or dt.date.today().isoformat()[:7]

    @app.get("/health")
    def health():
        with connect(settings.db_path) as db:
            count = db.execute("SELECT count(*) FROM transactions").fetchone()[0]
        return {"status": "ok", "transactions": count, "currency": "GBP", "currency_assumption": True}

    @app.get("/api/meta")
    def meta():
        with connect(settings.db_path) as db:
            categories = {r[0] for r in db.execute("SELECT category FROM rules UNION SELECT category FROM transactions")}
            categories.update({"Groceries", "Shopping", "Utilities", "Housing", "Transport", "Dining", "Fees", "Income", "Savings", "Transfers", "Other"})
            dates = db.execute("SELECT min(date),max(date),count(*) FROM transactions").fetchone()
        return {"categories": sorted(categories), "source": "MoneyVis · author-described historical bank transactions",
                "first_date": dates[0], "last_date": dates[1], "rows": dates[2], "max_import_bytes": settings.max_import_bytes,
                "currency": "GBP", "currency_assumption": True, "live": False}

    @app.get("/api/months")
    def months():
        with connect(settings.db_path) as db:
            return [r[0] for r in db.execute("SELECT DISTINCT substr(date,1,7) month FROM transactions ORDER BY month DESC")]

    @app.get("/api/summary")
    def get_summary(month: str | None = None):
        with connect(settings.db_path) as db:
            return analysis.summary(db, selected_month(db, month))

    @app.get("/api/imports")
    def get_imports():
        with connect(settings.db_path) as db:
            return [dict(r) for r in db.execute("SELECT * FROM imports ORDER BY created_at DESC")]

    @app.post("/api/imports")
    async def upload(file: UploadFile = File(...)):
        data = await file.read(settings.max_import_bytes+1)
        await file.close()
        return import_statement(data, file.filename or "statement.csv", settings)

    @app.get("/api/transactions")
    def transactions(month: str | None = None, search: str = Query(default="", max_length=100), category: str = Query(default="", max_length=50),
                     page: int = Query(default=1, ge=1, le=100000), page_size: int = Query(default=25, ge=1, le=100)):
        where, values = [], []
        if month:
            try:
                month_value(month)
            except ValueError as error:
                raise HTTPException(422, str(error)) from error
            where.append("substr(date,1,7)=?")
            values.append(month)
        if search:
            where.append("description LIKE ? ESCAPE '\\'")
            values.append("%"+search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")+"%")
        if category:
            where.append("category=?")
            values.append(category)
        clause = " WHERE "+" AND ".join(where) if where else ""
        with connect(settings.db_path) as db:
            total = db.execute("SELECT count(*) FROM transactions"+clause, values).fetchone()[0]
            rows = [dict(r) for r in db.execute("SELECT * FROM transactions"+clause+" ORDER BY date DESC,id DESC LIMIT ? OFFSET ?", [*values, page_size, (page-1)*page_size])]
        return {"items": rows, "total": total, "page": page, "page_size": page_size}

    @app.patch("/api/transactions/{transaction_id}")
    def override(transaction_id: int, change: OverrideInput):
        category = change.category.strip() if change.category is not None else None
        if category is not None and (not category or "\x00" in category):
            raise HTTPException(422, "Invalid category")
        with connect(settings.db_path) as db:
            if not db.execute("SELECT 1 FROM transactions WHERE id=?", (transaction_id,)).fetchone():
                raise HTTPException(404, "Transaction not found")
            db.execute("UPDATE transactions SET override_category=? WHERE id=?", (category, transaction_id))
            reclassify(db)
            return dict(db.execute("SELECT * FROM transactions WHERE id=?", (transaction_id,)).fetchone())

    @app.get("/api/rules")
    def get_rules():
        with connect(settings.db_path) as db:
            return rules(db)

    @app.post("/api/rules")
    def create_rule(rule: RuleInput):
        with connect(settings.db_path) as db:
            cursor = db.execute("INSERT INTO rules(priority,pattern,transaction_type,category) VALUES(?,?,?,?)", (rule.priority, rule.pattern, rule.transaction_type, rule.category))
            updated = reclassify(db)
            return {"id": cursor.lastrowid, "reclassified": updated, **rule.model_dump()}

    @app.put("/api/rules/{rule_id}")
    def update_rule(rule_id: int, rule: RuleInput):
        with connect(settings.db_path) as db:
            cursor = db.execute("UPDATE rules SET priority=?,pattern=?,transaction_type=?,category=? WHERE id=?", (rule.priority, rule.pattern, rule.transaction_type, rule.category, rule_id))
            if not cursor.rowcount:
                raise HTTPException(404, "Rule not found")
            return {"id": rule_id, "reclassified": reclassify(db), **rule.model_dump()}

    @app.delete("/api/rules/{rule_id}")
    def delete_rule(rule_id: int):
        with connect(settings.db_path) as db:
            if not db.execute("DELETE FROM rules WHERE id=?", (rule_id,)).rowcount:
                raise HTTPException(404, "Rule not found")
            return {"deleted": rule_id, "reclassified": reclassify(db)}

    @app.get("/api/budgets")
    def budgets(month: str | None = None):
        with connect(settings.db_path) as db:
            return analysis.budget_status(db, selected_month(db, month))

    @app.post("/api/budgets")
    def save_budget(budget: BudgetInput):
        with connect(settings.db_path) as db:
            db.execute("""INSERT INTO budgets(month,category,limit_pence,threshold_percent) VALUES(?,?,?,?)
                       ON CONFLICT(month,category) DO UPDATE SET limit_pence=excluded.limit_pence,threshold_percent=excluded.threshold_percent""",
                       (budget.month, budget.category, budget.limit_pence, budget.threshold_percent))
        return budget.model_dump()

    @app.delete("/api/budgets/{budget_id}")
    def delete_budget(budget_id: int):
        with connect(settings.db_path) as db:
            if not db.execute("DELETE FROM budgets WHERE id=?", (budget_id,)).rowcount:
                raise HTTPException(404, "Budget not found")
        return {"deleted": budget_id}

    @app.get("/api/alerts")
    def alerts(month: str | None = None):
        with connect(settings.db_path) as db:
            return [b for b in analysis.budget_status(db, selected_month(db, month)) if b["alert"]]

    @app.get("/api/recurring")
    def recurring():
        with connect(settings.db_path) as db:
            return analysis.recurring(db)

    static = Path(__file__).parent / "static"
    if static.is_dir():
        app.mount("/static", StaticFiles(directory=static), name="static")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(static / "index.html")
    return app


app = create_app()
