package com.ebenezer.biblioteca

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.ebenezer.biblioteca.ui.theme.BibliotecaEbenezerTheme

/**
 * PANTALLA PRINCIPAL DE LA BIBLIOTECA.
 * Aquí es donde el usuario verá la lista de sus mil libros.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            BibliotecaEbenezerTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    ListaDeLibros()
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ListaDeLibros() {
    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Biblioteca Ebenezer") })
        }
    ) { padding ->
        // LazyColumn es lo que permite que la app sea "Ligera". 
        // Solo dibuja lo que el usuario ve en pantalla.
        LazyColumn(
            modifier = Modifier.padding(padding),
            contentPadding = PaddingValues(16.dp)
        ) {
            items(10) { index -> // Por ahora mostramos 10 de prueba
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 8.dp)
                ) {
                    ListItem(
                        headlineContent = { Text("Libro de Prueba #$index") },
                        supportingContent = { Text("Párrafos listos para lectura") }
                    )
                }
            }
        }
    }
}