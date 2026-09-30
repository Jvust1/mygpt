package dev.mygpt.companionv2

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import dev.mygpt.spike.LexicalMemoryScorer
import java.util.UUID

/**
 * Explicit local long-term memory for the Android companion.
 *
 * The add/get/search/update/delete/history lifecycle is adapted from Mem0's
 * Apache-2.0 memory interface and audit-history model. Chat turns are never
 * inserted automatically.
 */
class LocalCompanionMemoryStore(context: Context) :
    SQLiteOpenHelper(context.applicationContext, DB_NAME, null, DB_VERSION),
    AutoCloseable {

    data class Memory(
        val memoryId: String,
        val namespace: String,
        val kind: String,
        val text: String,
        val source: String,
        val createdAtMs: Long,
        val updatedAtMs: Long,
    )

    data class HistoryEvent(
        val historyId: Long,
        val memoryId: String,
        val previousValue: String?,
        val newValue: String?,
        val action: String,
        val createdAtMs: Long,
        val deleted: Boolean,
    )

    init {
        setWriteAheadLoggingEnabled(true)
    }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE memories(
                memory_id TEXT PRIMARY KEY,
                namespace TEXT NOT NULL,
                kind TEXT NOT NULL,
                text TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL
            )
            """.trimIndent()
        )
        db.execSQL(
            """
            CREATE INDEX idx_memories_namespace_updated
            ON memories(namespace, updated_at_ms DESC)
            """.trimIndent()
        )
        db.execSQL(
            """
            CREATE TABLE memory_history(
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT NOT NULL,
                previous_value TEXT,
                new_value TEXT,
                action TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL,
                is_deleted INTEGER NOT NULL DEFAULT 0
            )
            """.trimIndent()
        )
        db.execSQL(
            """
            CREATE INDEX idx_memory_history_id
            ON memory_history(memory_id, history_id DESC)
            """.trimIndent()
        )
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        throw IllegalStateException(
            "unsupported companion memory schema migration: " + oldVersion + " -> " + newVersion
        )
    }

    fun addExplicit(
        namespace: String,
        text: String,
        kind: String = "user_instruction",
        nowMs: Long = System.currentTimeMillis(),
    ): Memory {
        validateNamespace(namespace)
        val normalized = validateText(text)
        require(kind in ALLOWED_KINDS) { "unsupported memory kind" }
        require(nowMs >= 0L) { "invalid memory time" }

        val memory = Memory(
            memoryId = "mem-" + UUID.randomUUID().toString().replace("-", "").take(24),
            namespace = namespace,
            kind = kind,
            text = normalized,
            source = "user_explicit",
            createdAtMs = nowMs,
            updatedAtMs = nowMs,
        )

        val db = writableDatabase
        db.beginTransaction()
        try {
            db.insertOrThrow("memories", null, memoryValues(memory))
            addHistory(
                db = db,
                memoryId = memory.memoryId,
                previousValue = null,
                newValue = memory.text,
                action = "ADD",
                atMs = nowMs,
                deleted = false,
            )
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        return memory
    }

    fun get(memoryId: String): Memory? {
        validateMemoryId(memoryId)
        readableDatabase.query(
            "memories",
            MEMORY_COLUMNS,
            "memory_id=?",
            arrayOf(memoryId),
            null,
            null,
            null,
            "1",
        ).use { cursor ->
            return if (cursor.moveToFirst()) memoryFrom(cursor) else null
        }
    }

    fun update(
        memoryId: String,
        replacementText: String,
        nowMs: Long = System.currentTimeMillis(),
    ): Memory {
        validateMemoryId(memoryId)
        val normalized = validateText(replacementText)
        val db = writableDatabase
        db.beginTransaction()
        try {
            val current = queryOne(db, memoryId)
                ?: throw IllegalArgumentException("memory not found")
            require(nowMs >= current.updatedAtMs) { "memory time cannot move backwards" }
            if (current.text == normalized) {
                db.setTransactionSuccessful()
                return current
            }

            val values = ContentValues().apply {
                put("text", normalized)
                put("updated_at_ms", nowMs)
            }
            val changed = db.update(
                "memories",
                values,
                "memory_id=?",
                arrayOf(memoryId),
            )
            if (changed != 1) error("memory update failed")
            addHistory(
                db, memoryId, current.text, normalized, "UPDATE", nowMs, false
            )
            val result = current.copy(text = normalized, updatedAtMs = nowMs)
            db.setTransactionSuccessful()
            return result
        } finally {
            db.endTransaction()
        }
    }

    /**
     * Delete active memory while preserving a local audit event.
     * Use purge() when the user explicitly asks to erase the content entirely.
     */
    fun delete(
        memoryId: String,
        nowMs: Long = System.currentTimeMillis(),
    ): Boolean {
        validateMemoryId(memoryId)
        val db = writableDatabase
        db.beginTransaction()
        try {
            val current = queryOne(db, memoryId) ?: run {
                db.setTransactionSuccessful()
                return false
            }
            require(nowMs >= current.updatedAtMs) { "memory time cannot move backwards" }
            addHistory(
                db, memoryId, current.text, null, "DELETE", nowMs, true
            )
            db.delete("memories", "memory_id=?", arrayOf(memoryId))
            db.setTransactionSuccessful()
            return true
        } finally {
            db.endTransaction()
        }
    }

    /**
     * Privacy erasure path: remove both active memory and its audit history.
     */
    fun purge(memoryId: String): Boolean {
        validateMemoryId(memoryId)
        val db = writableDatabase
        db.beginTransaction()
        try {
            val active = db.delete("memories", "memory_id=?", arrayOf(memoryId))
            val history = db.delete("memory_history", "memory_id=?", arrayOf(memoryId))
            db.setTransactionSuccessful()
            return active > 0 || history > 0
        } finally {
            db.endTransaction()
        }
    }

    fun recent(namespace: String, limit: Int = 8): List<Memory> {
        validateNamespace(namespace)
        require(limit in 1..100) { "limit must be in 1..100" }
        readableDatabase.query(
            "memories",
            MEMORY_COLUMNS,
            "namespace=?",
            arrayOf(namespace),
            null,
            null,
            "updated_at_ms DESC, memory_id ASC",
            limit.toString(),
        ).use { cursor ->
            val result = ArrayList<Memory>()
            while (cursor.moveToNext()) result += memoryFrom(cursor)
            return result
        }
    }

    fun search(namespace: String, query: String, limit: Int = 6): List<Memory> {
        validateNamespace(namespace)
        require(limit in 1..20) { "limit must be in 1..20" }
        if (query.length > 4000) throw IllegalArgumentException("memory query too long")

        // The real companion search uses the full query, not the first 16 tokens.
        // SQL remains namespace-scoped and bounded before any text is ranked.
        val candidates = recent(namespace, LexicalMemoryScorer.MAX_CANDIDATES)
        val scores = LexicalMemoryScorer.score(query, candidates.map { it.text })
        data class Ranked(val memory: Memory, val score: Double)
        return candidates.mapIndexed { index, memory -> Ranked(memory, scores[index]) }
            .filter { it.score > 0.0 }
            .sortedWith(
                compareByDescending<Ranked> { it.score }
                    .thenByDescending { it.memory.updatedAtMs }
                    .thenBy { it.memory.memoryId }
            )
            .take(limit)
            .map { it.memory }
    }

    fun history(memoryId: String, limit: Int = 100): List<HistoryEvent> {
        validateMemoryId(memoryId)
        require(limit in 1..100) { "limit must be in 1..100" }
        readableDatabase.query(
            "memory_history",
            arrayOf(
                "history_id",
                "memory_id",
                "previous_value",
                "new_value",
                "action",
                "created_at_ms",
                "is_deleted",
            ),
            "memory_id=?",
            arrayOf(memoryId),
            null,
            null,
            "history_id DESC",
            limit.toString(),
        ).use { cursor ->
            val result = ArrayList<HistoryEvent>()
            while (cursor.moveToNext()) {
                result += HistoryEvent(
                    historyId = cursor.getLong(0),
                    memoryId = cursor.getString(1),
                    previousValue = if (cursor.isNull(2)) null else cursor.getString(2),
                    newValue = if (cursor.isNull(3)) null else cursor.getString(3),
                    action = cursor.getString(4),
                    createdAtMs = cursor.getLong(5),
                    deleted = cursor.getInt(6) != 0,
                )
            }
            return result
        }
    }

    private fun queryOne(db: SQLiteDatabase, memoryId: String): Memory? {
        db.query(
            "memories",
            MEMORY_COLUMNS,
            "memory_id=?",
            arrayOf(memoryId),
            null,
            null,
            null,
            "1",
        ).use { cursor ->
            return if (cursor.moveToFirst()) memoryFrom(cursor) else null
        }
    }

    private fun memoryValues(memory: Memory) = ContentValues().apply {
        put("memory_id", memory.memoryId)
        put("namespace", memory.namespace)
        put("kind", memory.kind)
        put("text", memory.text)
        put("source", memory.source)
        put("created_at_ms", memory.createdAtMs)
        put("updated_at_ms", memory.updatedAtMs)
    }

    private fun addHistory(
        db: SQLiteDatabase,
        memoryId: String,
        previousValue: String?,
        newValue: String?,
        action: String,
        atMs: Long,
        deleted: Boolean,
    ) {
        db.insertOrThrow(
            "memory_history",
            null,
            ContentValues().apply {
                put("memory_id", memoryId)
                put("previous_value", previousValue)
                put("new_value", newValue)
                put("action", action)
                put("created_at_ms", atMs)
                put("is_deleted", if (deleted) 1 else 0)
            },
        )
    }

    private fun memoryFrom(cursor: Cursor): Memory =
        Memory(
            memoryId = cursor.getString(0),
            namespace = cursor.getString(1),
            kind = cursor.getString(2),
            text = cursor.getString(3),
            source = cursor.getString(4),
            createdAtMs = cursor.getLong(5),
            updatedAtMs = cursor.getLong(6),
        )

    private fun validateNamespace(value: String) {
        require(NAMESPACE.matches(value)) { "invalid memory namespace" }
    }

    private fun validateMemoryId(value: String) {
        require(MEMORY_ID.matches(value)) { "invalid memory id" }
    }

    private fun validateText(value: String): String {
        val normalized = value.trim()
        require(normalized.isNotEmpty()) { "memory text must not be blank" }
        require(normalized.length <= 1000) { "memory text too long" }
        require(normalized.none { it.code < 32 && it != '\n' && it != '\t' }) {
            "memory text contains control characters"
        }
        return normalized
    }

    companion object {
        private const val DB_NAME = "mygpt-companion-memory.sqlite3"
        private const val DB_VERSION = 1

        private val NAMESPACE =
            Regex("^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
        private val MEMORY_ID =
            Regex("^mem-[A-Za-z0-9]{8,48}$")
        private val ALLOWED_KINDS =
            setOf("preference", "fact", "study_pattern", "user_instruction", "companion_state")

        private val MEMORY_COLUMNS = arrayOf(
            "memory_id",
            "namespace",
            "kind",
            "text",
            "source",
            "created_at_ms",
            "updated_at_ms",
        )
    }
}
