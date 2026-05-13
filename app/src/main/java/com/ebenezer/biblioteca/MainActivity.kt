package com.ebenezer.biblioteca

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            BibliotecaEbenezerApp()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BibliotecaEbenezerApp(viewModel: LibraryViewModel = viewModel()) {
    MaterialTheme {
        var showBooks by remember { mutableStateOf(true) }
        val focusManager = LocalFocusManager.current

        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("Biblioteca Ebenezer") },
                    actions = {
                        TextButton(onClick = { showBooks = !showBooks }) {
                            Text(if (showBooks) "Buscar" else "Libros")
                        }
                    }
                )
            }
        ) { padding ->
            if (showBooks) {
                // Pantalla de libros
                val books by viewModel.books.collectAsState(initial = emptyList())
                LazyColumn(modifier = Modifier.padding(padding)) {
                    items(books) { book ->
                        ListItem(
                            headlineContent = { Text(book.titulo) },
                            supportingContent = { Text("Código: ${book.codigo}") },
                            modifier = Modifier.clickable {
                                viewModel.selectBook(book.id)
                                showBooks = false
                            }
                        )
                    }
                }
            } else {
                // Pantalla de párrafos o búsqueda
                val selectedBookId = viewModel.selectedBookId.collectAsState()
                val paragraphs by viewModel.paragraphs.collectAsState(initial = emptyList())
                val searchQuery = viewModel.searchQuery.collectAsState()
                val searchResults by viewModel.searchResults.collectAsState(initial = emptyList())

                Column(modifier = Modifier.padding(padding)) {
                    // Barra de búsqueda
                    OutlinedTextField(
                        value = searchQuery.value,
                        onValueChange = { viewModel.updateSearchQuery(it) },
                        label = { Text("Buscar en todos los libros") },
                        modifier = Modifier.fillMaxWidth().padding(8.dp),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = { focusManager.clearFocus() })
                    )

                    if (searchQuery.value.length >= 2) {
                        // Mostrar resultados de búsqueda
                        LazyColumn {
                            items(searchResults) { result ->
                                Card(modifier = Modifier.fillMaxWidth().padding(4.dp)) {
                                    Column(modifier = Modifier.padding(8.dp)) {
                                        Text(
                                            text = "${result.titulo} - Párrafo ${result.numero_parrafo}",
                                            fontWeight = FontWeight.Bold
                                        )
                                        Text(
                                            text = result.snippet.replace("<b>", "**").replace("</b>", "**"),
                                            fontSize = 14.sp
                                        )
                                    }
                                }
                            }
                        }
                    } else {
                        // Mostrar párrafos del libro seleccionado
                        LazyColumn {
                            items(paragraphs) { parrafo ->
                                Text(
                                    text = parrafo.contenido,
                                    modifier = Modifier.padding(8.dp),
                                    fontSize = 16.sp
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}