package com.ebenezer.biblioteca.data

data class ParrafoEntity(
    val id: Long,
    val libro_id: Long,
    val numero_parrafo: Int,
    val contenido: String,
    val tipo: Int = 0  // 0=normal, 1=título interno, 2=cita bíblica
)