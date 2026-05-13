package com.ebenezer.biblioteca

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.sqlite.db.SimpleSQLiteQuery
import com.ebenezer.biblioteca.data.AppDatabase
import com.ebenezer.biblioteca.data.LibroEntity
import com.ebenezer.biblioteca.data.ParrafoEntity
import com.ebenezer.biblioteca.data.SearchResult
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf

class LibraryViewModel(application: Application) : AndroidViewModel(application) {
    private val dao = AppDatabase.getDatabase(application).libraryDao()

    val books: Flow<List<LibroEntity>> = dao.getAllBooks()

    private val _selectedBookId = MutableStateFlow<Long?>(null)
    val selectedBookId: StateFlow<Long?> = _selectedBookId

    val paragraphs: Flow<List<ParrafoEntity>> = _selectedBookId.flatMapLatest { id ->
        if (id != null) dao.getParagraphsByBook(id)
        else flowOf(emptyList())
    }

    private val _searchQuery = MutableStateFlow("")
    val searchQuery: StateFlow<String> = _searchQuery

    val searchResults: Flow<List<SearchResult>> = _searchQuery.flatMapLatest { query ->
        if (query.length >= 2) {
            val sqlQuery = SimpleSQLiteQuery(
                """
                SELECT parrafos.id, parrafos.libro_id, parrafos.numero_parrafo,
                       snippet(parrafos_fts, 0, '<b>', '</b>', '...', 32) AS snippet,
                       libros.titulo
                FROM parrafos_fts
                JOIN parrafos ON parrafos_fts.rowid = parrafos.id
                JOIN libros ON parrafos.libro_id = libros.id
                WHERE parrafos_fts MATCH ?
                ORDER BY rank
                """,
                arrayOf(query)
            )
            dao.searchRaw(sqlQuery)
        } else {
            flowOf(emptyList())
        }
    }

    fun selectBook(bookId: Long) {
        _selectedBookId.value = bookId
    }

    fun updateSearchQuery(query: String) {
        _searchQuery.value = query
    }
}