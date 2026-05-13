package com.ebenezer.biblioteca.data

import android.content.Context
import androidx.sqlite.db.SupportSQLiteDatabase
import androidx.sqlite.db.framework.FrameworkSQLiteDatabase
import java.io.File
import java.io.FileOutputStream

object LibraryDb {
    private const val DB_NAME = "biblioteca.db"

    fun getDatabase(context: Context): SupportSQLiteDatabase {
        val dbFile = context.getDatabasePath(DB_NAME)

        // Si la base de datos no existe, la copiamos desde assets
        if (!dbFile.exists()) {
            try {
                copyDatabase(context, dbFile)
            } catch (e: Exception) {
                throw RuntimeException("No se pudo copiar la base de datos. Verifica que el archivo assets/database/biblioteca.db exista en el proyecto.", e)
            }
        }

        // Abrimos la base de datos
        return FrameworkSQLiteDatabase.openOrCreateDatabase(
            dbFile,
            null,
            object : androidx.sqlite.db.SupportSQLiteOpenHelper.Callback(1) {
                override fun onCreate(db: SupportSQLiteDatabase) {
                    // No hacemos nada, la BD ya está creada
                }

                override fun onUpgrade(db: SupportSQLiteDatabase, oldVersion: Int, newVersion: Int) {
                    // Sin migraciones por ahora
                }
            }
        )
    }

    private fun copyDatabase(context: Context, dbFile: File) {
        dbFile.parentFile?.mkdirs()
        context.assets.open("database/$DB_NAME").use { input ->
            FileOutputStream(dbFile).use { output ->
                input.copyTo(output)
            }
        }
    }
}