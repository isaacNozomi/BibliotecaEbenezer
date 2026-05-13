package com.ebenezer.biblioteca

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.ebenezer.biblioteca.data.Libro
import com.ebenezer.biblioteca.ui.theme.BibliotecaEbenezerTheme

/**
 * PANTALLA PRINCIPAL DEFINITIVA.
 * Esta pantalla se conecta al ViewModel para mostrar los libros reales
 * procesados por tu script de Python.
 */
class MainActivity : ComponentActivity() {
    
    // Inicializamos el ViewModel que maneja los datos
    private val viewModel: LibraryViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            // "Escuchamos" la lista de libros desde la base de datos
            val listaLibros por viewModel.libros.collectAsState()

            BibliotecaEbenezerTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    PantallaListaLibros(listaLibros)
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PantallaListaLibros(libros: List<Libro>) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Biblioteca Ebenezer") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    titleContentColor = MaterialTheme.colorScheme.onPrimaryContainer
                )
            )
        }
    ) { padding ->
        // Si no hay libros todavía, mostramos un mensaje de carga
        if (libros.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxSize().padding(padding),
                contentAlignment = androidx.compose.ui.Alignment.Center
            ) {
                CircularProgressIndicator()
            }
        } else {
            // Mostramos la lista real de libros
            LazyColumn(
                modifier = Modifier.padding(padding),
                contentPadding = PaddingValues(16.dp)
            ) {
                items(libros) { libro ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 8.dp),
                        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
                    ) {
                        ListItem(
                            headlineContent = { Text(libro.titulo) },
                            supportingContent = { Text("Código: ${libro.codigo}") },
                            leadingContent = {
                                Icon(
                                    imageVector = androidx.compose.material.icons.Icons.Default.Book,
                                    contentDescription = null
                                )
                            }
                        )
                    }
                }
            }
        }
    }
}