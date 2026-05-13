package com.ebenezer.biblioteca.data

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "parrafos",
    foreignKeys = [
        ForeignKey(
            entity = LibroEntity::class,
            parentColumns = ["id"],
            childColumns = ["libro_id"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("libro_id")]
)
data class ParrafoEntity(
    @PrimaryKey val id: Long,
    val libro_id: Long,
    val numero_parrafo: Int,
    val contenido: String
)