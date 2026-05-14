package com.ebenezer.biblioteca.data

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "parrafos")
data class ParrafoEntity(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val libro_id: Int,
    val numero_parrafo: Int,
    val contenido: String,
    val tipo: Int // 0: Normal, 1: Titulo, 2: Cita
)