package com.ebenezer.biblioteca.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "libros")
data class Libro(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val titulo: String,
    val codigo: String
)