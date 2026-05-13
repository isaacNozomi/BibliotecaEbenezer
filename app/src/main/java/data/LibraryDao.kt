package com.ebenezer.biblioteca.data

import androidx.room.*
import androidx.sqlite.db.SupportSQLiteQuery
import kotlinx.coroutines.flow.Flow

@Dao
interface LibraryDao {
    @Query("SELECT * FROM libros ORDER BY titulo")
    fun getAllBooks(): Flow<List<LibroEntity>>

    @Query("SELECT * FROM parrafos WHERE libro_id = :bookId ORDER BY numero_parrafo")
    fun getParagraphsByBook(bookId: Long): Flow<List<ParrafoEntity>>

    // Búsqueda FTS5 usando consulta cruda (sin verificación estática)
    @RawQuery(observedEntities = [ParrafoEntity::class, LibroEntity::class])
    fun searchRaw(query: SupportSQLiteQuery): Flow<List<SearchResult>>
}

// Clase para el resultado de búsqueda
data class SearchResult(
    val id: Long,
    val libro_id: Long,
    val numero_parrafo: Int,
    val snippet: String,
    val titulo: String
)