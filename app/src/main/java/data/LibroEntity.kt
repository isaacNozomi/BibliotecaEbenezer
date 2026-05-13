package com.ebenezer.biblioteca.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "libros")
data class LibroEntity(
    @PrimaryKey val id: Long,
    val titulo: String,
    val codigo: String,
    val fecha: String
)