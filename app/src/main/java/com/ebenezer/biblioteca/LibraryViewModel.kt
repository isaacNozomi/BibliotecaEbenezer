package com.ebenezer.biblioteca

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.ebenezer.biblioteca.data.AppDatabase
import com.ebenezer.biblioteca.data.Libro
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * LÓGICA DE NEGOCIO.
 * Se encarga de pedir los libros a la base de datos y dárselos a la pantalla.
 */
class LibraryViewModel(application: Application) : AndroidViewModel(application) {
    
    private val dao = AppDatabase.getDatabase(application).libraryDao()

    private val _libros = MutableStateFlow<List<Libro>>(emptyList())
    val libros: StateFlow<List<Libro>> = _libros

    init {
        cargarLibros()
    }

    private fun cargarLibros() {
        viewModelScope.launch {
            _libros.value = dao.obtenerTodosLosLibros()
        }
    }
}