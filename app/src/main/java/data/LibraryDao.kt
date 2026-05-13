package com.ebenezer.biblioteca.data

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface LibraryDao {
    // Obtener todos los libros
    @Query("SELECT * FROM libros ORDER BY titulo")
    fun getAllBooks(): Flow<List<LibroEntity>>

    // Obtener párrafos de un libro (paginado con Paging 3 se haría desde un PagingSource, aquí solo Flow)
    @Query("SELECT * FROM parrafos WHERE libro_id = :bookId ORDER BY numero_parrafo")
    fun getParagraphsByBook(bookId: Long): Flow<List<ParrafoEntity>>

    // Búsqueda FTS5 con snippet resaltado
    @Query("""
        SELECT parrafos.id, parrafos.libro_id, parrafos.numero_parrafo,
               snippet(parrafos_fts, 0, '<b>', '</b>', '...', 32) AS snippet,
               libros.titulo
        FROM parrafos_fts
        JOIN parrafos ON parrafos_fts.rowid = parrafos.id
        JOIN libros ON parrafos.libro_id = libros.id
        WHERE parrafos_fts MATCH :query
        ORDER BY rank
    """)
    fun search(query: String): Flow<List<SearchResult>>
}

// Clase para el resultado de búsqueda
data class SearchResult(
    val id: Long,
    val libro_id: Long,
    val numero_parrafo: Int,
    val snippet: String,
    val titulo: String
)