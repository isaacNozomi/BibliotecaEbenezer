package com.ebenezer.biblioteca.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "parrafos")
data class Parrafo(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val libroId: Int,
    val numero: Int,
    val contenido: String,
    val referenciaBiblica: String? = null // Aquí pondremos la conexión futura
)