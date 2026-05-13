package com.ebenezer.biblioteca.data

data class ParrafoEntity(
    val id: Long,
    val libro_id: Long,
    val numero_parrafo: Int,
    val contenido: String
)