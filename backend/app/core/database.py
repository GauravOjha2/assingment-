"""
Database layer with in-memory storage that mimics MongoDB's async API.

Supports the MongoDB operators used by the application:
  - $set, $push (in update_one)
  - $in (in find / find_one queries)
  - Filtered delete_many
"""

from typing import Optional, Any, Dict, List
from datetime import datetime
from copy import deepcopy
from bson import ObjectId


def _match_query(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
    """Check whether a document matches a MongoDB-style query.

    Supports:
      - Exact equality: {"key": value}
      - ObjectId comparison by string: {"_id": ObjectId(...)}
      - $in operator: {"key": {"$in": [v1, v2, ...]}}
    """
    for key, value in query.items():
        doc_val = doc.get(key)

        # Handle operator dict (e.g. {"$in": [...]})
        if isinstance(value, dict):
            if "$in" in value:
                in_list = value["$in"]
                # Compare by string representation for ObjectId fields
                if key == "_id":
                    if not any(str(doc_val) == str(v) for v in in_list):
                        return False
                else:
                    if doc_val not in in_list:
                        return False
            # Future operators can be added here
            continue

        # Plain equality
        if key == "_id":
            if str(doc_val) != str(value):
                return False
        else:
            if doc_val != value:
                return False

    return True


class InMemoryCursor:
    """An async-iterable cursor that supports chained .sort() and .limit()."""

    def __init__(self, data: List[Dict]):
        self._data = list(data)

    def sort(self, key_or_list, direction=None):
        """Sort by a single key or a list of (key, direction) pairs."""
        if isinstance(key_or_list, list):
            # e.g. [("difficulty", 1), ("topic", 1)]
            for sort_key, sort_dir in reversed(key_or_list):
                reverse = sort_dir == -1
                self._data.sort(
                    key=lambda x: x.get(sort_key, 0) if not isinstance(x.get(sort_key), str) else x.get(sort_key, ""),
                    reverse=reverse,
                )
        else:
            reverse = direction == -1
            self._data.sort(
                key=lambda x: x.get(key_or_list, 0) if not isinstance(x.get(key_or_list), str) else x.get(key_or_list, ""),
                reverse=reverse,
            )
        return self

    def limit(self, n: int):
        self._data = self._data[:n]
        return self

    def __aiter__(self):
        self._iter_data = list(self._data)
        return self

    async def __anext__(self):
        if not self._iter_data:
            raise StopAsyncIteration
        return self._iter_data.pop(0)

    async def to_list(self, length=None):
        result = list(self._data)
        if length:
            result = result[:length]
        return result


class InMemoryCollection:
    """In-memory collection that faithfully mimics Motor's async MongoDB API."""

    def __init__(self):
        self._data: List[Dict[str, Any]] = []

    # ── Read ──────────────────────────────────────────────────────

    def find(self, query: Optional[Dict[str, Any]] = None, *args, **kwargs):
        """Return a cursor for documents matching *query*."""
        if query is None:
            query = {}
        filtered = [doc for doc in self._data if _match_query(doc, query)]
        return InMemoryCursor(filtered)

    async def find_one(self, query: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        """Return the first document matching *query*, or None."""
        if query is None:
            query = {}
        for doc in self._data:
            if _match_query(doc, query):
                return doc
        return None

    # ── Write ─────────────────────────────────────────────────────

    async def insert_one(self, doc: Dict[str, Any]) -> Any:
        doc = dict(doc)  # shallow copy to avoid mutating caller's dict
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        if "created_at" not in doc:
            doc["created_at"] = datetime.utcnow()
        self._data.append(doc)
        return InsertResult(doc["_id"])

    async def insert_many(self, docs: List[Dict[str, Any]]) -> Any:
        ids = []
        for doc in docs:
            result = await self.insert_one(doc)
            ids.append(result.inserted_id)
        return InsertResultMany(ids)

    # ── Update ────────────────────────────────────────────────────

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], **kwargs):
        """Apply $set and $push operators to the first matching document."""
        for doc in self._data:
            if _match_query(doc, query):
                # $set operator
                if "$set" in update:
                    for k, v in update["$set"].items():
                        doc[k] = v

                # $push operator
                if "$push" in update:
                    for k, v in update["$push"].items():
                        if k not in doc:
                            doc[k] = []
                        doc[k].append(v)

                # $inc operator (for future use)
                if "$inc" in update:
                    for k, v in update["$inc"].items():
                        doc[k] = doc.get(k, 0) + v

                return UpdateResult(True, 1)
        return UpdateResult(False, 0)

    # ── Delete ────────────────────────────────────────────────────

    async def delete_many(self, query: Dict[str, Any]):
        """Delete documents matching *query*. Empty query deletes all."""
        if not query:
            count = len(self._data)
            self._data.clear()
            return DeleteResult(count)

        to_remove = [doc for doc in self._data if _match_query(doc, query)]
        for doc in to_remove:
            self._data.remove(doc)
        return DeleteResult(len(to_remove))

    # ── Index (no-op) ─────────────────────────────────────────────

    async def create_index(self, *args, **kwargs):
        pass


class InsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class InsertResultMany:
    def __init__(self, inserted_ids):
        self.inserted_ids = inserted_ids


class UpdateResult:
    def __init__(self, acknowledged, modified_count):
        self.acknowledged = acknowledged
        self.modified_count = modified_count


class DeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class InMemoryDatabase:
    """A simple in-memory database that mimics MongoDB's API."""

    def __init__(self):
        self._collections: Dict[str, InMemoryCollection] = {}

    def __getitem__(self, name: str) -> InMemoryCollection:
        if name not in self._collections:
            self._collections[name] = InMemoryCollection()
        return self._collections[name]

    def __getattr__(self, name: str) -> InMemoryCollection:
        return self[name]


class Database:
    """Manages the database connection - uses in-memory storage."""

    db: Optional[InMemoryDatabase] = None

    async def connect(self) -> None:
        """Use in-memory storage for this session."""
        self.db = InMemoryDatabase()
        print("[DB] Using in-memory storage (no MongoDB required)")

    async def disconnect(self) -> None:
        """Nothing to disconnect for in-memory."""
        print("[DB] In-memory database closed")

    def get_collection(self, name: str):
        """Get a collection by name."""
        if self.db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.db[name]


# Singleton instance
database = Database()


async def get_database():
    """Dependency injection helper for FastAPI routes."""
    if database.db is None:
        raise RuntimeError("Database not initialized")
    return database.db
