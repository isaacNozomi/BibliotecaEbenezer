package com.ebenezer.biblioteca.data

import android.database.Cursor
import androidx.sqlite.db.SupportSQLiteDatabase
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow

class LibraryDao(private val db: SupportSQLiteDatabase) {

    fun getAllBooks(): Flow<List<LibroEntity>> = flow {
        val list = mutableListOf<LibroEntity>()
        db.query("SELECT * FROM libros ORDER BY titulo").use { cursor ->
            while (cursor.moveToNext()) {
                list.add(
                    LibroEntity(
                        id = cursor.getLong(0),
                        titulo = cursor.getString(1),
                        codigo = cursor.getString(2),
                        fecha = cursor.getString(3)
                    )
                )
            }
        }
        emit(list)
    }

    fun getParagraphsByBook(bookId: Long): Flow<List<ParrafoEntity>> = flow {
        val list = mutableListOf<ParrafoEntity>()
        db.query("SELECT * FROM parrafos WHERE libro_id = ? ORDER BY numero_parrafo", arrayOf(bookId)).use { cursor ->
            while (cursor.moveToNext()) {
                list.add(
                    ParrafoEntity(
                        id = cursor.getLong(0),
                        libro_id = cursor.getLong(1),
                        numero_parrafo = cursor.getInt(2),
                        contenido = cursor.getString(3)
                    )
                )
            }
        }
        emit(list)
    }

    fun search(query: String): Flow<List<SearchResult>> = flow {
        val list = mutableListOf<SearchResult>()
        db.query("""
            SELECT p.id, p.libro_id, p.numero_parrafo,
                   snippet(parrafos_fts, 0, '<b>', '</b>', '...', 32) AS snippet,
                   l.titulo
            FROM parrafos_fts
            JOIN parrafos p ON parrafos_fts.rowid = p.id
            JOIN libros l ON p.libro_id = l.id
            WHERE parrafos_fts MATCH ?
            ORDER BY rank
        """, arrayOf(query)).use { cursor ->
            while (cursor.moveToNext()) {
                list.add(
                    SearchResult(
                        id = cursor.getLong(0),
                        libro_id = cursor.getLong(1),
                        numero_parrafo = cursor.getInt(2),
                        snippet = cursor.getString(3),
                        titulo = cursor.getString(4)
                    )
                )
            }
        }
        emit(list)
    }
}

data class SearchResult(
    val id: Long,
    val libro_id: Long,
    val numero_parrafo: Int,
    val snippet: String,
    val titulo: String
)