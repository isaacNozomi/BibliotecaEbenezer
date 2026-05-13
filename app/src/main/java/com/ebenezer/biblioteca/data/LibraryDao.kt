package com.ebenezer.biblioteca.data

import androidx.room.Dao
import androidx.room.Query

/**
 * INTERFAZ DE ACCESO A DATOS (DAO).
 * Aquí definimos las funciones para leer los libros y párrafos.
 */
@Dao
interface LibraryDao {

    // Obtener todos los libros para la lista principal
    @Query("SELECT * FROM libros ORDER BY titulo ASC")
    suspend fun obtenerTodosLosLibros(): List<Libro>

    // Obtener los párrafos de un libro específico
    @Query("SELECT * FROM parrafos WHERE libroId = :idLibro ORDER BY numero ASC")
    suspend fun obtenerParrafosPorLibro(idLibro: Int): List<Parrafo>

    // BUSCADOR: Encuentra texto en toda la biblioteca (mil libros a la vez)
    @Query("SELECT * FROM parrafos WHERE contenido LIKE '%' || :busqueda || '%' LIMIT 100")
    suspend fun buscarTexto(busqueda: String): List<Parrafo>
}