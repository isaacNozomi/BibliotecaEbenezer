package com.ebenezer.biblioteca.data

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import java.io.File
import java.io.FileOutputStream

object LibraryDb {
    private const val DB_NAME = "biblioteca.db"

    fun getDatabase(context: Context): SQLiteDatabase {
        val dbFile = context.getDatabasePath(DB_NAME)

        // Copiamos la base de datos desde assets si no existe
        if (!dbFile.exists()) {
            copyDatabase(context, dbFile)
        }

        // Abrimos la base de datos
        return SQLiteDatabase.openDatabase(dbFile.absolutePath, null, SQLiteDatabase.OPEN_READWRITE)
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