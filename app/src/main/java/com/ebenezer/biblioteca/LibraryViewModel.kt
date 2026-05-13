package com.ebenezer.biblioteca

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.ebenezer.biblioteca.data.AppDatabase
import com.ebenezer.biblioteca.data.LibraryDao
import com.ebenezer.biblioteca.data.LibroEntity
import com.ebenezer.biblioteca.data.ParrafoEntity
import com.ebenezer.biblioteca.data.SearchResult
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.launch

class LibraryViewModel(application: Application) : AndroidViewModel(application) {
    private val dao: LibraryDao = AppDatabase.getDatabase(application).libraryDao()

    // Lista de libros
    val books: Flow<List<LibroEntity>> = dao.getAllBooks()

    // Párrafos de un libro seleccionado
    private val _selectedBookId = MutableStateFlow<Long?>(null)
    val selectedBookId: StateFlow<Long?> = _selectedBookId

    val paragraphs: Flow<List<ParrafoEntity>> = _selectedBookId.flatMapLatest { id ->
        if (id != null) dao.getParagraphsByBook(id)
        else flowOf(emptyList())
    }

    // Búsqueda
    private val _searchQuery = MutableStateFlow("")
    val searchQuery: StateFlow<String> = _searchQuery

    val searchResults: Flow<List<SearchResult>> = _searchQuery.flatMapLatest { query ->
        if (query.length >= 2) dao.search(query)
        else flowOf(emptyList())
    }

    fun selectBook(bookId: Long) {
        _selectedBookId.value = bookId
    }

    fun updateSearchQuery(query: String) {
        _searchQuery.value = query
    }
}