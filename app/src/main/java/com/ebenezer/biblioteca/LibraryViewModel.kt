package com.ebenezer.biblioteca

import android.app.Application
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import com.ebenezer.biblioteca.data.LibraryDao
import com.ebenezer.biblioteca.data.LibraryDb
import com.ebenezer.biblioteca.data.LibroEntity
import com.ebenezer.biblioteca.data.ParrafoEntity
import com.ebenezer.biblioteca.data.SearchResult
import kotlinx.coroutines.flow.*

class LibraryViewModel(application: Application) : AndroidViewModel(application) {

    // Usamos lazy para solo intentar conectar a la BD cuando sea necesario
    private val dao by lazy {
        try {
            LibraryDao(LibraryDb.getDatabase(application))
        } catch (e: Exception) {
            Log.e("LibraryViewModel", "Error al abrir la base de datos", e)
            null
        }
    }

    val books: Flow<List<LibroEntity>> = dao?.getAllBooks() ?: flow {
        emit(emptyList())
        Log.e("LibraryViewModel", "DAO no disponible, mostrando lista vacía")
    }

    private val _selectedBookId = MutableStateFlow<Long?>(null)
    val selectedBookId: StateFlow<Long?> = _selectedBookId

    val paragraphs: Flow<List<ParrafoEntity>> = _selectedBookId.flatMapLatest { id ->
        if (id != null && dao != null) {
            dao!!.getParagraphsByBook(id)
        } else {
            flowOf(emptyList())
        }
    }

    private val _searchQuery = MutableStateFlow("")
    val searchQuery: StateFlow<String> = _searchQuery

    val searchResults: Flow<List<SearchResult>> = _searchQuery.flatMapLatest { query ->
        if (query.length >= 2 && dao != null) {
            dao!!.search(query)
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