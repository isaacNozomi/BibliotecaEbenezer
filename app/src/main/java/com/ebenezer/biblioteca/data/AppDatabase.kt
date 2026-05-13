package com.ebenezer.biblioteca.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

/**
 * CONFIGURACIÓN DE LA BASE DE DATOS.
 * Se conecta al archivo 'biblioteca.db' que generamos con Python.
 */
@Database(entities = [Libro::class, Parrafo::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    
    abstract fun libraryDao(): LibraryDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "biblioteca.db"
                )
                // ESTA LÍNEA ES LA MÁS IMPORTANTE:
                // Le dice a la App que use el archivo que está en assets/database/
                .createFromAsset("database/biblioteca.db")
                .build()
                INSTANCE = instance
                instance
            }
        }
    }
}