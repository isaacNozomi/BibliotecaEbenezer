package com.ebenezer.biblioteca.data

import androidx.room.Entity
import androidx.room.Fts5

@Fts5(contentEntity = ParrafoEntity::class, tokenizer = "unicode61")
@Entity(tableName = "parrafos_fts")
data class ParrafoFtsEntity(
    val contenido: String
)